"""Application factory."""

import logging
import time

from flask import Flask, g, jsonify, request

from app.config import BaseConfig, get_config
from app.extensions import db
from app.services.redis_service import cache
from app.utils.errors import register_error_handlers


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )


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
