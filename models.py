from typing import Any

from pydantic import field_validator
from sqlmodel import Field, SQLModel

# ============================================
# DATABASE MODELS (Tables)
# ============================================


class User(SQLModel, table=True):
    """Family member model"""

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, min_length=1)
    email: str = Field(unique=True, index=True)
    role: str = Field(default="member")  # "admin" or "member"
    is_active: bool = Field(default=True)
    created_at: str


class CreditCard(SQLModel, table=True):
    """Credit card tracking model"""

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    card_name: str  # e.g., "Chase Sapphire", "Amex Gold"
    last_four: str = Field(min_length=4, max_length=4)  # Last 4 digits
    credit_limit: float = Field(gt=0)
    billing_day: int = Field(ge=1, le=31)  # Day of month (1-31)
    is_active: bool = Field(default=True)
    tags: str | None = None  # Comma-separated tags for filtering


class DebitCard(SQLModel, table=True):
    """Debit card tracking model - linked to a savings account"""

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    card_name: str  # e.g., "Chase Debit", "BoA Debit"
    last_four: str = Field(min_length=4, max_length=4)  # Last 4 digits
    savings_account_id: int = Field(foreign_key="savingsaccount.id", index=True)  # Linked bank account
    daily_limit: float | None = Field(default=None)  # Optional daily spending limit
    is_active: bool = Field(default=True)
    tags: str | None = None  # Comma-separated tags for filtering
    created_at: str


class Budget(SQLModel, table=True):
    """Monthly budget tracking"""

    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, foreign_key="user.id")  # None = family-wide budget
    category: str = Field(index=True, min_length=1)
    amount: float = Field(gt=0)
    period: str = Field(default="monthly")  # "monthly", "weekly", "yearly"
    month: str = Field(index=True)  # Format: "2024-01"
    is_active: bool = Field(default=True)
    tags: str | None = None  # Comma-separated tags for filtering


class Expense(SQLModel, table=True):
    """Enhanced expense model with user and credit card tracking"""

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    amount: float = Field(gt=0)
    category: str = Field(index=True, min_length=1)
    description: str | None = None
    date: str = Field(index=True)
    payment_method: str  # "cash", "debit_card", "credit_card", "upi"
    credit_card_id: int | None = Field(default=None, foreign_key="creditcard.id")
    is_recurring: bool = Field(default=False)
    tags: str | None = None  # Comma-separated tags for filtering
    savings_account_id: int | None = Field(default=None, foreign_key="savingsaccount.id")


# ============================================
# REQUEST MODELS (Pydantic validation)
# ============================================


class UserCreate(SQLModel):
    """Model for creating users"""

    name: str = Field(min_length=1, description="User's full name")
    email: str = Field(description="User's email address")
    role: str = Field(default="member", description="Role: admin or member")

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if "@" not in v:
            raise ValueError("Invalid email format")
        return v.lower()

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in ["admin", "member"]:
            raise ValueError('Role must be "admin" or "member"')
        return v


class CreditCardCreate(SQLModel):
    """Model for creating credit cards"""

    user_id: int = Field(gt=0, description="User ID who owns the card")
    card_name: str = Field(min_length=1, description="Card name (e.g., Chase Sapphire)")
    last_four: str = Field(min_length=4, max_length=4, description="Last 4 digits")
    credit_limit: float = Field(gt=0, description="Credit limit in currency")
    billing_day: int = Field(ge=1, le=31, description="Billing day of month")
    tags: str | None = Field(default=None, description="Comma-separated tags")

    @field_validator("last_four")
    @classmethod
    def validate_last_four(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("Last four must be digits only")
        return v


class DebitCardCreate(SQLModel):
    """Model for creating debit cards"""

    user_id: int = Field(gt=0, description="User ID who owns the card")
    card_name: str = Field(min_length=1, description="Card name")
    last_four: str = Field(min_length=4, max_length=4, description="Last 4 digits")
    savings_account_id: int = Field(gt=0, description="Linked savings account ID")
    daily_limit: float | None = Field(default=None, description="Optional daily spending limit")
    tags: str | None = Field(default=None, description="Comma-separated tags")

    @field_validator("last_four")
    @classmethod
    def validate_last_four(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("Last four must be digits only")
        return v


class BudgetCreate(SQLModel):
    """Model for creating budgets"""

    user_id: int | None = Field(default=None, description="User ID (None for family budget)")
    category: str = Field(min_length=1, description="Budget category")
    amount: float = Field(gt=0, description="Budget amount")
    month: str = Field(description="Month in YYYY-MM format")
    period: str = Field(default="monthly", description="Budget period")
    tags: str | None = Field(default=None, description="Comma-separated tags")

    @field_validator("month")
    @classmethod
    def validate_month(cls, v: str) -> str:
        import re

        if not re.match(r"^\d{4}-\d{2}$", v):
            raise ValueError("Month must be in YYYY-MM format (e.g., 2024-01)")
        year, month = map(int, v.split("-"))
        if month < 1 or month > 12:
            raise ValueError("Month must be between 01 and 12")
        return v

    @field_validator("period")
    @classmethod
    def validate_period(cls, v: str) -> str:
        if v not in ["monthly", "weekly", "yearly"]:
            raise ValueError('Period must be "monthly", "weekly", or "yearly"')
        return v


class ExpenseCreate(SQLModel):
    """Model for creating expenses with enhanced tracking"""

    user_id: int = Field(gt=0, description="User ID who made the expense")
    amount: float = Field(gt=0, description="Expense amount")
    category: str = Field(min_length=1, description="Expense category")
    description: str | None = Field(default=None, description="Optional description")
    date: str = Field(description="Expense date (YYYY-MM-DD)")
    payment_method: str = Field(description="Payment method: cash, debit_card, credit_card, upi")
    credit_card_id: int | None = Field(default=None, description="Credit card ID if paid by card")
    is_recurring: bool = Field(default=False, description="Is this a recurring expense?")
    tags: str | None = Field(default=None, description="Comma-separated tags")
    savings_account_id: int | None = Field(default=None, foreign_key="savingsaccount.id")

    @field_validator("payment_method")
    @classmethod
    def validate_payment_method(cls, v: str) -> str:
        valid_methods = ["cash", "debit_card", "credit_card", "savings_account"]
        if v not in valid_methods:
            raise ValueError(f"Payment method must be one of: {', '.join(valid_methods)}")
        return v

    @field_validator("date")
    @classmethod
    def validate_date(cls, v: str) -> str:
        import re

        if not re.match(r"^\d{4}-\d{2}-\d{2}$", v):
            raise ValueError("Date must be in YYYY-MM-DD format")
        return v

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Any) -> float:
        if not isinstance(v, (int, float)):
            raise ValueError("amount must be a number")
        return float(v)

# ============================================
# SAVINGS GOAL MODELS
# ============================================

class SavingsGoal(SQLModel, table=True):
    """Savings goal tracking model"""
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    name: str = Field(min_length=1, description="Goal name")
    target_amount: float = Field(gt=0, description="Target amount to save")
    current_amount: float = Field(ge=0, default=0.0, description="Current saved amount")
    deadline: str = Field(index=True, description="Goal deadline (YYYY-MM-DD)")
    description: str | None = None
    is_active: bool = Field(default=True)
    created_at: str
    tags: str | None = None  # Comma-separated tags for filtering

class SavingsGoalCreate(SQLModel):
    """Model for creating savings goals"""
    user_id: int = Field(gt=0, description="User ID who owns the goal")
    name: str = Field(min_length=1, description="Goal name")
    target_amount: float = Field(gt=0, description="Target amount")
    current_amount: float = Field(ge=0, default=0.0, description="Current amount")
    deadline: str = Field(description="Deadline (YYYY-MM-DD)")
    description: str | None = None
    tags: str | None = None  # Comma-separated tags for filtering

    @field_validator("deadline")
    @classmethod
    def validate_deadline(cls, v: str) -> str:
        import re
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", v):
            raise ValueError("Deadline must be in YYYY-MM-DD format")
        return v

class SavingsGoalUpdate(SQLModel):
    """Model for updating savings goal amount"""
    amount: float = Field(gt=0, description="Amount to add or withdraw")

# ============================================
# ASSET MODELS
# ============================================

class Asset(SQLModel, table=True):
    """Asset tracking model for property, vehicles, investments, etc."""
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    name: str = Field(min_length=1, description="Asset name")
    payment_method: str
    asset_type: str = Field(index=True, description="Type of asset")
    purchase_value: float = Field(gt=0, description="Purchase/initial value")
    current_value: float = Field(gt=0, description="Current market value")
    purchase_date: str = Field(description="Purchase date (YYYY-MM-DD)")
    description: str | None = None
    location: str | None = Field(default=None, description="Physical location or account")
    credit_card_id: int | None = Field(default=None, description="Credit card ID if paid by card")
    savings_account_id: int | None = Field(default=None, foreign_key="savingsaccount.id")
    is_active: bool = Field(default=True)
    created_at: str
    updated_at: str | None = None
    tags: str | None = None


class AssetCreate(SQLModel):
    """Model for creating assets"""
    user_id: int = Field(gt=0, description="User ID who owns the asset")
    name: str = Field(min_length=1, description="Asset name")
    asset_type: str = Field(description="Type: property, vehicle, investment, electronics, jewelry, other")
    purchase_value: float = Field(gt=0, description="Purchase value")
    current_value: float = Field(gt=0, description="Current value")
    purchase_date: str = Field(description="Purchase date (YYYY-MM-DD)")
    description: str | None = None
    location: str | None = None
    payment_method: str
    credit_card_id: int | None = None
    savings_account_id: int | None = None
    tags: str | None = None

    @field_validator("payment_method")
    @classmethod
    def validate_payment_method(cls, v: str) -> str:
        valid_methods = ["cash", "debit_card", "credit_card", "savings_account"]
        if v not in valid_methods:
            raise ValueError(f"Payment method must be one of: {', '.join(valid_methods)}")
        return v

    @field_validator("asset_type")
    @classmethod
    def validate_asset_type(cls, v: str) -> str:
        valid_types = ["property", "vehicle", "investment", "electronics", "jewelry", "furniture", "art", "other"]
        if v not in valid_types:
            raise ValueError(f"Asset type must be one of: {', '.join(valid_types)}")
        return v

    @field_validator("purchase_date")
    @classmethod
    def validate_purchase_date(cls, v: str) -> str:
        import re
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", v):
            raise ValueError("Purchase date must be in YYYY-MM-DD format")
        return v

class AssetValueUpdate(SQLModel):
    """Model for updating asset current value"""
    current_value: float = Field(gt=0, description="New current value")

# ============================================
# RECURRING EXPENSE MODELS
# ============================================

class RecurringExpenseTemplate(SQLModel, table=True):
    """Template for recurring expenses"""
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    amount: float = Field(gt=0)
    category: str = Field(index=True, min_length=1)
    description: str | None = None
    frequency: str = Field(index=True)  # "daily", "weekly", "monthly", "yearly", "custom"
    interval: int = Field(default=1, ge=1)  # For custom frequency (e.g., every 2 weeks)
    day_of_week: int | None = Field(default=None, ge=0, le=6)  # 0=Monday, 6=Sunday (for weekly)
    day_of_month: int | None = Field(default=None, ge=1, le=31)  # For monthly/yearly
    month_of_year: int | None = Field(default=None, ge=1, le=12)  # For yearly
    start_date: str = Field(index=True)
    end_date: str | None = None  # None = indefinite
    next_occurrence: str = Field(index=True)
    last_generated: str | None = None
    is_active: bool = Field(default=True)
    tags: str | None = None
    created_at: str

class RecurringExpenseTemplateCreate(SQLModel):
    """Model for creating recurring expense templates"""
    user_id: int = Field(gt=0)
    amount: float = Field(gt=0)
    category: str = Field(min_length=1)
    description: str | None = None
    frequency: str  # "daily", "weekly", "monthly", "yearly", "custom"
    interval: int = Field(default=1, ge=1)
    day_of_week: int | None = None
    day_of_month: int | None = None
    month_of_year: int | None = None
    start_date: str
    end_date: str | None = None
    tags: str | None = None

    @field_validator("frequency")
    @classmethod
    def validate_frequency(cls, v: str) -> str:
        valid = ["daily", "weekly", "monthly", "yearly", "custom"]
        if v not in valid:
            raise ValueError(f"Frequency must be one of: {', '.join(valid)}")
        return v

    @field_validator("start_date")
    @classmethod
    def validate_start_date(cls, v: str) -> str:
        import re
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", v):
            raise ValueError("Start date must be in YYYY-MM-DD format")
        return v

# ============================================
# SAVINGS ACCOUNT MODELS
# ============================================

class SavingsAccount(SQLModel, table=True):
    """Savings account model"""
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    account_name: str = Field(min_length=1)
    bank_name: str = Field(min_length=1)
    account_number_last_four: str = Field(min_length=4, max_length=4)
    account_type: str  # "savings", "checking", "money_market"
    current_balance: float = Field(default=0.0)
    minimum_balance: float = Field(default=0.0)
    interest_rate: float = Field(default=0.0)  # Annual percentage
    tags: str | None = None
    is_active: bool = Field(default=True)
    created_at: str

class SavingsAccountCreate(SQLModel):
    """Model for creating savings accounts"""
    user_id: int = Field(gt=0)
    account_name: str = Field(min_length=1)
    bank_name: str = Field(min_length=1)
    account_number_last_four: str = Field(min_length=4, max_length=4)
    account_type: str
    minimum_balance: float = Field(ge=0, default=0.0)
    interest_rate: float = Field(ge=0, default=0.0)
    tags: str | None = None

    @field_validator("account_number_last_four")
    @classmethod
    def validate_account_number(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("Account number must be digits only")
        return v

    @field_validator("account_type")
    @classmethod
    def validate_account_type(cls, v: str) -> str:
        valid_types = ["savings", "checking", "money_market"]
        if v not in valid_types:
            raise ValueError(f"Account type must be one of: {', '.join(valid_types)}")
        return v

class SavingsAccountTransaction(SQLModel, table=True):
    """Transaction history for savings accounts"""
    id: int | None = Field(default=None, primary_key=True)
    savings_account_id: int = Field(foreign_key="savingsaccount.id", index=True)
    transaction_type: str = Field(index=True)  # "deposit", "withdrawal", "interest"
    amount: float = Field(gt=0)
    balance_after: float
    related_expense_id: int | None = Field(default=None, foreign_key="expense.id")
    related_asset_id: int | None = Field(default=None, foreign_key="asset.id")
    date: str = Field(index=True)
    description: str | None = None
    tags: str | None = None
    created_at: str

class SavingsAccountTransactionCreate(SQLModel):
    """Model for creating transactions"""
    savings_account_id: int = Field(gt=0)
    transaction_type: str
    amount: float = Field(gt=0)
    date: str
    description: str | None = None
    tags: str | None = None

class SavingsAccountDeposit(SQLModel):
    """Model for deposits"""
    amount: float = Field(gt=0)
    date: str | None = None
    description: str | None = None
    tags: str | None = None

class SavingsAccountWithdraw(SQLModel):
    """Model for withdrawals"""
    amount: float = Field(gt=0)
    date: str | None = None
    description: str | None = None
    tags: str | None = None


# ============================================
# CREDIT CARD TRANSACTION MODELS
# ============================================

class CreditCardTransaction(SQLModel, table=True):
    """Transaction history for credit cards"""
    id: int | None = Field(default=None, primary_key=True)
    credit_card_id: int = Field(foreign_key="creditcard.id", index=True)
    transaction_type: str = Field(index=True)  # "charge", "payment", "refund", "fee"
    amount: float = Field(gt=0)
    balance_after: float
    related_expense_id: int | None = Field(default=None, foreign_key="expense.id")
    related_asset_id: int | None = Field(default=None, foreign_key="asset.id")
    date: str = Field(index=True)
    description: str | None = None
    merchant: str | None = None
    tags: str | None = None
    created_at: str


class CreditCardTransactionCreate(SQLModel):
    """Model for creating credit card transactions"""
    credit_card_id: int = Field(gt=0)
    transaction_type: str
    amount: float = Field(gt=0)
    date: str
    description: str | None = None
    merchant: str | None = None
    tags: str | None = None

    @field_validator("transaction_type")
    @classmethod
    def validate_transaction_type(cls, v: str) -> str:
        valid_types = ["charge", "payment", "refund", "fee"]
        if v not in valid_types:
            raise ValueError(f"Transaction type must be one of: {', '.join(valid_types)}")
        return v


class CreditCardPayment(SQLModel):
    """Model for credit card payments"""
    amount: float = Field(gt=0)
    date: str | None = None
    description: str | None = None
    source_savings_account_id: int | None = None  # Optional: pay from savings account
