"""Redis cache-service unit tests (no Flask app required)."""

from app.services.redis_service import (
    RedisCache,
    product_detail_key,
    product_list_key,
)


class TestCacheKeys:
    def test_list_key_is_deterministic(self):
        first = product_list_key("Tools", 1, 20, None)
        second = product_list_key("Tools", 1, 20, None)
        assert first == second

    def test_list_key_varies_by_page(self):
        assert product_list_key("Tools", 1, 20, None) != product_list_key(
            "Tools", 2, 20, None
        )

    def test_list_key_varies_by_category(self):
        assert product_list_key("Tools", 1, 20, None) != product_list_key(
            "Toys", 1, 20, None
        )

    def test_list_key_is_case_insensitive(self):
        assert product_list_key("TOOLS", 1, 20, None) == product_list_key(
            "tools", 1, 20, None
        )

    def test_missing_category_becomes_all(self):
        assert "cat=all" in product_list_key(None, 1, 20, None)

    def test_detail_key_format(self):
        assert product_detail_key(42) == "products:detail:42"

    def test_keys_share_invalidation_prefix(self):
        assert product_list_key(None, 1, 20, None).startswith("products:")
        assert product_detail_key(1).startswith("products:")


class TestGracefulDegradation:
    """The API must keep working when Redis is unreachable."""

    def test_unconnected_cache_reports_unavailable(self):
        cache = RedisCache()
        assert cache.available is False
        assert cache.ping() is False

    def test_get_returns_none_without_connection(self):
        assert RedisCache().get("any-key") is None

    def test_set_returns_false_without_connection(self):
        assert RedisCache().set("any-key", {"a": 1}) is False

    def test_delete_and_invalidate_are_safe(self):
        cache = RedisCache()
        assert cache.delete("a", "b") == 0
        assert cache.invalidate("products:*") == 0

    def test_stats_are_reported(self):
        stats = RedisCache().stats()
        assert stats["connected"] is False
        assert stats["hit_rate"] == 0.0


class TestCacheBehaviourThroughApi:
    def test_second_read_is_served_from_cache(self, client, product_factory):
        product_factory(name="Cached Item")
        first = client.get("/api/products").get_json()
        second = client.get("/api/products").get_json()
        # Caching is disabled in the testing config, so both are uncached.
        assert first["meta"]["cached"] is False
        assert second["meta"]["cached"] is False
        assert "response_time_ms" in second["meta"]

    def test_write_then_read_reflects_change(self, client, product_factory):
        product_id = product_factory(name="Before", price=10.0)
        client.put(f"/api/products/{product_id}", json={"name": "After"})
        data = client.get(f"/api/products/{product_id}").get_json()["data"]
        assert data["name"] == "After"
