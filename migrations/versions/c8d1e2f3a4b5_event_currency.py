"""Add currency column to events

Revision ID: c8d1e2f3a4b5
Revises: a3f2c1b9e8d7
Create Date: 2026-09-01
"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'c8d1e2f3a4b5'
down_revision = 'a3f2c1b9e8d7'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'events',
        sa.Column('currency', sa.String(length=3), nullable=False, server_default='EUR')
    )


def downgrade():
    op.drop_column('events', 'currency')
