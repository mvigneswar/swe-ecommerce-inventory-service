"""Product catalog entity."""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import CheckConstraint, Index

from app.extensions import db


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    stock_quantity = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        CheckConstraint("price >= 0", name="chk_products_price"),
        CheckConstraint("stock_quantity >= 0", name="chk_products_stock"),
        Index("idx_products_category", "category"),
        Index("idx_products_name", "name"),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"},
    )

    def to_dict(self) -> dict:
        """JSON-safe representation (Decimal -> float, datetime -> ISO)."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "price": float(self.price) if self.price is not None else None,
            "stock_quantity": self.stock_quantity,
            "in_stock": (self.stock_quantity or 0) > 0,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<Product {self.id} {self.name!r} stock={self.stock_quantity}>"
