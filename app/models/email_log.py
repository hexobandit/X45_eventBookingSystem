"""
Email log model for tracking all outbound emails.
"""

from datetime import datetime
from app.extensions import db


class EmailLog(db.Model):
    """Persistent log of every email send attempt."""

    __tablename__ = 'email_logs'

    id = db.Column(db.Integer, primary_key=True)
    to_email = db.Column(db.String(255), nullable=False, index=True)
    subject = db.Column(db.String(500), nullable=False)
    email_type = db.Column(db.String(50), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, index=True)  # 'sent' or 'failed'
    error_message = db.Column(db.Text, nullable=True)
    smtp_response = db.Column(db.String(500), nullable=True)
    smtp_debug = db.Column(db.Text, nullable=True)  # Full SMTP session transcript

    # Optional references
    registration_id = db.Column(db.Integer, db.ForeignKey('registrations.id'), nullable=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    # Relationships
    registration = db.relationship('Registration', backref=db.backref('email_logs', lazy='dynamic'))
    event = db.relationship('Event', backref=db.backref('email_logs', lazy='dynamic'))

    def __repr__(self):
        return f'<EmailLog {self.status} → {self.to_email}: {self.subject[:40]}>'
