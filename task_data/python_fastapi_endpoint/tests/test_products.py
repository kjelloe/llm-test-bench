import pytest
from fastapi.testclient import TestClient
from products import app, _db, Product

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_db():
    """Isolate each test: clear the in-memory store and reset the ID counter."""
    import products as _mod
    _db.clear()
    _mod._next_id = 1
    yield
    _db.clear()
    _mod._next_id = 1


def test_create_product_returns_201():
    r = client.post("/products", json={"name": "Widget", "price": 9.99})
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Widget"
    assert body["price"] == 9.99
    assert body["id"] == 1


def test_create_product_name_is_trimmed():
    r = client.post("/products", json={"name": "  Gadget  ", "price": 5.0})
    assert r.status_code == 201
    assert r.json()["name"] == "Gadget"


def test_create_product_empty_name_returns_422():
    r = client.post("/products", json={"name": "", "price": 5.0})
    assert r.status_code in (400, 422)


def test_create_product_whitespace_name_returns_422():
    r = client.post("/products", json={"name": "   ", "price": 5.0})
    assert r.status_code in (400, 422)


def test_create_product_negative_price_returns_422():
    r = client.post("/products", json={"name": "Widget", "price": -1.0})
    assert r.status_code in (400, 422)


def test_create_product_zero_price_returns_422():
    r = client.post("/products", json={"name": "Widget", "price": 0.0})
    assert r.status_code in (400, 422)


def test_get_existing_product():
    client.post("/products", json={"name": "Widget", "price": 9.99})
    r = client.get("/products/1")
    assert r.status_code == 200
    assert r.json()["name"] == "Widget"


def test_get_missing_product_returns_404():
    r = client.get("/products/99999")
    assert r.status_code == 404
