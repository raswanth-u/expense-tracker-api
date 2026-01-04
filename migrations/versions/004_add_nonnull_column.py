"""Add non-nullable column: priority to expense

Revision ID: 004_add_nonnull_column
Revises: 003_add_nullable_column
Create Date: 2026-01-04

TEST: Adding a non-nullable column (Medium Risk)
This demonstrates how to add a required column to an existing table.
You MUST provide a server_default value for existing rows.

Strategy:
1. Add column with server_default
2. Existing rows automatically get the default value
3. Optionally, you can later remove the default if you want strict validation
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '004_add_nonnull_column'
down_revision: str | Sequence[str] | None = '003_add_nullable_column'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add priority column to expense table with default value."""
    # IMPORTANT: When adding non-nullable column, MUST provide server_default
    # This ensures existing rows get a valid value
    op.add_column(
        'expense', 
        sa.Column('priority', sa.String(), nullable=False, server_default='normal')
    )
    
    # Also add a verified flag to demonstrate boolean with default
    op.add_column(
        'expense',
        sa.Column('is_verified', sa.Boolean(), nullable=False, server_default='false')
    )
    

def downgrade() -> None:
    """Remove priority and is_verified columns from expense table."""
    op.drop_column('expense', 'is_verified')
    op.drop_column('expense', 'priority')
