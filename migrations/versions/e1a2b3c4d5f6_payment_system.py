"""Payment system: Stripe card payments, billing details, SEPA beneficiary

Revision ID: e1a2b3c4d5f6
Revises: d9e0f1a2b3c4
Create Date: 2026-09-09
"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'e1a2b3c4d5f6'
down_revision = 'd9e0f1a2b3c4'
branch_labels = None
depends_on = None

payment_method_enum = sa.Enum('CARD', 'BANK_TRANSFER', name='paymentmethod')


def upgrade():
    payment_method_enum.create(op.get_bind(), checkfirst=True)

    op.add_column('events', sa.Column('payment_beneficiary', sa.String(length=70), nullable=True))

    with op.batch_alter_table('registrations') as batch_op:
        batch_op.add_column(sa.Column('payment_method', payment_method_enum, nullable=True))
        batch_op.add_column(sa.Column('stripe_session_id', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('stripe_payment_intent_id', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('billing_name', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('billing_ico', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('billing_dic', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('billing_street', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('billing_city', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('billing_zip', sa.String(length=20), nullable=True))
        batch_op.create_index(batch_op.f('ix_registrations_stripe_session_id'), ['stripe_session_id'], unique=False)


def downgrade():
    with op.batch_alter_table('registrations') as batch_op:
        batch_op.drop_index(batch_op.f('ix_registrations_stripe_session_id'))
        batch_op.drop_column('billing_zip')
        batch_op.drop_column('billing_city')
        batch_op.drop_column('billing_street')
        batch_op.drop_column('billing_dic')
        batch_op.drop_column('billing_ico')
        batch_op.drop_column('billing_name')
        batch_op.drop_column('stripe_payment_intent_id')
        batch_op.drop_column('stripe_session_id')
        batch_op.drop_column('payment_method')

    op.drop_column('events', 'payment_beneficiary')

    payment_method_enum.drop(op.get_bind(), checkfirst=True)
