import os
from fastapi import FastAPI, Depends, HTTPException, Security
from fastapi.security import APIKeyHeader
from sqlmodel import Session, create_engine, SQLModel, select, func
from contextlib import asynccontextmanager
from models import Expense
from logging_config import setup_logging

logger = setup_logging()

logger.info("Starting Expenses API...")

# 1. Define where to look for the key
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def verify_api_key(api_key: str = Security(api_key_header)):
    expected_api_key = os.getenv("API_KEY", "dev-key-change-in-prod")
    if api_key != expected_api_key:
        logger.warning("Authentication failed: Invalid API key")
        raise HTTPException(status_code=403, detail="Could not validate credentials")
    return api_key

# 1. Setup DB Connection
DATABASE_URL =os.getenv("DATABASE_URL","postgresql://expense_admin:password@db:5432/expenses_db")
engine = create_engine(DATABASE_URL)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

@asynccontextmanager
async def lifespan(app:FastAPI):
    create_db_and_tables()
    yield

# 2. Dependency: Get a session for a single request
def get_session():
    with Session(engine) as session:
        yield session

app = FastAPI(lifespan=lifespan)

# 3. The Endpoint
@app.post("/expenses/")
def create_expenses(expense: Expense, session: Session=Depends(get_session), api_key: str = Depends(verify_api_key)):
    session.add(expense)        # Stage Changes
    session.commit()            # Save to DB
    session.refresh(expense)    # Reload to get the generated ID
    logger.info(f"Created expense with ID: {expense.id}")
    return expense

@app.put("/expenses/{expense_id}")
def update_expense(
    expense_id: int,
    expense_data: Expense,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key)
):
    existing = session.get(Expense, expense_id)
    if not existing:
        logger.warning(f"Update failed: Expense ID {expense_id} not found")
        raise HTTPException(status_code=404, detail="Expense not found")
    
    # Update fields from the incoming data
    existing.amount = expense_data.amount
    existing.category = expense_data.category
    existing.description = expense_data.description
    existing.date = expense_data.date
    existing.payment_method = expense_data.payment_method
    
    session.add(existing)
    session.commit()
    session.refresh(existing)
    logger.info(f"Updated expense with ID: {expense_id}")
    return existing

@app.get("/expenses/")
def get_expenses(
                    category: str | None = None,
                    min_amount: float | None = None,
                    max_amount: float | None = None,
                    from_date: str | None = None,
                    to_date: str | None = None,
                    payment_method: str | None = None,
                    session: Session=Depends(get_session),
                    api_key: str = Depends(verify_api_key)
                ):
    query = select(Expense)
    if category is not None:
        query = query.where(Expense.category == category)
    if min_amount is not None:
        query = query.where(Expense.amount >= min_amount)
    if max_amount is not None:
        query = query.where(Expense.amount <= max_amount) 
    if from_date is not None:
        query = query.where(Expense.date >= from_date)
    if to_date is not None:
        query = query.where(Expense.date <= to_date)
    if payment_method is not None:
        query = query.where(Expense.payment_method == payment_method)
    
    response = session.exec(query).all()
    logger.info(f"Retrieved {len(response)} expenses with filters - category: {category}, min_amount: {min_amount}, max_amount: {max_amount}, from_date: {from_date}, to_date: {to_date}, payment_method: {payment_method}")
    return list(response)

@app.get("/expenses/summary")
def get_summary(
    from_date: str | None = None,
    to_date: str | None = None,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key)
):
    query = select(
        Expense.category,
        func.sum(Expense.amount).label("total"),
    )

    # Optional date range filters reused from expenses
    if from_date is not None:
        query = query.where(Expense.date >= from_date)
    if to_date is not None:
        query = query.where(Expense.date <= to_date)

    query = query.group_by(Expense.category)

    results = session.exec(query).all()

    # Normalize into list of dicts for JSON
    return [
        {"category": category, "total": total}
        for category, total in results
    ]
    
@app.get("/expenses/payment_summary")
def get_payment_summary(
    from_date: str | None = None,
    to_date: str | None = None,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key)
):
    query = select(
        Expense.payment_method,
        func.sum(Expense.amount).label("total"),
    )

    # Optional date range filters reused from expenses
    if from_date is not None:
        query = query.where(Expense.date >= from_date)
    if to_date is not None:
        query = query.where(Expense.date <= to_date)

    query = query.group_by(Expense.payment_method)

    results = session.exec(query).all()

    # Normalize into list of dicts for JSON
    return [
        {"payment_method": payment_method, "total": total}
        for payment_method, total in results
    ]

# Note: Path parameter routes MUST come after /expenses/summary
@app.get("/expenses/{expense_id}")
def get_expense(expense_id: int, session: Session = Depends(get_session), api_key: str = Depends(verify_api_key)):
    expense = session.get(Expense, expense_id)
    if not expense:
        logger.warning(f"Get failed: Expense ID {expense_id} not found")
        raise HTTPException(status_code=404, detail="Expense not found")
    logger.info(f"Retrieved expense with ID: {expense_id}")
    return expense

@app.delete("/expenses/{expense_id}")
def delete_expense(expense_id: int, session: Session = Depends(get_session), api_key: str = Depends(verify_api_key)):
    expense = session.get(Expense, expense_id)
    if not expense:
        logger.warning(f"Delete failed: Expense ID {expense_id} not found")
        raise HTTPException(status_code=404, detail="Expense not found")
    session.delete(expense)
    session.commit()
    logger.info(f"Deleted expense with ID: {expense_id}")
    return {"message": "Expense deleted", "id": expense_id}

