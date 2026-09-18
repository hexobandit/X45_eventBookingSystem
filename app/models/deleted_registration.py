"""
Archive of deleted registrations.

When an admin deletes a registration the live row is removed (which frees
the participant's email for a new registration to the same course — the
`registrations` table has a unique (event_id, email) constraint) and a
snapshot is stored here together with the reason, who deleted it and
whether a cancellation email went out.
"""

import json
from datetime import datetime, date
from decimal import Decimal
from enum import Enum

from app.extensions import db


class DeletedRegistration(db.Model):
    """Read-mostly tombstone for a registration removed by an admin."""

    __tablename__ = 'deleted_registrations'

    id = db.Column(db.Integer, primary_key=True)

    # Original identifiers (the registration row no longer exists)
    registration_id = db.Column(db.Integer, index=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id', ondelete='SET NULL'), index=True)
    event_title = db.Column(db.String(200))

    # Key participant fields, denormalised for listing/searching
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), nullable=False, index=True)
    phone = db.Column(db.String(20))
    organization = db.Column(db.String(200))

    status = db.Column(db.String(20))          # registration status at deletion
    payment_status = db.Column(db.String(20))
    payment_method = db.Column(db.String(20))
    variable_symbol = db.Column(db.String(20))
    paid_at = db.Column(db.DateTime)
    registered_at = db.Column(db.DateTime)
    confirmed_at = db.Column(db.DateTime)
    notes = db.Column(db.Text)                 # attendee notes
    admin_note = db.Column(db.Text)

    # Full column dump of the deleted row (JSON) for anything not listed above
    snapshot = db.Column(db.Text)

    # Deletion metadata
    reason = db.Column(db.String(500))
    deleted_by = db.Column(db.String(255))
    deleted_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    cancellation_email_sent = db.Column(db.Boolean, nullable=False, default=False)

    event = db.relationship('Event')

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def snapshot_dict(self):
        try:
            return json.loads(self.snapshot) if self.snapshot else {}
        except (TypeError, ValueError):
            return {}

    @staticmethod
    def _jsonable(value):
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, Decimal):
            return str(value)
        return value

    @classmethod
    def from_registration(cls, registration, reason=None, deleted_by=None,
                          cancellation_email_sent=False):
        """Build the archive row from a live registration (not yet added to the session)."""
        columns = {
            c.name: cls._jsonable(getattr(registration, c.name))
            for c in registration.__table__.columns
        }
        event = registration.event
        return cls(
            registration_id=registration.id,
            event_id=registration.event_id,
            event_title=event.title if event else None,
            first_name=registration.first_name,
            last_name=registration.last_name,
            email=registration.email,
            phone=registration.phone,
            organization=registration.organization,
            status=registration.status.value if registration.status else None,
            payment_status=registration.payment_status.value if registration.payment_status else None,
            payment_method=registration.payment_method.value if registration.payment_method else None,
            variable_symbol=registration.variable_symbol,
            paid_at=registration.paid_at,
            registered_at=registration.created_at,
            confirmed_at=registration.confirmed_at,
            notes=registration.notes,
            admin_note=registration.admin_note,
            snapshot=json.dumps(columns, ensure_ascii=False),
            reason=(reason or '').strip()[:500] or None,
            deleted_by=deleted_by,
            cancellation_email_sent=bool(cancellation_email_sent),
        )

    def __repr__(self):
        return f'<DeletedRegistration {self.full_name} ({self.email})>'
