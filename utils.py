"""Utility functions for the expense tracker API."""

from datetime import datetime, date, timedelta
from typing import TypeVar

from dateutil.relativedelta import relativedelta
from fastapi import HTTPException
from sqlmodel import Session, SQLModel

T = TypeVar("T", bound=SQLModel)


# ============================================
# DATE UTILITIES
# ============================================


def get_month_date_range(month: str) -> tuple[date, date]:
    """
    Get start and end dates for a month.

    Args:
        month: Month string in YYYY-MM format

    Returns:
        Tuple of (start_date, end_date) as date objects
    """
    year, month_num = map(int, month.split("-"))
    start_date = date(year, month_num, 1)

    if month_num == 12:
        end_date = date(year, 12, 31)
    else:
        next_month = date(year, month_num + 1, 1)
        end_date = next_month - timedelta(days=1)

    return start_date, end_date


def get_month_exclusive_range(month: str) -> tuple[date, date]:
    """
    Get start and exclusive end dates for a month (for < comparisons).

    Args:
        month: Month string in YYYY-MM format

    Returns:
        Tuple of (start_date, end_date_exclusive) as date objects
    """
    year, month_num = map(int, month.split("-"))
    start_date = date(year, month_num, 1)

    if month_num == 12:
        end_date = date(year + 1, 1, 1)
    else:
        end_date = date(year, month_num + 1, 1)

    return start_date, end_date


def parse_month(month: str) -> tuple[int, int]:
    """Parse YYYY-MM string into (year, month) tuple."""
    try:
        year, month_num = map(int, month.split("-"))
        return year, month_num
    except (ValueError, AttributeError) as e:
        raise HTTPException(
            status_code=400,
            detail="Invalid month format. Use YYYY-MM"
        ) from e


def calculate_next_occurrence(
    current_date: date,
    frequency: str,
    interval: int,
    day_of_week: int | None = None,
    day_of_month: int | None = None,
    month_of_year: int | None = None
) -> date:
    """
    Calculate the next occurrence date based on frequency and parameters.

    Args:
        current_date: Current date as a date object
        frequency: One of "daily", "weekly", "monthly", "yearly", "custom"
        interval: Interval multiplier
        day_of_week: 0-6 for Monday-Sunday (for weekly)
        day_of_month: 1-31 (for monthly/yearly)
        month_of_year: 1-12 (for yearly)

    Returns:
        Next occurrence date as a date object
    """
    if isinstance(current_date, str):
        try:
            current = datetime.strptime(current_date, "%Y-%m-%d").date()
        except ValueError:
            current = datetime.now().date()
    else:
        current = current_date

    if frequency == "daily":
        next_date = current + timedelta(days=interval)

    elif frequency == "weekly":
        next_date = current + timedelta(weeks=interval)
        if day_of_week is not None:
            days_ahead = day_of_week - next_date.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            next_date = next_date + timedelta(days=days_ahead)

    elif frequency == "monthly":
        next_dt = datetime.combine(current, datetime.min.time()) + relativedelta(months=interval)
        next_date = next_dt.date()
        if day_of_month is not None:
            try:
                next_date = next_date.replace(day=day_of_month)
            except ValueError:
                # Handle months with fewer days
                next_dt = (datetime.combine(next_date.replace(day=1), datetime.min.time()) + relativedelta(months=1))
                next_date = (next_dt - timedelta(days=1)).date()

    elif frequency == "yearly":
        next_dt = datetime.combine(current, datetime.min.time()) + relativedelta(years=interval)
        next_date = next_dt.date()
        if month_of_year is not None and day_of_month is not None:
            try:
                next_date = next_date.replace(month=month_of_year, day=day_of_month)
            except ValueError:
                next_date = next_date.replace(month=month_of_year, day=28)

    elif frequency == "custom":
        next_date = current + timedelta(days=interval)

    else:
        next_date = current + timedelta(days=1)

    return next_date


def now_iso() -> datetime:
    """Get current datetime."""
    return datetime.now()


def today_str() -> date:
    """Get today's date."""
    return datetime.now().date()


def current_month() -> str:
    """Get current month as YYYY-MM string."""
    return datetime.now().strftime("%Y-%m")


# ============================================
# VALIDATION UTILITIES
# ============================================


def get_or_404(session: Session, model: type[T], id: int, name: str = "Resource") -> T:
    """
    Get a model by ID or raise 404.

    Args:
        session: Database session
        model: SQLModel class
        id: Primary key
        name: Resource name for error message

    Returns:
        Model instance

    Raises:
        HTTPException: 404 if not found
    """
    instance = session.get(model, id)
    if not instance:
        raise HTTPException(status_code=404, detail=f"{name} not found")
    return instance


def validate_active(instance: T, name: str = "Resource") -> None:
    """
    Validate that a model instance is active.

    Args:
        instance: Model with is_active attribute
        name: Resource name for error message

    Raises:
        HTTPException: 400 if inactive
    """
    if hasattr(instance, "is_active") and not instance.is_active:
        raise HTTPException(status_code=400, detail=f"{name} is inactive")


def get_active_or_404(session: Session, model: type[T], id: int, name: str = "Resource") -> T:
    """
    Get a model by ID, validate it's active, or raise appropriate error.

    Args:
        session: Database session
        model: SQLModel class
        id: Primary key
        name: Resource name for error message

    Returns:
        Active model instance

    Raises:
        HTTPException: 404 if not found, 400 if inactive
    """
    instance = get_or_404(session, model, id, name)
    validate_active(instance, name)
    return instance


# ============================================
# AGGREGATION UTILITIES
# ============================================


def group_by_field(items: list, field: str) -> dict[str, float]:
    """
    Group items by a field and sum amounts.

    Args:
        items: List of objects with 'amount' and the specified field
        field: Field name to group by

    Returns:
        Dict mapping field values to total amounts
    """
    result = {}
    for item in items:
        key = getattr(item, field)
        result[key] = result.get(key, 0) + item.amount
    return result


def calculate_percentage(part, total) -> float:
    """Calculate percentage safely, returning 0 if total is 0."""
    if total <= 0:
        return 0.0
    return round(float(part) / float(total) * 100, 2)


def round_dict_values(d: dict, decimals: int = 2) -> dict:
    """Round all numeric values in a dict to specified decimals."""
    return {k: round(v, decimals) if isinstance(v, (int, float)) else v for k, v in d.items()}
