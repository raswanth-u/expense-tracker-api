"""Initial schema - create all tables

Revision ID: 001_initial
Revises: None
Create Date: 2026-01-04

This migration creates all the initial tables for the expense tracker application.
Tables created:
- user
- savingsaccount
- savingsaccounttransaction
- creditcard
- creditcardtransaction
- debitcard
- budget
- expense
- savingsgoal
- asset
- recurringexpensetemplate
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create all initial tables."""
    
    # 1. User table (no dependencies)
    op.create_table(
        'user',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(), nullable=False, index=True),
        sa.Column('email', sa.String(), nullable=False, unique=True, index=True),
        sa.Column('role', sa.String(), nullable=False, server_default='member'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.String(), nullable=False),
    )
    
    # 2. SavingsAccount table (depends on user)
    op.create_table(
        'savingsaccount',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False, index=True),
        sa.Column('account_name', sa.String(), nullable=False),
        sa.Column('bank_name', sa.String(), nullable=False),
        sa.Column('account_number_last_four', sa.String(4), nullable=False),
        sa.Column('account_type', sa.String(), nullable=False),
        sa.Column('current_balance', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('minimum_balance', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('interest_rate', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('tags', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.String(), nullable=False),
    )
    
    # 3. CreditCard table (depends on user)
    op.create_table(
        'creditcard',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False, index=True),
        sa.Column('card_name', sa.String(), nullable=False),
        sa.Column('last_four', sa.String(4), nullable=False),
        sa.Column('credit_limit', sa.Float(), nullable=False),
        sa.Column('billing_day', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('tags', sa.String(), nullable=True),
    )
    
    # 4. DebitCard table (depends on user, savingsaccount)
    op.create_table(
        'debitcard',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False, index=True),
        sa.Column('card_name', sa.String(), nullable=False),
        sa.Column('last_four', sa.String(4), nullable=False),
        sa.Column('savings_account_id', sa.Integer(), sa.ForeignKey('savingsaccount.id'), nullable=False, index=True),
        sa.Column('daily_limit', sa.Float(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('tags', sa.String(), nullable=True),
        sa.Column('created_at', sa.String(), nullable=False),
    )
    
    # 5. Budget table (depends on user, optional)
    op.create_table(
        'budget',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=True),
        sa.Column('category', sa.String(), nullable=False, index=True),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('period', sa.String(), nullable=False, server_default='monthly'),
        sa.Column('month', sa.String(), nullable=False, index=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('tags', sa.String(), nullable=True),
    )
    
    # 6. Expense table (depends on user, creditcard, savingsaccount)
    op.create_table(
        'expense',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False, index=True),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('category', sa.String(), nullable=False, index=True),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('date', sa.String(), nullable=False, index=True),
        sa.Column('payment_method', sa.String(), nullable=False),
        sa.Column('credit_card_id', sa.Integer(), sa.ForeignKey('creditcard.id'), nullable=True),
        sa.Column('is_recurring', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('tags', sa.String(), nullable=True),
        sa.Column('savings_account_id', sa.Integer(), sa.ForeignKey('savingsaccount.id'), nullable=True),
    )
    
    # 7. SavingsGoal table (depends on user)
    op.create_table(
        'savingsgoal',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False, index=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('target_amount', sa.Float(), nullable=False),
        sa.Column('current_amount', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('deadline', sa.String(), nullable=False, index=True),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.String(), nullable=False),
        sa.Column('tags', sa.String(), nullable=True),
    )
    
    # 8. Asset table (depends on user, creditcard, savingsaccount)
    op.create_table(
        'asset',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False, index=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('payment_method', sa.String(), nullable=False),
        sa.Column('asset_type', sa.String(), nullable=False, index=True),
        sa.Column('purchase_value', sa.Float(), nullable=False),
        sa.Column('current_value', sa.Float(), nullable=False),
        sa.Column('purchase_date', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('location', sa.String(), nullable=True),
        sa.Column('credit_card_id', sa.Integer(), sa.ForeignKey('creditcard.id'), nullable=True),
        sa.Column('savings_account_id', sa.Integer(), sa.ForeignKey('savingsaccount.id'), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.String(), nullable=False),
        sa.Column('updated_at', sa.String(), nullable=True),
        sa.Column('tags', sa.String(), nullable=True),
    )
    
    # 9. RecurringExpenseTemplate table (depends on user)
    op.create_table(
        'recurringexpensetemplate',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False, index=True),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('category', sa.String(), nullable=False, index=True),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('frequency', sa.String(), nullable=False, index=True),
        sa.Column('interval', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('day_of_week', sa.Integer(), nullable=True),
        sa.Column('day_of_month', sa.Integer(), nullable=True),
        sa.Column('month_of_year', sa.Integer(), nullable=True),
        sa.Column('start_date', sa.String(), nullable=False, index=True),
        sa.Column('end_date', sa.String(), nullable=True),
        sa.Column('next_occurrence', sa.String(), nullable=False, index=True),
        sa.Column('last_generated', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('tags', sa.String(), nullable=True),
        sa.Column('created_at', sa.String(), nullable=False),
    )
    
    # 10. SavingsAccountTransaction table (depends on savingsaccount, expense, asset)
    op.create_table(
        'savingsaccounttransaction',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('savings_account_id', sa.Integer(), sa.ForeignKey('savingsaccount.id'), nullable=False, index=True),
        sa.Column('transaction_type', sa.String(), nullable=False, index=True),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('balance_after', sa.Float(), nullable=False),
        sa.Column('related_expense_id', sa.Integer(), sa.ForeignKey('expense.id'), nullable=True),
        sa.Column('related_asset_id', sa.Integer(), sa.ForeignKey('asset.id'), nullable=True),
        sa.Column('date', sa.String(), nullable=False, index=True),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('tags', sa.String(), nullable=True),
        sa.Column('created_at', sa.String(), nullable=False),
    )
    
    # 11. CreditCardTransaction table (depends on creditcard, expense, asset)
    op.create_table(
        'creditcardtransaction',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('credit_card_id', sa.Integer(), sa.ForeignKey('creditcard.id'), nullable=False, index=True),
        sa.Column('transaction_type', sa.String(), nullable=False, index=True),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('balance_after', sa.Float(), nullable=False),
        sa.Column('related_expense_id', sa.Integer(), sa.ForeignKey('expense.id'), nullable=True),
        sa.Column('related_asset_id', sa.Integer(), sa.ForeignKey('asset.id'), nullable=True),
        sa.Column('date', sa.String(), nullable=False, index=True),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('merchant', sa.String(), nullable=True),
        sa.Column('tags', sa.String(), nullable=True),
        sa.Column('created_at', sa.String(), nullable=False),
    )


def downgrade() -> None:
    """Drop all tables in reverse order."""
    op.drop_table('creditcardtransaction')
    op.drop_table('savingsaccounttransaction')
    op.drop_table('recurringexpensetemplate')
    op.drop_table('asset')
    op.drop_table('savingsgoal')
    op.drop_table('expense')
    op.drop_table('budget')
    op.drop_table('debitcard')
    op.drop_table('creditcard')
    op.drop_table('savingsaccount')
    op.drop_table('user')
