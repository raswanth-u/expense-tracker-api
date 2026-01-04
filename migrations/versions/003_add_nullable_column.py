"""Add nullable column: notes to expense

Revision ID: 003_add_nullable_column
Revises: 002_add_notification
Create Date: 2026-01-04

TEST: Adding a nullable column (Low Risk)
This demonstrates how to add an optional column to an existing table.
Nullable columns are safe because they don't require default values
and existing data remains valid.
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003_add_nullable_column'
down_revision: str | Sequence[str] | None = '002_add_notification'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add notes column to expense table."""
    # Adding a nullable column is safe - no data migration needed
    op.add_column('expense', sa.Column('notes', sa.String(), nullable=True))
    op.add_column('expense', sa.Column('receipt_url', sa.String(), nullable=True))
    

def downgrade() -> None:
    """Remove notes and receipt_url columns from expense table."""
    op.drop_column('expense', 'receipt_url')
    op.drop_column('expense', 'notes')
