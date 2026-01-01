#!/usr/bin/env python3
"""Seed database with test data - 20 entries per table."""

import random
from datetime import datetime, timedelta

import requests

BASE_URL = "https://localhost/api"
HEADERS = {"X-API-Key": "supersecretapikey"}
VERIFY_SSL = False

# Suppress SSL warnings
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def api_post(endpoint, data, trailing_slash=True):
    """Make POST request to API."""
    url = f"{BASE_URL}/{endpoint}{'/' if trailing_slash else ''}"
    resp = requests.post(url, json=data, headers=HEADERS, verify=VERIFY_SSL)
    if resp.status_code not in [200, 201]:
        print(f"Error {endpoint}: {resp.status_code} - {resp.text[:100]}")
        return None
    return resp.json()

def random_date(days_back=365):
    """Generate random date within last N days."""
    delta = timedelta(days=random.randint(0, days_back))
    return (datetime.now() - delta).strftime("%Y-%m-%d")

def random_month():
    """Generate random month in YYYY-MM format."""
    months_back = random.randint(0, 6)
    date = datetime.now() - timedelta(days=months_back * 30)
    return date.strftime("%Y-%m")

def current_datetime():
    """Get current datetime string."""
    return datetime.now().isoformat()

# ============================================================================
# SEED DATA
# ============================================================================

print("=" * 60)
print("Seeding Database with Test Data")
print("=" * 60)

# 1. CREATE 20 USERS
print("\n[1/9] Creating 20 Users...")
users = []
user_names = [
    ("John Doe", "john@family.com"),
    ("Jane Doe", "jane@family.com"),
    ("Mike Smith", "mike@family.com"),
    ("Sarah Johnson", "sarah@family.com"),
    ("David Brown", "david@family.com"),
    ("Emily Wilson", "emily@family.com"),
    ("Chris Taylor", "chris@family.com"),
    ("Lisa Anderson", "lisa@family.com"),
    ("Tom Martinez", "tom@family.com"),
    ("Amy Garcia", "amy@family.com"),
    ("Robert Lee", "robert@family.com"),
    ("Jennifer White", "jennifer@family.com"),
    ("William Harris", "william@family.com"),
    ("Elizabeth Clark", "elizabeth@family.com"),
    ("James Lewis", "james@family.com"),
    ("Mary Robinson", "mary@family.com"),
    ("Daniel Walker", "daniel@family.com"),
    ("Patricia Hall", "patricia@family.com"),
    ("Matthew Young", "matthew@family.com"),
    ("Linda King", "linda@family.com"),
]

for name, email in user_names:
    user = api_post("users", {
        "name": name,
        "email": email,
        "role": "admin" if len(users) == 0 else "member"
    })
    if user:
        users.append(user)
        print(f"  ✓ Created user: {name}")

print(f"  Total users created: {len(users)}")

# 2. CREATE 20 CREDIT CARDS
print("\n[2/9] Creating 20 Credit Cards...")
card_names = ["Chase Sapphire", "Amex Gold", "Capital One", "Discover IT", "Citi Double",
              "Bank of America", "Wells Fargo", "US Bank", "Barclays", "HSBC"]
cards = []

for i in range(20):
    user = random.choice(users)
    card = api_post("credit-cards", {
        "user_id": user["id"],
        "card_name": f"{random.choice(card_names)} {i+1}",
        "last_four": f"{random.randint(1000, 9999)}",
        "credit_limit": random.randint(5000, 50000),
        "billing_day": random.randint(1, 28),
        "tags": random.choice(["personal", "business", "travel", "rewards"])
    })
    if card:
        cards.append(card)
        print(f"  ✓ Created card: {card['card_name']}")

print(f"  Total cards created: {len(cards)}")

# 3. CREATE 20 SAVINGS ACCOUNTS
print("\n[3/9] Creating 20 Savings Accounts...")
bank_names = ["Chase", "Bank of America", "Wells Fargo", "Citi", "Capital One",
              "PNC", "US Bank", "TD Bank", "Ally Bank", "Marcus"]
accounts = []

for i in range(20):
    user = random.choice(users)
    account = api_post("savings-accounts", {
        "user_id": user["id"],
        "account_name": f"Savings Account {i+1}",
        "bank_name": random.choice(bank_names),
        "account_number_last_four": f"{random.randint(1000, 9999)}",
        "account_type": random.choice(["savings", "checking", "money_market"]),
        "minimum_balance": random.randint(100, 1000),
        "interest_rate": round(random.uniform(0.5, 5.0), 2),
        "tags": random.choice(["emergency", "vacation", "general", "investment"])
    })
    if account:
        accounts.append(account)
        print(f"  ✓ Created account: {account['account_name']}")

print(f"  Total accounts created: {len(accounts)}")

# 4. CREATE 20 BUDGETS
print("\n[4/9] Creating 20 Budgets...")
categories = ["Food", "Transport", "Shopping", "Entertainment", "Healthcare",
              "Education", "Bills & Utilities", "Rent", "Insurance", "Travel"]
budgets = []

for i in range(20):
    user = random.choice(users) if random.random() > 0.3 else None
    budget = api_post("budgets", {
        "user_id": user["id"] if user else None,
        "category": random.choice(categories),
        "amount": random.randint(200, 5000),
        "month": random_month(),
        "period": random.choice(["monthly", "weekly", "yearly"]),
        "tags": random.choice(["essential", "discretionary", "fixed", "variable"])
    })
    if budget:
        budgets.append(budget)
        print(f"  ✓ Created budget: {budget['category']} - ${budget['amount']}")

print(f"  Total budgets created: {len(budgets)}")

# 5. CREATE 20 EXPENSES
print("\n[5/9] Creating 20 Expenses...")
descriptions = ["Grocery shopping", "Gas station", "Restaurant dinner", "Coffee",
                "Online shopping", "Uber ride", "Movie tickets", "Gym membership",
                "Electric bill", "Phone bill", "Insurance premium", "Doctor visit",
                "Book purchase", "Concert tickets", "Home repair", "Gift purchase"]
expenses = []

for i in range(20):
    user = random.choice(users)
    payment_method = random.choice(["cash", "debit_card", "credit_card", "savings_account"])

    expense_data = {
        "user_id": user["id"],
        "amount": round(random.uniform(10, 500), 2),
        "category": random.choice(categories),
        "description": random.choice(descriptions),
        "date": random_date(180),
        "payment_method": payment_method,
        "is_recurring": random.choice([True, False]),
        "tags": random.choice(["essential", "discretionary", "urgent", "planned"])
    }

    if payment_method == "credit_card" and cards:
        expense_data["credit_card_id"] = random.choice(cards)["id"]
    elif payment_method == "savings_account" and accounts:
        expense_data["savings_account_id"] = random.choice(accounts)["id"]

    expense = api_post("expenses", expense_data)
    if expense:
        expenses.append(expense)
        print(f"  ✓ Created expense: ${expense['amount']} - {expense['category']}")

print(f"  Total expenses created: {len(expenses)}")

# 6. CREATE 20 SAVINGS GOALS
print("\n[6/9] Creating 20 Savings Goals...")
goal_names = ["Emergency Fund", "Vacation Fund", "New Car", "House Down Payment",
              "Wedding Fund", "Education Fund", "Retirement", "Home Renovation",
              "New Laptop", "Investment Portfolio"]
goals = []

for i in range(20):
    user = random.choice(users)
    target = random.randint(1000, 50000)
    goal = api_post("savings-goals", {
        "user_id": user["id"],
        "name": f"{random.choice(goal_names)} {i+1}",
        "target_amount": target,
        "current_amount": random.randint(0, target // 2),
        "deadline": (datetime.now() + timedelta(days=random.randint(30, 365))).strftime("%Y-%m-%d"),
        "description": f"Saving for {random.choice(goal_names).lower()}",
        "tags": random.choice(["short-term", "long-term", "priority", "flexible"])
    })
    if goal:
        goals.append(goal)
        print(f"  ✓ Created goal: {goal['name']} - ${goal['target_amount']}")

print(f"  Total goals created: {len(goals)}")

# 7. CREATE 20 ASSETS
print("\n[7/9] Creating 20 Assets...")
asset_names = ["Primary Residence", "Investment Property", "Tesla Model 3", "Toyota Camry",
               "Stock Portfolio", "MacBook Pro", "Diamond Ring", "Antique Furniture",
               "Art Collection", "Gold Coins"]
asset_types = ["property", "vehicle", "investment", "electronics", "jewelry", "furniture", "art", "other"]
assets = []

for i in range(20):
    user = random.choice(users)
    purchase_value = random.randint(500, 100000)
    payment_method = random.choice(["cash", "debit_card", "credit_card", "savings_account"])

    asset_data = {
        "user_id": user["id"],
        "name": f"{random.choice(asset_names)} {i+1}",
        "asset_type": random.choice(asset_types),
        "purchase_value": purchase_value,
        "current_value": int(purchase_value * random.uniform(0.8, 1.5)),
        "purchase_date": random_date(730),
        "description": f"Asset purchased in {random.randint(2020, 2025)}",
        "location": random.choice(["Home", "Bank Vault", "Garage", "Office", "Storage"]),
        "payment_method": payment_method,
        "tags": random.choice(["valuable", "appreciating", "depreciating", "essential"])
    }

    if payment_method == "credit_card" and cards:
        asset_data["credit_card_id"] = random.choice(cards)["id"]
    elif payment_method == "savings_account" and accounts:
        asset_data["savings_account_id"] = random.choice(accounts)["id"]

    asset = api_post("assets", asset_data)
    if asset:
        assets.append(asset)
        print(f"  ✓ Created asset: {asset['name']} - ${asset['purchase_value']}")

print(f"  Total assets created: {len(assets)}")

# 8. CREATE 20 RECURRING EXPENSE TEMPLATES
print("\n[8/9] Creating 20 Recurring Templates...")
recurring_descriptions = ["Netflix subscription", "Gym membership", "Phone bill", "Internet bill",
                         "Rent payment", "Car insurance", "Health insurance", "Spotify",
                         "Cloud storage", "Magazine subscription"]
templates = []

for i in range(20):
    user = random.choice(users)
    frequency = random.choice(["daily", "weekly", "monthly", "yearly"])

    template_data = {
        "user_id": user["id"],
        "amount": round(random.uniform(10, 500), 2),
        "category": random.choice(categories),
        "description": random.choice(recurring_descriptions),
        "frequency": frequency,
        "interval": 1,
        "start_date": random_date(30),
        "tags": random.choice(["subscription", "bill", "membership", "service"])
    }

    if frequency == "weekly":
        template_data["day_of_week"] = random.randint(0, 6)
    elif frequency == "monthly":
        template_data["day_of_month"] = random.randint(1, 28)
    elif frequency == "yearly":
        template_data["day_of_month"] = random.randint(1, 28)
        template_data["month_of_year"] = random.randint(1, 12)

    template = api_post("recurring-expenses", template_data)
    if template:
        templates.append(template)
        print(f"  ✓ Created template: {template['description']} - ${template['amount']}/{template['frequency']}")

print(f"  Total templates created: {len(templates)}")

# 9. CREATE SAVINGS ACCOUNT TRANSACTIONS (deposits for accounts)
print("\n[9/9] Creating Savings Account Transactions...")
transactions = 0

for account in accounts[:10]:  # Add deposits to first 10 accounts
    for _ in range(2):  # 2 deposits per account
        resp = requests.post(
            f"{BASE_URL}/savings-accounts/{account['id']}/deposit",
            json={
                "amount": random.randint(100, 5000),
                "date": random_date(90),
                "description": "Monthly deposit",
                "tags": "regular"
            },
            headers=HEADERS,
            verify=VERIFY_SSL
        )
        if resp.status_code in [200, 201]:
            transactions += 1
            print(f"  ✓ Deposited to account {account['id']}")

print(f"  Total transactions created: {transactions}")

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "=" * 60)
print("Database Seeding Complete!")
print("=" * 60)
print(f"""
Summary:
  • Users:              {len(users)}
  • Credit Cards:       {len(cards)}
  • Savings Accounts:   {len(accounts)}
  • Budgets:            {len(budgets)}
  • Expenses:           {len(expenses)}
  • Savings Goals:      {len(goals)}
  • Assets:             {len(assets)}
  • Recurring Templates:{len(templates)}
  • Account Transactions: {transactions}
""")
