"""
Spam log model for tracking blocked form submissions.
"""

from datetime import datetime
from app.extensions import db


class SpamLog(db.Model):
    """Log of form submissions blocked by anti-spam checks."""

    __tablename__ = 'spam_logs'

    id = db.Column(db.Integer, primary_key=True)
    form_type = db.Column(db.String(50), nullable=False, index=True)  # 'registration' or 'contact'
    reason = db.Column(db.String(100), nullable=False, index=True)  # 'honeypot', 'too_fast', 'no_js_token'
    ip_address = db.Column(db.String(45), nullable=True, index=True)
    user_agent = db.Column(db.String(500), nullable=True)

    # Submitted data (for review)
    submitted_email = db.Column(db.String(255), nullable=True)
    submitted_name = db.Column(db.String(200), nullable=True)
    submitted_data = db.Column(db.Text, nullable=True)  # JSON dump of other fields

    # Context
    event_slug = db.Column(db.String(200), nullable=True)
    time_on_page = db.Column(db.Float, nullable=True)  # seconds between load and submit

    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f'<SpamLog {self.reason} | {self.form_type} | {self.submitted_email}>'
