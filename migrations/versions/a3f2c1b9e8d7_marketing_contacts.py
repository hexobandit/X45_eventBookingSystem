"""Marketing contacts table + backfill from registrations and inquiries

Revision ID: a3f2c1b9e8d7
Revises: d75191cd781c
Create Date: 2026-07-16

Backfill inserts one row per distinct (lowercased) email across registrations
and inquiries with source='backfill' and marketing_consent=NULL. Marketing
consent is NEVER derived from gdpr_consent — different legal basis.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a3f2c1b9e8d7'
down_revision = 'd75191cd781c'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'marketing_contacts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=True),
        sa.Column('phone', sa.String(length=20), nullable=True),
        sa.Column('source', sa.String(length=20), nullable=False),
        sa.Column('marketing_consent', sa.Boolean(), nullable=True),
        sa.Column('marketing_consent_date', sa.DateTime(), nullable=True),
        sa.Column('first_seen_at', sa.DateTime(), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(), nullable=False),
        sa.Column('times_seen', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_marketing_contacts_email'), 'marketing_contacts',
                    ['email'], unique=True)

    # Backfill — a single INSERT ... SELECT in portable SQL (SQLite + PostgreSQL),
    # so no Python-side datetime binding is involved. Name/phone approximated
    # per email via MAX(); good enough for a mailing list.
    op.execute(sa.text("""
        INSERT INTO marketing_contacts
            (email, name, phone, source, marketing_consent,
             first_seen_at, last_seen_at, times_seen, created_at, updated_at)
        SELECT LOWER(TRIM(email)),
               MAX(name),
               MAX(phone),
               'backfill',
               NULL,
               COALESCE(MIN(created_at), CURRENT_TIMESTAMP),
               COALESCE(MAX(created_at), CURRENT_TIMESTAMP),
               COUNT(*),
               CURRENT_TIMESTAMP,
               CURRENT_TIMESTAMP
        FROM (
            SELECT email, first_name || ' ' || last_name AS name, phone, created_at
            FROM registrations
            UNION ALL
            SELECT email, name, NULL AS phone, created_at
            FROM inquiries
        ) all_emails
        WHERE email IS NOT NULL AND TRIM(email) != ''
        GROUP BY LOWER(TRIM(email))
    """))


def downgrade():
    op.drop_index(op.f('ix_marketing_contacts_email'), table_name='marketing_contacts')
    op.drop_table('marketing_contacts')
