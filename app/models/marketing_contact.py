"""
MarketingContact model — one row per email address that ever reached us
(course registration, contact form, book inquiry), for promo mailings.
"""

from datetime import datetime
from app.extensions import db


class MarketingContact(db.Model):
    """Aggregated contact for marketing mailings (email + name only, no message archive)."""

    __tablename__ = 'marketing_contacts'

    SOURCES = ('registration', 'contact', 'book_inquiry', 'backfill')

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    name = db.Column(db.String(200), nullable=True)
    phone = db.Column(db.String(20), nullable=True)

    # Where the email first came from: registration | contact | book_inquiry | backfill
    source = db.Column(db.String(20), nullable=False, default='registration')

    # NULL = never asked / never ticked the box. True only upgrades, never downgrades.
    marketing_consent = db.Column(db.Boolean, nullable=True)
    marketing_consent_date = db.Column(db.DateTime, nullable=True)

    first_seen_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    last_seen_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    times_seen = db.Column(db.Integer, nullable=False, default=1)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<MarketingContact {self.email}>'
