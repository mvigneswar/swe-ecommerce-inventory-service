"""Order placement, stock integrity and concurrency tests."""

import threading

import pytest

from app.extensions import db
from app.models.product import Product


class TestCreateOrder:
    def test_places_order_and_reduces_stock(self, client, sample_product):
        response = client.post(
            "/api/orders",
            json={
                "customer_email": "buyer@example.com",
                "items": [{"product_id": sample_product, "quantity": 3}],
            },
        )
        assert response.status_code == 201
        data = response.get_json()["data"]
        assert data["status"] == "Completed"
        assert data["total_amount"] == 300.00
        assert data["item_count"] == 1

        remaining = client.get(f"/api/products/{sample_product}").get_json()["data"]
        assert remaining["stock_quantity"] == 7

    def test_multi_item_order_totals_correctly(self, client, product_factory):
        first = product_factory(name="A", price=10.0, stock=5)
        second = product_factory(name="B", price=2.50, stock=5)
        response = client.post(
            "/api/orders",
            json={
                "customer_email": "buyer@example.com",
                "items": [
                    {"product_id": first, "quantity": 2},
                    {"product_id": second, "quantity": 4},
                ],
            },
        )
        assert response.status_code == 201
        # (10.00 * 2) + (2.50 * 4) = 30.00
        assert response.get_json()["data"]["total_amount"] == 30.00

    def test_duplicate_product_lines_are_merged(self, client, sample_product):
        response = client.post(
            "/api/orders",
            json={
                "customer_email": "buyer@example.com",
                "items": [
                    {"product_id": sample_product, "quantity": 2},
                    {"product_id": sample_product, "quantity": 3},
                ],
            },
        )
        assert response.status_code == 201
        assert response.get_json()["data"]["item_count"] == 1
        remaining = client.get(f"/api/products/{sample_product}").get_json()["data"]
        assert remaining["stock_quantity"] == 5  # 10 - (2 + 3)


class TestOrderValidation:
    def test_rejects_insufficient_stock(self, client, sample_product):
        response = client.post(
            "/api/orders",
            json={
                "customer_email": "buyer@example.com",
                "items": [{"product_id": sample_product, "quantity": 500}],
            },
        )
        assert response.status_code == 409
        error = response.get_json()["error"]
        assert error["code"] == "INSUFFICIENT_STOCK"
        assert error["details"]["available"] == 10

    def test_rejects_unknown_product(self, client):
        response = client.post(
            "/api/orders",
            json={
                "customer_email": "buyer@example.com",
                "items": [{"product_id": 424242, "quantity": 1}],
            },
        )
        assert response.status_code == 404

    def test_rejects_bad_email(self, client, sample_product):
        response = client.post(
            "/api/orders",
            json={
                "customer_email": "not-an-email",
                "items": [{"product_id": sample_product, "quantity": 1}],
            },
        )
        assert response.status_code == 400

    def test_rejects_empty_items(self, client):
        response = client.post(
            "/api/orders", json={"customer_email": "a@b.com", "items": []}
        )
        assert response.status_code == 400

    def test_rejects_zero_quantity(self, client, sample_product):
        response = client.post(
            "/api/orders",
            json={
                "customer_email": "a@b.com",
                "items": [{"product_id": sample_product, "quantity": 0}],
            },
        )
        assert response.status_code == 400

    def test_failed_order_rolls_back_all_stock(self, client, product_factory):
        """A later out-of-stock line must undo earlier successful decrements."""
        good = product_factory(name="Good", price=10.0, stock=10)
        scarce = product_factory(name="Scarce", price=10.0, stock=1)

        response = client.post(
            "/api/orders",
            json={
                "customer_email": "buyer@example.com",
                "items": [
                    {"product_id": good, "quantity": 5},
                    {"product_id": scarce, "quantity": 99},
                ],
            },
        )
        assert response.status_code == 409

        # The good product's stock must be untouched.
        remaining = client.get(f"/api/products/{good}").get_json()["data"]
        assert remaining["stock_quantity"] == 10


class TestReadCancelOrder:
    def test_fetches_order(self, client, sample_product):
        created = client.post(
            "/api/orders",
            json={
                "customer_email": "buyer@example.com",
                "items": [{"product_id": sample_product, "quantity": 1}],
            },
        ).get_json()["data"]

        response = client.get(f"/api/orders/{created['id']}")
        assert response.status_code == 200
        assert response.get_json()["data"]["id"] == created["id"]

    def test_missing_order_404(self, client):
        assert client.get("/api/orders/424242").status_code == 404

    def test_cancel_restores_stock(self, client, sample_product):
        created = client.post(
            "/api/orders",
            json={
                "customer_email": "buyer@example.com",
                "items": [{"product_id": sample_product, "quantity": 4}],
            },
        ).get_json()["data"]

        assert client.get(f"/api/products/{sample_product}").get_json()["data"][
            "stock_quantity"
        ] == 6

        response = client.post(f"/api/orders/{created['id']}/cancel")
        assert response.status_code == 200
        assert response.get_json()["data"]["status"] == "Cancelled"
        assert client.get(f"/api/products/{sample_product}").get_json()["data"][
            "stock_quantity"
        ] == 10

    def test_double_cancel_conflicts(self, client, sample_product):
        created = client.post(
            "/api/orders",
            json={
                "customer_email": "buyer@example.com",
                "items": [{"product_id": sample_product, "quantity": 1}],
            },
        ).get_json()["data"]

        client.post(f"/api/orders/{created['id']}/cancel")
        response = client.post(f"/api/orders/{created['id']}/cancel")
        assert response.status_code == 409


@pytest.mark.concurrency
class TestConcurrency:
    """Proves the `SELECT ... FOR UPDATE` row lock actually prevents overselling."""

    def test_only_one_buyer_wins_the_last_unit(self, app, product_factory):
        product_id = product_factory(name="Last One", price=100.0, stock=1)

        results: list[int] = []
        barrier = threading.Barrier(2)

        def place_order():
            # Each thread needs its own app context and DB session.
            with app.app_context():
                client = app.test_client()
                barrier.wait()  # maximise the race window
                response = client.post(
                    "/api/orders",
                    json={
                        "customer_email": "racer@example.com",
                        "items": [{"product_id": product_id, "quantity": 1}],
                    },
                )
                results.append(response.status_code)

        threads = [threading.Thread(target=place_order) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)

        assert len(results) == 2
        assert results.count(201) == 1, f"expected exactly one winner, got {results}"
        assert results.count(409) == 1, f"expected exactly one rejection, got {results}"

        with app.app_context():
            product = db.session.get(Product, product_id)
            db.session.refresh(product)
            assert product.stock_quantity == 0, "stock must never go negative"

    def test_concurrent_orders_never_oversell(self, app, product_factory):
        """10 buyers race for 5 units — exactly 5 succeed."""
        product_id = product_factory(name="Limited", price=10.0, stock=5)

        results: list[int] = []
        lock = threading.Lock()
        barrier = threading.Barrier(10)

        def place_order():
            with app.app_context():
                client = app.test_client()
                barrier.wait()
                response = client.post(
                    "/api/orders",
                    json={
                        "customer_email": "racer@example.com",
                        "items": [{"product_id": product_id, "quantity": 1}],
                    },
                )
                with lock:
                    results.append(response.status_code)

        threads = [threading.Thread(target=place_order) for _ in range(10)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)

        assert results.count(201) == 5, f"expected 5 successes, got {results}"

        with app.app_context():
            product = db.session.get(Product, product_id)
            db.session.refresh(product)
            assert product.stock_quantity == 0
