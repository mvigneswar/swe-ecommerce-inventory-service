"""Product catalog API tests."""


class TestHealth:
    def test_health_reports_mysql_up(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200
        body = response.get_json()
        assert body["success"] is True
        assert body["data"]["dependencies"]["mysql"] == "up"


class TestCreateProduct:
    def test_creates_product(self, client):
        response = client.post(
            "/api/products",
            json={
                "name": "Laptop Stand",
                "category": "Accessories",
                "price": 1299.99,
                "stock_quantity": 25,
            },
        )
        assert response.status_code == 201
        data = response.get_json()["data"]
        assert data["name"] == "Laptop Stand"
        assert data["price"] == 1299.99
        assert data["stock_quantity"] == 25
        assert data["in_stock"] is True

    def test_defaults_stock_to_zero(self, client):
        response = client.post(
            "/api/products",
            json={"name": "Preorder Item", "category": "New", "price": 10},
        )
        assert response.status_code == 201
        assert response.get_json()["data"]["stock_quantity"] == 0

    def test_rejects_missing_name(self, client):
        response = client.post("/api/products", json={"category": "X", "price": 1})
        assert response.status_code == 400
        assert response.get_json()["error"]["code"] == "VALIDATION_ERROR"

    def test_rejects_negative_price(self, client):
        response = client.post(
            "/api/products", json={"name": "Bad", "category": "X", "price": -1}
        )
        assert response.status_code == 400

    def test_rejects_negative_stock(self, client):
        response = client.post(
            "/api/products",
            json={"name": "Bad", "category": "X", "price": 1, "stock_quantity": -5},
        )
        assert response.status_code == 400

    def test_rejects_non_json_body(self, client):
        response = client.post(
            "/api/products", data="not json", content_type="text/plain"
        )
        assert response.status_code == 400


class TestReadProducts:
    def test_lists_products(self, client, product_factory):
        product_factory(name="A")
        product_factory(name="B")
        response = client.get("/api/products")
        assert response.status_code == 200
        body = response.get_json()
        assert len(body["data"]) == 2
        assert body["meta"]["pagination"]["total"] == 2

    def test_filters_by_category(self, client, product_factory):
        product_factory(name="Phone", category="Electronics")
        product_factory(name="Hammer", category="Tools")
        response = client.get("/api/products?category=Tools")
        data = response.get_json()["data"]
        assert len(data) == 1
        assert data[0]["name"] == "Hammer"

    def test_search_by_name(self, client, product_factory):
        product_factory(name="Blue Shirt")
        product_factory(name="Red Shoes")
        response = client.get("/api/products?search=Shirt")
        data = response.get_json()["data"]
        assert len(data) == 1
        assert data[0]["name"] == "Blue Shirt"

    def test_pagination(self, client, product_factory):
        for i in range(5):
            product_factory(name=f"P{i}")
        response = client.get("/api/products?page=1&limit=2")
        body = response.get_json()
        assert len(body["data"]) == 2
        assert body["meta"]["pagination"]["pages"] == 3

    def test_rejects_limit_over_max(self, client):
        response = client.get("/api/products?limit=99999")
        assert response.status_code == 400

    def test_get_single_product(self, client, sample_product):
        response = client.get(f"/api/products/{sample_product}")
        assert response.status_code == 200
        assert response.get_json()["data"]["id"] == sample_product

    def test_missing_product_returns_404(self, client):
        response = client.get("/api/products/424242")
        assert response.status_code == 404
        assert response.get_json()["error"]["code"] == "NOT_FOUND"

    def test_lists_categories(self, client, product_factory):
        product_factory(name="A", category="Alpha")
        product_factory(name="B", category="Beta")
        response = client.get("/api/products/categories")
        assert sorted(response.get_json()["data"]) == ["Alpha", "Beta"]


class TestUpdateDeleteProduct:
    def test_updates_price(self, client, sample_product):
        response = client.put(
            f"/api/products/{sample_product}", json={"price": 250.75}
        )
        assert response.status_code == 200
        assert response.get_json()["data"]["price"] == 250.75

    def test_partial_update_keeps_other_fields(self, client, sample_product):
        client.put(f"/api/products/{sample_product}", json={"stock_quantity": 99})
        response = client.get(f"/api/products/{sample_product}")
        data = response.get_json()["data"]
        assert data["stock_quantity"] == 99
        assert data["name"] == "Test Widget"

    def test_update_missing_product_404(self, client):
        response = client.put("/api/products/424242", json={"price": 5})
        assert response.status_code == 404

    def test_deletes_product(self, client, sample_product):
        assert client.delete(f"/api/products/{sample_product}").status_code == 200
        assert client.get(f"/api/products/{sample_product}").status_code == 404
