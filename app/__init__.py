"""Application factory."""

import logging
import time

from flask import Flask, g, jsonify, request

from app.config import BaseConfig, get_config
from app.extensions import db
from app.services.redis_service import cache
from app.utils.errors import register_error_handlers

logger = logging.getLogger(__name__)


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )


def _wait_for_db(app, retries: int = 15, delay: int = 2) -> None:
    """Retry DB connectivity on startup so we survive a slow MySQL container.

    Also runs ``create_all()`` so the API is self-sufficient even if
    ``init.sql`` has not finished loading yet. Failures are logged, not fatal.
    """
    from sqlalchemy import text

    for attempt in range(1, retries + 1):
        try:
            with app.app_context():
                with db.engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                db.create_all()
            logger.info("Database connection established.")
            return
        except Exception as exc:  # noqa: BLE001 - resilience, not a hard failure
            if attempt == retries:
                logger.warning(
                    "Could not reach the database after %d attempts: %s",
                    retries, exc,
                )
                return
            logger.info(
                "Database not ready (attempt %d/%d) — retrying", attempt, retries
            )
            time.sleep(delay)


def create_app(config_name: str | None = None) -> Flask:
    app = Flask(__name__)

    cfg: BaseConfig = get_config(config_name)
    app.config.from_object(cfg)
    # SQLALCHEMY_DATABASE_URI is a property, so from_object() skips it.
    app.config["SQLALCHEMY_DATABASE_URI"] = cfg.SQLALCHEMY_DATABASE_URI

    _configure_logging(app.config.get("LOG_LEVEL", "INFO"))

    # ---- extensions ----
    db.init_app(app)
    cache.init_app(app)

    # Import models so SQLAlchemy registers the tables.
    from app import models  # noqa: F401

    # Best-effort schema bootstrap + resilience against a slow DB start.
    _wait_for_db(app)

    # ---- blueprints ----
    from app.routes.health_routes import health_bp
    from app.routes.order_routes import order_bp
    from app.routes.product_routes import product_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(product_bp)
    app.register_blueprint(order_bp)

    register_error_handlers(app)

    # ---- request timing ----
    @app.before_request
    def _start_timer():
        g.start_time = time.perf_counter()

    @app.after_request
    def _add_timing_header(response):
        start = g.pop("start_time", None)
        if start is not None:
            elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
            response.headers["X-Response-Time-ms"] = str(elapsed_ms)
        return response

    @app.get("/")
    def index():
        return jsonify(
            {
                "service": "E-Commerce Inventory API",
                "version": "1.0.0",
                "docs": "/api/health",
            }
        )

    return app
