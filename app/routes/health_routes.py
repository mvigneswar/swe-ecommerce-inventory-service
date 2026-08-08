"""Liveness / readiness endpoint reporting dependency status."""

from flask import Blueprint
from sqlalchemy import text

from app.extensions import db
from app.services.redis_service import cache
from app.utils.responses import ok

health_bp = Blueprint("health", __name__, url_prefix="/api")


@health_bp.get("/health")
def health():
    # --- MySQL ---
    try:
        db.session.execute(text("SELECT 1"))
        mysql_status = "up"
    except Exception:  # noqa: BLE001 - health must never raise
        mysql_status = "down"

    # --- Redis ---
    redis_status = "up" if cache.ping() else "down"

    healthy = mysql_status == "up"  # Redis is optional; MySQL is not
    payload = {
        "status": "healthy" if healthy else "degraded",
        "dependencies": {"mysql": mysql_status, "redis": redis_status},
        "cache": cache.stats(),
    }
    return ok(payload, status=200 if healthy else 503)
