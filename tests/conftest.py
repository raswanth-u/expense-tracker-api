import os

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

# Import your app and models
from main import app, get_session


# ============================================
# FIXTURE: Test Database Engine
# ============================================
@pytest.fixture(name="session")
def session_fixture():
    """
    Create an in-memory SQLite database for testing.

    Python Syntax Explained:
    - @pytest.fixture: Decorator that marks this function as reusable test setup
    - name="session": Allows us to use 'session' as parameter name in tests
    - yield: Pauses here, runs test, then continues cleanup after
    """

    # Create in-memory SQLite database (fast, isolated)
    engine = create_engine(
        "sqlite:///:memory:",  # :memory: = RAM-only database
        connect_args={"check_same_thread": False},  # SQLite threading fix
        poolclass=StaticPool,  # Keep connection alive during test
    )

    # Create all tables
    SQLModel.metadata.create_all(engine)

    # Create a session for the test
    with Session(engine) as session:
        yield session  # Test runs here with this session

    # Cleanup happens automatically when 'with' block ends


# ============================================
# FIXTURE: Test Client
# ============================================
@pytest.fixture(name="client")
def client_fixture(session: Session):
    """
    Create a FastAPI test client with overridden database session.

    Python Syntax Explained:
    - session: Session: Type hint (session parameter must be Session type)
    - app.dependency_overrides: Dict that replaces real dependencies with test ones
    """

    # Override the database session dependency
    def get_session_override():
        return session  # Return our test session instead of real DB

    app.dependency_overrides[get_session] = get_session_override

    # Create test client
    client = TestClient(app)
    yield client  # Test runs here

    # Cleanup: Remove override
    app.dependency_overrides.clear()


# ============================================
# FIXTURE: API Key Header
# ============================================
@pytest.fixture(name="auth_headers")
def auth_headers_fixture():
    """
    Provide authentication headers for protected endpoints.

    Python Syntax Explained:
    - Dict literal: {"key": "value"}
    - os.getenv(): Get environment variable with default fallback
    """
    api_key = os.getenv("API_KEY", "dev-key-change-in-prod")
    return {"X-API-Key": api_key}
