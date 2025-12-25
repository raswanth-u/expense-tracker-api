"""
Comprehensive API tests for expense tracker.
Run with: pytest tests/ -v
"""
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Set test environment before importing app
os.environ["API_KEY"] = "test_api_key"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from main import app, get_db
from models import Base


# ============================================
# Test Database Setup
# ============================================
@pytest.fixture(scope="function")
def test_db():
    """Create a fresh test database for each test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestingSessionLocal()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(test_db):
    """Create test client with auth header."""
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Valid authentication headers."""
    return {"X-API-Key": "test_api_key"}


# ============================================
# Health Check Tests
# ============================================
class TestHealthCheck:
    """Tests for /health endpoint."""

    def test_health_check_returns_ok(self, client):
        """Health check should return status ok."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_health_check_includes_timestamp(self, client):
        """Health check should include timestamp."""
        response = client.get("/health")
        assert "timestamp" in response.json()


# ============================================
# Authentication Tests
# ============================================
class TestAuthentication:
    """Tests for API key authentication."""

    def test_request_without_api_key_fails(self, client):
        """Requests without API key should return 401."""
        response = client.get("/expenses/")
        assert response.status_code == 401

    def test_request_with_invalid_api_key_fails(self, client):
        """Requests with wrong API key should return 401."""
        response = client.get(
            "/expenses/",
            headers={"X-API-Key": "wrong_key"}
        )
        assert response.status_code == 401

    def test_request_with_valid_api_key_succeeds(self, client, auth_headers):
        """Requests with correct API key should succeed."""
        response = client.get("/expenses/", headers=auth_headers)
        assert response.status_code == 200


# ============================================
# Expense CRUD Tests
# ============================================
class TestExpenseCRUD:
    """Tests for expense create, read, update, delete."""

    def test_create_expense(self, client, auth_headers):
        """Should create a new expense."""
        expense_data = {
            "amount": 50.00,
            "description": "Test expense",
            "category": "food"
        }
        response = client.post(
            "/expenses/",
            json=expense_data,
            headers=auth_headers
        )
        assert response.status_code == 201
        assert response.json()["amount"] == 50.00
        assert response.json()["description"] == "Test expense"
        assert "id" in response.json()

    def test_list_expenses_empty(self, client, auth_headers):
        """Should return empty list when no expenses."""
        response = client.get("/expenses/", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []

    def test_list_expenses_after_create(self, client, auth_headers):
        """Should return created expenses."""
        # Create expense
        client.post(
            "/expenses/",
            json={"amount": 25.00, "description": "Coffee", "category": "food"},
            headers=auth_headers
        )

        # List expenses
        response = client.get("/expenses/", headers=auth_headers)
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["description"] == "Coffee"

    def test_get_expense_by_id(self, client, auth_headers):
        """Should retrieve expense by ID."""
        # Create expense
        create_response = client.post(
            "/expenses/",
            json={"amount": 100.00, "description": "Groceries", "category": "food"},
            headers=auth_headers
        )
        expense_id = create_response.json()["id"]

        # Get by ID
        response = client.get(f"/expenses/{expense_id}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["id"] == expense_id

    def test_get_nonexistent_expense_returns_404(self, client, auth_headers):
        """Should return 404 for non-existent expense."""
        response = client.get("/expenses/99999", headers=auth_headers)
        assert response.status_code == 404

    def test_delete_expense(self, client, auth_headers):
        """Should delete expense."""
        # Create expense
        create_response = client.post(
            "/expenses/",
            json={"amount": 75.00, "description": "Dinner", "category": "food"},
            headers=auth_headers
        )
        expense_id = create_response.json()["id"]

        # Delete
        delete_response = client.delete(
            f"/expenses/{expense_id}",
            headers=auth_headers
        )
        assert delete_response.status_code == 204

        # Verify deleted
        get_response = client.get(
            f"/expenses/{expense_id}",
            headers=auth_headers
        )
        assert get_response.status_code == 404


# ============================================
# Validation Tests
# ============================================
class TestValidation:
    """Tests for input validation."""

    def test_create_expense_negative_amount_fails(self, client, auth_headers):
        """Should reject negative amounts."""
        response = client.post(
            "/expenses/",
            json={"amount": -50.00, "description": "Invalid", "category": "food"},
            headers=auth_headers
        )
        assert response.status_code == 422

    def test_create_expense_missing_description_fails(self, client, auth_headers):
        """Should require description."""
        response = client.post(
            "/expenses/",
            json={"amount": 50.00, "category": "food"},
            headers=auth_headers
        )
        assert response.status_code == 422

    def test_create_expense_empty_description_fails(self, client, auth_headers):
        """Should reject empty description."""
        response = client.post(
            "/expenses/",
            json={"amount": 50.00, "description": "", "category": "food"},
            headers=auth_headers
        )
        assert response.status_code == 422
