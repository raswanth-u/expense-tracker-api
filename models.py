from typing import Optional
from sqlmodel import Field, SQLModel


class Expense(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    amount: float
    category: str
    description: Optional[str] = None
    date: str
    payment_method: Optional[str] = None



