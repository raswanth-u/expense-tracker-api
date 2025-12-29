import os
from dotenv import load_dotenv
import sqlalchemy
load_dotenv()  # Load .env file
from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List

from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.security import APIKeyHeader
from sqlmodel import Session, SQLModel, create_engine, func, select

from logging_config import setup_logging
from models import (
    Expense,
    ExpenseCreate,
    User,
    UserCreate,
    CreditCard,
    CreditCardCreate,
    Budget,
    BudgetCreate,
)

logger = setup_logging()

logger.info("Starting Expenses API...")

# 1. Define where to look for the key
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    expected_api_key = os.getenv("API_KEY", "dev-key-change-in-prod")
    if api_key != expected_api_key:
        logger.warning("Authentication failed: Invalid API key")
        raise HTTPException(status_code=403, detail="Could not validate credentials")
    return api_key

# 1. Setup DB Connection
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://expense_admin:password@localhost:5432/expenses_db"
)
logger.info(f"Using database: {DATABASE_URL.split('@')[1]}")
engine = create_engine(DATABASE_URL)

def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)
    logger.info("Database tables created/verified")

@asynccontextmanager
async def lifespan(app:FastAPI) -> AsyncGenerator[None, None]:
    create_db_and_tables()
    yield

# 2. Dependency: Get a session for a single request
def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session

app = FastAPI(
    title="Family Expense Tracker API",
    description="Track expenses, budgets, and credit cards for family members",
    version="2.0.0",
    lifespan=lifespan
)

# Health check endpoint (no auth required)
@app.get("/health")
def health_check():
    return "OK"

# ============================================
# USER MANAGEMENT ENDPOINTS
# ============================================

@app.post("/users/", response_model=User)
def create_user(
    user: UserCreate,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key)
):
    """Create a new family member"""
    
    # Check if email already exists
    existing_user = session.exec(
        select(User).where(User.email == user.email)
    ).first()
    
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail=f"User with email {user.email} already exists"
        )
    
    # Create user with timestamp
    db_user = User(
        **user.model_dump(),
        created_at=datetime.now().isoformat()
    )
    
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    
    logger.info(f"Created user: {db_user.name} (ID: {db_user.id})")
    return db_user

@app.get("/users/", response_model=List[User])
def get_users(
    is_active: bool | None = None,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key)
):
    """List all family members"""
    
    query = select(User)
    
    # Filter by active status if specified
    if is_active is not None:
        query = query.where(User.is_active == is_active)
    
    users = session.exec(query).all()
    logger.info(f"Retrieved {len(users)} users")
    
    return list(users)

@app.get("/users/{user_id}", response_model=User)
def get_user(
    user_id: int,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key)
):
    """Get specific family member details"""
    
    user = session.get(User, user_id)
    
    if not user:
        logger.warning(f"User ID {user_id} not found")
        raise HTTPException(status_code=404, detail="User not found")
    
    logger.info(f"Retrieved user: {user.name} (ID: {user_id})")
    return user

@app.put("/users/{user_id}", response_model=User)
def update_user(
    user_id: int,
    user_data: UserCreate,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key)
):
    """Update family member information"""
    
    user = session.get(User, user_id)
    
    if not user:
        logger.warning(f"Update failed: User ID {user_id} not found")
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if email is being changed to an existing email
    if user_data.email != user.email:
        existing = session.exec(
            select(User).where(User.email == user_data.email)
        ).first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Email {user_data.email} is already in use"
            )
    
    # Update fields
    user.name = user_data.name
    user.email = user_data.email
    user.role = user_data.role
    
    session.add(user)
    session.commit()
    session.refresh(user)
    
    logger.info(f"Updated user: {user.name} (ID: {user_id})")
    return user

@app.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key)
):
    """Deactivate a family member (soft delete)"""
    
    user = session.get(User, user_id)
    
    if not user:
        logger.warning(f"Delete failed: User ID {user_id} not found")
        raise HTTPException(status_code=404, detail="User not found")
    
    # Soft delete - just mark as inactive
    user.is_active = False
    
    session.add(user)
    session.commit()
    
    logger.info(f"Deactivated user: {user.name} (ID: {user_id})")
    return {
        "message": "User deactivated successfully",
        "user_id": user_id,
        "name": user.name
    }

@app.get("/users/{user_id}/stats")
def get_user_stats(
    user_id: int,
    month: str | None = None,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key)
):
    """Get spending statistics for a user"""
    
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Build query for user's expenses
    query = select(Expense).where(Expense.user_id == user_id)
    
    # Filter by month if provided
    if month:
        start_date = f"{month}-01"
        end_date = f"{month}-31"
        query = query.where(
            Expense.date >= start_date,
            Expense.date <= end_date
        )
    
    expenses = session.exec(query).all()
    
    # Calculate statistics
    total_spent = sum(e.amount for e in expenses)
    
    # Category breakdown
    category_totals = {}
    for expense in expenses:
        category_totals[expense.category] = \
            category_totals.get(expense.category, 0) + expense.amount
    
    # Payment method breakdown
    payment_totals = {}
    for expense in expenses:
        payment_totals[expense.payment_method] = \
            payment_totals.get(expense.payment_method, 0) + expense.amount
    
    return {
        "user_id": user_id,
        "user_name": user.name,
        "period": month or "all_time",
        "total_spent": round(total_spent, 2),
        "transaction_count": len(expenses),
        "average_transaction": round(total_spent / len(expenses), 2) if expenses else 0,
        "by_category": {k: round(v, 2) for k, v in category_totals.items()},
        "by_payment_method": {k: round(v, 2) for k, v in payment_totals.items()}
    }
# ============================================
# ============================================
# BUDGET MANAGEMENT ENDPOINTS
# ============================================

@app.post("/budgets/", response_model=Budget)
def create_budget(
    budget: BudgetCreate,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key)
):
    """Create a budget for a category"""
    
    # Verify user exists if user_id is provided
    if budget.user_id:
        user = session.get(User, budget.user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
    
    # Check if budget already exists for this category/user/month
    existing = session.exec(
        select(Budget).where(
            Budget.category == budget.category,
            Budget.month == budget.month,
            Budget.user_id == budget.user_id,
            Budget.is_active == True
        )
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Budget already exists for {budget.category} in {budget.month}"
        )
    
    db_budget = Budget(**budget.model_dump())
    session.add(db_budget)
    session.commit()
    session.refresh(db_budget)
    
    logger.info(f"Created budget: {db_budget.category} - ${db_budget.amount} for {db_budget.month}")
    return db_budget


@app.get("/budgets/", response_model=List[Budget])
def get_budgets(
    month: str | None = None,
    user_id: int | None = None,
    category: str | None = None,
    is_active: bool = True,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key)
):
    """List budgets with filters"""
    
    query = select(Budget).where(Budget.is_active == is_active)
    
    if month:
        query = query.where(Budget.month == month)
    if user_id is not None:
        query = query.where(Budget.user_id == user_id)
    if category:
        query = query.where(Budget.category == category)
    
    budgets = session.exec(query).all()
    logger.info(f"Retrieved {len(budgets)} budgets")
    
    return list(budgets)


@app.get("/budgets/{budget_id}", response_model=Budget)
def get_budget(
    budget_id: int,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key)
):
    """Get specific budget details"""
    
    budget = session.get(Budget, budget_id)
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    
    return budget


@app.put("/budgets/{budget_id}", response_model=Budget)
def update_budget(
    budget_id: int,
    budget_data: BudgetCreate,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key)
):
    """Update budget amount or details"""
    
    budget = session.get(Budget, budget_id)
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    
    # Update fields
    budget.category = budget_data.category
    budget.amount = budget_data.amount
    budget.month = budget_data.month
    budget.period = budget_data.period
    budget.user_id = budget_data.user_id
    
    session.add(budget)
    session.commit()
    session.refresh(budget)
    
    logger.info(f"Updated budget ID {budget_id}")
    return budget


@app.delete("/budgets/{budget_id}")
def delete_budget(
    budget_id: int,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key)
):
    """Deactivate a budget"""
    
    budget = session.get(Budget, budget_id)
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    
    budget.is_active = False
    session.add(budget)
    session.commit()
    
    logger.info(f"Deactivated budget ID {budget_id}")
    return {"message": "Budget deactivated", "budget_id": budget_id}


@app.get("/budgets/status/summary")
def get_budget_status(
    month: str,
    user_id: int | None = None,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key)
):
    """
    Check budget vs actual spending with alerts
    
    Status levels:
    - ok: < 80% spent
    - warning: 80-99% spent
    - exceeded: >= 100% spent
    """
    
    # Get budgets for the month
    budget_query = select(Budget).where(
        Budget.month == month,
        Budget.is_active == True
    )
    
    if user_id is not None:
        budget_query = budget_query.where(Budget.user_id == user_id)
    
    budgets = session.exec(budget_query).all()
    
    if not budgets:
        return {
            "month": month,
            "user_id": user_id,
            "message": "No budgets found for this period",
            "budgets": []
        }
    
    # Calculate date range for the month
    start_date = f"{month}-01"
    # Handle different month lengths
    year, month_num = map(int, month.split('-'))
    if month_num == 12:
        end_date = f"{year}-12-31"
    else:
        next_month = f"{year}-{month_num + 1:02d}-01"
        from datetime import datetime, timedelta
        end_date = (datetime.strptime(next_month, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
    
    results = []
    total_budget = 0
    total_spent = 0
    
    for budget in budgets:
        # Build expense query
        expense_query = select(func.sum(Expense.amount)).where(
            Expense.category == budget.category,
            Expense.date >= start_date,
            Expense.date <= end_date
        )
        
        # Filter by user if budget is user-specific
        if budget.user_id:
            expense_query = expense_query.where(Expense.user_id == budget.user_id)
        
        spent = session.exec(expense_query).one() or 0.0
        remaining = budget.amount - spent
        percentage = (spent / budget.amount * 100) if budget.amount > 0 else 0
        
        # Determine status
        if percentage >= 100:
            status = "exceeded"
            alert = f"⚠️ Budget exceeded by ${abs(remaining):.2f}"
        elif percentage >= 80:
            status = "warning"
            alert = f"⚡ Warning: {percentage:.1f}% of budget used"
        else:
            status = "ok"
            alert = None
        
        total_budget += budget.amount
        total_spent += spent
        
        results.append({
            "budget_id": budget.id,
            "category": budget.category,
            "user_id": budget.user_id,
            "budget": round(budget.amount, 2),
            "spent": round(spent, 2),
            "remaining": round(remaining, 2),
            "percentage": round(percentage, 2),
            "status": status,
            "alert": alert
        })
    
    # Sort by percentage (highest first)
    results.sort(key=lambda x: x["percentage"], reverse=True)
    
    # Overall summary
    overall_percentage = (total_spent / total_budget * 100) if total_budget > 0 else 0
    
    return {
        "month": month,
        "user_id": user_id,
        "period": f"{start_date} to {end_date}",
        "total_budget": round(total_budget, 2),
        "total_spent": round(total_spent, 2),
        "total_remaining": round(total_budget - total_spent, 2),
        "overall_percentage": round(overall_percentage, 2),
        "budgets": results,
        "alerts_count": sum(1 for r in results if r["status"] in ["warning", "exceeded"])
    }


@app.get("/budgets/status/alerts")
def get_budget_alerts(
    month: str,
    user_id: int | None = None,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key)
):
    """Get only budgets that need attention (warning or exceeded)"""
    
    status = get_budget_status(month, user_id, session, api_key)
    
    # Filter only warning and exceeded budgets
    alerts = [b for b in status["budgets"] if b["status"] in ["warning", "exceeded"]]
    
    return {
        "month": month,
        "user_id": user_id,
        "alert_count": len(alerts),
        "alerts": alerts
    }


@app.get("/budgets/compare")
def compare_budgets(
    month1: str,
    month2: str,
    user_id: int | None = None,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key)
):
    """Compare budget performance across two months"""
    
    status1 = get_budget_status(month1, user_id, session, api_key)
    status2 = get_budget_status(month2, user_id, session, api_key)
    
    # Create comparison by category
    categories = set()
    for b in status1["budgets"]:
        categories.add(b["category"])
    for b in status2["budgets"]:
        categories.add(b["category"])
    
    comparisons = []
    for category in sorted(categories):
        cat1 = next((b for b in status1["budgets"] if b["category"] == category), None)
        cat2 = next((b for b in status2["budgets"] if b["category"] == category), None)
        
        spent1 = cat1["spent"] if cat1 else 0
        spent2 = cat2["spent"] if cat2 else 0
        
        change = spent2 - spent1
        change_pct = (change / spent1 * 100) if spent1 > 0 else 0
        
        comparisons.append({
            "category": category,
            f"{month1}_spent": spent1,
            f"{month2}_spent": spent2,
            "change": round(change, 2),
            "change_percentage": round(change_pct, 2),
            "trend": "increased" if change > 0 else "decreased" if change < 0 else "stable"
        })
    
    return {
        "month1": month1,
        "month2": month2,
        "user_id": user_id,
        "total_change": round(status2["total_spent"] - status1["total_spent"], 2),
        "categories": comparisons
    }

# ============================================
# EXPENSE ENDPOINTS (UPDATED FOR NEW MODEL)
# ============================================

@app.post("/expenses/", response_model=Expense)
def create_expense(
    expense: ExpenseCreate,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key)
):
    """Create expense with user and credit card tracking"""
    
    # Validate user exists
    user = session.get(User, expense.user_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"User ID {expense.user_id} not found")
    
    if not user.is_active:
        raise HTTPException(status_code=400, detail="User is inactive")
    
    # Validate credit card if provided
    if expense.credit_card_id:
        card = session.get(CreditCard, expense.credit_card_id)
        if not card:
            raise HTTPException(status_code=404, detail="Credit card not found")
        if card.user_id != expense.user_id:
            raise HTTPException(
                status_code=400,
                detail="Credit card doesn't belong to this user"
            )
        if not card.is_active:
            raise HTTPException(status_code=400, detail="Credit card is inactive")
        
        # Ensure payment_method is credit_card
        if expense.payment_method != "credit_card":
            raise HTTPException(
                status_code=400,
                detail="Payment method must be 'credit_card' when credit_card_id is provided"
            )
    
    db_expense = Expense(**expense.model_dump())
    session.add(db_expense)
    session.commit()
    session.refresh(db_expense)
    
    logger.info(f"Created expense for user {expense.user_id}: ${db_expense.amount} - {db_expense.category}")
    return db_expense


@app.get("/expenses/", response_model=List[Expense])
def get_expenses(
    user_id: int | None = None,
    category: str | None = None,
    payment_method: str | None = None,
    credit_card_id: int | None = None,
    min_amount: float | None = None,
    max_amount: float | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    is_recurring: bool | None = None,
    tags: str | None = None,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key)
):
    """Get expenses with enhanced filters"""
    
    query = select(Expense)
    
    if user_id is not None:
        query = query.where(Expense.user_id == user_id)
    if category:
        query = query.where(Expense.category == category)
    if payment_method:
        query = query.where(Expense.payment_method == payment_method)
    if credit_card_id is not None:
        query = query.where(Expense.credit_card_id == credit_card_id)
    if min_amount is not None:
        query = query.where(Expense.amount >= min_amount)
    if max_amount is not None:
        query = query.where(Expense.amount <= max_amount)
    if from_date:
        query = query.where(Expense.date >= from_date)
    if to_date:
        query = query.where(Expense.date <= to_date)
    if is_recurring is not None:
        query = query.where(Expense.is_recurring == is_recurring)
    if tags:
        query = query.where(Expense.tags.like(f"%{tags}%"))
    
    expenses = session.exec(query).all()
    logger.info(f"Retrieved {len(expenses)} expenses")
    
    return list(expenses)

@app.get("/expenses/summary")
def get_expense_summary(
    from_date: str | None = None,
    to_date: str | None = None,
    user_id: int | None = None,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key)
):
    """Get expense summary by category"""
    
    query = select(
        Expense.category,
        func.sum(Expense.amount).label("total"),
        func.count(Expense.id).label("count")
    )
    
    if from_date:
        query = query.where(Expense.date >= from_date)
    if to_date:
        query = query.where(Expense.date <= to_date)
    if user_id is not None:
        query = query.where(Expense.user_id == user_id)
    
    query = query.group_by(Expense.category)
    results = session.exec(query).all()
    
    return [
        {
            "category": category,
            "total": round(total, 2),
            "count": count
        }
        for category, total, count in results
    ]


@app.get("/expenses/payment_summary")
def get_payment_summary(
    from_date: str | None = None,
    to_date: str | None = None,
    user_id: int | None = None,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key)
):
    """Get expense summary by payment method"""
    
    query = select(
        Expense.payment_method,
        func.sum(Expense.amount).label("total"),
        func.count(Expense.id).label("count")
    )
    
    if from_date:
        query = query.where(Expense.date >= from_date)
    if to_date:
        query = query.where(Expense.date <= to_date)
    if user_id is not None:
        query = query.where(Expense.user_id == user_id)
    
    query = query.group_by(Expense.payment_method)
    results = session.exec(query).all()
    
    return [
        {
            "payment_method": payment_method,
            "total": round(total, 2),
            "count": count
        }
        for payment_method, total, count in results
    ]

@app.get("/expenses/{expense_id}", response_model=Expense)
def get_expense(
    expense_id: int,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key)
):
    """Get single expense details"""
    
    expense = session.get(Expense, expense_id)
    if not expense:
        logger.warning(f"Get failed: Expense ID {expense_id} not found")
        raise HTTPException(status_code=404, detail="Expense not found")
    
    logger.info(f"Retrieved expense ID: {expense_id}")
    return expense


@app.put("/expenses/{expense_id}", response_model=Expense)
def update_expense(
    expense_id: int,
    expense_data: ExpenseCreate,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key)
):
    """Update expense"""
    
    existing = session.get(Expense, expense_id)
    if not existing:
        logger.warning(f"Update failed: Expense ID {expense_id} not found")
        raise HTTPException(status_code=404, detail="Expense not found")
    
    # Validate user
    user = session.get(User, expense_data.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Validate credit card if provided
    if expense_data.credit_card_id:
        card = session.get(CreditCard, expense_data.credit_card_id)
        if not card:
            raise HTTPException(status_code=404, detail="Credit card not found")
        if card.user_id != expense_data.user_id:
            raise HTTPException(
                status_code=400,
                detail="Credit card doesn't belong to this user"
            )
    
    # Update all fields
    existing.user_id = expense_data.user_id
    existing.amount = expense_data.amount
    existing.category = expense_data.category
    existing.description = expense_data.description
    existing.date = expense_data.date
    existing.payment_method = expense_data.payment_method
    existing.credit_card_id = expense_data.credit_card_id
    existing.is_recurring = expense_data.is_recurring
    existing.tags = expense_data.tags
    
    session.add(existing)
    session.commit()
    session.refresh(existing)
    
    logger.info(f"Updated expense ID: {expense_id}")
    return existing


@app.delete("/expenses/{expense_id}")
def delete_expense(
    expense_id: int,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key)
):
    """Delete expense"""
    
    expense = session.get(Expense, expense_id)
    if not expense:
        logger.warning(f"Delete failed: Expense ID {expense_id} not found")
        raise HTTPException(status_code=404, detail="Expense not found")
    
    session.delete(expense)
    session.commit()
    
    logger.info(f"Deleted expense ID: {expense_id}")
    return {"message": "Expense deleted", "id": expense_id}

# ============================================
# CREDIT CARD MANAGEMENT ENDPOINTS
# ============================================

@app.post("/credit-cards/", response_model=CreditCard)
def create_credit_card(
    card: CreditCardCreate,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key)
):
    """Register a credit card for tracking"""
    
    # Validate user exists
    user = session.get(User, card.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if not user.is_active:
        raise HTTPException(status_code=400, detail="User is inactive")
    
    # Check for duplicate card (same user + last_four)
    existing = session.exec(
        select(CreditCard).where(
            CreditCard.user_id == card.user_id,
            CreditCard.last_four == card.last_four,
            CreditCard.is_active == True
        )
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Card ending in {card.last_four} already exists for this user"
        )
    
    db_card = CreditCard(**card.model_dump())
    session.add(db_card)
    session.commit()
    session.refresh(db_card)
    
    logger.info(f"Created credit card for user {card.user_id}: {db_card.card_name}")
    return db_card


@app.get("/credit-cards/", response_model=List[CreditCard])
def get_credit_cards(
    user_id: int | None = None,
    is_active: bool = True,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key)
):
    """List credit cards"""
    
    query = select(CreditCard).where(CreditCard.is_active == is_active)
    
    if user_id is not None:
        query = query.where(CreditCard.user_id == user_id)
    
    cards = session.exec(query).all()
    logger.info(f"Retrieved {len(cards)} credit cards")
    
    return list(cards)


@app.get("/credit-cards/{card_id}/statement")
def get_credit_card_statement(
    card_id: int,
    month: str,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key)
):
    """
    Get credit card statement for a billing cycle
    
    Billing cycle: From previous billing_day to current billing_day
    Example: If billing_day is 15, cycle is 15th of prev month to 15th of current month
    """
    
    card = session.get(CreditCard, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Credit card not found")
    
    # Parse month (format: YYYY-MM)
    try:
        year, month_num = map(int, month.split('-'))
    except:
        raise HTTPException(status_code=400, detail="Invalid month format. Use YYYY-MM")
    
    # Calculate billing cycle dates
    billing_day = card.billing_day
    
    # Current billing date
    current_billing = f"{year}-{month_num:02d}-{billing_day:02d}"
    
    # Previous billing date
    if month_num == 1:
        prev_month = 12
        prev_year = year - 1
    else:
        prev_month = month_num - 1
        prev_year = year
    
    prev_billing = f"{prev_year}-{prev_month:02d}-{billing_day:02d}"
    
    # Get expenses for this billing cycle
    expenses = session.exec(
        select(Expense).where(
            Expense.credit_card_id == card_id,
            Expense.date >= prev_billing,
            Expense.date < current_billing
        ).order_by(Expense.date)
    ).all()
    
    # Calculate totals
    total_spent = sum(e.amount for e in expenses)
    
    # Group by category
    by_category = {}
    for expense in expenses:
        by_category[expense.category] = by_category.get(expense.category, 0) + expense.amount
    
    # Calculate credit utilization
    utilization = (total_spent / card.credit_limit * 100) if card.credit_limit > 0 else 0
    
    return {
        "card_name": card.card_name,
        "last_four": card.last_four,
        "billing_cycle": {
            "start": prev_billing,
            "end": current_billing,
            "billing_day": billing_day
        },
        "summary": {
            "total_spent": round(total_spent, 2),
            "transaction_count": len(expenses),
            "credit_limit": card.credit_limit,
            "available_credit": round(card.credit_limit - total_spent, 2),
            "utilization_percentage": round(utilization, 2)
        },
        "by_category": {k: round(v, 2) for k, v in by_category.items()},
        "transactions": [
            {
                "date": e.date,
                "category": e.category,
                "description": e.description,
                "amount": e.amount
            }
            for e in expenses
        ]
    }


@app.get("/credit-cards/{card_id}/utilization")
def get_credit_card_utilization(
    card_id: int,
    months: int = 3,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key)
):
    """
    Get credit card utilization trend over multiple months
    """
    
    card = session.get(CreditCard, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Credit card not found")
    
    from datetime import datetime, timedelta
    
    # Get current date
    today = datetime.now()
    
    # Calculate utilization for last N months
    utilization_history = []
    
    for i in range(months):
        # Calculate month
        month_date = today - timedelta(days=30 * i)
        month_str = month_date.strftime("%Y-%m")
        
        # Get expenses for this month
        start_date = f"{month_str}-01"
        year, month_num = map(int, month_str.split('-'))
        
        # Calculate end date
        if month_num == 12:
            end_date = f"{year + 1}-01-01"
        else:
            end_date = f"{year}-{month_num + 1:02d}-01"
        
        expenses = session.exec(
            select(func.sum(Expense.amount)).where(
                Expense.credit_card_id == card_id,
                Expense.date >= start_date,
                Expense.date < end_date
            )
        ).one()
        
        spent = expenses or 0.0
        utilization = (spent / card.credit_limit * 100) if card.credit_limit > 0 else 0
        
        utilization_history.append({
            "month": month_str,
            "spent": round(spent, 2),
            "utilization": round(utilization, 2)
        })
    
    # Reverse to show oldest first
    utilization_history.reverse()
    
    # Calculate average utilization
    avg_utilization = sum(h["utilization"] for h in utilization_history) / len(utilization_history)
    
    return {
        "card_name": card.card_name,
        "last_four": card.last_four,
        "credit_limit": card.credit_limit,
        "months_analyzed": months,
        "average_utilization": round(avg_utilization, 2),
        "history": utilization_history,
        "recommendation": (
            "Good! Keep utilization below 30%" if avg_utilization < 30 else
            "Consider paying down balance" if avg_utilization < 70 else
            "High utilization - pay down urgently"
        )
    }


@app.get("/credit-cards/summary")
def get_all_cards_summary(
    user_id: int | None = None,
    month: str | None = None,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key)
):
    """
    Get summary of all credit cards
    """
    
    # Get cards
    query = select(CreditCard).where(CreditCard.is_active == True)
    if user_id is not None:
        query = query.where(CreditCard.user_id == user_id)
    
    cards = session.exec(query).all()
    
    if not cards:
        return {
            "message": "No active credit cards found",
            "cards": []
        }
    
    # Use current month if not specified
    if not month:
        from datetime import datetime
        month = datetime.now().strftime("%Y-%m")
    
    # Get summary for each card
    card_summaries = []
    total_limit = 0
    total_spent = 0
    
    for card in cards:
        # Get expenses for this card in the month
        start_date = f"{month}-01"
        year, month_num = map(int, month.split('-'))
        
        if month_num == 12:
            end_date = f"{year + 1}-01-01"
        else:
            end_date = f"{year}-{month_num + 1:02d}-01"
        
        spent = session.exec(
            select(func.sum(Expense.amount)).where(
                Expense.credit_card_id == card.id,
                Expense.date >= start_date,
                Expense.date < end_date
            )
        ).one() or 0.0
        
        utilization = (spent / card.credit_limit * 100) if card.credit_limit > 0 else 0
        
        total_limit += card.credit_limit
        total_spent += spent
        
        card_summaries.append({
            "card_id": card.id,
            "card_name": card.card_name,
            "last_four": card.last_four,
            "credit_limit": card.credit_limit,
            "spent": round(spent, 2),
            "available": round(card.credit_limit - spent, 2),
            "utilization": round(utilization, 2)
        })
    
    overall_utilization = (total_spent / total_limit * 100) if total_limit > 0 else 0
    
    return {
        "month": month,
        "user_id": user_id,
        "total_cards": len(cards),
        "total_credit_limit": round(total_limit, 2),
        "total_spent": round(total_spent, 2),
        "total_available": round(total_limit - total_spent, 2),
        "overall_utilization": round(overall_utilization, 2),
        "cards": card_summaries
    }


@app.get("/credit-cards/{card_id}", response_model=CreditCard)
def get_credit_card(
    card_id: int,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key)
):
    """Get credit card details"""
    
    card = session.get(CreditCard, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Credit card not found")
    
    return card


@app.put("/credit-cards/{card_id}", response_model=CreditCard)
def update_credit_card(
    card_id: int,
    card_data: CreditCardCreate,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key)
):
    """Update credit card details"""
    
    card = session.get(CreditCard, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Credit card not found")
    
    # Update fields
    card.user_id = card_data.user_id
    card.card_name = card_data.card_name
    card.last_four = card_data.last_four
    card.credit_limit = card_data.credit_limit
    card.billing_day = card_data.billing_day
    
    session.add(card)
    session.commit()
    session.refresh(card)
    
    logger.info(f"Updated credit card ID {card_id}")
    return card


@app.delete("/credit-cards/{card_id}")
def delete_credit_card(
    card_id: int,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key)
):
    """Deactivate a credit card"""
    
    card = session.get(CreditCard, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Credit card not found")
    
    card.is_active = False
    session.add(card)
    session.commit()
    
    logger.info(f"Deactivated credit card ID {card_id}")
    return {"message": "Credit card deactivated", "card_id": card_id}