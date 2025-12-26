from fastapi.testclient import TestClient


# ============================================
# TEST: Create Expense - Success Case
# ============================================
def test_create_expense_success(client: TestClient, auth_headers: dict):
    """
    Test creating a valid expense.

    Python Syntax Explained:
    - Function name must start with 'test_' for pytest to discover it
    - client, auth_headers: Fixture parameters (pytest injects them automatically)
    - client: TestClient: Type hint for IDE autocomplete
    """

    # Arrange: Prepare test data
    expense_data = {
        "amount": 50.75,
        "category": "Food",
        "description": "Lunch at cafe",
        "date": "2024-01-15",
        "payment_method": "Credit Card"
    }

    # Act: Make POST request
    response = client.post(
        "/expenses/",           # Endpoint URL
        json=expense_data,       # Converts dict to JSON automatically
        headers=auth_headers     # Add authentication
    )

    # Assert: Check response
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    # Parse JSON response
    data = response.json()

    # Verify all fields match
    assert data["amount"] == expense_data["amount"]
    assert data["category"] == expense_data["category"]
    assert data["description"] == expense_data["description"]
    assert data["date"] == expense_data["date"]
    assert data["payment_method"] == expense_data["payment_method"]

    # Verify ID was generated
    assert "id" in data
    assert isinstance(data["id"], int)  # isinstance() checks type
    assert data["id"] > 0


# ============================================
# TEST: Create Expense - Missing Auth
# ============================================
def test_create_expense_no_auth(client: TestClient):
    """
    Test that creating expense without API key fails.

    Python Syntax Explained:
    - No auth_headers parameter = no authentication
    """

    expense_data = {
        "amount": 50.75,
        "category": "Food",
        "date": "2024-01-15"
    }

    # Make request WITHOUT auth headers
    response = client.post("/expenses/", json=expense_data)

    # Should return 403 Forbidden
    assert response.status_code == 403
    assert "Could not validate credentials" in response.json()["detail"]


# ============================================
# TEST: Create Expense - Invalid Data
# ============================================
def test_create_expense_invalid_data(client: TestClient, auth_headers: dict):
    """
    Test validation errors for invalid expense data.

    Python Syntax Explained:
    - Missing required fields should trigger FastAPI validation
    """

    # Missing required 'amount' field
    invalid_data = {
        "category": "Food",
        "date": "2024-01-15"
    }

    response = client.post(
        "/expenses/",
        json=invalid_data,
        headers=auth_headers
    )

    # FastAPI returns 422 for validation errors
    assert response.status_code == 422


# ============================================
# TEST: Create Expense - Wrong Type
# ============================================
def test_create_expense_wrong_type(client: TestClient, auth_headers: dict):
    """
    Test that wrong data types are rejected.
    """

    # Amount should be float, not string
    invalid_data = {
        "amount": "not-a-number",  # Wrong type
        "category": "Food",
        "date": "2024-01-15"
    }

    response = client.post(
        "/expenses/",
        json=invalid_data,
        headers=auth_headers
    )

    assert response.status_code == 422

# ============================================
# TEST: Get All Expenses - Empty Database
# ============================================
def test_get_expenses_empty(client: TestClient, auth_headers: dict):
    """
    Test getting expenses when database is empty.

    Python Syntax Explained:
    - Each test gets a fresh database (thanks to session fixture)
    """

    response = client.get("/expenses/", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == []  # Empty list


# ============================================
# TEST: Get All Expenses - With Data
# ============================================
def test_get_expenses_with_data(client: TestClient, auth_headers: dict):
    """
    Test getting expenses after creating some.
    """

    # Create 3 expenses
    expenses = [
        {"amount": 10.0, "category": "Food", "date": "2024-01-01"},
        {"amount": 20.0, "category": "Transport", "date": "2024-01-02"},
        {"amount": 30.0, "category": "Food", "date": "2024-01-03"},
    ]

    for expense in expenses:
        client.post("/expenses/", json=expense, headers=auth_headers)

    # Get all expenses
    response = client.get("/expenses/", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3


# ============================================
# TEST: Get Expenses - Filter by Category
# ============================================
def test_get_expenses_filter_category(client: TestClient, auth_headers: dict):
    """
    Test filtering expenses by category.

    Python Syntax Explained:
    - params={"key": "value"}: Query parameters (?category=Food)
    """

    # Create expenses in different categories
    client.post("/expenses/", json={
        "amount": 10.0, "category": "Food", "date": "2024-01-01"
    }, headers=auth_headers)

    client.post("/expenses/", json={
        "amount": 20.0, "category": "Transport", "date": "2024-01-02"
    }, headers=auth_headers)

    # Filter by Food category
    response = client.get(
        "/expenses/",
        params={"category": "Food"},  # Query parameter
        headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["category"] == "Food"


# ============================================
# TEST: Get Expenses - Filter by Amount Range
# ============================================
def test_get_expenses_filter_amount(client: TestClient, auth_headers: dict):
    """
    Test filtering by min/max amount.
    """

    # Create expenses with different amounts
    amounts = [10.0, 25.0, 50.0, 100.0]
    for amount in amounts:
        client.post("/expenses/", json={
            "amount": amount,
            "category": "Test",
            "date": "2024-01-01"
        }, headers=auth_headers)

    # Filter: 20 <= amount <= 60
    response = client.get(
        "/expenses/",
        params={"min_amount": 20, "max_amount": 60},
        headers=auth_headers
    )

    data = response.json()
    assert len(data) == 2  # 25.0 and 50.0
    assert all(20 <= item["amount"] <= 60 for item in data)
    # all(): Returns True if all items in iterable are True
    # Generator expression: (condition for item in list)


# ============================================
# TEST: Get Expenses - No Auth
# ============================================
def test_get_expenses_no_auth(client: TestClient):
    """
    Test that GET requires authentication.
    """

    response = client.get("/expenses/")  # No headers
    assert response.status_code == 403

# ============================================
# TEST: Get Single Expense - Success
# ============================================
def test_get_expense_by_id_success(client: TestClient, auth_headers: dict):
    """
    Test getting a specific expense by ID.
    """

    # Create an expense
    create_response = client.post("/expenses/", json={
        "amount": 42.0,
        "category": "Test",
        "date": "2024-01-01"
    }, headers=auth_headers)

    expense_id = create_response.json()["id"]

    # Get that expense
    response = client.get(f"/expenses/{expense_id}", headers=auth_headers)
    # f-string: f"/expenses/{variable}" inserts variable value

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == expense_id
    assert data["amount"] == 42.0


# ============================================
# TEST: Get Single Expense - Not Found
# ============================================
def test_get_expense_by_id_not_found(client: TestClient, auth_headers: dict):
    """
    Test getting non-existent expense returns 404.
    """

    response = client.get("/expenses/99999", headers=auth_headers)

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


# ============================================
# TEST: Get Single Expense - Invalid ID
# ============================================
def test_get_expense_invalid_id(client: TestClient, auth_headers: dict):
    """
    Test that invalid ID format returns 422.
    """

    response = client.get("/expenses/not-a-number", headers=auth_headers)

    # FastAPI validates path parameters
    assert response.status_code == 422

# ============================================
# TEST: Update Expense - Success
# ============================================
def test_update_expense_success(client: TestClient, auth_headers: dict):
    """
    Test updating an existing expense.
    """

    # Create expense
    create_response = client.post("/expenses/", json={
        "amount": 10.0,
        "category": "Food",
        "description": "Original",
        "date": "2024-01-01",
        "payment_method": "Cash"
    }, headers=auth_headers)

    expense_id = create_response.json()["id"]

    # Update expense
    updated_data = {
        "amount": 15.0,
        "category": "Transport",
        "description": "Updated",
        "date": "2024-01-02",
        "payment_method": "Card"
    }

    response = client.put(
        f"/expenses/{expense_id}",
        json=updated_data,
        headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()

    # Verify all fields updated
    assert data["id"] == expense_id  # ID shouldn't change
    assert data["amount"] == 15.0
    assert data["category"] == "Transport"
    assert data["description"] == "Updated"


# ============================================
# TEST: Update Expense - Not Found
# ============================================
def test_update_expense_not_found(client: TestClient, auth_headers: dict):
    """
    Test updating non-existent expense returns 404.
    """

    response = client.put(
        "/expenses/99999",
        json={
            "amount": 10.0,
            "category": "Test",
            "date": "2024-01-01"
        },
        headers=auth_headers
    )

    assert response.status_code == 404


# ============================================
# TEST: Update Expense - No Auth
# ============================================
def test_update_expense_no_auth(client: TestClient):
    """
    Test that update requires authentication.
    """

    response = client.put("/expenses/1", json={
        "amount": 10.0,
        "category": "Test",
        "date": "2024-01-01"
    })

    assert response.status_code == 403

# ============================================
# TEST: Delete Expense - Success
# ============================================
def test_delete_expense_success(client: TestClient, auth_headers: dict):
    """
    Test deleting an expense.
    """

    # Create expense
    create_response = client.post("/expenses/", json={
        "amount": 10.0,
        "category": "Test",
        "date": "2024-01-01"
    }, headers=auth_headers)

    expense_id = create_response.json()["id"]

    # Delete expense
    response = client.delete(f"/expenses/{expense_id}", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["id"] == expense_id

    # Verify it's actually deleted
    get_response = client.get(f"/expenses/{expense_id}", headers=auth_headers)
    assert get_response.status_code == 404


# ============================================
# TEST: Delete Expense - Not Found
# ============================================
def test_delete_expense_not_found(client: TestClient, auth_headers: dict):
    """
    Test deleting non-existent expense returns 404.
    """

    response = client.delete("/expenses/99999", headers=auth_headers)
    assert response.status_code == 404


# ============================================
# TEST: Delete Expense - No Auth
# ============================================
def test_delete_expense_no_auth(client: TestClient):
    """
    Test that delete requires authentication.
    """

    response = client.delete("/expenses/1")
    assert response.status_code == 403

# ============================================
# TEST: Summary - Empty Database
# ============================================
def test_summary_empty(client: TestClient, auth_headers: dict):
    """
    Test summary with no expenses.
    """

    response = client.get("/expenses/summary", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == []


# ============================================
# TEST: Summary - Group by Category
# ============================================
def test_summary_by_category(client: TestClient, auth_headers: dict):
    """
    Test summary groups expenses by category.
    """

    # Create expenses in different categories
    expenses = [
        {"amount": 10.0, "category": "Food", "date": "2024-01-01"},
        {"amount": 20.0, "category": "Food", "date": "2024-01-02"},
        {"amount": 30.0, "category": "Transport", "date": "2024-01-03"},
    ]

    for expense in expenses:
        client.post("/expenses/", json=expense, headers=auth_headers)

    # Get summary
    response = client.get("/expenses/summary", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()

    # Should have 2 categories
    assert len(data) == 2

    # Find Food category
    food_summary = next(item for item in data if item["category"] == "Food")
    # next(): Get first item matching condition

    assert food_summary["total"] == 30.0  # 10 + 20


# ============================================
# TEST: Summary - Date Range Filter
# ============================================
def test_summary_date_filter(client: TestClient, auth_headers: dict):
    """
    Test summary with date range filtering.
    """

    # Create expenses on different dates
    client.post("/expenses/", json={
        "amount": 10.0, "category": "Food", "date": "2024-01-01"
    }, headers=auth_headers)

    client.post("/expenses/", json={
        "amount": 20.0, "category": "Food", "date": "2024-01-15"
    }, headers=auth_headers)

    client.post("/expenses/", json={
        "amount": 30.0, "category": "Food", "date": "2024-02-01"
    }, headers=auth_headers)

    # Get summary for January only
    response = client.get(
        "/expenses/summary",
        params={"from_date": "2024-01-01", "to_date": "2024-01-31"},
        headers=auth_headers
    )

    data = response.json()
    assert len(data) == 1
    assert data[0]["total"] == 30.0  # Only Jan expenses

# ============================================
# TEST: Payment Summary - Success
# ============================================
def test_payment_summary(client: TestClient, auth_headers: dict):
    """
    Test payment method summary.
    """

    # Create expenses with different payment methods
    expenses = [
        {"amount": 10.0, "category": "Food", "date": "2024-01-01", "payment_method": "Cash"},
        {"amount": 20.0, "category": "Food", "date": "2024-01-02", "payment_method": "Cash"},
        {"amount": 30.0, "category": "Food", "date": "2024-01-03", "payment_method": "Card"},
    ]

    for expense in expenses:
        client.post("/expenses/", json=expense, headers=auth_headers)

    # Get payment summary
    response = client.get("/expenses/payment_summary", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()

    # Should have 2 payment methods
    assert len(data) == 2

    cash_summary = next(item for item in data if item["payment_method"] == "Cash")
    assert cash_summary["total"] == 30.0
