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


class Budget(SQLModel, table=True):
    """Monthly budget tracking"""

    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, foreign_key="user.id")  # None = family-wide budget
    category: str = Field(index=True, min_length=1)
    amount: float = Field(gt=0)
    period: str = Field(default="monthly")  # "monthly", "weekly", "yearly"
    month: str = Field(index=True)  # Format: "2024-01"
    is_active: bool = Field(default=True)


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

    @field_validator("payment_method")
    @classmethod
    def validate_payment_method(cls, v: str) -> str:
        valid_methods = ["cash", "debit_card", "credit_card", "upi"]
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
