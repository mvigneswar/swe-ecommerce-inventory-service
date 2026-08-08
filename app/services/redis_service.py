"""Redis cache-aside layer.

Design rule: **the cache never breaks the API**. Every Redis call is wrapped so
that a connection failure degrades to a normal database read instead of a 500.
"""

import json
import logging
from typing import Any

import redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)

PRODUCT_CACHE_PREFIX = "products"


class RedisCache:
    """Thin, failure-tolerant wrapper around redis-py."""

    def __init__(self) -> None:
        self._client: redis.Redis | None = None
        self._enabled: bool = False
        self._default_ttl: int = 60
        # Simple counters that power the /api/health cache stats.
        self.hits = 0
        self.misses = 0

    # ---------------- lifecycle ----------------

    def init_app(self, app) -> None:
        self._enabled = bool(app.config.get("CACHE_ENABLED", True))
        self._default_ttl = int(app.config.get("CACHE_TTL_SECONDS", 60))

        if not self._enabled:
            logger.info("Cache disabled by configuration.")
            return

        try:
            pool = redis.ConnectionPool(
                host=app.config["REDIS_HOST"],
                port=app.config["REDIS_PORT"],
                db=app.config["REDIS_DB"],
                password=app.config.get("REDIS_PASSWORD"),
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
                max_connections=50,
            )
            self._client = redis.Redis(connection_pool=pool)
            self._client.ping()
            logger.info("Redis connected.")
        except RedisError as exc:
            logger.warning("Redis unavailable, serving without cache: %s", exc)
            self._client = None

    @property
    def available(self) -> bool:
        return self._enabled and self._client is not None

    def ping(self) -> bool:
        if not self.available:
            return False
        try:
            return bool(self._client.ping())
        except RedisError:
            return False

    # ---------------- core operations ----------------

    def get(self, key: str) -> Any | None:
        if not self.available:
            return None
        try:
            raw = self._client.get(key)
        except RedisError as exc:
            logger.warning("Cache GET failed for %s: %s", key, exc)
            return None

        if raw is None:
            self.misses += 1
            return None

        self.hits += 1
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Corrupt cache entry at %s; dropping.", key)
            self.delete(key)
            return None

    def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        if not self.available:
            return False
        try:
            self._client.setex(
                key, ttl or self._default_ttl, json.dumps(value, default=str)
            )
            return True
        except (RedisError, TypeError) as exc:
            logger.warning("Cache SET failed for %s: %s", key, exc)
            return False

    def delete(self, *keys: str) -> int:
        if not self.available or not keys:
            return 0
        try:
            return int(self._client.delete(*keys))
        except RedisError as exc:
            logger.warning("Cache DELETE failed: %s", exc)
            return 0

    def invalidate(self, pattern: str = f"{PRODUCT_CACHE_PREFIX}:*") -> int:
        """Delete every key matching a pattern.

        Uses SCAN rather than KEYS: KEYS blocks the Redis event loop and is
        unsafe on large keyspaces.
        """
        if not self.available:
            return 0
        removed = 0
        try:
            for key in self._client.scan_iter(match=pattern, count=500):
                removed += int(self._client.delete(key))
        except RedisError as exc:
            logger.warning("Cache invalidation failed for %s: %s", pattern, exc)
        if removed:
            logger.info("Invalidated %d cache key(s) matching %s", removed, pattern)
        return removed

    def stats(self) -> dict:
        total = self.hits + self.misses
        return {
            "connected": self.ping(),
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(self.hits / total, 3) if total else 0.0,
        }


# ---------------- key builders ----------------


def product_list_key(category: str | None, page: int, limit: int, search: str | None) -> str:
    """Deterministic key so identical queries reuse the same entry."""
    return (
        f"{PRODUCT_CACHE_PREFIX}:list"
        f":cat={(category or 'all').lower()}"
        f":q={(search or '').lower()}"
        f":page={page}:limit={limit}"
    )


def product_detail_key(product_id: int) -> str:
    return f"{PRODUCT_CACHE_PREFIX}:detail:{product_id}"


cache = RedisCache()
