from typing import Any

from pydantic import BaseModel, field_validator
from sqlmodel import Field, SQLModel


# Database model
class Expense(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    amount: float
    category: str
    description: str | None = None
    date: str
    payment_method: str | None = None


# Request validation model
class ExpenseCreate(BaseModel):
    """Model for creating expenses with strict validation."""
    amount: float = Field(gt=0, description="Amount must be positive")
    category: str = Field(min_length=1, description="Category cannot be empty")
    description: str | None = None
    date: str = Field(min_length=1, description="Date cannot be empty")
    payment_method: str | None = None

    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v: Any) -> float:
        if not isinstance(v, (int, float)):
            raise ValueError('amount must be a number')
        return float(v)
