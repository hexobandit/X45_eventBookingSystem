"""Two offline payment methods (domestic CZK + SEPA EUR) and deleted-registration archive

Revision ID: f2b3c4d5e6a7
Revises: e1a2b3c4d5f6
Create Date: 2026-09-18
"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'f2b3c4d5e6a7'
down_revision = 'e1a2b3c4d5f6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('events') as batch_op:
        batch_op.add_column(sa.Column('payment_amount_czk', sa.Numeric(10, 2), nullable=True))
        batch_op.add_column(sa.Column('payment_sepa_iban', sa.String(length=34), nullable=True))
        batch_op.add_column(sa.Column('payment_sepa_bic', sa.String(length=11), nullable=True))
        batch_op.add_column(sa.Column('payment_amount_eur', sa.Numeric(10, 2), nullable=True))

    # Events that stored an IBAN in the (domestic) account field were in
    # practice SEPA setups — carry the IBAN over so their payment emails keep
    # working. The domestic field is left untouched (SPAYD accepts IBANs).
    op.execute(
        "UPDATE events SET payment_sepa_iban = REPLACE(payment_bank_account, ' ', '') "
        "WHERE payment_sepa_iban IS NULL AND payment_bank_account IS NOT NULL "
        "AND UPPER(SUBSTR(REPLACE(payment_bank_account, ' ', ''), 1, 2)) BETWEEN 'AA' AND 'ZZ' "
        "AND payment_bank_account NOT LIKE '%/%'"
    )

    op.create_table(
        'deleted_registrations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('registration_id', sa.Integer(), nullable=True),
        sa.Column('event_id', sa.Integer(), sa.ForeignKey('events.id', ondelete='SET NULL'), nullable=True),
        sa.Column('event_title', sa.String(length=200), nullable=True),
        sa.Column('first_name', sa.String(length=100), nullable=False),
        sa.Column('last_name', sa.String(length=100), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('phone', sa.String(length=20), nullable=True),
        sa.Column('organization', sa.String(length=200), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('payment_status', sa.String(length=20), nullable=True),
        sa.Column('payment_method', sa.String(length=20), nullable=True),
        sa.Column('variable_symbol', sa.String(length=20), nullable=True),
        sa.Column('paid_at', sa.DateTime(), nullable=True),
        sa.Column('registered_at', sa.DateTime(), nullable=True),
        sa.Column('confirmed_at', sa.DateTime(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('admin_note', sa.Text(), nullable=True),
        sa.Column('snapshot', sa.Text(), nullable=True),
        sa.Column('reason', sa.String(length=500), nullable=True),
        sa.Column('deleted_by', sa.String(length=255), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=False),
        sa.Column('cancellation_email_sent', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index('ix_deleted_registrations_registration_id', 'deleted_registrations', ['registration_id'])
    op.create_index('ix_deleted_registrations_event_id', 'deleted_registrations', ['event_id'])
    op.create_index('ix_deleted_registrations_email', 'deleted_registrations', ['email'])
    op.create_index('ix_deleted_registrations_deleted_at', 'deleted_registrations', ['deleted_at'])


def downgrade():
    op.drop_index('ix_deleted_registrations_deleted_at', table_name='deleted_registrations')
    op.drop_index('ix_deleted_registrations_email', table_name='deleted_registrations')
    op.drop_index('ix_deleted_registrations_event_id', table_name='deleted_registrations')
    op.drop_index('ix_deleted_registrations_registration_id', table_name='deleted_registrations')
    op.drop_table('deleted_registrations')

    with op.batch_alter_table('events') as batch_op:
        batch_op.drop_column('payment_amount_eur')
        batch_op.drop_column('payment_sepa_bic')
        batch_op.drop_column('payment_sepa_iban')
        batch_op.drop_column('payment_amount_czk')
