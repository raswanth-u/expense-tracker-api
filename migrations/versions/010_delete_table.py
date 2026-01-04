"""Delete table: notification (the one we created in test 002)

Revision ID: 010_delete_table
Revises: 009_add_unique_constraint
Create Date: 2026-01-04

TEST: Deleting a table (High Risk)
This demonstrates how to safely remove a table.

Strategy:
1. FULL BACKUP of the entire database
2. EXPORT the table data separately (for recovery)
3. Verify no foreign keys reference this table
4. Verify no application code uses this table
5. Drop the table
6. Update models and remove from codebase

WARNING: THIS IS IRREVERSIBLE!
The downgrade recreates the structure but NOT the data.
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '010_delete_table'
down_revision: str | Sequence[str] | None = '009_add_unique_constraint'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """
    Delete the notification table.
    
    BEFORE RUNNING:
    1. Full database backup
    2. Export notification table: pg_dump -t notification > notification_backup.sql
    3. Verify no FKs reference this table
    4. Verify no code uses this table
    """
    # Check for foreign key dependencies first
    # (notification table has no dependencies in our case)
    
    op.drop_table('notification')
    

def downgrade() -> None:
    """
    Recreate notification table structure.
    
    WARNING: Original data is LOST! Only structure is recreated.
    """
    op.create_table(
        'notification',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False, index=True),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('message', sa.String(), nullable=False),
        sa.Column('notification_type', sa.String(), nullable=False),
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.String(), nullable=False),
        sa.Column('read_at', sa.String(), nullable=True),
    )
