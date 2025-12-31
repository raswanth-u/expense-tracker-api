# Imports must come before load_dotenv() call
import os
from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager
from datetime import datetime

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.security import APIKeyHeader
from sqlmodel import Session, SQLModel, create_engine, func, select

from logging_config import setup_logging
from models import (
    Asset,
    AssetCreate,
    AssetValueUpdate,
    Budget,
    BudgetCreate,
    CreditCard,
    CreditCardCreate,
    Expense,
    ExpenseCreate,
    SavingsGoal,
    SavingsGoalCreate,
    SavingsGoalUpdate,
    User,
    UserCreate,
    RecurringExpenseTemplate,
    RecurringExpenseTemplateCreate,
)

# Load environment variables after imports
load_dotenv()

logger = setup_logging()
logger.info("Starting Family Expense Tracker API...")

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
    "DATABASE_URL", "postgresql://expense_admin:password@localhost:5432/expenses_db"
)
logger.info(f"Using database: {DATABASE_URL.split('@')[1]}")
engine = create_engine(DATABASE_URL)


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)
    logger.info("Database tables created/verified")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
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
    lifespan=lifespan,
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
    api_key: str = Depends(verify_api_key),
):
    """Create a new family member"""

    # Check if email already exists
    existing_user = session.exec(select(User).where(User.email == user.email)).first()

    if existing_user:
        raise HTTPException(status_code=400, detail=f"User with email {user.email} already exists")

    # Create user with timestamp
    db_user = User(**user.model_dump(), created_at=datetime.now().isoformat())

    session.add(db_user)
    session.commit()
    session.refresh(db_user)

    logger.info(f"Created user: {db_user.name} (ID: {db_user.id})")
    return db_user


@app.get("/users/", response_model=list[User])
def get_users(
    is_active: bool | None = None,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key),
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
    user_id: int, session: Session = Depends(get_session), api_key: str = Depends(verify_api_key)
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
    api_key: str = Depends(verify_api_key),
):
    """Update family member information"""

    user = session.get(User, user_id)

    if not user:
        logger.warning(f"Update failed: User ID {user_id} not found")
        raise HTTPException(status_code=404, detail="User not found")

    # Check if email is being changed to an existing email
    if user_data.email != user.email:
        existing = session.exec(select(User).where(User.email == user_data.email)).first()
        if existing:
            raise HTTPException(
                status_code=400, detail=f"Email {user_data.email} is already in use"
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
    user_id: int, session: Session = Depends(get_session), api_key: str = Depends(verify_api_key)
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
    return {"message": "User deactivated successfully", "user_id": user_id, "name": user.name}


@app.get("/users/{user_id}/stats")
def get_user_stats(
    user_id: int,
    month: str | None = None,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key),
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
        query = query.where(Expense.date >= start_date, Expense.date <= end_date)

    expenses = session.exec(query).all()

    # Calculate statistics
    total_spent = sum(e.amount for e in expenses)

    # Category breakdown
    category_totals = {}
    for expense in expenses:
        category_totals[expense.category] = (
            category_totals.get(expense.category, 0) + expense.amount
        )

    # Payment method breakdown
    payment_totals = {}
    for expense in expenses:
        payment_totals[expense.payment_method] = (
            payment_totals.get(expense.payment_method, 0) + expense.amount
        )

    return {
        "user_id": user_id,
        "user_name": user.name,
        "period": month or "all_time",
        "total_spent": round(total_spent, 2),
        "transaction_count": len(expenses),
        "average_transaction": round(total_spent / len(expenses), 2) if expenses else 0,
        "by_category": {k: round(v, 2) for k, v in category_totals.items()},
        "by_payment_method": {k: round(v, 2) for k, v in payment_totals.items()},
    }


# ============================================
# ============================================
# BUDGET MANAGEMENT ENDPOINTS
# ============================================


@app.post("/budgets/", response_model=Budget)
def create_budget(
    budget: BudgetCreate,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key),
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
            Budget.is_active,
        )
    ).first()

    if existing:
        raise HTTPException(
            status_code=400, detail=f"Budget already exists for {budget.category} in {budget.month}"
        )

    db_budget = Budget(**budget.model_dump())
    session.add(db_budget)
    session.commit()
    session.refresh(db_budget)

    logger.info(f"Created budget: {db_budget.category} - ${db_budget.amount} for {db_budget.month}")
    return db_budget


@app.get("/budgets/", response_model=list[Budget])
def get_budgets(
    month: str | None = None,
    user_id: int | None = None,
    category: str | None = None,
    is_active: bool = True,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key),
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
    budget_id: int, session: Session = Depends(get_session), api_key: str = Depends(verify_api_key)
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
    api_key: str = Depends(verify_api_key),
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
    budget_id: int, session: Session = Depends(get_session), api_key: str = Depends(verify_api_key)
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
    api_key: str = Depends(verify_api_key),
):
    """
    Check budget vs actual spending with alerts

    Status levels:
    - ok: < 80% spent
    - warning: 80-99% spent
    - exceeded: >= 100% spent
    """

    # Get budgets for the month
    budget_query = select(Budget).where(Budget.month == month, Budget.is_active)

    if user_id is not None:
        budget_query = budget_query.where(Budget.user_id == user_id)

    budgets = session.exec(budget_query).all()

    if not budgets:
        return {
            "month": month,
            "user_id": user_id,
            "message": "No budgets found for this period",
            "budgets": [],
        }

    # Calculate date range for the month
    start_date = f"{month}-01"
    # Handle different month lengths
    year, month_num = map(int, month.split("-"))
    if month_num == 12:
        end_date = f"{year}-12-31"
    else:
        next_month = f"{year}-{month_num + 1:02d}-01"
        from datetime import datetime, timedelta

        end_date = (datetime.strptime(next_month, "%Y-%m-%d") - timedelta(days=1)).strftime(
            "%Y-%m-%d"
        )

    results = []
    total_budget = 0
    total_spent = 0

    for budget in budgets:
        # Build expense query
        expense_query = select(func.sum(Expense.amount)).where(
            Expense.category == budget.category,
            Expense.date >= start_date,
            Expense.date <= end_date,
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

        results.append(
            {
                "budget_id": budget.id,
                "category": budget.category,
                "user_id": budget.user_id,
                "budget": round(budget.amount, 2),
                "spent": round(spent, 2),
                "remaining": round(remaining, 2),
                "percentage": round(percentage, 2),
                "status": status,
                "alert": alert,
            }
        )

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
        "alerts_count": sum(1 for r in results if r["status"] in ["warning", "exceeded"]),
    }


@app.get("/budgets/status/alerts")
def get_budget_alerts(
    month: str,
    user_id: int | None = None,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key),
):
    """Get only budgets that need attention (warning or exceeded)"""

    status = get_budget_status(month, user_id, session, api_key)

    # Filter only warning and exceeded budgets
    alerts = [b for b in status["budgets"] if b["status"] in ["warning", "exceeded"]]

    return {"month": month, "user_id": user_id, "alert_count": len(alerts), "alerts": alerts}


@app.get("/budgets/compare")
def compare_budgets(
    month1: str,
    month2: str,
    user_id: int | None = None,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key),
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

        comparisons.append(
            {
                "category": category,
                f"{month1}_spent": spent1,
                f"{month2}_spent": spent2,
                "change": round(change, 2),
                "change_percentage": round(change_pct, 2),
                "trend": "increased" if change > 0 else "decreased" if change < 0 else "stable",
            }
        )

    return {
        "month1": month1,
        "month2": month2,
        "user_id": user_id,
        "total_change": round(status2["total_spent"] - status1["total_spent"], 2),
        "categories": comparisons,
    }


# ============================================
# EXPENSE ENDPOINTS (UPDATED FOR NEW MODEL)
# ============================================


@app.post("/expenses/", response_model=Expense)
def create_expense(
    expense: ExpenseCreate,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key),
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
        if not card.is_active:
            raise HTTPException(status_code=400, detail="Credit card is inactive")

        # Ensure payment_method is credit_card
        if expense.payment_method != "credit_card":
            raise HTTPException(
                status_code=400,
                detail="Payment method must be 'credit_card' when credit_card_id is provided",
            )

    db_expense = Expense(**expense.model_dump())
    session.add(db_expense)
    session.commit()
    session.refresh(db_expense)

    logger.info(
        f"Created expense for user {expense.user_id}: ${db_expense.amount} - {db_expense.category}"
    )
    return db_expense


@app.get("/expenses/", response_model=list[Expense])
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
    api_key: str = Depends(verify_api_key),
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
    api_key: str = Depends(verify_api_key),
):
    """Get expense summary by category"""

    query = select(
        Expense.category,
        func.sum(Expense.amount).label("total"),
        func.count(Expense.id).label("count"),
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
        {"category": category, "total": round(total, 2), "count": count}
        for category, total, count in results
    ]


@app.get("/expenses/payment_summary")
def get_payment_summary(
    from_date: str | None = None,
    to_date: str | None = None,
    user_id: int | None = None,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key),
):
    """Get expense summary by payment method"""

    query = select(
        Expense.payment_method,
        func.sum(Expense.amount).label("total"),
        func.count(Expense.id).label("count"),
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
        {"payment_method": payment_method, "total": round(total, 2), "count": count}
        for payment_method, total, count in results
    ]


@app.get("/expenses/{expense_id}", response_model=Expense)
def get_expense(
    expense_id: int, session: Session = Depends(get_session), api_key: str = Depends(verify_api_key)
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
    api_key: str = Depends(verify_api_key),
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
        if not card.is_active:
            raise HTTPException(status_code=400, detail="Credit card is inactive")

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
    expense_id: int, session: Session = Depends(get_session), api_key: str = Depends(verify_api_key)
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
    api_key: str = Depends(verify_api_key),
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
            CreditCard.is_active,
        )
    ).first()

    if existing:
        raise HTTPException(
            status_code=400, detail=f"Card ending in {card.last_four} already exists for this user"
        )

    db_card = CreditCard(**card.model_dump())
    session.add(db_card)
    session.commit()
    session.refresh(db_card)

    logger.info(f"Created credit card for user {card.user_id}: {db_card.card_name}")
    return db_card


@app.get("/credit-cards/", response_model=list[CreditCard])
def get_credit_cards(
    user_id: int | None = None,
    is_active: bool = True,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key),
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
    api_key: str = Depends(verify_api_key),
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
        year, month_num = map(int, month.split("-"))
    except (ValueError, AttributeError) as e:
        raise HTTPException(status_code=400, detail="Invalid month format. Use YYYY-MM") from e

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
        select(Expense)
        .where(
            Expense.credit_card_id == card_id,
            Expense.date >= prev_billing,
            Expense.date < current_billing,
        )
        .order_by(Expense.date)
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
            "billing_day": billing_day,
        },
        "summary": {
            "total_spent": round(total_spent, 2),
            "transaction_count": len(expenses),
            "credit_limit": card.credit_limit,
            "available_credit": round(card.credit_limit - total_spent, 2),
            "utilization_percentage": round(utilization, 2),
        },
        "by_category": {k: round(v, 2) for k, v in by_category.items()},
        "transactions": [
            {
                "date": e.date,
                "category": e.category,
                "description": e.description,
                "amount": e.amount,
            }
            for e in expenses
        ],
    }


@app.get("/credit-cards/{card_id}/utilization")
def get_credit_card_utilization(
    card_id: int,
    months: int = 3,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key),
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
        year, month_num = map(int, month_str.split("-"))

        # Calculate end date
        if month_num == 12:
            end_date = f"{year + 1}-01-01"
        else:
            end_date = f"{year}-{month_num + 1:02d}-01"

        expenses = session.exec(
            select(func.sum(Expense.amount)).where(
                Expense.credit_card_id == card_id,
                Expense.date >= start_date,
                Expense.date < end_date,
            )
        ).one()

        spent = expenses or 0.0
        utilization = (spent / card.credit_limit * 100) if card.credit_limit > 0 else 0

        utilization_history.append(
            {"month": month_str, "spent": round(spent, 2), "utilization": round(utilization, 2)}
        )

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
            "Good! Keep utilization below 30%"
            if avg_utilization < 30
            else "Consider paying down balance"
            if avg_utilization < 70
            else "High utilization - pay down urgently"
        ),
    }


@app.get("/credit-cards/summary")
def get_all_cards_summary(
    user_id: int | None = None,
    month: str | None = None,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key),
):
    """
    Get summary of all credit cards
    """

    # Get cards
    query = select(CreditCard).where(CreditCard.is_active)
    if user_id is not None:
        query = query.where(CreditCard.user_id == user_id)

    cards = session.exec(query).all()

    if not cards:
        return {"message": "No active credit cards found", "cards": []}

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
        year, month_num = map(int, month.split("-"))

        if month_num == 12:
            end_date = f"{year + 1}-01-01"
        else:
            end_date = f"{year}-{month_num + 1:02d}-01"

        spent = (
            session.exec(
                select(func.sum(Expense.amount)).where(
                    Expense.credit_card_id == card.id,
                    Expense.date >= start_date,
                    Expense.date < end_date,
                )
            ).one()
            or 0.0
        )

        utilization = (spent / card.credit_limit * 100) if card.credit_limit > 0 else 0

        total_limit += card.credit_limit
        total_spent += spent

        card_summaries.append(
            {
                "card_id": card.id,
                "card_name": card.card_name,
                "last_four": card.last_four,
                "credit_limit": card.credit_limit,
                "spent": round(spent, 2),
                "available": round(card.credit_limit - spent, 2),
                "utilization": round(utilization, 2),
            }
        )

    overall_utilization = (total_spent / total_limit * 100) if total_limit > 0 else 0

    return {
        "month": month,
        "user_id": user_id,
        "total_cards": len(cards),
        "total_credit_limit": round(total_limit, 2),
        "total_spent": round(total_spent, 2),
        "total_available": round(total_limit - total_spent, 2),
        "overall_utilization": round(overall_utilization, 2),
        "cards": card_summaries,
    }


@app.get("/credit-cards/{card_id}", response_model=CreditCard)
def get_credit_card(
    card_id: int, session: Session = Depends(get_session), api_key: str = Depends(verify_api_key)
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
    api_key: str = Depends(verify_api_key),
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
    card_id: int, session: Session = Depends(get_session), api_key: str = Depends(verify_api_key)
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


# ============================================
# ADVANCED REPORTS & ANALYTICS ENDPOINTS
# ============================================


@app.get("/reports/monthly")
def get_monthly_report(
    month: str,
    user_id: int | None = None,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key),
):
    """
    Comprehensive monthly report with all metrics
    """

    start_date = f"{month}-01"
    year, month_num = map(int, month.split("-"))

    # Calculate end date
    if month_num == 12:
        end_date = f"{year + 1}-01-01"
    else:
        end_date = f"{year}-{month_num + 1:02d}-01"

    # Build base query
    expense_query = select(Expense).where(Expense.date >= start_date, Expense.date < end_date)

    if user_id is not None:
        expense_query = expense_query.where(Expense.user_id == user_id)

    expenses = session.exec(expense_query).all()

    if not expenses:
        return {
            "month": month,
            "user_id": user_id,
            "message": "No expenses found for this period",
            "total_spent": 0,
            "transaction_count": 0,
        }

    # Calculate totals
    total_spent = sum(e.amount for e in expenses)

    # Category breakdown
    by_category = {}
    for exp in expenses:
        by_category[exp.category] = by_category.get(exp.category, 0) + exp.amount

    # Payment method breakdown
    by_payment = {}
    for exp in expenses:
        by_payment[exp.payment_method] = by_payment.get(exp.payment_method, 0) + exp.amount

    # Daily spending trend
    by_date = {}
    for exp in expenses:
        by_date[exp.date] = by_date.get(exp.date, 0) + exp.amount

    # Get budget comparison if user specified
    budget_comparison = None
    if user_id is not None:
        budgets = session.exec(
            select(Budget).where(Budget.user_id == user_id, Budget.month == month, Budget.is_active)
        ).all()

        if budgets:
            total_budget = sum(b.amount for b in budgets)
            budget_comparison = {
                "total_budget": total_budget,
                "total_spent": total_spent,
                "remaining": total_budget - total_spent,
                "percentage": round((total_spent / total_budget * 100), 2)
                if total_budget > 0
                else 0,
            }

    # Top 5 expenses
    top_expenses = sorted(expenses, key=lambda x: x.amount, reverse=True)[:5]

    # Recurring expenses
    recurring = [e for e in expenses if e.is_recurring]
    recurring_total = sum(e.amount for e in recurring)

    return {
        "month": month,
        "user_id": user_id,
        "period": f"{start_date} to {end_date}",
        "summary": {
            "total_spent": round(total_spent, 2),
            "transaction_count": len(expenses),
            "average_transaction": round(total_spent / len(expenses), 2),
            "largest_expense": round(max(e.amount for e in expenses), 2),
            "smallest_expense": round(min(e.amount for e in expenses), 2),
        },
        "by_category": {
            k: round(v, 2) for k, v in sorted(by_category.items(), key=lambda x: x[1], reverse=True)
        },
        "by_payment_method": {k: round(v, 2) for k, v in by_payment.items()},
        "budget_comparison": budget_comparison,
        "top_expenses": [
            {
                "date": e.date,
                "category": e.category,
                "description": e.description,
                "amount": e.amount,
            }
            for e in top_expenses
        ],
        "recurring_expenses": {"count": len(recurring), "total": round(recurring_total, 2)},
        "daily_trend": {k: round(by_date[k], 2) for k in sorted(by_date.keys())},
    }


@app.get("/reports/family-summary")
def get_family_summary(
    month: str, session: Session = Depends(get_session), api_key: str = Depends(verify_api_key)
):
    """
    Family-wide spending summary showing all members
    """

    users = session.exec(select(User).where(User.is_active)).all()

    if not users:
        return {"month": month, "message": "No active users found", "members": []}

    start_date = f"{month}-01"
    year, month_num = map(int, month.split("-"))

    if month_num == 12:
        end_date = f"{year + 1}-01-01"
    else:
        end_date = f"{year}-{month_num + 1:02d}-01"

    member_summaries = []
    total_family_spent = 0

    for user in users:
        # Get user's expenses
        expenses = session.exec(
            select(Expense).where(
                Expense.user_id == user.id, Expense.date >= start_date, Expense.date < end_date
            )
        ).all()

        spent = sum(e.amount for e in expenses)
        total_family_spent += spent

        # Get user's budgets
        budgets = session.exec(
            select(Budget).where(Budget.user_id == user.id, Budget.month == month, Budget.is_active)
        ).all()

        total_budget = sum(b.amount for b in budgets)

        # Top category for this user
        by_category = {}
        for exp in expenses:
            by_category[exp.category] = by_category.get(exp.category, 0) + exp.amount

        top_category = max(by_category.items(), key=lambda x: x[1]) if by_category else ("None", 0)

        member_summaries.append(
            {
                "user_id": user.id,
                "name": user.name,
                "total_spent": round(spent, 2),
                "transaction_count": len(expenses),
                "budget": round(total_budget, 2) if budgets else None,
                "budget_status": (
                    "within_budget"
                    if total_budget > 0 and spent <= total_budget
                    else "over_budget"
                    if total_budget > 0 and spent > total_budget
                    else "no_budget"
                ),
                "top_category": {"name": top_category[0], "amount": round(top_category[1], 2)},
            }
        )

    # Sort by spending (highest first)
    member_summaries.sort(key=lambda x: x["total_spent"], reverse=True)

    return {
        "month": month,
        "period": f"{start_date} to {end_date}",
        "family_total": round(total_family_spent, 2),
        "member_count": len(users),
        "average_per_member": round(total_family_spent / len(users), 2),
        "members": member_summaries,
    }


@app.get("/reports/category-analysis")
def get_category_analysis(
    category: str,
    from_date: str,
    to_date: str,
    user_id: int | None = None,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key),
):
    """
    Deep dive analysis of a specific category
    """

    query = select(Expense).where(
        Expense.category == category, Expense.date >= from_date, Expense.date <= to_date
    )

    if user_id is not None:
        query = query.where(Expense.user_id == user_id)

    expenses = session.exec(query).all()

    if not expenses:
        return {"category": category, "message": "No expenses found for this category", "total": 0}

    # Calculate statistics
    amounts = [e.amount for e in expenses]
    total = sum(amounts)

    # Payment method breakdown
    by_payment = {}
    for exp in expenses:
        by_payment[exp.payment_method] = by_payment.get(exp.payment_method, 0) + exp.amount

    # Monthly trend
    by_month = {}
    for exp in expenses:
        month = exp.date[:7]  # YYYY-MM
        by_month[month] = by_month.get(month, 0) + exp.amount

    # If multiple users, show per-user breakdown
    by_user = {}
    if user_id is None:
        for exp in expenses:
            user = session.get(User, exp.user_id)
            user_name = user.name if user else f"User {exp.user_id}"
            by_user[user_name] = by_user.get(user_name, 0) + exp.amount

    return {
        "category": category,
        "period": f"{from_date} to {to_date}",
        "user_id": user_id,
        "summary": {
            "total_spent": round(total, 2),
            "transaction_count": len(expenses),
            "average_transaction": round(total / len(expenses), 2),
            "highest_transaction": round(max(amounts), 2),
            "lowest_transaction": round(min(amounts), 2),
        },
        "by_payment_method": {k: round(v, 2) for k, v in by_payment.items()},
        "monthly_trend": {k: round(by_month[k], 2) for k in sorted(by_month.keys())},
        "by_user": {k: round(v, 2) for k, v in by_user.items()} if by_user else None,
        "recent_transactions": [
            {
                "date": e.date,
                "description": e.description,
                "amount": e.amount,
                "payment_method": e.payment_method,
            }
            for e in sorted(expenses, key=lambda x: x.date, reverse=True)[:10]
        ],
    }


@app.get("/reports/spending-trends")
def get_spending_trends(
    months: int = 6,
    user_id: int | None = None,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key),
):
    """
    Analyze spending trends over multiple months
    """

    from datetime import datetime, timedelta

    today = datetime.now()
    monthly_data = []

    for i in range(months):
        # Calculate month
        month_date = today - timedelta(days=30 * i)
        month_str = month_date.strftime("%Y-%m")

        start_date = f"{month_str}-01"
        year, month_num = map(int, month_str.split("-"))

        if month_num == 12:
            end_date = f"{year + 1}-01-01"
        else:
            end_date = f"{year}-{month_num + 1:02d}-01"

        # Get expenses for this month
        query = select(Expense).where(Expense.date >= start_date, Expense.date < end_date)

        if user_id is not None:
            query = query.where(Expense.user_id == user_id)

        expenses = session.exec(query).all()

        total = sum(e.amount for e in expenses)

        # Category breakdown
        by_category = {}
        for exp in expenses:
            by_category[exp.category] = by_category.get(exp.category, 0) + exp.amount

        top_category = max(by_category.items(), key=lambda x: x[1]) if by_category else ("None", 0)

        monthly_data.append(
            {
                "month": month_str,
                "total_spent": round(total, 2),
                "transaction_count": len(expenses),
                "top_category": {"name": top_category[0], "amount": round(top_category[1], 2)},
            }
        )

    # Reverse to show oldest first
    monthly_data.reverse()

    # Calculate trend
    if len(monthly_data) >= 2:
        recent_avg = sum(m["total_spent"] for m in monthly_data[-3:]) / min(3, len(monthly_data))
        older_avg = sum(m["total_spent"] for m in monthly_data[:3]) / min(3, len(monthly_data))

        if recent_avg > older_avg * 1.1:
            trend = "increasing"
        elif recent_avg < older_avg * 0.9:
            trend = "decreasing"
        else:
            trend = "stable"
    else:
        trend = "insufficient_data"

    total_spent = sum(m["total_spent"] for m in monthly_data)
    avg_monthly = total_spent / len(monthly_data) if monthly_data else 0

    return {
        "user_id": user_id,
        "months_analyzed": months,
        "total_spent": round(total_spent, 2),
        "average_monthly": round(avg_monthly, 2),
        "trend": trend,
        "monthly_data": monthly_data,
    }


@app.get("/reports/payment-method-analysis")
def get_payment_method_analysis(
    from_date: str,
    to_date: str,
    user_id: int | None = None,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key),
):
    """
    Analyze spending by payment method
    """

    query = select(Expense).where(Expense.date >= from_date, Expense.date <= to_date)

    if user_id is not None:
        query = query.where(Expense.user_id == user_id)

    expenses = session.exec(query).all()

    if not expenses:
        return {"message": "No expenses found", "total": 0}

    total = sum(e.amount for e in expenses)

    # Payment method breakdown
    by_payment = {}
    payment_counts = {}

    for exp in expenses:
        method = exp.payment_method
        by_payment[method] = by_payment.get(method, 0) + exp.amount
        payment_counts[method] = payment_counts.get(method, 0) + 1

    # Calculate percentages and averages
    payment_analysis = []
    for method, amount in by_payment.items():
        percentage = (amount / total * 100) if total > 0 else 0
        count = payment_counts[method]
        avg_transaction = amount / count

        payment_analysis.append(
            {
                "payment_method": method,
                "total_spent": round(amount, 2),
                "transaction_count": count,
                "average_transaction": round(avg_transaction, 2),
                "percentage_of_total": round(percentage, 2),
            }
        )

    # Sort by amount
    payment_analysis.sort(key=lambda x: x["total_spent"], reverse=True)

    # Credit card specific analysis
    credit_card_expenses = [e for e in expenses if e.payment_method == "credit_card"]
    credit_card_total = sum(e.amount for e in credit_card_expenses)

    # Group by credit card
    by_card = {}
    if credit_card_expenses:
        for exp in credit_card_expenses:
            if exp.credit_card_id:
                card = session.get(CreditCard, exp.credit_card_id)
                card_name = f"{card.card_name} ({card.last_four})" if card else "Unknown Card"
                by_card[card_name] = by_card.get(card_name, 0) + exp.amount

    return {
        "period": f"{from_date} to {to_date}",
        "user_id": user_id,
        "total_spent": round(total, 2),
        "transaction_count": len(expenses),
        "by_payment_method": payment_analysis,
        "credit_card_breakdown": {k: round(v, 2) for k, v in by_card.items()} if by_card else None,
        "credit_card_total": round(credit_card_total, 2),
    }


@app.get("/reports/export")
def export_expenses(
    from_date: str,
    to_date: str,
    user_id: int | None = None,
    format: str = "json",
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key),
):
    """
    Export expenses in different formats (JSON or CSV)
    """

    query = select(Expense).where(Expense.date >= from_date, Expense.date <= to_date)

    if user_id is not None:
        query = query.where(Expense.user_id == user_id)

    expenses = session.exec(query.order_by(Expense.date)).all()

    if format == "csv":
        import csv
        import io

        from fastapi.responses import StreamingResponse

        output = io.StringIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow(
            [
                "Date",
                "User ID",
                "Category",
                "Description",
                "Amount",
                "Payment Method",
                "Credit Card ID",
                "Is Recurring",
                "Tags",
            ]
        )

        # Write data
        for exp in expenses:
            writer.writerow(
                [
                    exp.date,
                    exp.user_id,
                    exp.category,
                    exp.description or "",
                    exp.amount,
                    exp.payment_method,
                    exp.credit_card_id or "",
                    exp.is_recurring,
                    exp.tags or "",
                ]
            )

        output.seek(0)

        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=expenses_{from_date}_to_{to_date}.csv"
            },
        )

    else:  # JSON format
        return {
            "period": f"{from_date} to {to_date}",
            "user_id": user_id,
            "total_expenses": len(expenses),
            "total_amount": round(sum(e.amount for e in expenses), 2),
            "expenses": [
                {
                    "id": e.id,
                    "date": e.date,
                    "user_id": e.user_id,
                    "category": e.category,
                    "description": e.description,
                    "amount": e.amount,
                    "payment_method": e.payment_method,
                    "credit_card_id": e.credit_card_id,
                    "is_recurring": e.is_recurring,
                    "tags": e.tags,
                }
                for e in expenses
            ],
        }

# ============================================
# SAVINGS GOAL ENDPOINTS
# ============================================

@app.post("/savings-goals/", response_model=SavingsGoal)
def create_savings_goal(
    goal: SavingsGoalCreate,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key),
):
    """Create a new savings goal"""
    # Validate user exists
    user = session.get(User, goal.user_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"User ID {goal.user_id} not found")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="User is inactive")

    # Validate deadline is in the future
    from datetime import datetime
    try:
        deadline_date = datetime.strptime(goal.deadline, "%Y-%m-%d")
        if deadline_date.date() < datetime.now().date():
            raise HTTPException(status_code=400, detail="Deadline must be in the future")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")

    # Create savings goal
    db_goal = SavingsGoal(
        **goal.model_dump(),
        created_at=datetime.now().isoformat()
    )
    session.add(db_goal)
    session.commit()
    session.refresh(db_goal)

    logger.info(f"Created savings goal: {db_goal.name} for user {goal.user_id}")
    return db_goal

@app.get("/savings-goals/", response_model=list[SavingsGoal])
def list_savings_goals(
    user_id: int | None = None,
    is_active: bool = True,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key),
):
    """List savings goals"""
    query = select(SavingsGoal).where(SavingsGoal.is_active == is_active)

    if user_id is not None:
        query = query.where(SavingsGoal.user_id == user_id)

    goals = session.exec(query.order_by(SavingsGoal.created_at.desc())).all()
    logger.info(f"Retrieved {len(goals)} savings goals")
    return list(goals)

@app.get("/savings-goals/{goal_id}", response_model=SavingsGoal)
def get_savings_goal(
    goal_id: int,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key),
):
    """Get specific savings goal"""
    goal = session.get(SavingsGoal, goal_id)
    if not goal:
        logger.warning(f"Savings goal ID {goal_id} not found")
        raise HTTPException(status_code=404, detail="Savings goal not found")

    logger.info(f"Retrieved savings goal: {goal.name} (ID: {goal_id})")
    return goal

@app.put("/savings-goals/{goal_id}", response_model=SavingsGoal)
def update_savings_goal(
    goal_id: int,
    goal_data: SavingsGoalCreate,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key),
):
    """Update savings goal"""
    goal = session.get(SavingsGoal, goal_id)
    if not goal:
        logger.warning(f"Update failed: Savings goal ID {goal_id} not found")
        raise HTTPException(status_code=404, detail="Savings goal not found")

    # Validate user exists
    user = session.get(User, goal_data.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Update fields
    goal.user_id = goal_data.user_id
    goal.name = goal_data.name
    goal.target_amount = goal_data.target_amount
    goal.current_amount = goal_data.current_amount
    goal.deadline = goal_data.deadline
    goal.description = goal_data.description

    session.add(goal)
    session.commit()
    session.refresh(goal)

    logger.info(f"Updated savings goal ID: {goal_id}")
    return goal

@app.delete("/savings-goals/{goal_id}")
def delete_savings_goal(
    goal_id: int,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key),
):
    """Deactivate a savings goal"""
    goal = session.get(SavingsGoal, goal_id)
    if not goal:
        logger.warning(f"Delete failed: Savings goal ID {goal_id} not found")
        raise HTTPException(status_code=404, detail="Savings goal not found")

    goal.is_active = False
    session.add(goal)
    session.commit()

    logger.info(f"Deactivated savings goal ID: {goal_id}")
    return {"message": "Savings goal deactivated", "goal_id": goal_id}

@app.post("/savings-goals/{goal_id}/add", response_model=SavingsGoal)
def add_to_savings_goal(
    goal_id: int,
    update: SavingsGoalUpdate,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key),
):
    """Add money to a savings goal"""
    goal = session.get(SavingsGoal, goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Savings goal not found")

    if not goal.is_active:
        raise HTTPException(status_code=400, detail="Cannot add to inactive goal")

    # Add amount
    goal.current_amount += update.amount

    session.add(goal)
    session.commit()
    session.refresh(goal)

    logger.info(f"Added ${update.amount:.2f} to savings goal ID: {goal_id}")
    return goal

@app.post("/savings-goals/{goal_id}/withdraw", response_model=SavingsGoal)
def withdraw_from_savings_goal(
    goal_id: int,
    update: SavingsGoalUpdate,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key),
):
    """Withdraw money from a savings goal"""
    goal = session.get(SavingsGoal, goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Savings goal not found")

    if not goal.is_active:
        raise HTTPException(status_code=400, detail="Cannot withdraw from inactive goal")

    # Check if sufficient funds
    if goal.current_amount < update.amount:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient funds. Available: ${goal.current_amount:.2f}"
        )

    # Withdraw amount
    goal.current_amount -= update.amount

    session.add(goal)
    session.commit()
    session.refresh(goal)

    logger.info(f"Withdrew ${update.amount:.2f} from savings goal ID: {goal_id}")
    return goal

@app.get("/savings-goals/{goal_id}/progress")
def get_savings_goal_progress(
    goal_id: int,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key),
):
    """Get detailed progress information for a savings goal"""
    goal = session.get(SavingsGoal, goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Savings goal not found")

    from datetime import datetime

    # Calculate progress
    progress_percentage = (goal.current_amount / goal.target_amount * 100) if goal.target_amount > 0 else 0
    remaining_amount = goal.target_amount - goal.current_amount

    # Calculate time remaining
    try:
        deadline_date = datetime.strptime(goal.deadline, "%Y-%m-%d")
        today = datetime.now()
        days_remaining = (deadline_date - today).days

        # Calculate required savings rate
        if days_remaining > 0 and remaining_amount > 0:
            daily_required = remaining_amount / days_remaining
            weekly_required = daily_required * 7
            monthly_required = daily_required * 30
        else:
            daily_required = 0
            weekly_required = 0
            monthly_required = 0
    except ValueError:
        days_remaining = 0
        daily_required = 0
        weekly_required = 0
        monthly_required = 0

    # Determine status
    if progress_percentage >= 100:
        status = "completed"
    elif days_remaining < 0:
        status = "overdue"
    elif days_remaining < 30:
        status = "urgent"
    elif progress_percentage < 25:
        status = "just_started"
    elif progress_percentage < 50:
        status = "on_track"
    elif progress_percentage < 75:
        status = "halfway"
    else:
        status = "almost_there"

    return {
        "goal_id": goal_id,
        "goal_name": goal.name,
        "target_amount": goal.target_amount,
        "current_amount": goal.current_amount,
        "remaining_amount": remaining_amount,
        "progress_percentage": round(progress_percentage, 2),
        "deadline": goal.deadline,
        "days_remaining": days_remaining,
        "status": status,
        "required_savings": {
            "daily": round(daily_required, 2),
            "weekly": round(weekly_required, 2),
            "monthly": round(monthly_required, 2),
        },
        "is_achievable": days_remaining > 0 and remaining_amount >= 0,
    }

# ============================================
# ASSET MANAGEMENT ENDPOINTS
# ============================================

@app.post("/assets/", response_model=Asset)
def create_asset(
    asset: AssetCreate,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key),
):
    """Create a new asset"""
    # Validate user exists
    user = session.get(User, asset.user_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"User ID {asset.user_id} not found")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="User is inactive")

    # Create asset
    db_asset = Asset(
        **asset.model_dump(),
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat()
    )
    session.add(db_asset)
    session.commit()
    session.refresh(db_asset)

    logger.info(f"Created asset: {db_asset.name} ({db_asset.asset_type}) for user {asset.user_id}")
    return db_asset

@app.get("/assets/", response_model=list[Asset])
def list_assets(
    user_id: int | None = None,
    asset_type: str | None = None,
    is_active: bool = True,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key),
):
    """List assets with filters"""
    query = select(Asset).where(Asset.is_active == is_active)

    if user_id is not None:
        query = query.where(Asset.user_id == user_id)

    if asset_type:
        query = query.where(Asset.asset_type == asset_type)

    assets = session.exec(query.order_by(Asset.created_at.desc())).all()
    logger.info(f"Retrieved {len(assets)} assets")
    return list(assets)

@app.get("/assets/summary")
def get_assets_summary(
    user_id: int | None = None,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key),
):
    """Get summary of all assets"""
    query = select(Asset).where(Asset.is_active)

    if user_id is not None:
        query = query.where(Asset.user_id == user_id)

    assets = session.exec(query).all()

    if not assets:
        return {
            "message": "No assets found",
            "total_assets": 0,
            "total_purchase_value": 0,
            "total_current_value": 0,
        }

    # Calculate totals
    total_purchase = sum(a.purchase_value for a in assets)
    total_current = sum(a.current_value for a in assets)
    total_gain_loss = total_current - total_purchase
    gain_loss_percentage = (total_gain_loss / total_purchase * 100) if total_purchase > 0 else 0

    # Group by asset type
    by_type = {}
    for asset in assets:
        if asset.asset_type not in by_type:
            by_type[asset.asset_type] = {
                "count": 0,
                "purchase_value": 0,
                "current_value": 0,
            }
        by_type[asset.asset_type]["count"] += 1
        by_type[asset.asset_type]["purchase_value"] += asset.purchase_value
        by_type[asset.asset_type]["current_value"] += asset.current_value

    # Calculate gain/loss per type
    for asset_type in by_type:
        purchase = by_type[asset_type]["purchase_value"]
        current = by_type[asset_type]["current_value"]
        gain_loss = current - purchase
        by_type[asset_type]["gain_loss"] = round(gain_loss, 2)
        by_type[asset_type]["gain_loss_percentage"] = round(
            (gain_loss / purchase * 100) if purchase > 0 else 0, 2
        )

    # Group by user if not filtered
    by_user = {}
    if user_id is None:
        for asset in assets:
            user = session.get(User, asset.user_id)
            user_name = user.name if user else f"User {asset.user_id}"

            if user_name not in by_user:
                by_user[user_name] = {
                    "count": 0,
                    "total_value": 0,
                }
            by_user[user_name]["count"] += 1
            by_user[user_name]["total_value"] += asset.current_value

    return {
        "user_id": user_id,
        "total_assets": len(assets),
        "total_purchase_value": round(total_purchase, 2),
        "total_current_value": round(total_current, 2),
        "total_gain_loss": round(total_gain_loss, 2),
        "gain_loss_percentage": round(gain_loss_percentage, 2),
        "by_type": by_type,
        "by_user": by_user if by_user else None,
    }

@app.get("/assets/depreciation")
def get_asset_depreciation(
    user_id: int | None = None,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key),
):
    """Get depreciation analysis of assets"""
    query = select(Asset).where(Asset.is_active)

    if user_id is not None:
        query = query.where(Asset.user_id == user_id)

    assets = session.exec(query).all()

    if not assets:
        return {"message": "No assets found"}

    depreciation_list = []

    for asset in assets:
        depreciation = asset.purchase_value - asset.current_value
        depreciation_pct = (depreciation / asset.purchase_value * 100) if asset.purchase_value > 0 else 0

        # Calculate age in days
        from datetime import datetime
        try:
            purchase_date = datetime.strptime(asset.purchase_date, "%Y-%m-%d")
            age_days = (datetime.now() - purchase_date).days
            age_years = age_days / 365.25
        except ValueError:
            age_days = 0
            age_years = 0

        depreciation_list.append({
            "asset_id": asset.id,
            "name": asset.name,
            "type": asset.asset_type,
            "purchase_value": asset.purchase_value,
            "current_value": asset.current_value,
            "depreciation": round(depreciation, 2),
            "depreciation_percentage": round(depreciation_pct, 2),
            "age_years": round(age_years, 2),
            "annual_depreciation": round(depreciation / age_years, 2) if age_years > 0 else 0,
        })

    # Sort by depreciation percentage (highest first)
    depreciation_list.sort(key=lambda x: x["depreciation_percentage"], reverse=True)

    total_depreciation = sum(d["depreciation"] for d in depreciation_list)

    return {
        "user_id": user_id,
        "total_assets": len(assets),
        "total_depreciation": round(total_depreciation, 2),
        "assets": depreciation_list,
    }

@app.get("/assets/{asset_id}", response_model=Asset)
def get_asset(
    asset_id: int,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key),
):
    """Get specific asset"""
    asset = session.get(Asset, asset_id)
    if not asset:
        logger.warning(f"Asset ID {asset_id} not found")
        raise HTTPException(status_code=404, detail="Asset not found")

    logger.info(f"Retrieved asset: {asset.name} (ID: {asset_id})")
    return asset

@app.put("/assets/{asset_id}", response_model=Asset)
def update_asset(
    asset_id: int,
    asset_data: AssetCreate,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key),
):
    """Update asset details"""
    asset = session.get(Asset, asset_id)
    if not asset:
        logger.warning(f"Update failed: Asset ID {asset_id} not found")
        raise HTTPException(status_code=404, detail="Asset not found")

    # Validate user exists
    user = session.get(User, asset_data.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Update fields
    asset.user_id = asset_data.user_id
    asset.name = asset_data.name
    asset.asset_type = asset_data.asset_type
    asset.purchase_value = asset_data.purchase_value
    asset.current_value = asset_data.current_value
    asset.purchase_date = asset_data.purchase_date
    asset.description = asset_data.description
    asset.location = asset_data.location
    asset.updated_at = datetime.now().isoformat()

    session.add(asset)
    session.commit()
    session.refresh(asset)

    logger.info(f"Updated asset ID: {asset_id}")
    return asset

@app.delete("/assets/{asset_id}")
def delete_asset(
    asset_id: int,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key),
):
    """Deactivate an asset"""
    asset = session.get(Asset, asset_id)
    if not asset:
        logger.warning(f"Delete failed: Asset ID {asset_id} not found")
        raise HTTPException(status_code=404, detail="Asset not found")

    asset.is_active = False
    asset.updated_at = datetime.now().isoformat()
    session.add(asset)
    session.commit()

    logger.info(f"Deactivated asset ID: {asset_id}")
    return {"message": "Asset deactivated", "asset_id": asset_id}

@app.put("/assets/{asset_id}/value", response_model=Asset)
def update_asset_value(
    asset_id: int,
    value_update: AssetValueUpdate,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key),
):
    """Update current value of an asset"""
    asset = session.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    old_value = asset.current_value
    asset.current_value = value_update.current_value
    asset.updated_at = datetime.now().isoformat()

    session.add(asset)
    session.commit()
    session.refresh(asset)

    logger.info(f"Updated asset value ID: {asset_id} from ${old_value:.2f} to ${value_update.current_value:.2f}")
    return asset

# ============================================
# RECURRING EXPENSE ENDPOINTS
# ============================================

@app.post("/recurring-expenses/", response_model=RecurringExpenseTemplate)
def create_recurring_template(
    template: RecurringExpenseTemplateCreate,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key),
):
    """Create a recurring expense template"""
    # Validate user exists
    user = session.get(User, template.user_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"User ID {template.user_id} not found")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="User is inactive")
    
    # Validate credit card if provided
    if template.credit_card_id:
        card = session.get(CreditCard, template.credit_card_id)
        if not card:
            raise HTTPException(status_code=404, detail="Credit card not found")
        if not card.is_active:
            raise HTTPException(status_code=400, detail="Credit card is inactive")
    
    # Calculate next occurrence
    next_occurrence = calculate_next_occurrence(
        template.start_date,
        template.frequency,
        template.interval,
        template.day_of_week,
        template.day_of_month,
        template.month_of_year
    )
    
    # Create template
    db_template = RecurringExpenseTemplate(
        **template.model_dump(),
        next_occurrence=next_occurrence,
        created_at=datetime.now().isoformat()
    )
    session.add(db_template)
    session.commit()
    session.refresh(db_template)
    
    logger.info(f"Created recurring template: {db_template.description or db_template.category} for user {template.user_id}")
    return db_template

@app.get("/recurring-expenses/", response_model=list[RecurringExpenseTemplate])
def list_recurring_templates(
    user_id: int | None = None,
    is_active: bool = True,
    frequency: str | None = None,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key),
):
    """List recurring expense templates"""
    query = select(RecurringExpenseTemplate).where(RecurringExpenseTemplate.is_active == is_active)
    
    if user_id is not None:
        query = query.where(RecurringExpenseTemplate.user_id == user_id)
    
    if frequency:
        query = query.where(RecurringExpenseTemplate.frequency == frequency)
    
    templates = session.exec(query.order_by(RecurringExpenseTemplate.next_occurrence)).all()
    logger.info(f"Retrieved {len(templates)} recurring templates")
    return list(templates)

@app.get("/recurring-expenses/{template_id}", response_model=RecurringExpenseTemplate)
def get_recurring_template(
    template_id: int,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key),
):
    """Get specific recurring template"""
    template = session.get(RecurringExpenseTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Recurring template not found")
    return template

@app.put("/recurring-expenses/{template_id}", response_model=RecurringExpenseTemplate)
def update_recurring_template(
    template_id: int,
    template_data: RecurringExpenseTemplateCreate,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key),
):
    """Update recurring expense template"""
    template = session.get(RecurringExpenseTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Recurring template not found")
    
    # Validate user
    user = session.get(User, template_data.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Validate credit card if provided
    if template_data.credit_card_id:
        card = session.get(CreditCard, template_data.credit_card_id)
        if not card:
            raise HTTPException(status_code=404, detail="Credit card not found")
    
    # Update fields
    template.user_id = template_data.user_id
    template.amount = template_data.amount
    template.category = template_data.category
    template.description = template_data.description
    template.payment_method = template_data.payment_method
    template.credit_card_id = template_data.credit_card_id
    template.frequency = template_data.frequency
    template.interval = template_data.interval
    template.day_of_week = template_data.day_of_week
    template.day_of_month = template_data.day_of_month
    template.month_of_year = template_data.month_of_year
    template.start_date = template_data.start_date
    template.end_date = template_data.end_date
    template.tags = template_data.tags
    
    # Recalculate next occurrence
    template.next_occurrence = calculate_next_occurrence(
        template.start_date,
        template.frequency,
        template.interval,
        template.day_of_week,
        template.day_of_month,
        template.month_of_year
    )
    
    session.add(template)
    session.commit()
    session.refresh(template)
    
    logger.info(f"Updated recurring template ID: {template_id}")
    return template

@app.delete("/recurring-expenses/{template_id}")
def delete_recurring_template(
    template_id: int,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key),
):
    """Deactivate recurring expense template"""
    template = session.get(RecurringExpenseTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Recurring template not found")
    
    template.is_active = False
    session.add(template)
    session.commit()
    
    logger.info(f"Deactivated recurring template ID: {template_id}")
    return {"message": "Recurring template deactivated", "template_id": template_id}

@app.post("/recurring-expenses/{template_id}/generate", response_model=Expense)
def generate_expense_from_template(
    template_id: int,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key),
):
    """Manually generate an expense from a recurring template"""
    template = session.get(RecurringExpenseTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Recurring template not found")
    
    if not template.is_active:
        raise HTTPException(status_code=400, detail="Template is inactive")
    
    # Create expense from template
    expense = Expense(
        user_id=template.user_id,
        amount=template.amount,
        category=template.category,
        description=template.description,
        date=datetime.now().strftime("%Y-%m-%d"),
        payment_method=template.payment_method,
        credit_card_id=template.credit_card_id,
        is_recurring=True,
        tags=template.tags
    )
    
    session.add(expense)
    
    # Update template
    template.last_generated = datetime.now().strftime("%Y-%m-%d")
    template.next_occurrence = calculate_next_occurrence(
        template.next_occurrence,
        template.frequency,
        template.interval,
        template.day_of_week,
        template.day_of_month,
        template.month_of_year
    )
    session.add(template)
    
    session.commit()
    session.refresh(expense)
    
    logger.info(f"Generated expense from template ID: {template_id}")
    return expense

@app.get("/recurring-expenses/upcoming")
def get_upcoming_recurring_expenses(
    days: int = 7,
    user_id: int | None = None,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key),
):
    """Get upcoming recurring expenses within specified days"""
    from datetime import datetime, timedelta
    
    today = datetime.now().date()
    end_date = today + timedelta(days=days)
    
    query = select(RecurringExpenseTemplate).where(
        RecurringExpenseTemplate.is_active == True
    )
    
    if user_id is not None:
        query = query.where(RecurringExpenseTemplate.user_id == user_id)
    
    templates = session.exec(query).all()
    
    upcoming = []
    for template in templates:
        try:
            next_date = datetime.strptime(template.next_occurrence, "%Y-%m-%d").date()
            if today <= next_date <= end_date:
                days_until = (next_date - today).days
                upcoming.append({
                    "template_id": template.id,
                    "user_id": template.user_id,
                    "amount": template.amount,
                    "category": template.category,
                    "description": template.description,
                    "payment_method": template.payment_method,
                    "frequency": template.frequency,
                    "next_occurrence": template.next_occurrence,
                    "days_until": days_until,
                    "status": "today" if days_until == 0 else "upcoming"
                })
        except ValueError:
            continue
    
    # Sort by next occurrence
    upcoming.sort(key=lambda x: x["days_until"])
    
    return {
        "period": f"next {days} days",
        "user_id": user_id,
        "count": len(upcoming),
        "upcoming_expenses": upcoming
    }

@app.post("/recurring-expenses/{template_id}/skip")
def skip_next_occurrence(
    template_id: int,
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key),
):
    """Skip the next occurrence of a recurring expense"""
    template = session.get(RecurringExpenseTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Recurring template not found")
    
    if not template.is_active:
        raise HTTPException(status_code=400, detail="Template is inactive")
    
    old_next = template.next_occurrence
    
    # Calculate the occurrence after next
    template.next_occurrence = calculate_next_occurrence(
        template.next_occurrence,
        template.frequency,
        template.interval,
        template.day_of_week,
        template.day_of_month,
        template.month_of_year
    )
    
    session.add(template)
    session.commit()
    session.refresh(template)
    
    logger.info(f"Skipped occurrence for template ID: {template_id} from {old_next} to {template.next_occurrence}")
    return {
        "message": "Next occurrence skipped",
        "template_id": template_id,
        "old_next_occurrence": old_next,
        "new_next_occurrence": template.next_occurrence
    }

@app.post("/recurring-expenses/generate-due")
def generate_due_recurring_expenses(
    session: Session = Depends(get_session),
    api_key: str = Depends(verify_api_key),
):
    """Generate all recurring expenses that are due (next_occurrence <= today)"""
    from datetime import datetime
    
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Find all templates that are due
    templates = session.exec(
        select(RecurringExpenseTemplate).where(
            RecurringExpenseTemplate.is_active == True,
            RecurringExpenseTemplate.next_occurrence <= today
        )
    ).all()
    
    generated = []
    errors = []
    
    for template in templates:
        try:
            # Create expense
            expense = Expense(
                user_id=template.user_id,
                amount=template.amount,
                category=template.category,
                description=template.description,
                date=template.next_occurrence,
                payment_method=template.payment_method,
                credit_card_id=template.credit_card_id,
                is_recurring=True,
                tags=template.tags
            )
            
            session.add(expense)
            
            # Update template
            template.last_generated = template.next_occurrence
            template.next_occurrence = calculate_next_occurrence(
                template.next_occurrence,
                template.frequency,
                template.interval,
                template.day_of_week,
                template.day_of_month,
                template.month_of_year
            )
            session.add(template)
            
            generated.append({
                "template_id": template.id,
                "expense_id": None,  # Will be set after commit
                "amount": template.amount,
                "category": template.category,
                "date": expense.date
            })
            
        except Exception as e:
            errors.append({
                "template_id": template.id,
                "error": str(e)
            })
    
    session.commit()
    
    logger.info(f"Generated {len(generated)} recurring expenses, {len(errors)} errors")
    return {
        "generated_count": len(generated),
        "error_count": len(errors),
        "generated": generated,
        "errors": errors
    }

# Helper function for calculating next occurrence
def calculate_next_occurrence(
    current_date: str,
    frequency: str,
    interval: int,
    day_of_week: int | None,
    day_of_month: int | None,
    month_of_year: int | None
) -> str:
    """Calculate the next occurrence date based on frequency and parameters"""
    from datetime import datetime, timedelta
    from dateutil.relativedelta import relativedelta
    
    try:
        current = datetime.strptime(current_date, "%Y-%m-%d")
    except ValueError:
        return datetime.now().strftime("%Y-%m-%d")
    
    if frequency == "daily":
        next_date = current + timedelta(days=interval)
    
    elif frequency == "weekly":
        # Add weeks
        next_date = current + timedelta(weeks=interval)
        # Adjust to specific day of week if provided
        if day_of_week is not None:
            days_ahead = day_of_week - next_date.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            next_date = next_date + timedelta(days=days_ahead)
    
    elif frequency == "monthly":
        next_date = current + relativedelta(months=interval)
        # Adjust to specific day of month if provided
        if day_of_month is not None:
            try:
                next_date = next_date.replace(day=day_of_month)
            except ValueError:
                # Handle invalid dates (e.g., Feb 31)
                next_date = next_date.replace(day=1) + relativedelta(months=1) - timedelta(days=1)
    
    elif frequency == "yearly":
        next_date = current + relativedelta(years=interval)
        # Adjust to specific month and day if provided
        if month_of_year is not None:
            next_date = next_date.replace(month=month_of_year)
        if day_of_month is not None:
            try:
                next_date = next_date.replace(day=day_of_month)
            except ValueError:
                next_date = next_date.replace(day=1) + relativedelta(months=1) - timedelta(days=1)
    
    elif frequency == "custom":
        # For custom, just add interval days
        next_date = current + timedelta(days=interval)
    
    else:
        next_date = current + timedelta(days=1)
    
    return next_date.strftime("%Y-%m-%d")