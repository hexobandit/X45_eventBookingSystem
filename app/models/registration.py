"""
Registration model for event attendees.
"""

from datetime import datetime
from enum import Enum
from app.extensions import db


class RegistrationStatus(Enum):
    """Registration status enumeration."""
    PENDING = 'pending'
    CONFIRMED = 'confirmed'
    CANCELLED = 'cancelled'
    WAITLIST = 'waitlist'


class PaymentStatus(Enum):
    """Payment status enumeration."""
    UNPAID = 'unpaid'
    PAID = 'paid'
    REFUNDED = 'refunded'


class PaymentMethod(Enum):
    """How the attendee chose to pay."""
    CARD = 'card'
    BANK_TRANSFER = 'bank_transfer'


class Registration(db.Model):
    """Event registration model."""

    __tablename__ = 'registrations'

    id = db.Column(db.Integer, primary_key=True)

    # Event reference
    event_id = db.Column(db.Integer, db.ForeignKey('events.id', ondelete='CASCADE'), nullable=False, index=True)

    # Attendee information
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), nullable=False, index=True)
    phone = db.Column(db.String(20))
    organization = db.Column(db.String(200))  # Practice/clinic name

    # Additional info
    notes = db.Column(db.Text)

    # GDPR
    gdpr_consent = db.Column(db.Boolean, nullable=False, default=False)
    gdpr_consent_date = db.Column(db.DateTime)

    # Status
    status = db.Column(
        db.Enum(RegistrationStatus),
        nullable=False,
        default=RegistrationStatus.PENDING,
        index=True
    )

    # Confirmation
    confirmation_token = db.Column(db.String(100), unique=True, index=True)
    confirmed_at = db.Column(db.DateTime)

    # Cancellation
    cancelled_at = db.Column(db.DateTime)
    cancellation_reason = db.Column(db.String(500))

    # Email tracking
    confirmation_email_sent = db.Column(db.Boolean, default=False)
    reminder_email_sent = db.Column(db.Boolean, default=False)
    payment_email_sent = db.Column(db.Boolean, default=False)
    payment_email_sent_at = db.Column(db.DateTime)
    custom_email_sent = db.Column(db.Boolean, default=False)
    custom_email_sent_at = db.Column(db.DateTime)

    # Payment tracking
    payment_status = db.Column(
        db.Enum(PaymentStatus),
        nullable=False,
        default=PaymentStatus.UNPAID,
        index=True
    )
    paid_at = db.Column(db.DateTime)
    payment_note = db.Column(db.String(500))

    # Per-registration variable symbol for payment matching
    variable_symbol = db.Column(db.String(20))

    # Payment method chosen at registration (NULL for legacy rows)
    payment_method = db.Column(db.Enum(PaymentMethod))

    # Stripe references (card payments)
    stripe_session_id = db.Column(db.String(255), index=True)
    stripe_payment_intent_id = db.Column(db.String(255))

    # Billing details for company invoices (all optional)
    billing_name = db.Column(db.String(200))
    billing_ico = db.Column(db.String(20))     # company registration number (IČO)
    billing_dic = db.Column(db.String(20))     # VAT number (DIČ)
    billing_street = db.Column(db.String(200))
    billing_city = db.Column(db.String(100))
    billing_zip = db.Column(db.String(20))

    # Admin processing
    admin_note = db.Column(db.Text)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    event = db.relationship('Event', back_populates='registrations')

    # Unique constraint: one registration per email per event
    __table_args__ = (
        db.UniqueConstraint('event_id', 'email', name='uq_registration_event_email'),
    )

    @property
    def full_name(self):
        """Return full name of attendee."""
        return f"{self.first_name} {self.last_name}"

    @property
    def is_confirmed(self):
        """Check if registration is confirmed."""
        return self.status == RegistrationStatus.CONFIRMED

    @property
    def is_pending(self):
        """Check if registration is pending."""
        return self.status == RegistrationStatus.PENDING

    @property
    def is_cancelled(self):
        """Check if registration is cancelled."""
        return self.status == RegistrationStatus.CANCELLED

    @property
    def is_waitlisted(self):
        """Check if registration is on the waitlist."""
        return self.status == RegistrationStatus.WAITLIST

    @property
    def is_paid(self):
        """Check if registration is paid."""
        return self.payment_status == PaymentStatus.PAID

    def confirm(self):
        """Confirm the registration."""
        self.status = RegistrationStatus.CONFIRMED
        self.confirmed_at = datetime.utcnow()

    def cancel(self, reason=None):
        """Cancel the registration."""
        was_waitlisted = self.status == RegistrationStatus.WAITLIST
        self.status = RegistrationStatus.CANCELLED
        self.cancelled_at = datetime.utcnow()
        if reason:
            self.cancellation_reason = reason

        # Only decrement if this was an active (non-waitlist) registration
        if self.event and not was_waitlisted:
            self.event.decrement_registration()

    def move_to_waitlist(self):
        """Move registration to waitlist."""
        self.status = RegistrationStatus.WAITLIST

    def promote_from_waitlist(self):
        """Promote a waitlisted registration to PENDING and increment event count."""
        if self.status != RegistrationStatus.WAITLIST:
            return False
        self.status = RegistrationStatus.PENDING
        if self.event:
            if not self.event.increment_registration():
                return False
        return True

    @classmethod
    def generate_token(cls):
        """Generate a unique confirmation token."""
        import secrets
        return secrets.token_urlsafe(32)

    def __repr__(self):
        return f'<Registration {self.full_name} for {self.event_id}>'
