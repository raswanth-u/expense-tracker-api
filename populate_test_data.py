#!/usr/bin/env python3
"""
Populate database with 20 entries per table for db_manager testing.
"""

import requests
import random
from datetime import datetime, timedelta

API_URL = "https://localhost:8443/api"
API_KEY = "supersecretapikey"

# Disable SSL warnings
requests.packages.urllib3.disable_warnings()


def api_post(endpoint: str, data: dict) -> dict:
    """Make a POST request to the API."""
    headers = {"X-API-Key": API_KEY}
    url = f"{API_URL}/{endpoint}"
    resp = requests.post(url, json=data, headers=headers, verify=False)
    if resp.status_code in (200, 201):
        return resp.json()
    else:
        print(f"Error: {resp.status_code} - {resp.text}")
        return {}


def create_users(count=20):
    """Create test users."""
    print(f"Creating {count} users...")
    users = []
    for i in range(count):
        result = api_post("users/", {
            "name": f"Test User {i+1}",
            "email": f"testuser{i+1}@example.com",
            "role": random.choice(["admin", "member"])
        })
        if result.get("id"):
            users.append(result)
            print(f"  Created user: {result['name']} (ID: {result['id']})")
    return users


def create_accounts(users, count_per_user=1):
    """Create savings accounts for users."""
    print(f"Creating accounts for {len(users)} users...")
    accounts = []
    for i, user in enumerate(users):
        result = api_post("savings-accounts/", {
            "user_id": user["id"],
            "account_name": f"Account {i+1}",
            "bank_name": random.choice(["Chase", "Bank of America", "Wells Fargo", "Citi"]),
            "account_number_last_four": f"{random.randint(1000, 9999)}",
            "account_type": random.choice(["checking", "savings"]),
            "current_balance": round(random.uniform(1000, 10000), 2),
            "minimum_balance": 100.00,
            "interest_rate": round(random.uniform(0.5, 3.0), 2)
        })
        if result.get("id"):
            accounts.append(result)
            print(f"  Created account: {result['account_name']} (ID: {result['id']})")
    return accounts


def create_credit_cards(users, count_per_user=1):
    """Create credit cards for users."""
    print(f"Creating credit cards for {len(users)} users...")
    cards = []
    for i, user in enumerate(users):
        result = api_post("credit-cards/", {
            "user_id": user["id"],
            "card_name": f"Credit Card {i+1}",
            "last_four": f"{random.randint(1000, 9999)}",
            "credit_limit": round(random.uniform(3000, 15000), 2),
            "billing_day": random.randint(1, 28),
            "interest_rate": round(random.uniform(15, 25), 2)
        })
        if result.get("id"):
            cards.append(result)
            print(f"  Created card: {result['card_name']} (ID: {result['id']})")
    return cards


def create_debit_cards(users, accounts):
    """Create debit cards linked to accounts."""
    print(f"Creating debit cards...")
    debit_cards = []
    for i, (user, account) in enumerate(zip(users, accounts)):
        result = api_post("debit-cards/", {
            "user_id": user["id"],
            "savings_account_id": account["id"],
            "card_name": f"Debit Card {i+1}",
            "last_four": f"{random.randint(1000, 9999)}",
            "daily_limit": round(random.uniform(500, 2000), 2)
        })
        if result.get("id"):
            debit_cards.append(result)
            print(f"  Created debit card: {result['card_name']} (ID: {result['id']})")
    return debit_cards


def create_budgets(users, count=20):
    """Create budgets."""
    print(f"Creating {count} budgets...")
    categories = ["Food", "Transport", "Entertainment", "Utilities", "Shopping", 
                  "Healthcare", "Education", "Housing", "Insurance", "Personal"]
    budgets = []
    for i in range(count):
        user = random.choice(users)
        result = api_post("budgets/", {
            "user_id": user["id"],
            "category": random.choice(categories),
            "amount": round(random.uniform(100, 1000), 2),
            "month": f"2026-{random.randint(1, 12):02d}",
            "period": "monthly"
        })
        if result.get("id"):
            budgets.append(result)
            print(f"  Created budget: {result['category']} ${result['amount']} (ID: {result['id']})")
    return budgets


def create_expenses(users, credit_cards, count=20):
    """Create expenses."""
    print(f"Creating {count} expenses...")
    categories = ["Food", "Transport", "Entertainment", "Utilities", "Shopping",
                  "Healthcare", "Education", "Housing", "Insurance", "Personal"]
    expenses = []
    for i in range(count):
        user = random.choice(users)
        expense_date = datetime.now() - timedelta(days=random.randint(1, 90))
        
        data = {
            "user_id": user["id"],
            "amount": round(random.uniform(10, 500), 2),
            "category": random.choice(categories),
            "date": expense_date.strftime("%Y-%m-%d"),
            "description": f"Test expense {i+1}",
            "payment_method": random.choice(["cash", "credit_card"]),
        }
        
        if data["payment_method"] == "credit_card" and credit_cards:
            data["credit_card_id"] = random.choice(credit_cards)["id"]
        
        result = api_post("expenses/", data)
        if result.get("id"):
            expenses.append(result)
            print(f"  Created expense: ${result['amount']} - {result['category']} (ID: {result['id']})")
    return expenses


def create_goals(users, count=20):
    """Create savings goals."""
    print(f"Creating {count} savings goals...")
    goal_names = ["Emergency Fund", "Vacation", "New Car", "House Down Payment",
                  "Education", "Wedding", "Retirement", "Investment", "Gadgets", "Travel"]
    goals = []
    for i in range(count):
        user = random.choice(users)
        deadline = datetime.now() + timedelta(days=random.randint(90, 365*3))
        result = api_post("savings-goals/", {
            "user_id": user["id"],
            "name": f"{random.choice(goal_names)} {i+1}",
            "target_amount": round(random.uniform(1000, 50000), 2),
            "current_amount": round(random.uniform(0, 5000), 2),
            "deadline": deadline.strftime("%Y-%m-%d"),
            "description": f"Goal description {i+1}"
        })
        if result.get("id"):
            goals.append(result)
            print(f"  Created goal: {result['name']} (ID: {result['id']})")
    return goals


def create_recurring(users, count=20):
    """Create recurring expense templates."""
    print(f"Creating {count} recurring templates...")
    categories = ["Utilities", "Subscriptions", "Insurance", "Rent", "Gym"]
    frequencies = ["daily", "weekly", "monthly", "yearly"]
    recurring = []
    for i in range(count):
        user = random.choice(users)
        start_date = datetime.now() - timedelta(days=random.randint(30, 180))
        
        data = {
            "user_id": user["id"],
            "amount": round(random.uniform(10, 500), 2),
            "category": random.choice(categories),
            "frequency": random.choice(frequencies),
            "start_date": start_date.strftime("%Y-%m-%d"),
            "description": f"Recurring {i+1}",
            "interval": 1
        }
        
        if data["frequency"] == "weekly":
            data["day_of_week"] = random.randint(0, 6)
        elif data["frequency"] in ["monthly", "yearly"]:
            data["day_of_month"] = random.randint(1, 28)
        
        result = api_post("recurring-expenses/", data)
        if result.get("id"):
            recurring.append(result)
            print(f"  Created recurring: {result['category']} ${result['amount']} (ID: {result['id']})")
    return recurring


def create_assets(users, count=20):
    """Create assets."""
    print(f"Creating {count} assets...")
    asset_types = ["vehicle", "property", "electronics", "furniture", "investment", "jewelry"]
    assets = []
    for i in range(count):
        user = random.choice(users)
        purchase_date = datetime.now() - timedelta(days=random.randint(30, 365*3))
        purchase_value = round(random.uniform(100, 50000), 2)
        depreciation = random.uniform(0, 0.3)
        
        result = api_post("assets/", {
            "user_id": user["id"],
            "name": f"Asset {i+1}",
            "asset_type": random.choice(asset_types),
            "purchase_value": purchase_value,
            "current_value": round(purchase_value * (1 - depreciation), 2),
            "purchase_date": purchase_date.strftime("%Y-%m-%d"),
            "description": f"Asset description {i+1}",
            "location": random.choice(["Home", "Office", "Storage", "Bank"])
        })
        if result.get("id"):
            assets.append(result)
            print(f"  Created asset: {result['name']} (ID: {result['id']})")
    return assets


def main():
    """Main function to populate database."""
    print("=" * 60)
    print("  POPULATING DATABASE WITH TEST DATA")
    print("=" * 60)
    print()
    
    # Create users first
    users = create_users(20)
    if not users:
        print("Failed to create users!")
        return
    
    print()
    
    # Create related entities
    accounts = create_accounts(users)
    print()
    
    credit_cards = create_credit_cards(users)
    print()
    
    debit_cards = create_debit_cards(users, accounts)
    print()
    
    budgets = create_budgets(users, 20)
    print()
    
    expenses = create_expenses(users, credit_cards, 20)
    print()
    
    goals = create_goals(users, 20)
    print()
    
    recurring = create_recurring(users, 20)
    print()
    
    assets = create_assets(users, 20)
    print()
    
    print("=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    print(f"  Users created: {len(users)}")
    print(f"  Accounts created: {len(accounts)}")
    print(f"  Credit cards created: {len(credit_cards)}")
    print(f"  Debit cards created: {len(debit_cards)}")
    print(f"  Budgets created: {len(budgets)}")
    print(f"  Expenses created: {len(expenses)}")
    print(f"  Goals created: {len(goals)}")
    print(f"  Recurring created: {len(recurring)}")
    print(f"  Assets created: {len(assets)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
