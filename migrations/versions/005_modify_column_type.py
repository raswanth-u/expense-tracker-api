"""Modify column type: amount from float to numeric(12,2)

Revision ID: 005_modify_column_type
Revises: 004_add_nonnull_column
Create Date: 2026-01-04

TEST: Modifying column type (High Risk)
This demonstrates how to safely change a column's data type.

Strategy for HIGH RISK operations:
1. Create new column with desired type
2. Copy data from old column to new column
3. Drop old column
4. Rename new column to original name

However, PostgreSQL supports ALTER COLUMN TYPE for compatible types,
which we'll demonstrate here. For incompatible types, use the 3-step approach.
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '005_modify_column_type'
down_revision: str | Sequence[str] | None = '004_add_nonnull_column'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """
    Change expense.amount from DOUBLE PRECISION (float) to NUMERIC(12,2).
    NUMERIC provides exact decimal representation - better for money!
    """
    # For compatible type changes, PostgreSQL can do direct conversion
    # The USING clause tells PostgreSQL how to convert existing data
    op.execute("""
        ALTER TABLE expense 
        ALTER COLUMN amount TYPE NUMERIC(12,2) 
        USING amount::NUMERIC(12,2)
    """)
    
    # Do the same for other money columns
    op.execute("""
        ALTER TABLE creditcard 
        ALTER COLUMN credit_limit TYPE NUMERIC(12,2) 
        USING credit_limit::NUMERIC(12,2)
    """)
    

def downgrade() -> None:
    """Revert to DOUBLE PRECISION (float)."""
    op.execute("""
        ALTER TABLE expense 
        ALTER COLUMN amount TYPE DOUBLE PRECISION 
        USING amount::DOUBLE PRECISION
    """)
    
    op.execute("""
        ALTER TABLE creditcard 
        ALTER COLUMN credit_limit TYPE DOUBLE PRECISION 
        USING credit_limit::DOUBLE PRECISION
    """)
