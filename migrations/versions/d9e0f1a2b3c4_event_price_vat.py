"""Add price_includes_vat flag to events

Revision ID: d9e0f1a2b3c4
Revises: c8d1e2f3a4b5
Create Date: 2026-09-01
"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'd9e0f1a2b3c4'
down_revision = 'c8d1e2f3a4b5'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'events',
        sa.Column('price_includes_vat', sa.Boolean(), nullable=False, server_default='0')
    )


def downgrade():
    op.drop_column('events', 'price_includes_vat')
