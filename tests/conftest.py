import os

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from main import app, get_session


# ============================================
# FIXTURE: Test Database Engine
# ============================================
@pytest.fixture(name="session")
def session_fixture():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        yield session


# ============================================
# FIXTURE: Test Client
# ============================================
@pytest.fixture(name="client")
def client_fixture(session: Session):
    """Create a FastAPI test client with overridden database session."""

    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


# ============================================
# FIXTURE: API Key Header
# ============================================
@pytest.fixture(name="auth_headers")
def auth_headers_fixture():
    """Provide authentication headers for protected endpoints."""
    api_key = os.getenv("API_KEY", "dev-key-change-in-prod")
    return {"X-API-Key": api_key}


# ============================================
# FIXTURE: Test User
# ============================================
@pytest.fixture(name="test_user")
def test_user_fixture(client: TestClient, auth_headers: dict):
    """Create a test user and return the response."""
    response = client.post(
        "/users/",
        json={"name": "Test User", "email": "testuser@example.com", "role": "member"},
        headers=auth_headers,
    )
    return response.json()


# ============================================
# FIXTURE: Test Budget
# ============================================
@pytest.fixture(name="test_budget")
def test_budget_fixture(client: TestClient, auth_headers: dict, test_user: dict):
    """Create a test budget and return the response."""
    response = client.post(
        "/budgets/",
        json={"user_id": test_user["id"], "category": "Food", "amount": 500.0, "month": "2024-12"},
        headers=auth_headers,
    )
    return response.json()


# ============================================
# FIXTURE: Test Credit Card
# ============================================
@pytest.fixture(name="test_card")
def test_card_fixture(client: TestClient, auth_headers: dict, test_user: dict):
    """Create a test credit card and return the response."""
    response = client.post(
        "/credit-cards/",
        json={
            "user_id": test_user["id"],
            "card_name": "Test Card",
            "last_four": "1234",
            "credit_limit": 5000.0,
            "billing_day": 15,
        },
        headers=auth_headers,
    )
    return response.json()


# ============================================
# FIXTURE: Test Expense
# ============================================
@pytest.fixture(name="test_expense")
def test_expense_fixture(client: TestClient, auth_headers: dict, test_user: dict):
    """Create a test expense and return the response."""
    response = client.post(
        "/expenses/",
        json={
            "user_id": test_user["id"],
            "amount": 50.0,
            "category": "Food",
            "description": "Test expense",
            "date": "2024-12-15",
            "payment_method": "cash",
        },
        headers=auth_headers,
    )
    return response.json()
