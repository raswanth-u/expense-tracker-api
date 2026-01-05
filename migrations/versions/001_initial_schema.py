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
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False, unique=True),
        sa.Column('role', sa.String(), nullable=False, server_default='member'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    
    # 2. SavingsAccount table (depends on user)
    op.create_table(
        'savingsaccount',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('account_name', sa.String(), nullable=False),
        sa.Column('bank_name', sa.String(), nullable=False),
        sa.Column('account_number_last_four', sa.String(4), nullable=False),
        sa.Column('account_type', sa.String(), nullable=False),
        sa.Column('current_balance', sa.Numeric(12, 2), nullable=False, server_default='0.0'),
        sa.Column('minimum_balance', sa.Numeric(12, 2), nullable=False, server_default='0.0'),
        sa.Column('interest_rate', sa.Numeric(5, 4), nullable=False, server_default='0.0'),
        sa.Column('tags', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    
    # 3. CreditCard table (depends on user)
    op.create_table(
        'creditcard',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('card_name', sa.String(), nullable=False),
        sa.Column('last_four', sa.String(4), nullable=False),
        sa.Column('credit_limit', sa.Numeric(12, 2), nullable=False),
        sa.Column('billing_day', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('tags', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    
    # 4. DebitCard table (depends on user, savingsaccount)
    op.create_table(
        'debitcard',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('card_name', sa.String(), nullable=False),
        sa.Column('last_four', sa.String(4), nullable=False),
        sa.Column('savings_account_id', sa.Integer(), sa.ForeignKey('savingsaccount.id'), nullable=False),
        sa.Column('daily_limit', sa.Numeric(12, 2), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('tags', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    
    # 5. Budget table (depends on user, optional)
    op.create_table(
        'budget',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=True),
        sa.Column('category', sa.String(), nullable=False),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('period', sa.String(), nullable=False, server_default='monthly'),
        sa.Column('month', sa.String(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('tags', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    
    # 6. Expense table (depends on user, creditcard, savingsaccount)
    op.create_table(
        'expense',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('category', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('payment_method', sa.String(), nullable=False),
        sa.Column('credit_card_id', sa.Integer(), sa.ForeignKey('creditcard.id'), nullable=True),
        sa.Column('is_recurring', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('tags', sa.String(), nullable=True),
        sa.Column('savings_account_id', sa.Integer(), sa.ForeignKey('savingsaccount.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    
    # 7. SavingsGoal table (depends on user)
    op.create_table(
        'savingsgoal',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('target_amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('current_amount', sa.Numeric(12, 2), nullable=False, server_default='0.0'),
        sa.Column('deadline', sa.Date(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('tags', sa.String(), nullable=True),
    )
    
    # 8. Asset table (depends on user, creditcard, savingsaccount)
    op.create_table(
        'asset',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('payment_method', sa.String(), nullable=False),
        sa.Column('asset_type', sa.String(), nullable=False),
        sa.Column('purchase_value', sa.Numeric(12, 2), nullable=False),
        sa.Column('current_value', sa.Numeric(12, 2), nullable=False),
        sa.Column('purchase_date', sa.Date(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('location', sa.String(), nullable=True),
        sa.Column('credit_card_id', sa.Integer(), sa.ForeignKey('creditcard.id'), nullable=True),
        sa.Column('savings_account_id', sa.Integer(), sa.ForeignKey('savingsaccount.id'), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('tags', sa.String(), nullable=True),
    )
    
    # 9. RecurringExpenseTemplate table (depends on user)
    op.create_table(
        'recurringexpensetemplate',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('category', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('frequency', sa.String(), nullable=False),
        sa.Column('interval', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('day_of_week', sa.Integer(), nullable=True),
        sa.Column('day_of_month', sa.Integer(), nullable=True),
        sa.Column('month_of_year', sa.Integer(), nullable=True),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('next_occurrence', sa.Date(), nullable=False),
        sa.Column('last_generated', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('tags', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    
    # 10. SavingsAccountTransaction table (depends on savingsaccount, expense, asset)
    op.create_table(
        'savingsaccounttransaction',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('savings_account_id', sa.Integer(), sa.ForeignKey('savingsaccount.id'), nullable=False),
        sa.Column('transaction_type', sa.String(), nullable=False),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('balance_after', sa.Numeric(12, 2), nullable=False),
        sa.Column('related_expense_id', sa.Integer(), sa.ForeignKey('expense.id'), nullable=True),
        sa.Column('related_asset_id', sa.Integer(), sa.ForeignKey('asset.id'), nullable=True),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('tags', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    
    # 11. CreditCardTransaction table (depends on creditcard, expense, asset)
    op.create_table(
        'creditcardtransaction',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('credit_card_id', sa.Integer(), sa.ForeignKey('creditcard.id'), nullable=False),
        sa.Column('transaction_type', sa.String(), nullable=False),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('balance_after', sa.Numeric(12, 2), nullable=False),
        sa.Column('related_expense_id', sa.Integer(), sa.ForeignKey('expense.id'), nullable=True),
        sa.Column('related_asset_id', sa.Integer(), sa.ForeignKey('asset.id'), nullable=True),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('merchant', sa.String(), nullable=True),
        sa.Column('tags', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )

    # Create indexes for better query performance
    op.create_index(op.f('ix_user_name'), 'user', ['name'], unique=False)
    op.create_index(op.f('ix_user_email'), 'user', ['email'], unique=True)
    
    # Foreign key indexes for better JOIN performance
    op.create_index(op.f('ix_savingsaccount_user_id'), 'savingsaccount', ['user_id'], unique=False)
    op.create_index(op.f('ix_creditcard_user_id'), 'creditcard', ['user_id'], unique=False)
    op.create_index(op.f('ix_debitcard_user_id'), 'debitcard', ['user_id'], unique=False)
    op.create_index(op.f('ix_debitcard_savings_account_id'), 'debitcard', ['savings_account_id'], unique=False)
    
    # Frequently queried columns
    op.create_index(op.f('ix_budget_category'), 'budget', ['category'], unique=False)
    op.create_index(op.f('ix_budget_month'), 'budget', ['month'], unique=False)
    op.create_index(op.f('ix_expense_user_id'), 'expense', ['user_id'], unique=False)
    op.create_index(op.f('ix_expense_category'), 'expense', ['category'], unique=False)
    op.create_index(op.f('ix_expense_date'), 'expense', ['date'], unique=False)
    op.create_index(op.f('ix_savingsgoal_user_id'), 'savingsgoal', ['user_id'], unique=False)
    op.create_index(op.f('ix_savingsgoal_deadline'), 'savingsgoal', ['deadline'], unique=False)
    op.create_index(op.f('ix_asset_user_id'), 'asset', ['user_id'], unique=False)
    op.create_index(op.f('ix_asset_asset_type'), 'asset', ['asset_type'], unique=False)
    op.create_index(op.f('ix_recurringexpensetemplate_user_id'), 'recurringexpensetemplate', ['user_id'], unique=False)
    op.create_index(op.f('ix_recurringexpensetemplate_category'), 'recurringexpensetemplate', ['category'], unique=False)
    op.create_index(op.f('ix_recurringexpensetemplate_frequency'), 'recurringexpensetemplate', ['frequency'], unique=False)
    op.create_index(op.f('ix_recurringexpensetemplate_start_date'), 'recurringexpensetemplate', ['start_date'], unique=False)
    op.create_index(op.f('ix_recurringexpensetemplate_next_occurrence'), 'recurringexpensetemplate', ['next_occurrence'], unique=False)
    
    # Transaction table indexes
    op.create_index(op.f('ix_savingsaccounttransaction_savings_account_id'), 'savingsaccounttransaction', ['savings_account_id'], unique=False)
    op.create_index(op.f('ix_savingsaccounttransaction_transaction_type'), 'savingsaccounttransaction', ['transaction_type'], unique=False)
    op.create_index(op.f('ix_savingsaccounttransaction_date'), 'savingsaccounttransaction', ['date'], unique=False)
    op.create_index(op.f('ix_creditcardtransaction_credit_card_id'), 'creditcardtransaction', ['credit_card_id'], unique=False)
    op.create_index(op.f('ix_creditcardtransaction_transaction_type'), 'creditcardtransaction', ['transaction_type'], unique=False)
    op.create_index(op.f('ix_creditcardtransaction_date'), 'creditcardtransaction', ['date'], unique=False)

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
