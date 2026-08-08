"""Shared pytest fixtures.

Tests run against a dedicated `ecommerce_test_db` schema that is dropped and
recreated for every test, so no test can leak state into another.
"""

import os

import pytest

os.environ["FLASK_ENV"] = "testing"

from app import create_app  # noqa: E402
from app.extensions import db as _db  # noqa: E402
from app.models.product import Product  # noqa: E402


@pytest.fixture(scope="session")
def app():
    application = create_app("testing")
    with application.app_context():
        yield application


@pytest.fixture(autouse=True)
def clean_db(app):
    """Give every test a pristine schema."""
    with app.app_context():
        _db.drop_all()
        _db.create_all()
        yield
        _db.session.remove()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def sample_product(app):
    product = Product(
        name="Test Widget",
        description="A widget used in tests",
        category="Tools",
        price=100.00,
        stock_quantity=10,
    )
    _db.session.add(product)
    _db.session.commit()
    return product.id


@pytest.fixture
def product_factory(app):
    def _make(name="Item", category="General", price=50.0, stock=5):
        product = Product(
            name=name, category=category, price=price, stock_quantity=stock
        )
        _db.session.add(product)
        _db.session.commit()
        return product.id

    return _make
