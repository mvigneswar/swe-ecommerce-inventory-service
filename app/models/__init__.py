"""Model exports — importing this module registers all tables on the metadata."""

from app.models.order import Order, OrderItem
from app.models.product import Product

__all__ = ["Product", "Order", "OrderItem"]
