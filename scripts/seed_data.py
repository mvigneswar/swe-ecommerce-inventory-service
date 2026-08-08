"""Populate the catalog with demo products.

Usage:
    python scripts/seed_data.py            # add 120 products
    python scripts/seed_data.py --count 500 --reset
"""

import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models.order import Order, OrderItem  # noqa: E402
from app.models.product import Product  # noqa: E402
from app.services.redis_service import cache  # noqa: E402

CATALOG = {
    "Electronics": [
        "Wireless Mouse", "Mechanical Keyboard", "27in Monitor", "USB-C Hub",
        "Noise Cancelling Headphones", "Webcam 1080p", "Portable SSD 1TB",
        "Bluetooth Speaker", "Smart Watch", "Laptop Cooling Pad",
    ],
    "Books": [
        "Clean Code", "Designing Data-Intensive Applications", "The Pragmatic Programmer",
        "System Design Interview", "Cracking the Coding Interview", "Refactoring",
        "Fluent Python", "Database Internals",
    ],
    "Home": [
        "Ceramic Mug", "Desk Lamp", "Office Chair", "Standing Desk",
        "Air Purifier", "Coffee Maker", "Storage Box", "Wall Clock",
    ],
    "Apparel": [
        "Cotton T-Shirt", "Hoodie", "Running Shoes", "Denim Jacket",
        "Baseball Cap", "Wool Socks", "Backpack",
    ],
    "Sports": [
        "Yoga Mat", "Dumbbell Set", "Resistance Bands", "Water Bottle",
        "Skipping Rope", "Foam Roller", "Cricket Bat",
    ],
}

PRICE_BANDS = {
    "Electronics": (799, 89999),
    "Books": (299, 2499),
    "Home": (399, 24999),
    "Apparel": (499, 7999),
    "Sports": (299, 14999),
}


def seed(count: int, reset: bool) -> None:
    app = create_app()
    with app.app_context():
        db.create_all()

        if reset:
            # Delete children first: products are referenced by order_items.
            OrderItem.query.delete()
            orders_removed = Order.query.delete()
            deleted = Product.query.delete()
            db.session.commit()
            print(
                f"Removed {deleted} product(s) and {orders_removed} order(s)."
            )

        products = []
        for index in range(count):
            category = random.choice(list(CATALOG.keys()))
            base_name = random.choice(CATALOG[category])
            low, high = PRICE_BANDS[category]
            products.append(
                Product(
                    name=f"{base_name} — Model {index + 1:04d}",
                    description=f"High quality {base_name.lower()} in the {category} range.",
                    category=category,
                    price=round(random.uniform(low, high), 2),
                    stock_quantity=random.randint(0, 250),
                )
            )

        db.session.bulk_save_objects(products)
        db.session.commit()
        cache.invalidate("products:*")

        total = Product.query.count()
        print(f"Inserted {count} product(s). Catalog now holds {total}.")
        for category in CATALOG:
            n = Product.query.filter_by(category=category).count()
            print(f"  {category:<14} {n}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed the product catalog.")
    parser.add_argument("--count", type=int, default=120, help="how many products to add")
    parser.add_argument("--reset", action="store_true", help="delete existing products first")
    args = parser.parse_args()
    seed(args.count, args.reset)
