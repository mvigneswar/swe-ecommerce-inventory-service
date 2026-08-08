"""Order aggregate: Order (header) + OrderItem (lines)."""

from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Index

from app.extensions import db


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Order(db.Model):
    __tablename__ = "orders"

    STATUSES = ("Pending", "Completed", "Cancelled")

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    customer_email = db.Column(db.String(255), nullable=False)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(
        db.Enum(*STATUSES, name="order_status"),
        nullable=False,
        default="Pending",
    )
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    items = db.relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="selectin",  # avoids N+1 when listing orders
    )

    __table_args__ = (
        CheckConstraint("total_amount >= 0", name="chk_orders_total"),
        Index("idx_orders_email", "customer_email"),
        Index("idx_orders_status", "status"),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"},
    )

    def to_dict(self, include_items: bool = True) -> dict:
        data = {
            "id": self.id,
            "customer_email": self.customer_email,
            "total_amount": float(self.total_amount)
            if self.total_amount is not None
            else None,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_items:
            data["items"] = [item.to_dict() for item in self.items]
            data["item_count"] = len(self.items)
        return data

    def __repr__(self) -> str:
        return f"<Order {self.id} {self.customer_email!r} {self.status}>"


class OrderItem(db.Model):
    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    order_id = db.Column(
        db.Integer,
        db.ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    product_id = db.Column(
        db.Integer, db.ForeignKey("products.id"), nullable=False
    )
    quantity = db.Column(db.Integer, nullable=False)
    # Price snapshot at purchase time — catalog price may change later.
    price = db.Column(db.Numeric(10, 2), nullable=False)

    order = db.relationship("Order", back_populates="items")
    product = db.relationship("Product", lazy="joined")

    __table_args__ = (
        CheckConstraint("quantity > 0", name="chk_items_qty"),
        Index("idx_items_order_product", "order_id", "product_id"),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"},
    )

    def to_dict(self) -> dict:
        unit_price = float(self.price) if self.price is not None else 0.0
        return {
            "id": self.id,
            "product_id": self.product_id,
            "product_name": self.product.name if self.product else None,
            "quantity": self.quantity,
            "unit_price": unit_price,
            "line_total": round(unit_price * (self.quantity or 0), 2),
        }

    def __repr__(self) -> str:
        return f"<OrderItem order={self.order_id} product={self.product_id}>"
