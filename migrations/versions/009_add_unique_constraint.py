"""Add unique constraint: compound unique on creditcard(user_id, card_name)

Revision ID: 009_add_unique_constraint
Revises: 008_add_foreign_key
Create Date: 2026-01-04

TEST: Adding a unique constraint (High Risk)
This demonstrates how to add a unique constraint to existing data.

Strategy:
1. BACKUP FIRST!
2. Check for existing duplicates
3. Resolve duplicates (manual or automated)
4. Add the constraint

WARNING: If duplicates exist, the migration will FAIL!
You must handle duplicates BEFORE adding the constraint.
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '009_add_unique_constraint'
down_revision: str | Sequence[str] | None = '008_add_foreign_key'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """
    Add unique constraint on creditcard (user_id, card_name).
    This prevents a user from having two cards with the same name.
    
    BEFORE RUNNING:
    Run this query to check for duplicates:
    SELECT user_id, card_name, COUNT(*) 
    FROM creditcard 
    GROUP BY user_id, card_name 
    HAVING COUNT(*) > 1;
    """
    # First, let's add a unique constraint on creditcard
    op.create_unique_constraint(
        'uq_creditcard_user_card_name',  # constraint name
        'creditcard',                     # table
        ['user_id', 'card_name']          # columns (compound unique)
    )
    
    # Also add a unique constraint on savings account number per user
    op.create_unique_constraint(
        'uq_savingsaccount_user_account',
        'savingsaccount',
        ['user_id', 'account_name', 'bank_name']
    )
    

def downgrade() -> None:
    """Remove unique constraints."""
    op.drop_constraint('uq_savingsaccount_user_account', 'savingsaccount', type_='unique')
    op.drop_constraint('uq_creditcard_user_card_name', 'creditcard', type_='unique')
