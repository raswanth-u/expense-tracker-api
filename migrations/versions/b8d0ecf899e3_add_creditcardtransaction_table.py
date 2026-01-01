"""Add CreditCardTransaction table

Revision ID: b8d0ecf899e3
Revises: a7c9dbe788d2
Create Date: 2025-01-01 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b8d0ecf899e3'
down_revision: str | Sequence[str] | None = 'a7c9dbe788d2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create creditcardtransaction table."""
    op.create_table(
        'creditcardtransaction',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('credit_card_id', sa.Integer(), nullable=False),
        sa.Column('transaction_type', sa.String(), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('balance_after', sa.Float(), nullable=False),
        sa.Column('related_expense_id', sa.Integer(), nullable=True),
        sa.Column('related_asset_id', sa.Integer(), nullable=True),
        sa.Column('date', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('merchant', sa.String(), nullable=True),
        sa.Column('tags', sa.String(), nullable=True),
        sa.Column('created_at', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['credit_card_id'], ['creditcard.id'], ),
        sa.ForeignKeyConstraint(['related_expense_id'], ['expense.id'], ),
        sa.ForeignKeyConstraint(['related_asset_id'], ['asset.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_creditcardtransaction_credit_card_id'), 'creditcardtransaction', ['credit_card_id'], unique=False)
    op.create_index(op.f('ix_creditcardtransaction_transaction_type'), 'creditcardtransaction', ['transaction_type'], unique=False)
    op.create_index(op.f('ix_creditcardtransaction_date'), 'creditcardtransaction', ['date'], unique=False)


def downgrade() -> None:
    """Drop creditcardtransaction table."""
    op.drop_index(op.f('ix_creditcardtransaction_date'), table_name='creditcardtransaction')
    op.drop_index(op.f('ix_creditcardtransaction_transaction_type'), table_name='creditcardtransaction')
    op.drop_index(op.f('ix_creditcardtransaction_credit_card_id'), table_name='creditcardtransaction')
    op.drop_table('creditcardtransaction')
