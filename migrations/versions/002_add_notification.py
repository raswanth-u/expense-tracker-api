"""Add new table: notification

Revision ID: 002_add_notification
Revises: 001_initial
Create Date: 2026-01-04

TEST: Adding a new table (Low Risk)
This demonstrates how to safely add a new table to the database.

The Notification table will track user notifications for budget alerts,
expense reminders, etc.
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002_add_notification'
down_revision: str | Sequence[str] | None = '001_initial'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add notification table."""
    op.create_table(
        'notification',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False, index=True),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('message', sa.String(), nullable=False),
        sa.Column('notification_type', sa.String(), nullable=False),  # 'budget_alert', 'reminder', 'info'
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.String(), nullable=False),
        sa.Column('read_at', sa.String(), nullable=True),
    )
    

def downgrade() -> None:
    """Remove notification table."""
    op.drop_table('notification')
