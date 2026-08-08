"""Product catalog business logic with a cache-aside read path."""

import logging
import time

from flask import current_app

from app.extensions import db
from app.models.product import Product
from app.services.redis_service import (
    cache,
    product_detail_key,
    product_list_key,
)
from app.utils.errors import NotFoundError
from app.utils.responses import ok

logger = logging.getLogger(__name__)


def _invalidate_product_cache() -> None:
    cache.invalidate("products:*")


def list_products(category=None, search=None, page=1, limit=20):
    """Cache-aside read: try Redis, fall back to MySQL, then populate Redis."""
    started = time.perf_counter()
    key = product_list_key(category, page, limit, search)

    cached = cache.get(key)
    if cached is not None:
        elapsed = round((time.perf_counter() - started) * 1000, 2)
        return ok(cached["items"], cached=True, response_time_ms=elapsed,
                  pagination=cached["pagination"])

    query = Product.query
    if category:
        query = query.filter(Product.category == category)
    if search:
        query = query.filter(Product.name.like(f"%{search}%"))

    total = query.count()
    rows = (
        query.order_by(Product.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    items = [row.to_dict() for row in rows]
    pagination = {
        "page": page,
        "limit": limit,
        "total": total,
        "pages": (total + limit - 1) // limit if limit else 0,
    }

    cache.set(key, {"items": items, "pagination": pagination})

    elapsed = round((time.perf_counter() - started) * 1000, 2)
    return ok(items, cached=False, response_time_ms=elapsed, pagination=pagination)


def get_product(product_id: int):
    started = time.perf_counter()
    key = product_detail_key(product_id)

    cached = cache.get(key)
    if cached is not None:
        elapsed = round((time.perf_counter() - started) * 1000, 2)
        return ok(cached, cached=True, response_time_ms=elapsed)

    product = db.session.get(Product, product_id)
    if product is None:
        raise NotFoundError(f"Product {product_id} not found.")

    data = product.to_dict()
    cache.set(key, data)

    elapsed = round((time.perf_counter() - started) * 1000, 2)
    return ok(data, cached=False, response_time_ms=elapsed)


def create_product(data: dict):
    product = Product(**data)
    db.session.add(product)
    db.session.commit()

    _invalidate_product_cache()
    logger.info("Created product %s", product.id)
    return ok(product.to_dict(), status=201)


def update_product(product_id: int, data: dict):
    product = db.session.get(Product, product_id)
    if product is None:
        raise NotFoundError(f"Product {product_id} not found.")

    for field, value in data.items():
        setattr(product, field, value)
    db.session.commit()

    _invalidate_product_cache()
    logger.info("Updated product %s", product_id)
    return ok(product.to_dict())


def delete_product(product_id: int):
    product = db.session.get(Product, product_id)
    if product is None:
        raise NotFoundError(f"Product {product_id} not found.")

    db.session.delete(product)
    db.session.commit()

    _invalidate_product_cache()
    logger.info("Deleted product %s", product_id)
    return ok({"deleted_id": product_id})


def list_categories():
    rows = db.session.query(Product.category).distinct().order_by(Product.category).all()
    return ok([row[0] for row in rows])
