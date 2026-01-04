"""Add foreign key: budget.category_id references a new categories table

Revision ID: 008_add_foreign_key
Revises: 007_delete_column
Create Date: 2026-01-04

TEST: Adding a foreign key constraint (Medium Risk)
This demonstrates how to add a foreign key to an existing table.

Strategy:
1. Create the referenced table first (if it doesn't exist)
2. Add the foreign key column (nullable initially)
3. Populate data / migrate existing values
4. Optionally make it non-nullable
5. Add the constraint

For this test, we'll add a 'reviewed_by' FK to expense that references user.
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '008_add_foreign_key'
down_revision: str | Sequence[str] | None = '007_delete_column'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """
    Add reviewed_by column to expense with FK to user.
    This tracks who verified/reviewed each expense.
    """
    # Step 1: Add nullable column first (safe)
    op.add_column(
        'expense', 
        sa.Column('reviewed_by', sa.Integer(), nullable=True)
    )
    
    # Step 2: Add the foreign key constraint
    op.create_foreign_key(
        'fk_expense_reviewed_by_user',  # constraint name
        'expense',                       # source table
        'user',                          # target table
        ['reviewed_by'],                 # source column(s)
        ['id'],                          # target column(s)
        ondelete='SET NULL'              # what to do when user is deleted
    )
    
    # Step 3: Create index for performance
    op.create_index('ix_expense_reviewed_by', 'expense', ['reviewed_by'])
    

def downgrade() -> None:
    """Remove reviewed_by column and its FK."""
    op.drop_index('ix_expense_reviewed_by', 'expense')
    op.drop_constraint('fk_expense_reviewed_by_user', 'expense', type_='foreignkey')
    op.drop_column('expense', 'reviewed_by')
