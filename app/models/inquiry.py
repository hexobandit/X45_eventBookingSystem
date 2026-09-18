"""
Inquiry model — order interest, notify list, and general inquiries.
"""

import enum
from datetime import datetime
from app.extensions import db


class InquiryType(enum.Enum):
    BOOK_ORDER = 'book_order'    # order-interest form (legacy value name)
    BOOK_NOTIFY = 'book_notify'  # "notify me" list signups
    CONTACT = 'contact'          # general inquiry


class Inquiry(db.Model):
    """An order interest, notify-list signup, or general inquiry."""

    __tablename__ = 'inquiries'

    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.Enum(InquiryType), nullable=False, default=InquiryType.CONTACT, index=True)

    name = db.Column(db.String(200), nullable=True)
    email = db.Column(db.String(255), nullable=False, index=True)
    message = db.Column(db.Text, nullable=True)

    # GDPR
    gdpr_consent = db.Column(db.Boolean, default=False, nullable=False)
    gdpr_consent_date = db.Column(db.DateTime, nullable=True)

    # Admin workflow
    handled = db.Column(db.Boolean, default=False, nullable=False, index=True)
    admin_note = db.Column(db.Text, nullable=True)
    notified_at = db.Column(db.DateTime, nullable=True)  # when a batch email was last sent

    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        # one notify-list signup per email
        db.Index('ix_inquiries_type_email', 'type', 'email'),
    )

    def __repr__(self):
        return f'<Inquiry {self.type.value} | {self.email}>'
