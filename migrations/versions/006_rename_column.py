"""Rename column: debitcard.id to debitcard.debit_card_id

Revision ID: 006_rename_column
Revises: 005_modify_column_type
Create Date: 2026-01-04

TEST: Renaming a column (High Risk)
This demonstrates how to safely rename a column.

Strategy Options:
1. Direct rename (PostgreSQL supports ALTER COLUMN RENAME)
2. Create new, copy, drop old (for databases that don't support rename)

IMPORTANT: This will break any application code that references the old column name!
You MUST update:
- Backend models (models.py)
- Frontend/CLI models (models.rs)
- API endpoints
- Any raw SQL queries

This example renames debitcard.id to debitcard.debit_card_id
This is a BREAKING CHANGE that requires code updates!
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '006_rename_column'
down_revision: str | Sequence[str] | None = '005_modify_column_type'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """
    Rename debitcard.id to debitcard.debit_card_id
    
    WARNING: This is a breaking change! Application code must be updated.
    """
    # PostgreSQL supports direct column rename
    op.alter_column('debitcard', 'id', new_column_name='debit_card_id')
    
    # Also demonstrate renaming a non-PK column (safer example)
    # Rename 'card_name' to 'name' in debitcard
    op.alter_column('debitcard', 'card_name', new_column_name='name')
    

def downgrade() -> None:
    """Revert column names."""
    op.alter_column('debitcard', 'name', new_column_name='card_name')
    op.alter_column('debitcard', 'debit_card_id', new_column_name='id')
