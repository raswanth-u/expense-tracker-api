"""Family Expense Tracker API - Refactored with Service Layer."""

import os
from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from decimal import Decimal

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
    CreditCardPayment,
    CreditCardTransaction,
    DebitCard,
    DebitCardCreate,
    Expense,
    ExpenseCreate,
    RecurringExpenseTemplate,
    RecurringExpenseTemplateCreate,
    SavingsAccount,
    SavingsAccountCreate,
    SavingsAccountDeposit,
    SavingsAccountTransaction,
    SavingsAccountWithdraw,
    SavingsGoal,
    SavingsGoalCreate,
    SavingsGoalUpdate,
    User,
    UserCreate,
)
from services import (
    AssetService,
    BudgetService,
    CreditCardService,
    CRUDService,
    ExpenseService,
    RecurringExpenseService,
    SavingsAccountService,
    SavingsGoalService,
    UserService,
)
from utils import (
    calculate_next_occurrence,
    calculate_percentage,
    current_month,
    get_month_exclusive_range,
    get_or_404,
    group_by_field,
    now_iso,
    parse_month,
    today_str,
)

# Load environment variables
load_dotenv()

logger = setup_logging()
logger.info("Starting Family Expense Tracker API...")

# Security
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    expected = os.getenv("API_KEY", "dev-key-change-in-prod")
    if api_key != expected:
        logger.warning("Authentication failed: Invalid API key")
        raise HTTPException(status_code=403, detail="Could not validate credentials")
    return api_key


# Database setup
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


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


app = FastAPI(
    title="Family Expense Tracker API",
    description="Track expenses, budgets, and credit cards for family members",
    version="3.0.0",
    lifespan=lifespan,
)


# Common dependencies
SessionDep = Depends(get_session)
AuthDep = Depends(verify_api_key)


@app.get("/health")
def health_check():
    return "OK"


# ============================================
# USER ENDPOINTS
# ============================================


@app.post("/users/", response_model=User)
def create_user(user: UserCreate, session: Session = SessionDep, _: str = AuthDep):
    db_user = UserService.create(session, user)
    logger.info(f"Created user: {db_user.name} (ID: {db_user.id})")
    return db_user


@app.get("/users/", response_model=list[User])
def get_users(is_active: bool | None = None, session: Session = SessionDep, _: str = AuthDep):
    filters = {"is_active": is_active} if is_active is not None else {}
    return CRUDService.list_all(session, User, filters)


@app.get("/users/{user_id}", response_model=User)
def get_user(user_id: int, session: Session = SessionDep, _: str = AuthDep):
    return get_or_404(session, User, user_id, "User")


@app.put("/users/{user_id}", response_model=User)
def update_user(user_id: int, data: UserCreate, session: Session = SessionDep, _: str = AuthDep):
    user = get_or_404(session, User, user_id, "User")
    updated = UserService.update(session, user, data)
    logger.info(f"Updated user: {updated.name} (ID: {user_id})")
    return updated


@app.delete("/users/{user_id}")
def delete_user(user_id: int, hard: bool = False, session: Session = SessionDep, _: str = AuthDep):
    user = get_or_404(session, User, user_id, "User")
    if hard:
        # Cascade delete all dependent records in FK-safe order
        from sqlmodel import delete, update

        # 1. Clear FK references from transactions to assets/expenses belonging to this user
        # (transactions of OTHER users might reference this user's assets/expenses)
        session.exec(
            update(SavingsAccountTransaction)
            .where(SavingsAccountTransaction.related_asset_id.in_(
                select(Asset.id).where(Asset.user_id == user_id)
            ))
            .values(related_asset_id=None)
        )
        session.exec(
            update(SavingsAccountTransaction)
            .where(SavingsAccountTransaction.related_expense_id.in_(
                select(Expense.id).where(Expense.user_id == user_id)
            ))
            .values(related_expense_id=None)
        )
        session.exec(
            update(CreditCardTransaction)
            .where(CreditCardTransaction.related_asset_id.in_(
                select(Asset.id).where(Asset.user_id == user_id)
            ))
            .values(related_asset_id=None)
        )
        session.exec(
            update(CreditCardTransaction)
            .where(CreditCardTransaction.related_expense_id.in_(
                select(Expense.id).where(Expense.user_id == user_id)
            ))
            .values(related_expense_id=None)
        )

        # 2. Delete transactions belonging to this user
        session.exec(delete(SavingsAccountTransaction).where(
            SavingsAccountTransaction.savings_account_id.in_(
                select(SavingsAccount.id).where(SavingsAccount.user_id == user_id)
            )
        ))
        session.exec(delete(CreditCardTransaction).where(
            CreditCardTransaction.credit_card_id.in_(
                select(CreditCard.id).where(CreditCard.user_id == user_id)
            )
        ))

        # 3. Delete expenses (they reference users, cards, accounts)
        session.exec(delete(Expense).where(Expense.user_id == user_id))

        # 4. Delete recurring expense templates
        session.exec(delete(RecurringExpenseTemplate).where(RecurringExpenseTemplate.user_id == user_id))

        # 5. Delete assets BEFORE savings accounts (assets have FK to savings_account_id)
        session.exec(delete(Asset).where(Asset.user_id == user_id))

        # 6. Delete debit cards (reference savings accounts)
        session.exec(delete(DebitCard).where(
            DebitCard.savings_account_id.in_(
                select(SavingsAccount.id).where(SavingsAccount.user_id == user_id)
            )
        ))

        # 7. Delete credit cards
        session.exec(delete(CreditCard).where(CreditCard.user_id == user_id))

        # 8. Delete savings accounts
        session.exec(delete(SavingsAccount).where(SavingsAccount.user_id == user_id))

        # 9. Delete savings goals
        session.exec(delete(SavingsGoal).where(SavingsGoal.user_id == user_id))

        # 10. Delete budgets
        session.exec(delete(Budget).where(Budget.user_id == user_id))

        session.commit()

        return CRUDService.hard_delete(session, user)
    CRUDService.soft_delete(session, user)
    logger.info(f"Deactivated user ID: {user_id}")
    return {"message": "User deactivated successfully", "user_id": user_id, "name": user.name}


@app.get("/users/{user_id}/stats")
def get_user_stats(user_id: int, month: str | None = None, session: Session = SessionDep, _: str = AuthDep):
    user = get_or_404(session, User, user_id, "User")
    return UserService.get_stats(session, user, month)


# ============================================
# BUDGET ENDPOINTS
# ============================================


@app.post("/budgets/", response_model=Budget)
def create_budget(budget: BudgetCreate, session: Session = SessionDep, _: str = AuthDep):
    db_budget = BudgetService.validate_and_create(session, budget)
    logger.info(f"Created budget: {db_budget.category} - ${db_budget.amount}")
    return db_budget


@app.get("/budgets/", response_model=list[Budget])
def get_budgets(
    month: str | None = None,
    user_id: int | None = None,
    category: str | None = None,
    is_active: bool = True,
    session: Session = SessionDep,
    _: str = AuthDep
):
    query = select(Budget).where(Budget.is_active == is_active)
    if month:
        query = query.where(Budget.month == month)
    if user_id is not None:
        query = query.where(Budget.user_id == user_id)
    if category:
        query = query.where(Budget.category == category)
    return list(session.exec(query).all())


@app.get("/budgets/status/summary")
def get_budget_status(month: str, user_id: int | None = None, session: Session = SessionDep, _: str = AuthDep):
    return BudgetService.get_status(session, month, user_id)


@app.get("/budgets/status/alerts")
def get_budget_alerts(month: str, user_id: int | None = None, session: Session = SessionDep, _: str = AuthDep):
    status = BudgetService.get_status(session, month, user_id)
    alerts = [b for b in status["budgets"] if b["status"] in ["warning", "exceeded"]]
    return {"month": month, "user_id": user_id, "alert_count": len(alerts), "alerts": alerts}


@app.get("/budgets/compare")
def compare_budgets(month1: str, month2: str, user_id: int | None = None, session: Session = SessionDep, _: str = AuthDep):
    status1 = BudgetService.get_status(session, month1, user_id)
    status2 = BudgetService.get_status(session, month2, user_id)

    categories = {b["category"] for b in status1.get("budgets", [])} | {b["category"] for b in status2.get("budgets", [])}
    comparisons = []

    for category in sorted(categories):
        cat1 = next((b for b in status1.get("budgets", []) if b["category"] == category), None)
        cat2 = next((b for b in status2.get("budgets", []) if b["category"] == category), None)
        spent1, spent2 = (cat1["spent"] if cat1 else 0), (cat2["spent"] if cat2 else 0)
        change = spent2 - spent1

        comparisons.append({
            "category": category,
            f"{month1}_spent": spent1,
            f"{month2}_spent": spent2,
            "change": round(change, 2),
            "change_percentage": round((change / spent1 * 100) if spent1 > 0 else 0, 2),
            "trend": "increased" if change > 0 else "decreased" if change < 0 else "stable",
        })

    total1 = status1.get("total_spent", 0)
    total2 = status2.get("total_spent", 0)

    return {
        "month1": month1, "month2": month2, "user_id": user_id,
        "total_change": round(total2 - total1, 2),
        "categories": comparisons,
    }


@app.get("/budgets/{budget_id}", response_model=Budget)
def get_budget(budget_id: int, session: Session = SessionDep, _: str = AuthDep):
    return get_or_404(session, Budget, budget_id, "Budget")


@app.put("/budgets/{budget_id}", response_model=Budget)
def update_budget(budget_id: int, data: BudgetCreate, session: Session = SessionDep, _: str = AuthDep):
    budget = get_or_404(session, Budget, budget_id, "Budget")
    return CRUDService.update(session, budget, data)


@app.delete("/budgets/{budget_id}")
def delete_budget(budget_id: int, session: Session = SessionDep, _: str = AuthDep):
    budget = get_or_404(session, Budget, budget_id, "Budget")
    return CRUDService.soft_delete(session, budget)


# ============================================
# EXPENSE ENDPOINTS
# ============================================


@app.post("/expenses/", response_model=Expense)
def create_expense(expense: ExpenseCreate, session: Session = SessionDep, _: str = AuthDep):
    db_expense = ExpenseService.validate_and_create(session, expense)
    logger.info(f"Created expense: ${db_expense.amount} - {db_expense.category}")
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
    session: Session = SessionDep,
    _: str = AuthDep
):
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
    return list(session.exec(query).all())


@app.get("/expenses/summary")
def get_expense_summary(from_date: str | None = None, to_date: str | None = None, user_id: int | None = None, session: Session = SessionDep, _: str = AuthDep):
    return ExpenseService.get_summary(session, "category", from_date, to_date, user_id)


@app.get("/expenses/payment_summary")
def get_payment_summary(from_date: str | None = None, to_date: str | None = None, user_id: int | None = None, session: Session = SessionDep, _: str = AuthDep):
    return ExpenseService.get_summary(session, "payment_method", from_date, to_date, user_id)


@app.get("/expenses/{expense_id}", response_model=Expense)
def get_expense(expense_id: int, session: Session = SessionDep, _: str = AuthDep):
    return get_or_404(session, Expense, expense_id, "Expense")


@app.get("/expenses/{expense_id}/details")
def get_expense_details(expense_id: int, session: Session = SessionDep, _: str = AuthDep):
    """Get expense with all linked details (user, card, transactions)."""
    expense = get_or_404(session, Expense, expense_id, "Expense")
    user = get_or_404(session, User, expense.user_id, "User")

    result = {
        "expense": expense,
        "user": {"id": user.id, "name": user.name, "email": user.email, "role": user.role, "is_active": user.is_active},
        "credit_card": None,
        "credit_card_transaction": None,
        "savings_account": None,
        "savings_transaction": None,
    }

    # Get credit card info if applicable
    if expense.credit_card_id:
        card = session.get(CreditCard, expense.credit_card_id)
        if card:
            result["credit_card"] = {
                "id": card.id,
                "user_id": card.user_id,
                "card_name": card.card_name,
                "last_four": card.last_four,
                "credit_limit": card.credit_limit,
                "billing_day": card.billing_day,
                "tags": card.tags,
                "is_active": card.is_active,
            }
            # Get linked transaction
            txn = session.exec(
                select(CreditCardTransaction)
                .where(CreditCardTransaction.related_expense_id == expense_id)
            ).first()
            if txn:
                result["credit_card_transaction"] = txn

    # Get savings account info if applicable
    if expense.savings_account_id:
        account = session.get(SavingsAccount, expense.savings_account_id)
        if account:
            result["savings_account"] = {
                "id": account.id,
                "user_id": account.user_id,
                "account_name": account.account_name,
                "bank_name": account.bank_name,
                "account_number_last_four": account.account_number_last_four,
                "account_type": account.account_type,
                "current_balance": account.current_balance,
                "minimum_balance": account.minimum_balance,
                "interest_rate": account.interest_rate,
                "tags": account.tags,
                "is_active": account.is_active,
                "created_at": account.created_at,
            }
            # Get linked transaction
            txn = session.exec(
                select(SavingsAccountTransaction)
                .where(SavingsAccountTransaction.related_expense_id == expense_id)
            ).first()
            if txn:
                result["savings_transaction"] = txn

    return result


@app.put("/expenses/{expense_id}", response_model=Expense)
def update_expense(expense_id: int, data: ExpenseCreate, session: Session = SessionDep, _: str = AuthDep):
    expense = get_or_404(session, Expense, expense_id, "Expense")
    return ExpenseService.validate_and_update(session, expense, data)


@app.delete("/expenses/{expense_id}")
def delete_expense(expense_id: int, session: Session = SessionDep, _: str = AuthDep):
    expense = get_or_404(session, Expense, expense_id, "Expense")

    # First, clear any related transaction references
    from sqlmodel import update

    # Clear savings account transaction references
    session.exec(
        update(SavingsAccountTransaction)
        .where(SavingsAccountTransaction.related_expense_id == expense_id)
        .values(related_expense_id=None)
    )

    # Clear credit card transaction references
    session.exec(
        update(CreditCardTransaction)
        .where(CreditCardTransaction.related_expense_id == expense_id)
        .values(related_expense_id=None)
    )

    session.commit()

    return CRUDService.hard_delete(session, expense)


# ============================================
# CREDIT CARD ENDPOINTS
# ============================================


@app.post("/credit-cards/", response_model=CreditCard)
def create_credit_card(card: CreditCardCreate, session: Session = SessionDep, _: str = AuthDep):
    db_card = CreditCardService.validate_and_create(session, card)
    logger.info(f"Created credit card: {db_card.card_name}")
    return db_card


@app.get("/credit-cards/", response_model=list[CreditCard])
def get_credit_cards(user_id: int | None = None, is_active: bool = True, session: Session = SessionDep, _: str = AuthDep):
    query = select(CreditCard).where(CreditCard.is_active == is_active)
    if user_id is not None:
        query = query.where(CreditCard.user_id == user_id)
    return list(session.exec(query).all())


@app.get("/credit-cards/summary")
def get_all_cards_summary(user_id: int | None = None, month: str | None = None, session: Session = SessionDep, _: str = AuthDep):
    query = select(CreditCard).where(CreditCard.is_active)
    if user_id is not None:
        query = query.where(CreditCard.user_id == user_id)

    cards = list(session.exec(query).all())
    if not cards:
        return {"message": "No active credit cards found", "cards": []}

    month = month or current_month()
    start_date, end_date = get_month_exclusive_range(month)

    summaries = []
    total_limit, total_spent = Decimal("0"), Decimal("0")

    for card in cards:
        spent = session.exec(
            select(func.sum(Expense.amount)).where(
                Expense.credit_card_id == card.id,
                Expense.date >= start_date,
                Expense.date < end_date
            )
        ).one() or Decimal("0")

        total_limit += card.credit_limit
        total_spent += spent

        summaries.append({
            "card_id": card.id,
            "card_name": card.card_name,
            "last_four": card.last_four,
            "credit_limit": card.credit_limit,
            "spent": round(spent, 2),
            "available": round(card.credit_limit - spent, 2),
            "utilization": calculate_percentage(spent, card.credit_limit),
        })

    return {
        "month": month,
        "user_id": user_id,
        "total_cards": len(cards),
        "total_credit_limit": round(total_limit, 2),
        "total_spent": round(total_spent, 2),
        "total_available": round(total_limit - total_spent, 2),
        "overall_utilization": calculate_percentage(total_spent, total_limit),
        "cards": summaries,
    }


@app.get("/credit-cards/{card_id}", response_model=CreditCard)
def get_credit_card(card_id: int, session: Session = SessionDep, _: str = AuthDep):
    return get_or_404(session, CreditCard, card_id, "Credit card")


@app.put("/credit-cards/{card_id}", response_model=CreditCard)
def update_credit_card(card_id: int, data: CreditCardCreate, session: Session = SessionDep, _: str = AuthDep):
    card = get_or_404(session, CreditCard, card_id, "Credit card")
    return CRUDService.update(session, card, data)


@app.delete("/credit-cards/{card_id}")
def delete_credit_card(card_id: int, session: Session = SessionDep, _: str = AuthDep):
    card = get_or_404(session, CreditCard, card_id, "Credit card")
    return CRUDService.soft_delete(session, card)


@app.get("/credit-cards/{card_id}/statement")
def get_credit_card_statement(card_id: int, month: str, session: Session = SessionDep, _: str = AuthDep):
    card = get_or_404(session, CreditCard, card_id, "Credit card")
    year, month_num = parse_month(month)

    # Calculate billing cycle dates
    billing_day = card.billing_day
    current_billing = f"{year}-{month_num:02d}-{billing_day:02d}"
    prev_year, prev_month = (year - 1, 12) if month_num == 1 else (year, month_num - 1)
    prev_billing = f"{prev_year}-{prev_month:02d}-{billing_day:02d}"

    expenses = list(session.exec(
        select(Expense)
        .where(Expense.credit_card_id == card_id, Expense.date >= prev_billing, Expense.date < current_billing)
        .order_by(Expense.date)
    ).all())

    total_spent = sum(e.amount for e in expenses)
    by_category = group_by_field(expenses, "category")
    utilization = calculate_percentage(total_spent, card.credit_limit)

    return {
        "card_name": card.card_name,
        "last_four": card.last_four,
        "billing_cycle": {"start": prev_billing, "end": current_billing, "billing_day": billing_day},
        "summary": {
            "total_spent": round(total_spent, 2),
            "transaction_count": len(expenses),
            "credit_limit": card.credit_limit,
            "available_credit": round(card.credit_limit - total_spent, 2),
            "utilization_percentage": utilization,
        },
        "by_category": {k: round(v, 2) for k, v in by_category.items()},
        "transactions": [{"date": e.date, "category": e.category, "description": e.description, "amount": e.amount} for e in expenses],
    }


@app.get("/credit-cards/{card_id}/utilization")
def get_credit_card_utilization(card_id: int, months: int = 3, session: Session = SessionDep, _: str = AuthDep):
    card = get_or_404(session, CreditCard, card_id, "Credit card")
    today = datetime.now()
    history = []

    for i in range(months):
        month_date = today - timedelta(days=30 * i)
        month_str = month_date.strftime("%Y-%m")
        start_date, end_date = get_month_exclusive_range(month_str)

        spent = session.exec(
            select(func.sum(Expense.amount)).where(
                Expense.credit_card_id == card_id,
                Expense.date >= start_date,
                Expense.date < end_date
            )
        ).one() or Decimal("0")

        history.append({
            "month": month_str,
            "spent": round(spent, 2),
            "utilization": calculate_percentage(spent, card.credit_limit)
        })

    history.reverse()
    avg_util = sum(h["utilization"] for h in history) / len(history)

    return {
        "card_name": card.card_name,
        "last_four": card.last_four,
        "credit_limit": card.credit_limit,
        "months_analyzed": months,
        "average_utilization": round(avg_util, 2),
        "history": history,
        "recommendation": (
            "Good! Keep utilization below 30%" if avg_util < 30
            else "Consider paying down balance" if avg_util < 70
            else "High utilization - pay down urgently"
        ),
    }


@app.get("/credit-cards/{card_id}/transactions")
def get_credit_card_transactions(
    card_id: int,
    from_date: str | None = None,
    to_date: str | None = None,
    transaction_type: str | None = None,
    session: Session = SessionDep,
    _: str = AuthDep
):
    """Get credit card transaction history."""
    get_or_404(session, CreditCard, card_id, "Credit card")
    query = select(CreditCardTransaction).where(CreditCardTransaction.credit_card_id == card_id)
    if from_date:
        query = query.where(CreditCardTransaction.date >= from_date)
    if to_date:
        query = query.where(CreditCardTransaction.date <= to_date)
    if transaction_type:
        query = query.where(CreditCardTransaction.transaction_type == transaction_type)
    return list(session.exec(query.order_by(CreditCardTransaction.date.desc())).all())


@app.post("/credit-cards/{card_id}/payment")
def make_credit_card_payment(card_id: int, payment: CreditCardPayment, session: Session = SessionDep, _: str = AuthDep):
    """Record a payment to the credit card."""
    from sqlalchemy import case
    card = get_or_404(session, CreditCard, card_id, "Credit card")

    # Calculate current balance from transactions
    current_balance = session.exec(
        select(func.sum(
            case(
                (CreditCardTransaction.transaction_type.in_(["charge", "fee"]), CreditCardTransaction.amount),
                else_=-CreditCardTransaction.amount
            )
        )).where(CreditCardTransaction.credit_card_id == card_id)
    ).one() or Decimal("0")

    new_balance = current_balance - payment.amount

    # Create transaction record
    txn = CreditCardTransaction(
        credit_card_id=card_id,
        transaction_type="payment",
        amount=payment.amount,
        balance_after=new_balance,
        date=payment.date or today_str(),
        description=payment.description or "Card payment",
        created_at=now_iso(),
    )
    session.add(txn)

    # If paying from savings account, record withdrawal
    if payment.source_savings_account_id:
        account = get_or_404(session, SavingsAccount, payment.source_savings_account_id, "Savings account")
        if account.current_balance < payment.amount:
            raise HTTPException(status_code=400, detail="Insufficient balance in savings account")
        account.current_balance -= payment.amount
        session.add(account)

        savings_txn = SavingsAccountTransaction(
            savings_account_id=payment.source_savings_account_id,
            transaction_type="withdrawal",
            amount=payment.amount,
            balance_after=account.current_balance,
            date=payment.date or today_str(),
            description=f"Credit card payment: {card.card_name}",
            created_at=now_iso(),
        )
        session.add(savings_txn)

    session.commit()
    session.refresh(txn)
    return txn


# ============================================
# DEBIT CARD ENDPOINTS
# ============================================


@app.post("/debit-cards/", response_model=DebitCard)
def create_debit_card(card: DebitCardCreate, session: Session = SessionDep, _: str = AuthDep):
    """Create a new debit card linked to a savings account."""
    # Verify the savings account exists
    account = get_or_404(session, SavingsAccount, card.savings_account_id, "Savings account")
    
    # IMPORTANT: Debit card owner must be the same as account owner
    if card.user_id != account.user_id:
        raise HTTPException(
            status_code=400,
            detail=f"Debit card owner (User {card.user_id}) must match savings account owner (User {account.user_id})"
        )

    db_card = DebitCard(
        user_id=card.user_id,
        card_name=card.card_name,
        last_four=card.last_four,
        savings_account_id=card.savings_account_id,
        daily_limit=card.daily_limit,
        tags=card.tags,
        created_at=now_iso(),
    )
    session.add(db_card)
    session.commit()
    session.refresh(db_card)
    logger.info(f"Created debit card: {db_card.card_name} linked to account {db_card.savings_account_id}")
    return db_card


@app.get("/debit-cards/")
def list_debit_cards(
    user_id: int | None = None,
    active: bool | None = None,
    session: Session = SessionDep,
    _: str = AuthDep,
):
    """List debit cards with optional filters."""
    query = select(DebitCard)
    if user_id is not None:
        query = query.where(DebitCard.user_id == user_id)
    if active is not None:
        query = query.where(DebitCard.is_active == active)

    cards = list(session.exec(query.order_by(DebitCard.id)).all())
    return cards


@app.get("/debit-cards/{card_id}")
def get_debit_card(card_id: int, session: Session = SessionDep, _: str = AuthDep):
    """Get debit card details including linked savings account."""
    card = get_or_404(session, DebitCard, card_id, "Debit card")
    account = session.get(SavingsAccount, card.savings_account_id)
    return {
        "card": card,
        "linked_account": account,
    }


@app.put("/debit-cards/{card_id}")
def update_debit_card(card_id: int, card_data: DebitCardCreate, session: Session = SessionDep, _: str = AuthDep):
    """Update a debit card."""
    card = get_or_404(session, DebitCard, card_id, "Debit card")
    for key, value in card_data.model_dump(exclude_unset=True).items():
        setattr(card, key, value)
    session.commit()
    session.refresh(card)
    return card


@app.delete("/debit-cards/{card_id}")
def delete_debit_card(card_id: int, session: Session = SessionDep, _: str = AuthDep):
    """Delete a debit card."""
    card = get_or_404(session, DebitCard, card_id, "Debit card")
    session.delete(card)
    session.commit()
    return {"message": f"Debit card {card_id} deleted"}


@app.get("/debit-cards/{card_id}/transactions")
def get_debit_card_transactions(
    card_id: int,
    from_date: str | None = None,
    to_date: str | None = None,
    session: Session = SessionDep,
    _: str = AuthDep,
):
    """Get transactions for a debit card (from linked savings account)."""
    card = get_or_404(session, DebitCard, card_id, "Debit card")

    # Get transactions from the linked savings account
    query = select(SavingsAccountTransaction).where(
        SavingsAccountTransaction.savings_account_id == card.savings_account_id
    )

    if from_date:
        query = query.where(SavingsAccountTransaction.date >= from_date)
    if to_date:
        query = query.where(SavingsAccountTransaction.date <= to_date)

    transactions = list(session.exec(query.order_by(SavingsAccountTransaction.id.desc())).all())
    return transactions


# ============================================
# REPORTS ENDPOINTS
# ============================================


@app.get("/reports/monthly")
def get_monthly_report(month: str, user_id: int | None = None, session: Session = SessionDep, _: str = AuthDep):
    start_date, end_date = get_month_exclusive_range(month)

    query = select(Expense).where(Expense.date >= start_date, Expense.date < end_date)
    if user_id is not None:
        query = query.where(Expense.user_id == user_id)

    expenses = list(session.exec(query).all())

    if not expenses:
        return {"month": month, "user_id": user_id, "message": "No expenses found", "total_spent": 0, "transaction_count": 0}

    total = sum(e.amount for e in expenses)
    by_category = group_by_field(expenses, "category")
    by_payment = group_by_field(expenses, "payment_method")
    by_date = {}
    for e in expenses:
        by_date[e.date] = by_date.get(e.date, 0) + e.amount

    # Budget comparison
    budget_comparison = None
    if user_id:
        budgets = list(session.exec(
            select(Budget).where(Budget.user_id == user_id, Budget.month == month, Budget.is_active)
        ).all())
        if budgets:
            total_budget = sum(b.amount for b in budgets)
            budget_comparison = {
                "total_budget": total_budget,
                "total_spent": total,
                "remaining": total_budget - total,
                "percentage": calculate_percentage(total, total_budget),
            }

    recurring = [e for e in expenses if e.is_recurring]
    top5 = sorted(expenses, key=lambda x: x.amount, reverse=True)[:5]

    return {
        "month": month,
        "user_id": user_id,
        "period": f"{start_date} to {end_date}",
        "summary": {
            "total_spent": round(total, 2),
            "transaction_count": len(expenses),
            "average_transaction": round(total / len(expenses), 2),
            "largest_expense": round(max(e.amount for e in expenses), 2),
            "smallest_expense": round(min(e.amount for e in expenses), 2),
        },
        "by_category": {k: round(v, 2) for k, v in sorted(by_category.items(), key=lambda x: x[1], reverse=True)},
        "by_payment_method": {k: round(v, 2) for k, v in by_payment.items()},
        "budget_comparison": budget_comparison,
        "top_expenses": [{"date": e.date, "category": e.category, "description": e.description, "amount": e.amount} for e in top5],
        "recurring_expenses": {"count": len(recurring), "total": round(sum(e.amount for e in recurring), 2)},
        "daily_trend": {k: round(by_date[k], 2) for k in sorted(by_date.keys())},
    }


@app.get("/reports/family-summary")
def get_family_summary(month: str, session: Session = SessionDep, _: str = AuthDep):
    users = list(session.exec(select(User).where(User.is_active)).all())
    if not users:
        return {"month": month, "message": "No active users found", "members": []}

    start_date, end_date = get_month_exclusive_range(month)
    summaries = []
    total_family = 0

    for user in users:
        expenses = list(session.exec(
            select(Expense).where(Expense.user_id == user.id, Expense.date >= start_date, Expense.date < end_date)
        ).all())

        spent = sum(e.amount for e in expenses)
        total_family += spent

        budgets = list(session.exec(
            select(Budget).where(Budget.user_id == user.id, Budget.month == month, Budget.is_active)
        ).all())
        total_budget = sum(b.amount for b in budgets)

        by_category = group_by_field(expenses, "category")
        top_cat = max(by_category.items(), key=lambda x: x[1]) if by_category else ("None", 0)

        summaries.append({
            "user_id": user.id,
            "name": user.name,
            "total_spent": round(spent, 2),
            "transaction_count": len(expenses),
            "budget": round(total_budget, 2) if budgets else None,
            "budget_status": "within_budget" if total_budget > 0 and spent <= total_budget else "over_budget" if total_budget > 0 else "no_budget",
            "top_category": {"name": top_cat[0], "amount": round(top_cat[1], 2)},
        })

    summaries.sort(key=lambda x: x["total_spent"], reverse=True)

    return {
        "month": month,
        "period": f"{start_date} to {end_date}",
        "family_total": round(total_family, 2),
        "member_count": len(users),
        "average_per_member": round(total_family / len(users), 2),
        "members": summaries,
    }


@app.get("/reports/category-analysis")
def get_category_analysis(category: str, from_date: str, to_date: str, user_id: int | None = None, session: Session = SessionDep, _: str = AuthDep):
    query = select(Expense).where(Expense.category == category, Expense.date >= from_date, Expense.date <= to_date)
    if user_id is not None:
        query = query.where(Expense.user_id == user_id)

    expenses = list(session.exec(query).all())
    if not expenses:
        return {"category": category, "message": "No expenses found", "total": 0}

    amounts = [e.amount for e in expenses]
    total = sum(amounts)
    by_payment = group_by_field(expenses, "payment_method")

    by_month = {}
    for e in expenses:
        m = e.date.strftime("%Y-%m")
        by_month[m] = by_month.get(m, 0) + e.amount

    by_user = {}
    if user_id is None:
        for e in expenses:
            user = session.get(User, e.user_id)
            name = user.name if user else f"User {e.user_id}"
            by_user[name] = by_user.get(name, 0) + e.amount

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
            {"date": e.date, "description": e.description, "amount": e.amount, "payment_method": e.payment_method}
            for e in sorted(expenses, key=lambda x: x.date, reverse=True)[:10]
        ],
    }


@app.get("/reports/spending-trends")
def get_spending_trends(months: int = 6, user_id: int | None = None, session: Session = SessionDep, _: str = AuthDep):
    today = datetime.now()
    monthly_data = []

    for i in range(months):
        month_date = today - timedelta(days=30 * i)
        month_str = month_date.strftime("%Y-%m")
        start_date, end_date = get_month_exclusive_range(month_str)

        query = select(Expense).where(Expense.date >= start_date, Expense.date < end_date)
        if user_id is not None:
            query = query.where(Expense.user_id == user_id)

        expenses = list(session.exec(query).all())
        total = sum(e.amount for e in expenses)
        by_cat = group_by_field(expenses, "category")
        top_cat = max(by_cat.items(), key=lambda x: x[1]) if by_cat else ("None", 0)

        monthly_data.append({
            "month": month_str,
            "total_spent": round(total, 2),
            "transaction_count": len(expenses),
            "top_category": {"name": top_cat[0], "amount": round(top_cat[1], 2)},
        })

    monthly_data.reverse()

    if len(monthly_data) >= 2:
        recent = float(sum(m["total_spent"] for m in monthly_data[-3:])) / min(3, len(monthly_data))
        older = float(sum(m["total_spent"] for m in monthly_data[:3])) / min(3, len(monthly_data))
        trend = "increasing" if recent > older * 1.1 else "decreasing" if recent < older * 0.9 else "stable"
    else:
        trend = "insufficient_data"

    total_spent = float(sum(m["total_spent"] for m in monthly_data))

    return {
        "user_id": user_id,
        "months_analyzed": months,
        "total_spent": round(total_spent, 2),
        "average_monthly": round(total_spent / len(monthly_data), 2) if monthly_data else 0,
        "trend": trend,
        "monthly_data": monthly_data,
    }


@app.get("/reports/payment-method-analysis")
def get_payment_method_analysis(from_date: str, to_date: str, user_id: int | None = None, session: Session = SessionDep, _: str = AuthDep):
    query = select(Expense).where(Expense.date >= from_date, Expense.date <= to_date)
    if user_id is not None:
        query = query.where(Expense.user_id == user_id)

    expenses = list(session.exec(query).all())
    if not expenses:
        return {"message": "No expenses found", "total": 0}

    total = sum(e.amount for e in expenses)
    by_payment = {}
    counts = {}

    for e in expenses:
        by_payment[e.payment_method] = by_payment.get(e.payment_method, 0) + e.amount
        counts[e.payment_method] = counts.get(e.payment_method, 0) + 1

    analysis = [
        {
            "payment_method": method,
            "total_spent": round(amount, 2),
            "transaction_count": counts[method],
            "average_transaction": round(amount / counts[method], 2),
            "percentage_of_total": calculate_percentage(amount, total),
        }
        for method, amount in by_payment.items()
    ]
    analysis.sort(key=lambda x: x["total_spent"], reverse=True)

    # Credit card breakdown
    cc_expenses = [e for e in expenses if e.payment_method == "credit_card"]
    by_card = {}
    for e in cc_expenses:
        if e.credit_card_id:
            card = session.get(CreditCard, e.credit_card_id)
            name = f"{card.card_name} ({card.last_four})" if card else "Unknown"
            by_card[name] = by_card.get(name, 0) + e.amount

    return {
        "period": f"{from_date} to {to_date}",
        "user_id": user_id,
        "total_spent": round(total, 2),
        "transaction_count": len(expenses),
        "by_payment_method": analysis,
        "credit_card_breakdown": {k: round(v, 2) for k, v in by_card.items()} if by_card else None,
        "credit_card_total": round(sum(e.amount for e in cc_expenses), 2),
    }


@app.get("/reports/export")
def export_expenses(from_date: str, to_date: str, user_id: int | None = None, format: str = "json", session: Session = SessionDep, _: str = AuthDep):
    query = select(Expense).where(Expense.date >= from_date, Expense.date <= to_date)
    if user_id is not None:
        query = query.where(Expense.user_id == user_id)

    expenses = list(session.exec(query.order_by(Expense.date)).all())

    if format == "csv":
        import csv
        import io

        from fastapi.responses import StreamingResponse

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Date", "User ID", "Category", "Description", "Amount", "Payment Method", "Credit Card ID", "Is Recurring", "Tags"])
        for e in expenses:
            writer.writerow([e.date, e.user_id, e.category, e.description or "", e.amount, e.payment_method, e.credit_card_id or "", e.is_recurring, e.tags or ""])
        output.seek(0)

        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=expenses_{from_date}_to_{to_date}.csv"}
        )

    return {
        "period": f"{from_date} to {to_date}",
        "user_id": user_id,
        "total_expenses": len(expenses),
        "total_amount": round(sum(e.amount for e in expenses), 2),
        "expenses": [
            {"id": e.id, "date": e.date, "user_id": e.user_id, "category": e.category, "description": e.description, "amount": e.amount, "payment_method": e.payment_method, "credit_card_id": e.credit_card_id, "is_recurring": e.is_recurring, "tags": e.tags}
            for e in expenses
        ],
    }


# ============================================
# SAVINGS GOAL ENDPOINTS
# ============================================


@app.post("/savings-goals/", response_model=SavingsGoal)
def create_savings_goal(goal: SavingsGoalCreate, session: Session = SessionDep, _: str = AuthDep):
    db_goal = SavingsGoalService.validate_and_create(session, goal)
    logger.info(f"Created savings goal: {db_goal.name}")
    return db_goal


@app.get("/savings-goals/", response_model=list[SavingsGoal])
def list_savings_goals(user_id: int | None = None, is_active: bool = True, session: Session = SessionDep, _: str = AuthDep):
    query = select(SavingsGoal).where(SavingsGoal.is_active == is_active)
    if user_id is not None:
        query = query.where(SavingsGoal.user_id == user_id)
    return list(session.exec(query.order_by(SavingsGoal.created_at.desc())).all())


@app.get("/savings-goals/{goal_id}", response_model=SavingsGoal)
def get_savings_goal(goal_id: int, session: Session = SessionDep, _: str = AuthDep):
    return get_or_404(session, SavingsGoal, goal_id, "Savings goal")


@app.put("/savings-goals/{goal_id}", response_model=SavingsGoal)
def update_savings_goal(goal_id: int, data: SavingsGoalCreate, session: Session = SessionDep, _: str = AuthDep):
    goal = get_or_404(session, SavingsGoal, goal_id, "Savings goal")
    get_or_404(session, User, data.user_id, "User")
    return CRUDService.update(session, goal, data)


@app.delete("/savings-goals/{goal_id}")
def delete_savings_goal(goal_id: int, session: Session = SessionDep, _: str = AuthDep):
    goal = get_or_404(session, SavingsGoal, goal_id, "Savings goal")
    return CRUDService.soft_delete(session, goal)


@app.post("/savings-goals/{goal_id}/add", response_model=SavingsGoal)
def add_to_savings_goal(goal_id: int, update: SavingsGoalUpdate, session: Session = SessionDep, _: str = AuthDep):
    goal = get_or_404(session, SavingsGoal, goal_id, "Savings goal")
    return SavingsGoalService.add_amount(session, goal, update.amount)


@app.post("/savings-goals/{goal_id}/withdraw", response_model=SavingsGoal)
def withdraw_from_savings_goal(goal_id: int, update: SavingsGoalUpdate, session: Session = SessionDep, _: str = AuthDep):
    goal = get_or_404(session, SavingsGoal, goal_id, "Savings goal")
    return SavingsGoalService.withdraw_amount(session, goal, update.amount)


@app.get("/savings-goals/{goal_id}/progress")
def get_savings_goal_progress(goal_id: int, session: Session = SessionDep, _: str = AuthDep):
    goal = get_or_404(session, SavingsGoal, goal_id, "Savings goal")
    return SavingsGoalService.get_progress(goal)


# ============================================
# ASSET ENDPOINTS
# ============================================


@app.post("/assets/", response_model=Asset)
def create_asset(asset: AssetCreate, session: Session = SessionDep, _: str = AuthDep):
    db_asset = AssetService.validate_and_create(session, asset)
    logger.info(f"Created asset: {db_asset.name}")
    return db_asset


@app.get("/assets/", response_model=list[Asset])
def list_assets(user_id: int | None = None, asset_type: str | None = None, is_active: bool = True, session: Session = SessionDep, _: str = AuthDep):
    query = select(Asset).where(Asset.is_active == is_active)
    if user_id is not None:
        query = query.where(Asset.user_id == user_id)
    if asset_type:
        query = query.where(Asset.asset_type == asset_type)
    return list(session.exec(query.order_by(Asset.created_at.desc())).all())


@app.get("/assets/summary")
def get_assets_summary(user_id: int | None = None, session: Session = SessionDep, _: str = AuthDep):
    query = select(Asset).where(Asset.is_active)
    if user_id is not None:
        query = query.where(Asset.user_id == user_id)

    assets = list(session.exec(query).all())
    if not assets:
        return {"message": "No assets found", "total_assets": 0, "total_purchase_value": 0, "total_current_value": 0}

    total_purchase = sum(a.purchase_value for a in assets)
    total_current = sum(a.current_value for a in assets)
    gain_loss = total_current - total_purchase

    by_type = {}
    for a in assets:
        if a.asset_type not in by_type:
            by_type[a.asset_type] = {"count": 0, "purchase_value": 0, "current_value": 0}
        by_type[a.asset_type]["count"] += 1
        by_type[a.asset_type]["purchase_value"] += a.purchase_value
        by_type[a.asset_type]["current_value"] += a.current_value

    for t in by_type:
        gl = by_type[t]["current_value"] - by_type[t]["purchase_value"]
        by_type[t]["gain_loss"] = round(gl, 2)
        by_type[t]["gain_loss_percentage"] = calculate_percentage(gl, by_type[t]["purchase_value"])

    by_user = {}
    if user_id is None:
        for a in assets:
            user = session.get(User, a.user_id)
            name = user.name if user else f"User {a.user_id}"
            if name not in by_user:
                by_user[name] = {"count": 0, "total_value": 0}
            by_user[name]["count"] += 1
            by_user[name]["total_value"] += a.current_value

    return {
        "user_id": user_id,
        "total_assets": len(assets),
        "total_purchase_value": round(total_purchase, 2),
        "total_current_value": round(total_current, 2),
        "total_gain_loss": round(gain_loss, 2),
        "gain_loss_percentage": calculate_percentage(gain_loss, total_purchase),
        "by_type": by_type,
        "by_user": by_user if by_user else None,
    }


@app.get("/assets/depreciation")
def get_asset_depreciation(user_id: int | None = None, session: Session = SessionDep, _: str = AuthDep):
    """Return raw asset data - calculations done in frontend."""
    query = select(Asset).where(Asset.is_active)
    if user_id is not None:
        query = query.where(Asset.user_id == user_id)

    assets = list(session.exec(query).all())
    if not assets:
        return {"message": "No assets found", "assets": []}

    # Return raw data - frontend will calculate depreciation/appreciation
    return {
        "user_id": user_id,
        "total_assets": len(assets),
        "assets": [
            {
                "asset_id": a.id,
                "name": a.name,
                "asset_type": a.asset_type,
                "purchase_value": a.purchase_value,
                "current_value": a.current_value,
                "purchase_date": a.purchase_date,
            }
            for a in assets
        ],
    }


@app.get("/assets/{asset_id}", response_model=Asset)
def get_asset(asset_id: int, session: Session = SessionDep, _: str = AuthDep):
    return get_or_404(session, Asset, asset_id, "Asset")


@app.put("/assets/{asset_id}", response_model=Asset)
def update_asset(asset_id: int, data: AssetCreate, session: Session = SessionDep, _: str = AuthDep):
    asset = get_or_404(session, Asset, asset_id, "Asset")
    get_or_404(session, User, data.user_id, "User")
    asset = CRUDService.update(session, asset, data)
    asset.updated_at = now_iso()
    session.add(asset)
    session.commit()
    session.refresh(asset)
    return asset


@app.delete("/assets/{asset_id}")
def delete_asset(asset_id: int, session: Session = SessionDep, _: str = AuthDep):
    asset = get_or_404(session, Asset, asset_id, "Asset")
    return CRUDService.soft_delete(session, asset)


@app.put("/assets/{asset_id}/value", response_model=Asset)
def update_asset_value(asset_id: int, update: AssetValueUpdate, session: Session = SessionDep, _: str = AuthDep):
    asset = get_or_404(session, Asset, asset_id, "Asset")
    return AssetService.update_value(session, asset, update.current_value)


# ============================================
# RECURRING EXPENSE ENDPOINTS
# ============================================


@app.post("/recurring-expenses/", response_model=RecurringExpenseTemplate)
def create_recurring_template(template: RecurringExpenseTemplateCreate, session: Session = SessionDep, _: str = AuthDep):
    db_template = RecurringExpenseService.validate_and_create(session, template)
    logger.info(f"Created recurring template: {db_template.category}")
    return db_template


@app.get("/recurring-expenses/", response_model=list[RecurringExpenseTemplate])
def list_recurring_templates(user_id: int | None = None, is_active: bool = True, frequency: str | None = None, session: Session = SessionDep, _: str = AuthDep):
    query = select(RecurringExpenseTemplate).where(RecurringExpenseTemplate.is_active == is_active)
    if user_id is not None:
        query = query.where(RecurringExpenseTemplate.user_id == user_id)
    if frequency:
        query = query.where(RecurringExpenseTemplate.frequency == frequency)
    return list(session.exec(query.order_by(RecurringExpenseTemplate.next_occurrence)).all())


@app.get("/recurring-expenses/upcoming")
def get_upcoming_recurring(days: int = 7, user_id: int | None = None, session: Session = SessionDep, _: str = AuthDep):
    cutoff = (datetime.now() + timedelta(days=days)).date()
    query = select(RecurringExpenseTemplate).where(
        RecurringExpenseTemplate.is_active,
        RecurringExpenseTemplate.next_occurrence <= cutoff
    )
    if user_id is not None:
        query = query.where(RecurringExpenseTemplate.user_id == user_id)

    templates = list(session.exec(query.order_by(RecurringExpenseTemplate.next_occurrence)).all())
    total = sum(t.amount for t in templates)

    return {
        "days_ahead": days,
        "user_id": user_id,
        "count": len(templates),
        "total_amount": round(total, 2),
        "upcoming": [
            {"template_id": t.id, "category": t.category, "amount": t.amount, "next_occurrence": t.next_occurrence, "frequency": t.frequency}
            for t in templates
        ],
    }


@app.get("/recurring-expenses/{template_id}", response_model=RecurringExpenseTemplate)
def get_recurring_template(template_id: int, session: Session = SessionDep, _: str = AuthDep):
    return get_or_404(session, RecurringExpenseTemplate, template_id, "Recurring template")


@app.put("/recurring-expenses/{template_id}", response_model=RecurringExpenseTemplate)
def update_recurring_template(template_id: int, data: RecurringExpenseTemplateCreate, session: Session = SessionDep, _: str = AuthDep):
    template = get_or_404(session, RecurringExpenseTemplate, template_id, "Recurring template")
    get_or_404(session, User, data.user_id, "User")

    # Recalculate next occurrence
    next_occ = calculate_next_occurrence(data.start_date, data.frequency, data.interval, data.day_of_week, data.day_of_month, data.month_of_year)

    for field, value in data.model_dump().items():
        setattr(template, field, value)
    template.next_occurrence = next_occ

    session.add(template)
    session.commit()
    session.refresh(template)
    return template


@app.delete("/recurring-expenses/{template_id}")
def delete_recurring_template(template_id: int, session: Session = SessionDep, _: str = AuthDep):
    template = get_or_404(session, RecurringExpenseTemplate, template_id, "Recurring template")
    return CRUDService.soft_delete(session, template)


@app.post("/recurring-expenses/{template_id}/generate", response_model=Expense)
def generate_expense_from_template(template_id: int, session: Session = SessionDep, _: str = AuthDep):
    template = get_or_404(session, RecurringExpenseTemplate, template_id, "Recurring template")
    return RecurringExpenseService.generate_expense(session, template)


@app.post("/recurring-expenses/{template_id}/skip")
def skip_recurring_occurrence(template_id: int, session: Session = SessionDep, _: str = AuthDep):
    template = get_or_404(session, RecurringExpenseTemplate, template_id, "Recurring template")
    return RecurringExpenseService.skip_occurrence(session, template)


@app.post("/recurring-expenses/generate-due")
def generate_due_recurring(session: Session = SessionDep, _: str = AuthDep):
    today = today_str()
    templates = list(session.exec(
        select(RecurringExpenseTemplate).where(
            RecurringExpenseTemplate.is_active,
            RecurringExpenseTemplate.next_occurrence <= today
        )
    ).all())

    generated, errors = [], []
    for t in templates:
        try:
            expense = RecurringExpenseService.generate_expense(session, t)
            generated.append({"template_id": t.id, "expense_id": expense.id, "amount": t.amount, "category": t.category, "date": expense.date})
        except Exception as e:
            errors.append({"template_id": t.id, "error": str(e)})

    return {"generated_count": len(generated), "error_count": len(errors), "generated": generated, "errors": errors}


# ============================================
# SAVINGS ACCOUNT ENDPOINTS
# ============================================


@app.post("/savings-accounts/", response_model=SavingsAccount)
def create_savings_account(account: SavingsAccountCreate, session: Session = SessionDep, _: str = AuthDep):
    db_account = SavingsAccountService.validate_and_create(session, account)
    logger.info(f"Created savings account: {db_account.account_name}")
    return db_account


@app.get("/savings-accounts/", response_model=list[SavingsAccount])
def list_savings_accounts(user_id: int | None = None, is_active: bool = True, session: Session = SessionDep, _: str = AuthDep):
    query = select(SavingsAccount).where(SavingsAccount.is_active == is_active)
    if user_id is not None:
        query = query.where(SavingsAccount.user_id == user_id)
    return list(session.exec(query).all())


@app.get("/savings-accounts/{account_id}", response_model=SavingsAccount)
def get_savings_account(account_id: int, session: Session = SessionDep, _: str = AuthDep):
    return get_or_404(session, SavingsAccount, account_id, "Savings account")


@app.put("/savings-accounts/{account_id}", response_model=SavingsAccount)
def update_savings_account(account_id: int, data: SavingsAccountCreate, session: Session = SessionDep, _: str = AuthDep):
    account = get_or_404(session, SavingsAccount, account_id, "Savings account")
    get_or_404(session, User, data.user_id, "User")
    return CRUDService.update(session, account, data)


@app.delete("/savings-accounts/{account_id}")
def delete_savings_account(account_id: int, session: Session = SessionDep, _: str = AuthDep):
    account = get_or_404(session, SavingsAccount, account_id, "Savings account")
    return CRUDService.soft_delete(session, account)


@app.post("/savings-accounts/{account_id}/deposit", response_model=SavingsAccount)
def deposit_to_account(account_id: int, deposit: SavingsAccountDeposit, session: Session = SessionDep, _: str = AuthDep):
    account = get_or_404(session, SavingsAccount, account_id, "Savings account")
    return SavingsAccountService.deposit(session, account, deposit.amount, deposit.date, deposit.description, deposit.tags)


@app.post("/savings-accounts/{account_id}/withdraw", response_model=SavingsAccount)
def withdraw_from_account(account_id: int, withdrawal: SavingsAccountWithdraw, session: Session = SessionDep, _: str = AuthDep):
    account = get_or_404(session, SavingsAccount, account_id, "Savings account")
    return SavingsAccountService.withdraw(session, account, withdrawal.amount, withdrawal.date, withdrawal.description, withdrawal.tags)


@app.post("/savings-accounts/{account_id}/interest", response_model=SavingsAccount)
def post_interest(account_id: int, interest: SavingsAccountDeposit, session: Session = SessionDep, _: str = AuthDep):
    account = get_or_404(session, SavingsAccount, account_id, "Savings account")
    return SavingsAccountService.post_interest(session, account, interest.amount, interest.date, interest.description)


@app.get("/savings-accounts/{account_id}/transactions")
def get_account_transactions(account_id: int, from_date: str | None = None, to_date: str | None = None, transaction_type: str | None = None, session: Session = SessionDep, _: str = AuthDep):
    get_or_404(session, SavingsAccount, account_id, "Savings account")

    query = select(SavingsAccountTransaction).where(SavingsAccountTransaction.savings_account_id == account_id)
    if from_date:
        query = query.where(SavingsAccountTransaction.date >= from_date)
    if to_date:
        query = query.where(SavingsAccountTransaction.date <= to_date)
    if transaction_type:
        query = query.where(SavingsAccountTransaction.transaction_type == transaction_type)

    transactions = list(session.exec(query.order_by(SavingsAccountTransaction.date.desc())).all())

    return {
        "account_id": account_id,
        "transaction_count": len(transactions),
        "transactions": [
            {"id": t.id, "type": t.transaction_type, "amount": t.amount, "balance_after": t.balance_after, "date": t.date, "description": t.description}
            for t in transactions
        ],
    }


@app.get("/savings-accounts/{account_id}/summary")
def get_account_summary(account_id: int, session: Session = SessionDep, _: str = AuthDep):
    account = get_or_404(session, SavingsAccount, account_id, "Savings account")

    transactions = list(session.exec(
        select(SavingsAccountTransaction).where(SavingsAccountTransaction.savings_account_id == account_id)
    ).all())

    deposits = sum(t.amount for t in transactions if t.transaction_type == "deposit")
    withdrawals = sum(t.amount for t in transactions if t.transaction_type == "withdrawal")
    interest = sum(t.amount for t in transactions if t.transaction_type == "interest")

    return {
        "account_id": account_id,
        "account_name": account.account_name,
        "bank_name": account.bank_name,
        "current_balance": account.current_balance,
        "minimum_balance": account.minimum_balance,
        "interest_rate": account.interest_rate,
        "total_deposits": round(deposits, 2),
        "total_withdrawals": round(withdrawals, 2),
        "total_interest_earned": round(interest, 2),
        "transaction_count": len(transactions),
    }


@app.get("/savings-accounts/summary/all")
def get_all_accounts_summary(user_id: int | None = None, session: Session = SessionDep, _: str = AuthDep):
    query = select(SavingsAccount).where(SavingsAccount.is_active)
    if user_id is not None:
        query = query.where(SavingsAccount.user_id == user_id)

    accounts = list(session.exec(query).all())
    if not accounts:
        return {"message": "No savings accounts found", "total_balance": 0}

    total = sum(a.current_balance for a in accounts)

    return {
        "user_id": user_id,
        "total_accounts": len(accounts),
        "total_balance": round(total, 2),
        "accounts": [
            {"account_id": a.id, "account_name": a.account_name, "bank_name": a.bank_name, "balance": a.current_balance}
            for a in accounts
        ],
    }
