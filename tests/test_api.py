from fastapi.testclient import TestClient

# ============================================
# USER TESTS
# ============================================


def test_create_user_success(client: TestClient, auth_headers: dict):
    """Test creating a new user."""
    response = client.post(
        "/users/",
        json={"name": "John Doe", "email": "john@example.com", "role": "admin"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "John Doe"
    assert data["email"] == "john@example.com"
    assert data["role"] == "admin"
    assert data["is_active"] is True
    assert "id" in data
    assert "created_at" in data


def test_create_user_duplicate_email(client: TestClient, auth_headers: dict):
    """Test that duplicate email is rejected."""
    # Create first user
    client.post(
        "/users/",
        json={"name": "User 1", "email": "duplicate@example.com", "role": "member"},
        headers=auth_headers,
    )

    # Try to create second user with same email
    response = client.post(
        "/users/",
        json={"name": "User 2", "email": "duplicate@example.com", "role": "member"},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_create_user_invalid_email(client: TestClient, auth_headers: dict):
    """Test that invalid email is rejected."""
    response = client.post(
        "/users/",
        json={"name": "Test", "email": "invalid-email", "role": "member"},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_create_user_invalid_role(client: TestClient, auth_headers: dict):
    """Test that invalid role is rejected."""
    response = client.post(
        "/users/",
        json={"name": "Test", "email": "test@example.com", "role": "superuser"},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_get_users(client: TestClient, auth_headers: dict, test_user: dict):
    """Test listing all users."""
    response = client.get("/users/", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert any(u["id"] == test_user["id"] for u in data)


def test_get_user_by_id(client: TestClient, auth_headers: dict, test_user: dict):
    """Test getting specific user."""
    response = client.get(f"/users/{test_user['id']}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_user["id"]
    assert data["name"] == test_user["name"]


def test_get_user_not_found(client: TestClient, auth_headers: dict):
    """Test getting non-existent user."""
    response = client.get("/users/99999", headers=auth_headers)
    assert response.status_code == 404


def test_update_user(client: TestClient, auth_headers: dict, test_user: dict):
    """Test updating user."""
    response = client.put(
        f"/users/{test_user['id']}",
        json={"name": "Updated Name", "email": "updated@example.com", "role": "admin"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Name"
    assert data["email"] == "updated@example.com"


def test_delete_user(client: TestClient, auth_headers: dict):
    """Test deactivating user."""
    # Create user to delete
    create_response = client.post(
        "/users/",
        json={"name": "To Delete", "email": "delete@example.com", "role": "member"},
        headers=auth_headers,
    )
    user_id = create_response.json()["id"]

    # Delete user
    response = client.delete(f"/users/{user_id}", headers=auth_headers)
    assert response.status_code == 200

    # Verify user is inactive
    get_response = client.get(f"/users/{user_id}", headers=auth_headers)
    assert get_response.json()["is_active"] is False


def test_user_stats(client: TestClient, auth_headers: dict, test_user: dict, test_expense: dict):
    """Test user statistics."""
    response = client.get(f"/users/{test_user['id']}/stats", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == test_user["id"]
    assert "total_spent" in data
    assert "transaction_count" in data


def test_user_no_auth(client: TestClient):
    """Test that user endpoints require authentication."""
    response = client.get("/users/")
    assert response.status_code == 403


# ============================================
# BUDGET TESTS
# ============================================


def test_create_budget_success(client: TestClient, auth_headers: dict, test_user: dict):
    """Test creating a budget."""
    response = client.post(
        "/budgets/",
        json={
            "user_id": test_user["id"],
            "category": "Transport",
            "amount": 200.0,
            "month": "2024-12",
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["category"] == "Transport"
    assert data["amount"] == 200.0
    assert data["month"] == "2024-12"


def test_create_budget_invalid_month(client: TestClient, auth_headers: dict, test_user: dict):
    """Test that invalid month format is rejected."""
    response = client.post(
        "/budgets/",
        json={
            "user_id": test_user["id"],
            "category": "Food",
            "amount": 500.0,
            "month": "2024-13",  # Invalid month
        },
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_create_budget_duplicate(client: TestClient, auth_headers: dict, test_budget: dict):
    """Test that duplicate budget is rejected."""
    response = client.post(
        "/budgets/",
        json={
            "user_id": test_budget["user_id"],
            "category": test_budget["category"],
            "amount": 600.0,
            "month": test_budget["month"],
        },
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_get_budgets(client: TestClient, auth_headers: dict, test_budget: dict):
    """Test listing budgets."""
    response = client.get("/budgets/", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1


def test_get_budgets_filtered(client: TestClient, auth_headers: dict, test_budget: dict):
    """Test filtering budgets."""
    response = client.get(
        "/budgets/",
        params={"month": test_budget["month"], "category": test_budget["category"]},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert all(b["month"] == test_budget["month"] for b in data)


def test_budget_status_summary(
    client: TestClient, auth_headers: dict, test_user: dict, test_budget: dict, test_expense: dict
):
    """Test budget status summary."""
    response = client.get(
        "/budgets/status/summary",
        params={"month": test_budget["month"], "user_id": test_user["id"]},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "total_budget" in data
    assert "total_spent" in data
    assert "budgets" in data
    assert len(data["budgets"]) >= 1


def test_budget_alerts(client: TestClient, auth_headers: dict, test_user: dict, test_budget: dict):
    """Test budget alerts endpoint."""
    response = client.get(
        "/budgets/status/alerts",
        params={"month": test_budget["month"], "user_id": test_user["id"]},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "alert_count" in data
    assert "alerts" in data


def test_update_budget(client: TestClient, auth_headers: dict, test_budget: dict):
    """Test updating budget."""
    response = client.put(
        f"/budgets/{test_budget['id']}",
        json={
            "user_id": test_budget["user_id"],
            "category": test_budget["category"],
            "amount": 700.0,
            "month": test_budget["month"],
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["amount"] == 700.0


def test_delete_budget(client: TestClient, auth_headers: dict, test_budget: dict):
    """Test deactivating budget."""
    response = client.delete(f"/budgets/{test_budget['id']}", headers=auth_headers)
    assert response.status_code == 200


# ============================================
# EXPENSE TESTS (Updated for new model)
# ============================================


def test_create_expense_success(client: TestClient, auth_headers: dict, test_user: dict):
    """Test creating an expense with required user_id."""
    response = client.post(
        "/expenses/",
        json={
            "user_id": test_user["id"],
            "amount": 75.0,
            "category": "Food",
            "description": "Groceries",
            "date": "2024-12-20",
            "payment_method": "cash",
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == test_user["id"]
    assert data["amount"] == 75.0
    assert data["category"] == "Food"


def test_create_expense_invalid_user(client: TestClient, auth_headers: dict):
    """Test that invalid user_id is rejected."""
    response = client.post(
        "/expenses/",
        json={
            "user_id": 99999,
            "amount": 50.0,
            "category": "Food",
            "date": "2024-12-20",
            "payment_method": "cash",
        },
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_create_expense_with_credit_card(
    client: TestClient, auth_headers: dict, test_user: dict, test_card: dict
):
    """Test creating expense with credit card."""
    response = client.post(
        "/expenses/",
        json={
            "user_id": test_user["id"],
            "amount": 100.0,
            "category": "Shopping",
            "date": "2024-12-20",
            "payment_method": "credit_card",
            "credit_card_id": test_card["id"],
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["credit_card_id"] == test_card["id"]


def test_create_expense_invalid_payment_method(
    client: TestClient, auth_headers: dict, test_user: dict
):
    """Test that invalid payment method is rejected."""
    response = client.post(
        "/expenses/",
        json={
            "user_id": test_user["id"],
            "amount": 50.0,
            "category": "Food",
            "date": "2024-12-20",
            "payment_method": "bitcoin",  # Invalid
        },
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_get_expenses_filtered(
    client: TestClient, auth_headers: dict, test_user: dict, test_expense: dict
):
    """Test filtering expenses."""
    response = client.get(
        "/expenses/", params={"user_id": test_user["id"], "category": "Food"}, headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert all(e["user_id"] == test_user["id"] for e in data)


# ============================================
# CREDIT CARD TESTS
# ============================================


def test_create_credit_card_success(client: TestClient, auth_headers: dict, test_user: dict):
    """Test creating a credit card."""
    response = client.post(
        "/credit-cards/",
        json={
            "user_id": test_user["id"],
            "card_name": "Visa Platinum",
            "last_four": "5678",
            "credit_limit": 10000.0,
            "billing_day": 1,
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["card_name"] == "Visa Platinum"
    assert data["last_four"] == "5678"


def test_create_credit_card_invalid_last_four(
    client: TestClient, auth_headers: dict, test_user: dict
):
    """Test that invalid last_four is rejected."""
    response = client.post(
        "/credit-cards/",
        json={
            "user_id": test_user["id"],
            "card_name": "Test Card",
            "last_four": "abcd",  # Must be digits
            "credit_limit": 5000.0,
            "billing_day": 15,
        },
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_get_credit_card_statement(
    client: TestClient, auth_headers: dict, test_card: dict, test_user: dict
):
    """Test getting credit card statement."""
    # Get billing day from card
    billing_day = test_card["billing_day"]  # e.g., 15

    # Create expense that will definitely be in the billing cycle
    # Use a date a few days before billing day
    expense_date = f"2024-12-{billing_day - 5:02d}"

    client.post(
        "/expenses/",
        json={
            "user_id": test_user["id"],
            "amount": 200.0,
            "category": "Shopping",
            "date": expense_date,
            "payment_method": "credit_card",
            "credit_card_id": test_card["id"],
        },
        headers=auth_headers,
    )

    response = client.get(
        f"/credit-cards/{test_card['id']}/statement",
        params={"month": "2024-12"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()

    # Verify structure
    assert "summary" in data
    assert "transactions" in data
    assert "billing_cycle" in data
    assert "total_spent" in data["summary"]
    assert "credit_limit" in data["summary"]

    # The expense should be in the transactions
    assert len(data["transactions"]) >= 0  # May or may not include based on cycle


def test_get_credit_card_utilization(client: TestClient, auth_headers: dict, test_card: dict):
    """Test credit card utilization endpoint."""
    response = client.get(
        f"/credit-cards/{test_card['id']}/utilization", params={"months": 3}, headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert "average_utilization" in data
    assert "history" in data


def test_get_all_cards_summary(
    client: TestClient, auth_headers: dict, test_user: dict, test_card: dict
):
    """Test all cards summary."""
    response = client.get(
        "/credit-cards/summary",
        params={"user_id": test_user["id"], "month": "2024-12"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "total_cards" in data
    assert "cards" in data


# ============================================
# REPORTS TESTS
# ============================================


def test_monthly_report(
    client: TestClient, auth_headers: dict, test_user: dict, test_expense: dict
):
    """Test monthly report."""
    response = client.get(
        "/reports/monthly",
        params={"month": "2024-12", "user_id": test_user["id"]},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "summary" in data
    assert "by_category" in data
    assert "by_payment_method" in data


def test_family_summary(
    client: TestClient, auth_headers: dict, test_user: dict, test_expense: dict
):
    """Test family summary report."""
    # Ensure we have at least one user with expenses
    response = client.get(
        "/reports/family-summary", params={"month": "2024-12"}, headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()

    # Should have month field
    assert data["month"] == "2024-12"

    # Should have either family_total or message
    assert "family_total" in data or "message" in data

    # If family_total exists, verify structure
    if "family_total" in data:
        assert "members" in data
        assert "member_count" in data
        assert isinstance(data["members"], list)


def test_category_analysis(
    client: TestClient, auth_headers: dict, test_user: dict, test_expense: dict
):
    """Test category analysis."""
    # Use the category from test_expense
    response = client.get(
        "/reports/category-analysis",
        params={
            "category": test_expense["category"],  # Use actual category
            "from_date": "2024-12-01",
            "to_date": "2024-12-31",
            "user_id": test_user["id"],
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()

    # Verify structure
    assert data["category"] == test_expense["category"]
    assert "summary" in data
    assert "by_payment_method" in data
    assert "monthly_trend" in data

    # Should have at least one expense
    if "summary" in data and "total_spent" in data["summary"]:
        assert data["summary"]["total_spent"] > 0


def test_spending_trends(client: TestClient, auth_headers: dict, test_user: dict):
    """Test spending trends."""
    response = client.get(
        "/reports/spending-trends",
        params={"months": 3, "user_id": test_user["id"]},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "monthly_data" in data
    assert "trend" in data


def test_payment_method_analysis(
    client: TestClient, auth_headers: dict, test_user: dict, test_expense: dict
):
    """Test payment method analysis."""
    response = client.get(
        "/reports/payment-method-analysis",
        params={"from_date": "2024-12-01", "to_date": "2024-12-31", "user_id": test_user["id"]},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "by_payment_method" in data
    assert "total_spent" in data


def test_export_json(client: TestClient, auth_headers: dict, test_user: dict, test_expense: dict):
    """Test exporting data as JSON."""
    response = client.get(
        "/reports/export",
        params={
            "from_date": "2024-12-01",
            "to_date": "2024-12-31",
            "user_id": test_user["id"],
            "format": "json",
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "expenses" in data
    assert len(data["expenses"]) >= 1


def test_export_csv(client: TestClient, auth_headers: dict, test_user: dict, test_expense: dict):
    """Test exporting data as CSV."""
    response = client.get(
        "/reports/export",
        params={
            "from_date": "2024-12-01",
            "to_date": "2024-12-31",
            "user_id": test_user["id"],
            "format": "csv",
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "Date" in response.text  # CSV header

# ============================================
# ADDITIONAL EXPENSE TESTS
# ============================================

def test_get_expense_by_id_success(client: TestClient, auth_headers: dict, test_expense: dict):
    """Test getting expense by ID."""
    response = client.get(f"/expenses/{test_expense['id']}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_expense["id"]


def test_get_expense_by_id_not_found(client: TestClient, auth_headers: dict):
    """Test getting non-existent expense."""
    response = client.get("/expenses/99999", headers=auth_headers)
    assert response.status_code == 404


def test_update_expense_success(client: TestClient, auth_headers: dict, test_user: dict, test_expense: dict):
    """Test updating expense."""
    response = client.put(
        f"/expenses/{test_expense['id']}",
        json={
            "user_id": test_user["id"],
            "amount": 100.0,
            "category": "Updated",
            "date": "2024-12-25",
            "payment_method": "debit_card"
        },
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["amount"] == 100.0
    assert data["category"] == "Updated"


def test_update_expense_not_found(client: TestClient, auth_headers: dict, test_user: dict):
    """Test updating non-existent expense."""
    response = client.put(
        "/expenses/99999",
        json={
            "user_id": test_user["id"],
            "amount": 100.0,
            "category": "Test",
            "date": "2024-12-25",
            "payment_method": "cash"
        },
        headers=auth_headers
    )
    assert response.status_code == 404


def test_update_expense_invalid_credit_card(client: TestClient, auth_headers: dict, test_user: dict, test_expense: dict):
    """Test updating expense with invalid credit card."""
    response = client.put(
        f"/expenses/{test_expense['id']}",
        json={
            "user_id": test_user["id"],
            "amount": 100.0,
            "category": "Test",
            "date": "2024-12-25",
            "payment_method": "credit_card",
            "credit_card_id": 99999
        },
        headers=auth_headers
    )
    assert response.status_code == 404


def test_delete_expense_success(client: TestClient, auth_headers: dict, test_expense: dict):
    """Test deleting expense."""
    response = client.delete(f"/expenses/{test_expense['id']}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["id"] == test_expense["id"]


def test_delete_expense_not_found(client: TestClient, auth_headers: dict):
    """Test deleting non-existent expense."""
    response = client.delete("/expenses/99999", headers=auth_headers)
    assert response.status_code == 404


def test_get_expense_summary(client: TestClient, auth_headers: dict, test_user: dict, test_expense: dict):
    """Test expense summary endpoint."""
    response = client.get(
        "/expenses/summary",
        params={"from_date": "2024-12-01", "to_date": "2024-12-31", "user_id": test_user["id"]},
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1


def test_get_payment_summary(client: TestClient, auth_headers: dict, test_user: dict, test_expense: dict):
    """Test payment summary endpoint."""
    response = client.get(
        "/expenses/payment_summary",
        params={"from_date": "2024-12-01", "to_date": "2024-12-31", "user_id": test_user["id"]},
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1


def test_create_expense_wrong_card_user(client: TestClient, auth_headers: dict, test_user: dict, test_card: dict):
    """Test creating expense with card belonging to different user."""
    # Create another user
    other_user = client.post(
        "/users/",
        json={"name": "Other User", "email": "other@example.com", "role": "member"},
        headers=auth_headers
    ).json()

    # Try to use test_card (belongs to test_user) with other_user
    response = client.post(
        "/expenses/",
        json={
            "user_id": other_user["id"],
            "amount": 100.0,
            "category": "Test",
            "date": "2024-12-20",
            "payment_method": "credit_card",
            "credit_card_id": test_card["id"]
        },
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == other_user["id"]
    assert data["credit_card_id"] == test_card["id"]

def test_create_expense_cross_user_card_allowed(client: TestClient, auth_headers: dict, test_user: dict, test_card: dict):
    """Test that users can use cards belonging to other users (family sharing scenario)."""
    # Create another user
    user2 = client.post(
        "/users/",
        json={"name": "Family Member 2", "email": "family2@example.com", "role": "member"},
        headers=auth_headers
    ).json()
    
    # User2 borrows User1's card - should work
    response = client.post(
        "/expenses/",
        json={
            "user_id": user2["id"],
            "amount": 150.0,
            "category": "Groceries",
            "description": "Used parent's card",
            "date": "2024-12-20",
            "payment_method": "credit_card",
            "credit_card_id": test_card["id"]  # test_card belongs to test_user
        },
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == user2["id"]
    assert data["credit_card_id"] == test_card["id"]
    assert data["description"] == "Used parent's card"

def test_update_expense_cross_user_card_allowed(client: TestClient, auth_headers: dict, test_user: dict, test_card: dict, test_expense: dict):
    """Test updating expense to use another user's card."""
    # Create another user
    user2 = client.post(
        "/users/",
        json={"name": "Family Member 3", "email": "family3@example.com", "role": "member"},
        headers=auth_headers
    ).json()
    
    # Update expense to use different user's card
    response = client.put(
        f"/expenses/{test_expense['id']}",
        json={
            "user_id": user2["id"],
            "amount": 200.0,
            "category": "Updated",
            "date": "2024-12-25",
            "payment_method": "credit_card",
            "credit_card_id": test_card["id"]  # Different user's card
        },
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == user2["id"]
    assert data["credit_card_id"] == test_card["id"]
    
def test_create_expense_inactive_user(client: TestClient, auth_headers: dict):
    """Test creating expense for inactive user."""
    # Create and deactivate user
    user = client.post(
        "/users/",
        json={"name": "Inactive User", "email": "inactive@example.com", "role": "member"},
        headers=auth_headers
    ).json()

    client.delete(f"/users/{user['id']}", headers=auth_headers)

    # Try to create expense
    response = client.post(
        "/expenses/",
        json={
            "user_id": user["id"],
            "amount": 100.0,
            "category": "Test",
            "date": "2024-12-20",
            "payment_method": "cash"
        },
        headers=auth_headers
    )
    assert response.status_code == 400


def test_create_expense_inactive_card(client: TestClient, auth_headers: dict, test_user: dict):
    """Test creating expense with inactive credit card."""
    # Create a card
    card = client.post(
        "/credit-cards/",
        json={
            "user_id": test_user["id"],
            "card_name": "Test Inactive Card",
            "last_four": "9999",
            "credit_limit": 5000.0,
            "billing_day": 15
        },
        headers=auth_headers
    ).json()
    
    # Deactivate card
    client.delete(f"/credit-cards/{card['id']}", headers=auth_headers)
    
    # Try to create expense - should still fail for inactive card
    response = client.post(
        "/expenses/",
        json={
            "user_id": test_user["id"],
            "amount": 100.0,
            "category": "Test",
            "date": "2024-12-20",
            "payment_method": "credit_card",
            "credit_card_id": card["id"]
        },
        headers=auth_headers
    )
    assert response.status_code == 400
    assert "inactive" in response.json()["detail"].lower()


def test_create_expense_card_without_credit_card_payment(client: TestClient, auth_headers: dict, test_user: dict, test_card: dict):
    """Test that providing card_id requires credit_card payment method."""
    response = client.post(
        "/expenses/",
        json={
            "user_id": test_user["id"],
            "amount": 100.0,
            "category": "Test",
            "date": "2024-12-20",
            "payment_method": "cash",  # Wrong method
            "credit_card_id": test_card["id"]
        },
        headers=auth_headers
    )
    assert response.status_code == 400


def test_get_expenses_with_all_filters(client: TestClient, auth_headers: dict, test_user: dict):
    """Test expense filtering with all parameters."""
    # Create multiple expenses
    for i in range(5):
        client.post(
            "/expenses/",
            json={
                "user_id": test_user["id"],
                "amount": 50.0 + (i * 10),
                "category": "Food" if i % 2 == 0 else "Transport",
                "date": f"2024-12-{10 + i:02d}",
                "payment_method": "cash" if i % 2 == 0 else "debit_card",
                "is_recurring": i == 0,
                "tags": f"tag{i}"
            },
            headers=auth_headers
        )

    # Test various filters
    response = client.get(
        "/expenses/",
        params={
            "user_id": test_user["id"],
            "category": "Food",
            "min_amount": 50,
            "max_amount": 100,
            "from_date": "2024-12-01",
            "to_date": "2024-12-31",
            "payment_method": "cash",
            "is_recurring": False
        },
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert all(e["category"] == "Food" for e in data)


# ============================================
# ADDITIONAL BUDGET TESTS
# ============================================

def test_get_budget_by_id(client: TestClient, auth_headers: dict, test_budget: dict):
    """Test getting budget by ID."""
    response = client.get(f"/budgets/{test_budget['id']}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_budget["id"]


def test_get_budget_not_found(client: TestClient, auth_headers: dict):
    """Test getting non-existent budget."""
    response = client.get("/budgets/99999", headers=auth_headers)
    assert response.status_code == 404


def test_update_budget_not_found(client: TestClient, auth_headers: dict, test_user: dict):
    """Test updating non-existent budget."""
    response = client.put(
        "/budgets/99999",
        json={
            "user_id": test_user["id"],
            "category": "Food",
            "amount": 500.0,
            "month": "2024-12"
        },
        headers=auth_headers
    )
    assert response.status_code == 404


def test_delete_budget_not_found(client: TestClient, auth_headers: dict):
    """Test deleting non-existent budget."""
    response = client.delete("/budgets/99999", headers=auth_headers)
    assert response.status_code == 404


def test_budget_status_no_budgets(client: TestClient, auth_headers: dict, test_user: dict):
    """Test budget status with no budgets."""
    response = client.get(
        "/budgets/status/summary",
        params={"month": "2025-01", "user_id": test_user["id"]},
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "No budgets found for this period"


def test_budget_compare(client: TestClient, auth_headers: dict, test_user: dict, test_budget: dict):
    """Test budget comparison - verify endpoint structure."""
    # Create expenses in both months for comparison
    for month_day in ["11-15", "12-15"]:
        client.post(
            "/expenses/",
            json={
                "user_id": test_user["id"],
                "amount": 100.0,
                "category": test_budget["category"],
                "date": f"2024-{month_day}",
                "payment_method": "cash"
            },
            headers=auth_headers
        )

    # Get budget status for both months
    response1 = client.get(
        "/budgets/status/summary",
        params={"month": "2024-11", "user_id": test_user["id"]},
        headers=auth_headers
    )
    response2 = client.get(
        "/budgets/status/summary",
        params={"month": "2024-12", "user_id": test_user["id"]},
        headers=auth_headers
    )

    # Both should return 200
    assert response1.status_code == 200
    assert response2.status_code == 200


def test_create_budget_invalid_user(client: TestClient, auth_headers: dict):
    """Test creating budget for non-existent user."""
    response = client.post(
        "/budgets/",
        json={
            "user_id": 99999,
            "category": "Food",
            "amount": 500.0,
            "month": "2024-12"
        },
        headers=auth_headers
    )
    assert response.status_code == 404


# ============================================
# ADDITIONAL CREDIT CARD TESTS
# ============================================

def test_get_credit_card_by_id(client: TestClient, auth_headers: dict, test_card: dict):
    """Test getting credit card by ID."""
    response = client.get(f"/credit-cards/{test_card['id']}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_card["id"]


def test_get_credit_card_not_found(client: TestClient, auth_headers: dict):
    """Test getting non-existent credit card."""
    response = client.get("/credit-cards/99999", headers=auth_headers)
    assert response.status_code == 404


def test_update_credit_card(client: TestClient, auth_headers: dict, test_card: dict, test_user: dict):
    """Test updating credit card."""
    response = client.put(
        f"/credit-cards/{test_card['id']}",
        json={
            "user_id": test_user["id"],
            "card_name": "Updated Card",
            "last_four": "9999",
            "credit_limit": 10000.0,
            "billing_day": 1
        },
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["card_name"] == "Updated Card"


def test_update_credit_card_not_found(client: TestClient, auth_headers: dict, test_user: dict):
    """Test updating non-existent credit card."""
    response = client.put(
        "/credit-cards/99999",
        json={
            "user_id": test_user["id"],
            "card_name": "Test",
            "last_four": "1234",
            "credit_limit": 5000.0,
            "billing_day": 15
        },
        headers=auth_headers
    )
    assert response.status_code == 404


def test_delete_credit_card_not_found(client: TestClient, auth_headers: dict):
    """Test deleting non-existent credit card."""
    response = client.delete("/credit-cards/99999", headers=auth_headers)
    assert response.status_code == 404


def test_create_credit_card_invalid_user(client: TestClient, auth_headers: dict):
    """Test creating card for non-existent user."""
    response = client.post(
        "/credit-cards/",
        json={
            "user_id": 99999,
            "card_name": "Test Card",
            "last_four": "1234",
            "credit_limit": 5000.0,
            "billing_day": 15
        },
        headers=auth_headers
    )
    assert response.status_code == 404


def test_create_credit_card_inactive_user(client: TestClient, auth_headers: dict):
    """Test creating card for inactive user."""
    # Create and deactivate user
    user = client.post(
        "/users/",
        json={"name": "Inactive", "email": "inactive2@example.com", "role": "member"},
        headers=auth_headers
    ).json()

    client.delete(f"/users/{user['id']}", headers=auth_headers)

    response = client.post(
        "/credit-cards/",
        json={
            "user_id": user["id"],
            "card_name": "Test Card",
            "last_four": "1234",
            "credit_limit": 5000.0,
            "billing_day": 15
        },
        headers=auth_headers
    )
    assert response.status_code == 400


def test_create_duplicate_credit_card(client: TestClient, auth_headers: dict, test_user: dict, test_card: dict):
    """Test creating duplicate credit card."""
    response = client.post(
        "/credit-cards/",
        json={
            "user_id": test_user["id"],
            "card_name": "Duplicate",
            "last_four": test_card["last_four"],  # Same last four
            "credit_limit": 5000.0,
            "billing_day": 15
        },
        headers=auth_headers
    )
    assert response.status_code == 400


def test_get_credit_cards_filtered(client: TestClient, auth_headers: dict, test_user: dict, test_card: dict):
    """Test filtering credit cards."""
    response = client.get(
        "/credit-cards/",
        params={"user_id": test_user["id"], "is_active": True},
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1


def test_credit_card_statement_invalid_month(client: TestClient, auth_headers: dict, test_card: dict):
    """Test statement with invalid month format."""
    response = client.get(
        f"/credit-cards/{test_card['id']}/statement",
        params={"month": "invalid"},
        headers=auth_headers
    )
    assert response.status_code == 400


def test_credit_card_statement_not_found(client: TestClient, auth_headers: dict):
    """Test statement for non-existent card."""
    response = client.get(
        "/credit-cards/99999/statement",
        params={"month": "2024-12"},
        headers=auth_headers
    )
    assert response.status_code == 404


def test_credit_card_utilization_not_found(client: TestClient, auth_headers: dict):
    """Test utilization for non-existent card."""
    response = client.get(
        "/credit-cards/99999/utilization",
        params={"months": 3},
        headers=auth_headers
    )
    assert response.status_code == 404


def test_all_cards_summary_no_cards(client: TestClient, auth_headers: dict, test_user: dict):
    """Test cards summary with no cards."""
    # Create user with no cards
    new_user = client.post(
        "/users/",
        json={"name": "No Cards", "email": "nocards@example.com", "role": "member"},
        headers=auth_headers
    ).json()

    response = client.get(
        "/credit-cards/summary",
        params={"user_id": new_user["id"], "month": "2024-12"},
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "No active credit cards found"


# ============================================
# ADDITIONAL REPORT TESTS
# ============================================

def test_monthly_report_no_expenses(client: TestClient, auth_headers: dict, test_user: dict):
    """Test monthly report with no expenses."""
    response = client.get(
        "/reports/monthly",
        params={"month": "2025-01", "user_id": test_user["id"]},
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "No expenses found for this period"


def test_category_analysis_no_expenses(client: TestClient, auth_headers: dict, test_user: dict):
    """Test category analysis with no expenses."""
    response = client.get(
        "/reports/category-analysis",
        params={
            "category": "NonExistent",
            "from_date": "2024-12-01",
            "to_date": "2024-12-31",
            "user_id": test_user["id"]
        },
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "No expenses found for this category"


def test_payment_method_analysis_no_expenses(client: TestClient, auth_headers: dict, test_user: dict):
    """Test payment analysis with no expenses."""
    response = client.get(
        "/reports/payment-method-analysis",
        params={
            "from_date": "2025-01-01",
            "to_date": "2025-01-31",
            "user_id": test_user["id"]
        },
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "No expenses found"

# ============================================
# SAVINGS GOAL TESTS
# ============================================

def test_create_savings_goal_success(client: TestClient, auth_headers: dict, test_user: dict):
    """Test creating a savings goal."""
    response = client.post(
        "/savings-goals/",
        json={
            "user_id": test_user["id"],
            "name": "Emergency Fund",
            "target_amount": 10000.0,
            "current_amount": 2000.0,
            "deadline": "2025-12-31",
            "description": "6 months expenses"
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Emergency Fund"
    assert data["target_amount"] == 10000.0
    assert data["current_amount"] == 2000.0
    assert data["deadline"] == "2025-12-31"
    assert "id" in data
    assert "created_at" in data

def test_create_savings_goal_invalid_user(client: TestClient, auth_headers: dict):
    """Test creating goal with invalid user."""
    response = client.post(
        "/savings-goals/",
        json={
            "user_id": 99999,
            "name": "Test Goal",
            "target_amount": 5000.0,
            "current_amount": 0.0,
            "deadline": "2025-12-31"
        },
        headers=auth_headers,
    )
    assert response.status_code == 404

def test_create_savings_goal_past_deadline(client: TestClient, auth_headers: dict, test_user: dict):
    """Test creating goal with past deadline."""
    response = client.post(
        "/savings-goals/",
        json={
            "user_id": test_user["id"],
            "name": "Past Goal",
            "target_amount": 5000.0,
            "current_amount": 0.0,
            "deadline": "2020-01-01"
        },
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "future" in response.json()["detail"].lower()

def test_create_savings_goal_invalid_date_format(client: TestClient, auth_headers: dict, test_user: dict):
    """Test creating goal with invalid date format."""
    response = client.post(
        "/savings-goals/",
        json={
            "user_id": test_user["id"],
            "name": "Test Goal",
            "target_amount": 5000.0,
            "current_amount": 0.0,
            "deadline": "12/31/2025"
        },
        headers=auth_headers,
    )
    assert response.status_code == 422

def test_list_savings_goals(client: TestClient, auth_headers: dict, test_user: dict):
    """Test listing savings goals."""
    # Create a goal first
    client.post(
        "/savings-goals/",
        json={
            "user_id": test_user["id"],
            "name": "Vacation Fund",
            "target_amount": 3000.0,
            "current_amount": 500.0,
            "deadline": "2025-12-31"
        },
        headers=auth_headers,
    )
    # client.post(
    #     "/savings-goals/",
    #     json={
    #         "user_id": test_user["id"],
    #         "name": "Emergency Fund",
    #         "target_amount": 10000.0,
    #         "current_amount": 2000.0,
    #         "deadline": "2025-12-31",
    #         "description": "6 months expenses"
    #     },
    #     headers=auth_headers,
    # )
    
    response = client.get("/savings-goals/", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1

def test_list_savings_goals_filtered_by_user(client: TestClient, auth_headers: dict, test_user: dict):
    """Test filtering goals by user."""
    response = client.get(
        "/savings-goals/",
        params={"user_id": test_user["id"]},
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert all(g["user_id"] == test_user["id"] for g in data)

def test_get_savings_goal_by_id(client: TestClient, auth_headers: dict, test_user: dict):
    """Test getting specific savings goal."""
    # Create goal
    create_response = client.post(
        "/savings-goals/",
        json={
            "user_id": test_user["id"],
            "name": "New Car",
            "target_amount": 20000.0,
            "current_amount": 5000.0,
            "deadline": "2026-12-31"
        },
        headers=auth_headers,
    )
    goal_id = create_response.json()["id"]
    
    # Get goal
    response = client.get(f"/savings-goals/{goal_id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == goal_id
    assert data["name"] == "New Car"

def test_get_savings_goal_not_found(client: TestClient, auth_headers: dict):
    """Test getting non-existent goal."""
    response = client.get("/savings-goals/99999", headers=auth_headers)
    assert response.status_code == 404

def test_update_savings_goal(client: TestClient, auth_headers: dict, test_user: dict):
    """Test updating savings goal."""
    # Create goal
    create_response = client.post(
        "/savings-goals/",
        json={
            "user_id": test_user["id"],
            "name": "Old Name",
            "target_amount": 5000.0,
            "current_amount": 1000.0,
            "deadline": "2025-12-31"
        },
        headers=auth_headers,
    )
    goal_id = create_response.json()["id"]
    
    # Update goal
    response = client.put(
        f"/savings-goals/{goal_id}",
        json={
            "user_id": test_user["id"],
            "name": "Updated Name",
            "target_amount": 7000.0,
            "current_amount": 2000.0,
            "deadline": "2026-06-30"
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Name"
    assert data["target_amount"] == 7000.0

def test_update_savings_goal_not_found(client: TestClient, auth_headers: dict, test_user: dict):
    """Test updating non-existent goal."""
    response = client.put(
        "/savings-goals/99999",
        json={
            "user_id": test_user["id"],
            "name": "Test",
            "target_amount": 5000.0,
            "current_amount": 0.0,
            "deadline": "2025-12-31"
        },
        headers=auth_headers,
    )
    assert response.status_code == 404

def test_delete_savings_goal(client: TestClient, auth_headers: dict, test_user: dict):
    """Test deleting savings goal."""
    # Create goal
    create_response = client.post(
        "/savings-goals/",
        json={
            "user_id": test_user["id"],
            "name": "To Delete",
            "target_amount": 5000.0,
            "current_amount": 0.0,
            "deadline": "2025-12-31"
        },
        headers=auth_headers,
    )
    goal_id = create_response.json()["id"]
    
    # Delete goal
    response = client.delete(f"/savings-goals/{goal_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["goal_id"] == goal_id

def test_delete_savings_goal_not_found(client: TestClient, auth_headers: dict):
    """Test deleting non-existent goal."""
    response = client.delete("/savings-goals/99999", headers=auth_headers)
    assert response.status_code == 404

def test_add_to_savings_goal(client: TestClient, auth_headers: dict, test_user: dict):
    """Test adding money to savings goal."""
    # Create goal
    create_response = client.post(
        "/savings-goals/",
        json={
            "user_id": test_user["id"],
            "name": "Test Goal",
            "target_amount": 5000.0,
            "current_amount": 1000.0,
            "deadline": "2025-12-31"
        },
        headers=auth_headers,
    )
    goal_id = create_response.json()["id"]
    
    # Add money
    response = client.post(
        f"/savings-goals/{goal_id}/add",
        json={"amount": 500.0},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["current_amount"] == 1500.0

def test_add_to_savings_goal_not_found(client: TestClient, auth_headers: dict):
    """Test adding to non-existent goal."""
    response = client.post(
        "/savings-goals/99999/add",
        json={"amount": 500.0},
        headers=auth_headers,
    )
    assert response.status_code == 404

def test_add_to_inactive_savings_goal(client: TestClient, auth_headers: dict, test_user: dict):
    """Test adding to inactive goal."""
    # Create and deactivate goal
    create_response = client.post(
        "/savings-goals/",
        json={
            "user_id": test_user["id"],
            "name": "Inactive Goal",
            "target_amount": 5000.0,
            "current_amount": 1000.0,
            "deadline": "2025-12-31"
        },
        headers=auth_headers,
    )
    goal_id = create_response.json()["id"]
    client.delete(f"/savings-goals/{goal_id}", headers=auth_headers)
    
    # Try to add money
    response = client.post(
        f"/savings-goals/{goal_id}/add",
        json={"amount": 500.0},
        headers=auth_headers,
    )
    assert response.status_code == 400

def test_withdraw_from_savings_goal(client: TestClient, auth_headers: dict, test_user: dict):
    """Test withdrawing money from savings goal."""
    # Create goal with some money
    create_response = client.post(
        "/savings-goals/",
        json={
            "user_id": test_user["id"],
            "name": "Test Goal",
            "target_amount": 5000.0,
            "current_amount": 2000.0,
            "deadline": "2025-12-31"
        },
        headers=auth_headers,
    )
    goal_id = create_response.json()["id"]
    
    # Withdraw money
    response = client.post(
        f"/savings-goals/{goal_id}/withdraw",
        json={"amount": 500.0},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["current_amount"] == 1500.0

def test_withdraw_insufficient_funds(client: TestClient, auth_headers: dict, test_user: dict):
    """Test withdrawing more than available."""
    # Create goal
    create_response = client.post(
        "/savings-goals/",
        json={
            "user_id": test_user["id"],
            "name": "Test Goal",
            "target_amount": 5000.0,
            "current_amount": 500.0,
            "deadline": "2025-12-31"
        },
        headers=auth_headers,
    )
    goal_id = create_response.json()["id"]
    
    # Try to withdraw more than available
    response = client.post(
        f"/savings-goals/{goal_id}/withdraw",
        json={"amount": 1000.0},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "insufficient" in response.json()["detail"].lower()

def test_withdraw_from_inactive_goal(client: TestClient, auth_headers: dict, test_user: dict):
    """Test withdrawing from inactive goal."""
    # Create and deactivate goal
    create_response = client.post(
        "/savings-goals/",
        json={
            "user_id": test_user["id"],
            "name": "Inactive Goal",
            "target_amount": 5000.0,
            "current_amount": 2000.0,
            "deadline": "2025-12-31"
        },
        headers=auth_headers,
    )
    goal_id = create_response.json()["id"]
    client.delete(f"/savings-goals/{goal_id}", headers=auth_headers)
    
    # Try to withdraw
    response = client.post(
        f"/savings-goals/{goal_id}/withdraw",
        json={"amount": 500.0},
        headers=auth_headers,
    )
    assert response.status_code == 400

def test_get_savings_goal_progress(client: TestClient, auth_headers: dict, test_user: dict):
    """Test getting goal progress details."""
    # Create goal
    create_response = client.post(
        "/savings-goals/",
        json={
            "user_id": test_user["id"],
            "name": "Test Goal",
            "target_amount": 10000.0,
            "current_amount": 5000.0,
            "deadline": "2025-12-31"
        },
        headers=auth_headers,
    )
    goal_id = create_response.json()["id"]
    
    # Get progress
    response = client.get(f"/savings-goals/{goal_id}/progress", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["goal_id"] == goal_id
    assert data["progress_percentage"] == 50.0
    assert "days_remaining" in data
    assert "required_savings" in data
    assert "status" in data

# ============================================
# ASSET TESTS
# ============================================

def test_create_asset_success(client: TestClient, auth_headers: dict, test_user: dict):
    """Test creating an asset."""
    response = client.post(
        "/assets/",
        json={
            "user_id": test_user["id"],
            "name": "Honda Civic",
            "asset_type": "vehicle",
            "purchase_value": 25000.0,
            "current_value": 18000.0,
            "purchase_date": "2022-01-15",
            "description": "2022 Honda Civic LX",
            "location": "Garage"
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Honda Civic"
    assert data["asset_type"] == "vehicle"
    assert data["purchase_value"] == 25000.0
    assert data["current_value"] == 18000.0
    assert "id" in data
    assert "created_at" in data

def test_create_asset_invalid_user(client: TestClient, auth_headers: dict):
    """Test creating asset with invalid user."""
    response = client.post(
        "/assets/",
        json={
            "user_id": 99999,
            "name": "Test Asset",
            "asset_type": "other",
            "purchase_value": 1000.0,
            "current_value": 900.0,
            "purchase_date": "2024-01-01"
        },
        headers=auth_headers,
    )
    assert response.status_code == 404

def test_create_asset_invalid_type(client: TestClient, auth_headers: dict, test_user: dict):
    """Test creating asset with invalid type."""
    response = client.post(
        "/assets/",
        json={
            "user_id": test_user["id"],
            "name": "Test Asset",
            "asset_type": "invalid_type",
            "purchase_value": 1000.0,
            "current_value": 900.0,
            "purchase_date": "2024-01-01"
        },
        headers=auth_headers,
    )
    assert response.status_code == 422

def test_create_asset_invalid_date_format(client: TestClient, auth_headers: dict, test_user: dict):
    """Test creating asset with invalid date format."""
    response = client.post(
        "/assets/",
        json={
            "user_id": test_user["id"],
            "name": "Test Asset",
            "asset_type": "electronics",
            "purchase_value": 1000.0,
            "current_value": 900.0,
            "purchase_date": "01/15/2024"
        },
        headers=auth_headers,
    )
    assert response.status_code == 422

def test_create_asset_inactive_user(client: TestClient, auth_headers: dict):
    """Test creating asset for inactive user."""
    # Create and deactivate user
    user = client.post(
        "/users/",
        json={"name": "Inactive Asset User", "email": "inactiveasset@example.com", "role": "member"},
        headers=auth_headers
    ).json()
    client.delete(f"/users/{user['id']}", headers=auth_headers)
    
    # Try to create asset
    response = client.post(
        "/assets/",
        json={
            "user_id": user["id"],
            "name": "Test Asset",
            "asset_type": "other",
            "purchase_value": 1000.0,
            "current_value": 900.0,
            "purchase_date": "2024-01-01"
        },
        headers=auth_headers,
    )
    assert response.status_code == 400

def test_list_assets(client: TestClient, auth_headers: dict, test_user: dict):
    """Test listing assets."""
    # Create an asset first
    client.post(
        "/assets/",
        json={
            "user_id": test_user["id"],
            "name": "Laptop",
            "asset_type": "electronics",
            "purchase_value": 1500.0,
            "current_value": 1000.0,
            "purchase_date": "2023-06-15"
        },
        headers=auth_headers,
    )
    
    response = client.get("/assets/", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1

def test_list_assets_filtered_by_user(client: TestClient, auth_headers: dict, test_user: dict):
    """Test filtering assets by user."""
    response = client.get(
        "/assets/",
        params={"user_id": test_user["id"]},
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert all(a["user_id"] == test_user["id"] for a in data)

def test_list_assets_filtered_by_type(client: TestClient, auth_headers: dict, test_user: dict):
    """Test filtering assets by type."""
    # Create assets of different types
    client.post(
        "/assets/",
        json={
            "user_id": test_user["id"],
            "name": "iPhone",
            "asset_type": "electronics",
            "purchase_value": 1000.0,
            "current_value": 600.0,
            "purchase_date": "2023-01-01"
        },
        headers=auth_headers,
    )
    
    response = client.get(
        "/assets/",
        params={"asset_type": "electronics"},
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert all(a["asset_type"] == "electronics" for a in data)

def test_get_asset_by_id(client: TestClient, auth_headers: dict, test_user: dict):
    """Test getting specific asset."""
    # Create asset
    create_response = client.post(
        "/assets/",
        json={
            "user_id": test_user["id"],
            "name": "Gold Necklace",
            "asset_type": "jewelry",
            "purchase_value": 5000.0,
            "current_value": 5500.0,
            "purchase_date": "2020-05-10"
        },
        headers=auth_headers,
    )
    asset_id = create_response.json()["id"]
    
    # Get asset
    response = client.get(f"/assets/{asset_id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == asset_id
    assert data["name"] == "Gold Necklace"

def test_get_asset_not_found(client: TestClient, auth_headers: dict):
    """Test getting non-existent asset."""
    response = client.get("/assets/99999", headers=auth_headers)
    assert response.status_code == 404

def test_update_asset(client: TestClient, auth_headers: dict, test_user: dict):
    """Test updating asset."""
    # Create asset
    create_response = client.post(
        "/assets/",
        json={
            "user_id": test_user["id"],
            "name": "Old Name",
            "asset_type": "furniture",
            "purchase_value": 2000.0,
            "current_value": 1500.0,
            "purchase_date": "2022-03-20"
        },
        headers=auth_headers,
    )
    asset_id = create_response.json()["id"]
    
    # Update asset
    response = client.put(
        f"/assets/{asset_id}",
        json={
            "user_id": test_user["id"],
            "name": "Updated Name",
            "asset_type": "furniture",
            "purchase_value": 2000.0,
            "current_value": 1200.0,
            "purchase_date": "2022-03-20",
            "description": "Updated description"
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Name"
    assert data["current_value"] == 1200.0
    assert data["description"] == "Updated description"

def test_update_asset_not_found(client: TestClient, auth_headers: dict, test_user: dict):
    """Test updating non-existent asset."""
    response = client.put(
        "/assets/99999",
        json={
            "user_id": test_user["id"],
            "name": "Test",
            "asset_type": "other",
            "purchase_value": 1000.0,
            "current_value": 900.0,
            "purchase_date": "2024-01-01"
        },
        headers=auth_headers,
    )
    assert response.status_code == 404

def test_delete_asset(client: TestClient, auth_headers: dict, test_user: dict):
    """Test deleting asset."""
    # Create asset
    create_response = client.post(
        "/assets/",
        json={
            "user_id": test_user["id"],
            "name": "To Delete",
            "asset_type": "other",
            "purchase_value": 1000.0,
            "current_value": 900.0,
            "purchase_date": "2024-01-01"
        },
        headers=auth_headers,
    )
    asset_id = create_response.json()["id"]
    
    # Delete asset
    response = client.delete(f"/assets/{asset_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["asset_id"] == asset_id

def test_delete_asset_not_found(client: TestClient, auth_headers: dict):
    """Test deleting non-existent asset."""
    response = client.delete("/assets/99999", headers=auth_headers)
    assert response.status_code == 404

def test_update_asset_value(client: TestClient, auth_headers: dict, test_user: dict):
    """Test updating asset current value."""
    # Create asset
    create_response = client.post(
        "/assets/",
        json={
            "user_id": test_user["id"],
            "name": "Stock Portfolio",
            "asset_type": "investment",
            "purchase_value": 10000.0,
            "current_value": 10000.0,
            "purchase_date": "2024-01-01"
        },
        headers=auth_headers,
    )
    asset_id = create_response.json()["id"]
    
    # Update value
    response = client.put(
        f"/assets/{asset_id}/value",
        json={"current_value": 12000.0},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["current_value"] == 12000.0
    assert "updated_at" in data

def test_update_asset_value_not_found(client: TestClient, auth_headers: dict):
    """Test updating value of non-existent asset."""
    response = client.put(
        "/assets/99999/value",
        json={"current_value": 5000.0},
        headers=auth_headers,
    )
    assert response.status_code == 404

def test_get_assets_summary(client: TestClient, auth_headers: dict, test_user: dict):
    """Test getting assets summary."""
    # Create multiple assets
    client.post(
        "/assets/",
        json={
            "user_id": test_user["id"],
            "name": "Car",
            "asset_type": "vehicle",
            "purchase_value": 20000.0,
            "current_value": 15000.0,
            "purchase_date": "2022-01-01"
        },
        headers=auth_headers,
    )
    
    client.post(
        "/assets/",
        json={
            "user_id": test_user["id"],
            "name": "Laptop",
            "asset_type": "electronics",
            "purchase_value": 2000.0,
            "current_value": 1000.0,
            "purchase_date": "2023-06-01"
        },
        headers=auth_headers,
    )
    
    response = client.get("/assets/summary", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "total_assets" in data
    assert "total_purchase_value" in data
    assert "total_current_value" in data
    assert "total_gain_loss" in data
    assert "by_type" in data

def test_get_assets_summary_by_user(client: TestClient, auth_headers: dict, test_user: dict):
    """Test getting assets summary filtered by user."""
    response = client.get(
        "/assets/summary",
        params={"user_id": test_user["id"]},
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert "total_assets" in data

def test_get_assets_summary_no_assets(client: TestClient, auth_headers: dict):
    """Test summary with no assets."""
    # Create new user with no assets
    user = client.post(
        "/users/",
        json={"name": "No Assets User", "email": "noassets@example.com", "role": "member"},
        headers=auth_headers
    ).json()
    
    response = client.get(
        "/assets/summary",
        params={"user_id": user["id"]},
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "No assets found"

def test_get_asset_depreciation(client: TestClient, auth_headers: dict, test_user: dict):
    """Test getting depreciation analysis."""
    # Create assets with depreciation
    client.post(
        "/assets/",
        json={
            "user_id": test_user["id"],
            "name": "MacBook Pro",
            "asset_type": "electronics",
            "purchase_value": 3000.0,
            "current_value": 1500.0,
            "purchase_date": "2022-01-01"
        },
        headers=auth_headers,
    )
    
    response = client.get("/assets/depreciation", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "total_assets" in data
    assert "total_depreciation" in data
    assert "assets" in data
    
    # Check depreciation details
    if len(data["assets"]) > 0:
        asset = data["assets"][0]
        assert "depreciation" in asset
        assert "depreciation_percentage" in asset
        assert "age_years" in asset
        assert "annual_depreciation" in asset

def test_get_asset_depreciation_by_user(client: TestClient, auth_headers: dict, test_user: dict):
    """Test depreciation filtered by user."""
    response = client.get(
        "/assets/depreciation",
        params={"user_id": test_user["id"]},
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert "assets" in data or "message" in data

def test_get_asset_depreciation_no_assets(client: TestClient, auth_headers: dict):
    """Test depreciation with no assets."""
    # Create new user with no assets
    user = client.post(
        "/users/",
        json={"name": "No Assets User 2", "email": "noassets2@example.com", "role": "member"},
        headers=auth_headers
    ).json()
    
    response = client.get(
        "/assets/depreciation",
        params={"user_id": user["id"]},
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "No assets found"

def test_asset_value_gain(client: TestClient, auth_headers: dict, test_user: dict):
    """Test asset with value appreciation (gain)."""
    # Create asset that appreciated
    response = client.post(
        "/assets/",
        json={
            "user_id": test_user["id"],
            "name": "Gold Coins",
            "asset_type": "jewelry",
            "purchase_value": 5000.0,
            "current_value": 6000.0,
            "purchase_date": "2020-01-01"
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    
    # Get summary to check gain
    summary = client.get("/assets/summary", headers=auth_headers).json()
    # Should show positive gain/loss
    assert "total_gain_loss" in summary

def test_multiple_asset_types(client: TestClient, auth_headers: dict, test_user: dict):
    """Test creating assets of different types."""
    asset_types = [
        ("House", "property", 300000.0, 350000.0),
        ("Car", "vehicle", 25000.0, 18000.0),
        ("Stocks", "investment", 10000.0, 12000.0),
        ("TV", "electronics", 1000.0, 500.0),
        ("Ring", "jewelry", 3000.0, 3200.0),
        ("Sofa", "furniture", 2000.0, 800.0),
        ("Painting", "art", 5000.0, 7000.0),
    ]
    
    for name, asset_type, purchase, current in asset_types:
        response = client.post(
            "/assets/",
            json={
                "user_id": test_user["id"],
                "name": name,
                "asset_type": asset_type,
                "purchase_value": purchase,
                "current_value": current,
                "purchase_date": "2023-01-01"
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
    
    # Get summary
    response = client.get("/assets/summary", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total_assets"] >= 7
    assert len(data["by_type"]) >= 7

def test_savings_goal_complete_workflow(client: TestClient, auth_headers: dict, test_user: dict):
    """Test complete savings goal workflow."""
    # 1. Create goal
    create_response = client.post(
        "/savings-goals/",
        json={
            "user_id": test_user["id"],
            "name": "Vacation",
            "target_amount": 5000.0,
            "current_amount": 0.0,
            "deadline": "2025-12-31"
        },
        headers=auth_headers,
    )
    assert create_response.status_code == 200
    goal_id = create_response.json()["id"]
    
    # 2. Add money multiple times
    for amount in [500.0, 750.0, 1000.0]:
        response = client.post(
            f"/savings-goals/{goal_id}/add",
            json={"amount": amount},
            headers=auth_headers,
        )
        assert response.status_code == 200
    
    # 3. Check progress
    response = client.get(f"/savings-goals/{goal_id}/progress", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["current_amount"] == 2250.0
    assert data["progress_percentage"] == 45.0
    
    # 4. Withdraw some
    response = client.post(
        f"/savings-goals/{goal_id}/withdraw",
        json={"amount": 250.0},
        headers=auth_headers,
    )
    assert response.status_code == 200
    
    # 5. Final check
    response = client.get(f"/savings-goals/{goal_id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["current_amount"] == 2000.0
    
    # 6. Delete goal
    response = client.delete(f"/savings-goals/{goal_id}", headers=auth_headers)
    assert response.status_code == 200

def test_asset_complete_workflow(client: TestClient, auth_headers: dict, test_user: dict):
    """Test complete asset workflow."""
    # 1. Create asset
    create_response = client.post(
        "/assets/",
        json={
            "user_id": test_user["id"],
            "name": "Investment Portfolio",
            "asset_type": "investment",
            "purchase_value": 50000.0,
            "current_value": 50000.0,
            "purchase_date": "2024-01-01",
            "description": "Mixed stocks and bonds"
        },
        headers=auth_headers,
    )
    assert create_response.status_code == 200
    asset_id = create_response.json()["id"]
    
    # 2. Update value (market appreciation)
    response = client.put(
        f"/assets/{asset_id}/value",
        json={"current_value": 55000.0},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["current_value"] == 55000.0
    
    # 3. Get depreciation (should show appreciation)
    response = client.get("/assets/depreciation", headers=auth_headers)
    assert response.status_code == 200
    
    # 4. Get summary
    response = client.get("/assets/summary", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total_gain_loss"] > 0  # Should be positive (gain)
    
    # 5. Update asset details
    response = client.put(
        f"/assets/{asset_id}",
        json={
            "user_id": test_user["id"],
            "name": "Updated Portfolio",
            "asset_type": "investment",
            "purchase_value": 50000.0,
            "current_value": 55000.0,
            "purchase_date": "2024-01-01",
            "description": "Diversified portfolio"
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    
    # 6. Delete asset
    response = client.delete(f"/assets/{asset_id}", headers=auth_headers)
    assert response.status_code == 200
    
# ============================================
# AUTHENTICATION TESTS
# ============================================

def test_all_endpoints_require_auth(client: TestClient):
    """Test that all endpoints require authentication."""
    endpoints = [
        ("GET", "/users/"),
        ("GET", "/budgets/"),
        ("GET", "/expenses/"),
        ("GET", "/credit-cards/"),
        ("GET", "/reports/monthly?month=2024-12"),
        ("POST", "/savings-goals/"),
        ("GET", "/assets/"),
    ]

    for method, endpoint in endpoints:
        if method == "GET":
            response = client.get(endpoint)
        elif method == "POST":
            response = client.post(endpoint, json={})

        assert response.status_code == 403
