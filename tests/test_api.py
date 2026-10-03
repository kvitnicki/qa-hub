import pytest
from fastapi.testclient import TestClient

from app.main import app, items_db


@pytest.fixture(autouse=True)
def clear_db():
    """Очищаем in-memory БД перед каждым тестом."""
    items_db.clear()
    yield
    items_db.clear()


client = TestClient(app)


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "QA Portfolio API", "status": "ok"}


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_get_items_empty():
    response = client.get("/items")
    assert response.status_code == 200
    assert response.json() == []


def test_create_item():
    item = {"id": 1, "name": "Laptop", "price": 999.99}
    response = client.post("/items", json=item)
    assert response.status_code == 201
    data = response.json()
    assert data["id"] == 1
    assert data["name"] == "Laptop"
    assert data["price"] == 999.99
    assert data["in_stock"] is True


def test_create_duplicate_item():
    item = {"id": 1, "name": "Laptop", "price": 999.99}
    client.post("/items", json=item)
    response = client.post("/items", json=item)
    assert response.status_code == 400
    assert response.json()["detail"] == "Item already exists"


def test_get_item():
    item = {"id": 1, "name": "Laptop", "price": 999.99}
    client.post("/items", json=item)
    response = client.get("/items/1")
    assert response.status_code == 200
    assert response.json()["name"] == "Laptop"


def test_get_nonexistent_item():
    response = client.get("/items/999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Item not found"


def test_delete_item():
    item = {"id": 1, "name": "Laptop", "price": 999.99}
    client.post("/items", json=item)
    response = client.delete("/items/1")
    assert response.status_code == 204

    response = client.get("/items/1")
    assert response.status_code == 404


def test_delete_nonexistent_item():
    response = client.delete("/items/999")
    assert response.status_code == 404


def test_validation_error():
    item = {"id": 1, "name": "Laptop", "price": "not-a-number"}
    response = client.post("/items", json=item)
    assert response.status_code == 422
