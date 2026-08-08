"""Order placement — the transactional heart of the service.

Concurrency guarantees
----------------------
1. Every product row is locked with ``SELECT ... FOR UPDATE`` before its stock is
   read, so two concurrent buyers cannot both observe the same last unit.
2. Rows are locked in **ascending product-id order**. Consistent lock ordering is
   what prevents deadlocks when two orders touch the same products in different
   sequences.
3. The whole operation is one transaction: any failure rolls back every change,
   so stock can never drift out of sync with the order record.
"""

import logging
from decimal import Decimal

from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.extensions import db
from app.models.order import Order, OrderItem
from app.models.product import Product
from app.services.redis_service import cache
from app.utils.errors import (
    AppError,
    ConflictError,
    InsufficientStockError,
    NotFoundError,
)
from app.utils.responses import ok

logger = logging.getLogger(__name__)


def create_order(data: dict):
    """Place an order and atomically decrement stock."""
    items = data["items"]
    # Deterministic lock ordering — the deadlock guard.
    ordered_items = sorted(items, key=lambda i: i["product_id"])

    try:
        total = Decimal("0.00")
        pending_lines: list[OrderItem] = []

        for line in ordered_items:
            product_id = line["product_id"]
            quantity = line["quantity"]

            # Row-level lock held until commit/rollback.
            product = (
                db.session.query(Product)
                .filter(Product.id == product_id)
                .with_for_update()
                .first()
            )

            if product is None:
                raise NotFoundError(f"Product {product_id} not found.")

            if product.stock_quantity < quantity:
                raise InsufficientStockError(
                    f"Insufficient stock for '{product.name}'.",
                    details={
                        "product_id": product_id,
                        "requested": quantity,
                        "available": product.stock_quantity,
                    },
                )

            product.stock_quantity -= quantity
            line_total = Decimal(str(product.price)) * quantity
            total += line_total

            pending_lines.append(
                OrderItem(
                    product_id=product.id,
                    quantity=quantity,
                    price=product.price,
                )
            )

        order = Order(
            customer_email=data["customer_email"],
            total_amount=total.quantize(Decimal("0.01")),
            status="Completed",
        )
        order.items = pending_lines
        db.session.add(order)
        db.session.commit()

        # Stock changed, so cached catalog data is now stale.
        cache.invalidate("products:*")

        logger.info(
            "Order %s placed by %s for %s",
            order.id,
            order.customer_email,
            order.total_amount,
        )
        return ok(order.to_dict(), status=201)

    except AppError:
        db.session.rollback()
        raise
    except OperationalError as exc:
        db.session.rollback()
        # MySQL error 1213 = deadlock, 1205 = lock wait timeout.
        logger.warning("Lock contention while placing order: %s", exc)
        raise ConflictError(
            "The order could not be completed due to high contention. Please retry."
        ) from exc
    except SQLAlchemyError as exc:
        db.session.rollback()
        logger.exception("Database error while placing order")
        raise AppError("Failed to place order.", status=500) from exc


def get_order(order_id: int):
    order = db.session.get(Order, order_id)
    if order is None:
        raise NotFoundError(f"Order {order_id} not found.")
    return ok(order.to_dict())


def list_orders(email: str | None = None, page: int = 1, limit: int = 20):
    query = Order.query
    if email:
        query = query.filter(Order.customer_email == email)

    total = query.count()
    rows = (
        query.order_by(Order.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return ok(
        [row.to_dict(include_items=False) for row in rows],
        pagination={
            "page": page,
            "limit": limit,
            "total": total,
            "pages": (total + limit - 1) // limit if limit else 0,
        },
    )


def cancel_order(order_id: int):
    """Cancel an order and restore stock inside a single transaction."""
    try:
        order = db.session.get(Order, order_id)
        if order is None:
            raise NotFoundError(f"Order {order_id} not found.")
        if order.status == "Cancelled":
            raise ConflictError(f"Order {order_id} is already cancelled.")

        for item in sorted(order.items, key=lambda i: i.product_id):
            product = (
                db.session.query(Product)
                .filter(Product.id == item.product_id)
                .with_for_update()
                .first()
            )
            if product is not None:
                product.stock_quantity += item.quantity

        order.status = "Cancelled"
        db.session.commit()
        cache.invalidate("products:*")

        logger.info("Order %s cancelled and stock restored", order_id)
        return ok(order.to_dict())

    except AppError:
        db.session.rollback()
        raise
    except SQLAlchemyError as exc:
        db.session.rollback()
        logger.exception("Database error while cancelling order")
        raise AppError("Failed to cancel order.", status=500) from exc
