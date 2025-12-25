
from sqlmodel import Field, SQLModel


class Expense(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    amount: float
    category: str
    description: str | None = None
    date: str
    payment_method: str | None = None



