"""Service layer for the expense tracker API - handles business logic."""

from datetime import datetime
from typing import Any, TypeVar

from fastapi import HTTPException
from sqlmodel import Session, SQLModel, func, select

from models import (
    Asset,
    Budget,
    CreditCard,
    Expense,
    RecurringExpenseTemplate,
    SavingsAccount,
    SavingsAccountTransaction,
    SavingsGoal,
    User,
)
from utils import (
    calculate_percentage,
    get_active_or_404,
    get_month_exclusive_range,
    get_or_404,
    group_by_field,
    now_iso,
    today_str,
)

T = TypeVar("T", bound=SQLModel)


# ============================================
# BASE CRUD SERVICE
# ============================================


class CRUDService:
    """Base service for common CRUD operations."""

    @staticmethod
    def create(session: Session, model: type[T], data: SQLModel, **extra) -> T:
        """Create a new record."""
        db_obj = model(**data.model_dump(), **extra)
        session.add(db_obj)
        session.commit()
        session.refresh(db_obj)
        return db_obj

    @staticmethod
    def get(session: Session, model: type[T], id: int, name: str = "Resource") -> T:
        """Get a record by ID or raise 404."""
        return get_or_404(session, model, id, name)

    @staticmethod
    def list_all(
        session: Session,
        model: type[T],
        filters: dict[str, Any] | None = None,
        order_by: Any | None = None
    ) -> list[T]:
        """List records with optional filters."""
        query = select(model)

        if filters:
            for field, value in filters.items():
                if value is not None:
                    query = query.where(getattr(model, field) == value)

        if order_by is not None:
            query = query.order_by(order_by)

        return list(session.exec(query).all())

    @staticmethod
    def update(session: Session, instance: T, data: SQLModel, exclude: set | None = None) -> T:
        """Update a record with new data."""
        update_data = data.model_dump(exclude=exclude or set())
        for field, value in update_data.items():
            setattr(instance, field, value)
        session.add(instance)
        session.commit()
        session.refresh(instance)
        return instance

    @staticmethod
    def soft_delete(session: Session, instance: T) -> dict:
        """Soft delete by setting is_active = False."""
        instance.is_active = False
        session.add(instance)
        session.commit()
        return {"message": f"{type(instance).__name__} deactivated", "id": instance.id}

    @staticmethod
    def hard_delete(session: Session, instance: T) -> dict:
        """Permanently delete a record."""
        id_val = instance.id
        session.delete(instance)
        session.commit()
        return {"message": f"{type(instance).__name__} deleted", "id": id_val}


# ============================================
# USER SERVICE
# ============================================


class UserService:
    """Service for user operations."""

    @staticmethod
    def create(session: Session, data: SQLModel) -> User:
        """Create a new user with email uniqueness check."""
        existing = session.exec(
            select(User).where(User.email == data.email)
        ).first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"User with email {data.email} already exists"
            )
        return CRUDService.create(session, User, data, created_at=now_iso())

    @staticmethod
    def update(session: Session, user: User, data: SQLModel) -> User:
        """Update user with email uniqueness check."""
        if data.email != user.email:
            existing = session.exec(
                select(User).where(User.email == data.email)
            ).first()
            if existing:
                raise HTTPException(
                    status_code=400,
                    detail=f"Email {data.email} is already in use"
                )
        return CRUDService.update(session, user, data)

    @staticmethod
    def get_stats(session: Session, user: User, month: str | None = None) -> dict:
        """Get spending statistics for a user."""
        query = select(Expense).where(Expense.user_id == user.id)

        if month:
            start_date, end_date = get_month_exclusive_range(month)
            query = query.where(Expense.date >= start_date, Expense.date < end_date)

        expenses = list(session.exec(query).all())
        total_spent = sum(e.amount for e in expenses)

        return {
            "user_id": user.id,
            "user_name": user.name,
            "period": month or "all_time",
            "total_spent": round(total_spent, 2),
            "transaction_count": len(expenses),
            "average_transaction": round(total_spent / len(expenses), 2) if expenses else 0,
            "by_category": {k: round(v, 2) for k, v in group_by_field(expenses, "category").items()},
            "by_payment_method": {k: round(v, 2) for k, v in group_by_field(expenses, "payment_method").items()},
        }


# ============================================
# EXPENSE SERVICE
# ============================================


class ExpenseService:
    """Service for expense operations."""

    @staticmethod
    def validate_and_create(session: Session, data: SQLModel) -> Expense:
        """Validate references and create expense."""
        # Validate user
        get_active_or_404(session, User, data.user_id, "User")

        # Validate credit card if provided
        if data.credit_card_id:
            get_active_or_404(session, CreditCard, data.credit_card_id, "Credit card")
            if data.payment_method != "credit_card":
                raise HTTPException(
                    status_code=400,
                    detail="Payment method must be 'credit_card' when credit_card_id is provided"
                )

        # Handle savings account deduction
        account = None
        if data.savings_account_id:
            account = get_active_or_404(session, SavingsAccount, data.savings_account_id, "Savings account")
            if data.payment_method != "savings_account":
                raise HTTPException(
                    status_code=400,
                    detail="Payment method must be 'savings_account' when savings_account_id is provided"
                )
            account.current_balance -= data.amount
            session.add(account)

        # Create expense
        expense = CRUDService.create(session, Expense, data)

        # Create savings transaction if applicable
        if account:
            ExpenseService._create_savings_transaction(
                session, account, expense, data.amount
            )

        return expense

    @staticmethod
    def _create_savings_transaction(
        session: Session,
        account: SavingsAccount,
        expense: Expense,
        amount: float
    ) -> None:
        """Create a withdrawal transaction for savings account."""
        transaction = SavingsAccountTransaction(
            savings_account_id=account.id,
            transaction_type="withdrawal",
            amount=amount,
            balance_after=account.current_balance,
            related_expense_id=expense.id,
            date=expense.date,
            description=expense.description or f"{expense.category} expense",
            tags=expense.tags,
            created_at=now_iso()
        )
        session.add(transaction)
        session.commit()

    @staticmethod
    def validate_and_update(session: Session, expense: Expense, data: SQLModel) -> Expense:
        """Validate references and update expense."""
        # Validate user
        get_or_404(session, User, data.user_id, "User")

        # Validate credit card if provided
        if data.credit_card_id:
            get_active_or_404(session, CreditCard, data.credit_card_id, "Credit card")

        return CRUDService.update(session, expense, data)

    @staticmethod
    def get_summary(
        session: Session,
        group_field: str,
        from_date: str | None = None,
        to_date: str | None = None,
        user_id: int | None = None
    ) -> list[dict]:
        """Get expense summary grouped by a field."""
        query = select(
            getattr(Expense, group_field),
            func.sum(Expense.amount).label("total"),
            func.count(Expense.id).label("count"),
        )

        if from_date:
            query = query.where(Expense.date >= from_date)
        if to_date:
            query = query.where(Expense.date <= to_date)
        if user_id is not None:
            query = query.where(Expense.user_id == user_id)

        query = query.group_by(getattr(Expense, group_field))
        results = session.exec(query).all()

        return [
            {group_field: value, "total": round(total, 2), "count": count}
            for value, total, count in results
        ]


# ============================================
# BUDGET SERVICE
# ============================================


class BudgetService:
    """Service for budget operations."""

    @staticmethod
    def validate_and_create(session: Session, data: SQLModel) -> Budget:
        """Validate and create budget with duplicate check."""
        # Validate user if provided
        if data.user_id:
            get_or_404(session, User, data.user_id, "User")

        # Check for duplicate
        existing = session.exec(
            select(Budget).where(
                Budget.category == data.category,
                Budget.month == data.month,
                Budget.user_id == data.user_id,
                Budget.is_active,
            )
        ).first()

        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Budget already exists for {data.category} in {data.month}"
            )

        return CRUDService.create(session, Budget, data)

    @staticmethod
    def get_status(
        session: Session,
        month: str,
        user_id: int | None = None
    ) -> dict:
        """Get budget status with spending comparison."""
        query = select(Budget).where(Budget.month == month, Budget.is_active)
        if user_id is not None:
            query = query.where(Budget.user_id == user_id)

        budgets = list(session.exec(query).all())

        if not budgets:
            return {
                "month": month,
                "user_id": user_id,
                "message": "No budgets found for this period",
                "budgets": [],
            }

        start_date, end_date = get_month_exclusive_range(month)
        results = []
        total_budget = 0
        total_spent = 0

        for budget in budgets:
            spent = BudgetService._get_category_spending(
                session, budget.category, start_date, end_date, budget.user_id
            )
            remaining = budget.amount - spent
            percentage = calculate_percentage(spent, budget.amount)

            status, alert = BudgetService._determine_status(percentage, remaining)

            total_budget += budget.amount
            total_spent += spent

            results.append({
                "budget_id": budget.id,
                "category": budget.category,
                "user_id": budget.user_id,
                "budget": round(budget.amount, 2),
                "spent": round(spent, 2),
                "remaining": round(remaining, 2),
                "percentage": percentage,
                "status": status,
                "alert": alert,
            })

        results.sort(key=lambda x: x["percentage"], reverse=True)

        return {
            "month": month,
            "user_id": user_id,
            "period": f"{start_date} to {end_date}",
            "total_budget": round(total_budget, 2),
            "total_spent": round(total_spent, 2),
            "total_remaining": round(total_budget - total_spent, 2),
            "overall_percentage": calculate_percentage(total_spent, total_budget),
            "budgets": results,
            "alerts_count": sum(1 for r in results if r["status"] in ["warning", "exceeded"]),
        }

    @staticmethod
    def _get_category_spending(
        session: Session,
        category: str,
        start_date: str,
        end_date: str,
        user_id: int | None
    ) -> float:
        """Get total spending for a category in a date range."""
        query = select(func.sum(Expense.amount)).where(
            Expense.category == category,
            Expense.date >= start_date,
            Expense.date < end_date,
        )
        if user_id:
            query = query.where(Expense.user_id == user_id)

        return session.exec(query).one() or 0.0

    @staticmethod
    def _determine_status(percentage: float, remaining: float) -> tuple[str, str | None]:
        """Determine budget status and alert message."""
        if percentage >= 100:
            return "exceeded", f"⚠️ Budget exceeded by ${abs(remaining):.2f}"
        elif percentage >= 80:
            return "warning", f"⚡ Warning: {percentage:.1f}% of budget used"
        else:
            return "ok", None


# ============================================
# CREDIT CARD SERVICE
# ============================================


class CreditCardService:
    """Service for credit card operations."""

    @staticmethod
    def validate_and_create(session: Session, data: SQLModel) -> CreditCard:
        """Validate and create credit card with duplicate check."""
        # Validate user
        get_active_or_404(session, User, data.user_id, "User")

        # Check for duplicate
        existing = session.exec(
            select(CreditCard).where(
                CreditCard.user_id == data.user_id,
                CreditCard.last_four == data.last_four,
                CreditCard.is_active,
            )
        ).first()

        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Card ending in {data.last_four} already exists for this user"
            )

        return CRUDService.create(session, CreditCard, data)


# ============================================
# SAVINGS GOAL SERVICE
# ============================================


class SavingsGoalService:
    """Service for savings goal operations."""

    @staticmethod
    def validate_and_create(session: Session, data: SQLModel) -> SavingsGoal:
        """Validate and create savings goal."""
        # Validate user
        get_active_or_404(session, User, data.user_id, "User")

        # Validate deadline is in the future
        try:
            deadline_date = datetime.strptime(data.deadline, "%Y-%m-%d")
            if deadline_date.date() < datetime.now().date():
                raise HTTPException(status_code=400, detail="Deadline must be in the future")
        except ValueError as e:
            raise HTTPException(status_code=400, detail="Invalid date format") from e

        return CRUDService.create(session, SavingsGoal, data, created_at=now_iso())

    @staticmethod
    def add_amount(session: Session, goal: SavingsGoal, amount: float) -> SavingsGoal:
        """Add money to a savings goal."""
        if not goal.is_active:
            raise HTTPException(status_code=400, detail="Cannot add to inactive goal")

        goal.current_amount += amount
        session.add(goal)
        session.commit()
        session.refresh(goal)
        return goal

    @staticmethod
    def withdraw_amount(session: Session, goal: SavingsGoal, amount: float) -> SavingsGoal:
        """Withdraw money from a savings goal."""
        if not goal.is_active:
            raise HTTPException(status_code=400, detail="Cannot withdraw from inactive goal")

        if goal.current_amount < amount:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient funds. Available: ${goal.current_amount:.2f}"
            )

        goal.current_amount -= amount
        session.add(goal)
        session.commit()
        session.refresh(goal)
        return goal

    @staticmethod
    def get_progress(goal: SavingsGoal) -> dict:
        """Get detailed progress for a savings goal."""
        progress_pct = calculate_percentage(goal.current_amount, goal.target_amount)
        remaining = goal.target_amount - goal.current_amount

        try:
            deadline_date = datetime.strptime(goal.deadline, "%Y-%m-%d")
            days_remaining = (deadline_date - datetime.now()).days

            if days_remaining > 0 and remaining > 0:
                daily_required = remaining / days_remaining
            else:
                daily_required = 0
        except ValueError:
            days_remaining = 0
            daily_required = 0

        status = SavingsGoalService._determine_status(progress_pct, days_remaining)

        return {
            "goal_id": goal.id,
            "goal_name": goal.name,
            "target_amount": goal.target_amount,
            "current_amount": goal.current_amount,
            "remaining_amount": remaining,
            "progress_percentage": progress_pct,
            "deadline": goal.deadline,
            "days_remaining": days_remaining,
            "status": status,
            "required_savings": {
                "daily": round(daily_required, 2),
                "weekly": round(daily_required * 7, 2),
                "monthly": round(daily_required * 30, 2),
            },
            "is_achievable": days_remaining > 0 and remaining >= 0,
        }

    @staticmethod
    def _determine_status(progress_pct: float, days_remaining: int) -> str:
        """Determine savings goal status."""
        if progress_pct >= 100:
            return "completed"
        elif days_remaining < 0:
            return "overdue"
        elif days_remaining < 30:
            return "urgent"
        elif progress_pct < 25:
            return "just_started"
        elif progress_pct < 50:
            return "on_track"
        elif progress_pct < 75:
            return "halfway"
        else:
            return "almost_there"


# ============================================
# ASSET SERVICE
# ============================================


class AssetService:
    """Service for asset operations."""

    @staticmethod
    def validate_and_create(session: Session, data: SQLModel) -> Asset:
        """Validate and create asset with optional payment handling."""
        # Validate user
        get_active_or_404(session, User, data.user_id, "User")

        # Validate credit card if provided
        account = None
        if data.credit_card_id:
            get_active_or_404(session, CreditCard, data.credit_card_id, "Credit card")
            if data.payment_method != "credit_card":
                raise HTTPException(
                    status_code=400,
                    detail="Payment method must be 'credit_card' when credit_card_id is provided"
                )

        # Handle savings account deduction
        if data.savings_account_id:
            account = get_active_or_404(session, SavingsAccount, data.savings_account_id, "Savings account")
            account.current_balance -= data.purchase_value
            session.add(account)

        # Create asset
        asset = CRUDService.create(
            session, Asset, data,
            created_at=now_iso(),
            updated_at=now_iso()
        )

        # Create savings transaction if applicable
        if account:
            AssetService._create_savings_transaction(session, account, asset)

        return asset

    @staticmethod
    def _create_savings_transaction(
        session: Session,
        account: SavingsAccount,
        asset: Asset
    ) -> None:
        """Create a withdrawal transaction for asset purchase."""
        transaction = SavingsAccountTransaction(
            savings_account_id=account.id,
            transaction_type="withdrawal",
            amount=asset.purchase_value,
            balance_after=account.current_balance,
            related_asset_id=asset.id,
            date=asset.purchase_date,
            description=f"Asset purchase: {asset.name}",
            tags=asset.tags,
            created_at=now_iso()
        )
        session.add(transaction)
        session.commit()

    @staticmethod
    def update_value(session: Session, asset: Asset, new_value: float) -> Asset:
        """Update asset current value."""
        asset.current_value = new_value
        asset.updated_at = now_iso()
        session.add(asset)
        session.commit()
        session.refresh(asset)
        return asset


# ============================================
# RECURRING EXPENSE SERVICE
# ============================================


class RecurringExpenseService:
    """Service for recurring expense operations."""

    @staticmethod
    def validate_and_create(session: Session, data: SQLModel) -> RecurringExpenseTemplate:
        """Validate and create recurring expense template."""
        from utils import calculate_next_occurrence

        # Validate user
        get_active_or_404(session, User, data.user_id, "User")

        # Calculate next occurrence
        next_occurrence = calculate_next_occurrence(
            data.start_date,
            data.frequency,
            data.interval,
            data.day_of_week,
            data.day_of_month,
            data.month_of_year
        )

        return CRUDService.create(
            session, RecurringExpenseTemplate, data,
            next_occurrence=next_occurrence,
            created_at=now_iso()
        )

    @staticmethod
    def generate_expense(session: Session, template: RecurringExpenseTemplate) -> Expense:
        """Generate an expense from a template."""
        from utils import calculate_next_occurrence

        if not template.is_active:
            raise HTTPException(status_code=400, detail="Template is inactive")

        expense = Expense(
            user_id=template.user_id,
            amount=template.amount,
            category=template.category,
            description=template.description,
            date=today_str(),
            payment_method="cash",
            is_recurring=True,
            tags=template.tags
        )
        session.add(expense)

        # Update template
        template.last_generated = today_str()
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

        return expense

    @staticmethod
    def skip_occurrence(session: Session, template: RecurringExpenseTemplate) -> dict:
        """Skip the next occurrence of a recurring expense."""
        from utils import calculate_next_occurrence

        if not template.is_active:
            raise HTTPException(status_code=400, detail="Template is inactive")

        old_next = template.next_occurrence
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

        return {
            "message": "Next occurrence skipped",
            "template_id": template.id,
            "old_next_occurrence": old_next,
            "new_next_occurrence": template.next_occurrence
        }


# ============================================
# SAVINGS ACCOUNT SERVICE
# ============================================


class SavingsAccountService:
    """Service for savings account operations."""

    @staticmethod
    def validate_and_create(session: Session, data: SQLModel) -> SavingsAccount:
        """Validate and create savings account."""
        # Validate user
        get_active_or_404(session, User, data.user_id, "User")

        return CRUDService.create(session, SavingsAccount, data, created_at=now_iso())

    @staticmethod
    def deposit(
        session: Session,
        account: SavingsAccount,
        amount: float,
        date: str | None = None,
        description: str | None = None,
        tags: str | None = None
    ) -> SavingsAccount:
        """Deposit money into account."""
        if not account.is_active:
            raise HTTPException(status_code=400, detail="Account is inactive")

        account.current_balance += amount
        session.add(account)

        transaction = SavingsAccountTransaction(
            savings_account_id=account.id,
            transaction_type="deposit",
            amount=amount,
            balance_after=account.current_balance,
            date=date or today_str(),
            description=description or "Deposit",
            tags=tags,
            created_at=now_iso()
        )
        session.add(transaction)
        session.commit()
        session.refresh(account)

        return account

    @staticmethod
    def withdraw(
        session: Session,
        account: SavingsAccount,
        amount: float,
        date: str | None = None,
        description: str | None = None,
        tags: str | None = None
    ) -> SavingsAccount:
        """Withdraw money from account."""
        if not account.is_active:
            raise HTTPException(status_code=400, detail="Account is inactive")

        if account.current_balance < amount:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient funds. Available: ${account.current_balance:.2f}"
            )

        account.current_balance -= amount
        session.add(account)

        transaction = SavingsAccountTransaction(
            savings_account_id=account.id,
            transaction_type="withdrawal",
            amount=amount,
            balance_after=account.current_balance,
            date=date or today_str(),
            description=description or "Withdrawal",
            tags=tags,
            created_at=now_iso()
        )
        session.add(transaction)
        session.commit()
        session.refresh(account)

        return account

    @staticmethod
    def post_interest(
        session: Session,
        account: SavingsAccount,
        amount: float,
        date: str | None = None,
        description: str | None = None
    ) -> SavingsAccount:
        """Post interest to account."""
        if not account.is_active:
            raise HTTPException(status_code=400, detail="Account is inactive")

        account.current_balance += amount
        session.add(account)

        transaction = SavingsAccountTransaction(
            savings_account_id=account.id,
            transaction_type="interest",
            amount=amount,
            balance_after=account.current_balance,
            date=date or today_str(),
            description=description or "Interest payment",
            created_at=now_iso()
        )
        session.add(transaction)
        session.commit()
        session.refresh(account)

        return account
