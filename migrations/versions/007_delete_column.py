"""Delete column: daily_limit from debitcard

Revision ID: 007_delete_column
Revises: 006_rename_column
Create Date: 2026-01-04

TEST: Deleting a column (Medium Risk)
This demonstrates how to safely remove a column from a table.

Strategy:
1. ALWAYS backup first
2. Verify no code dependencies on the column
3. Drop the column
4. Update models and API

WARNING: This is IRREVERSIBLE unless you have a backup!
The downgrade includes re-creating the column, but data will be lost.
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '007_delete_column'
down_revision: str | Sequence[str] | None = '006_rename_column'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """
    Remove daily_limit column from debitcard table.
    
    BEFORE RUNNING:
    1. Ensure backup exists
    2. Verify no application code uses this column
    3. Check no reports depend on this data
    """
    op.drop_column('debitcard', 'daily_limit')
    

def downgrade() -> None:
    """
    Re-add daily_limit column.
    
    NOTE: Original data is LOST! This only recreates the column structure.
    """
    op.add_column(
        'debitcard', 
        sa.Column('daily_limit', sa.Float(), nullable=True)
    )
