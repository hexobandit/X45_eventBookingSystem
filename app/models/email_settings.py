"""
EmailSettings model - singleton for SMTP configuration stored in DB.
"""

import hashlib
import base64
from flask import current_app
from cryptography.fernet import Fernet

from app.extensions import db


class EmailSettings(db.Model):
    """Singleton model for SMTP email configuration."""

    __tablename__ = 'email_settings'

    id = db.Column(db.Integer, primary_key=True)
    smtp_host = db.Column(db.String(255), nullable=True)
    smtp_port = db.Column(db.Integer, default=587)
    smtp_username = db.Column(db.String(255), nullable=True)
    smtp_password_encrypted = db.Column(db.Text, nullable=True)
    smtp_use_tls = db.Column(db.Boolean, default=True)
    sender_email = db.Column(db.String(255), nullable=True)
    sender_name = db.Column(db.String(255), nullable=True)
    admin_email = db.Column(db.String(255), nullable=True)
    client_notification_emails = db.Column(db.String(500), nullable=True)
    doctor_notification_emails = db.Column(db.String(500), nullable=True)
    is_configured = db.Column(db.Boolean, default=False)

    @staticmethod
    def _get_fernet_key():
        """Derive a Fernet key from Flask SECRET_KEY."""
        secret = current_app.config['SECRET_KEY'].encode('utf-8')
        digest = hashlib.sha256(secret).digest()
        return base64.urlsafe_b64encode(digest)

    def set_password(self, plaintext):
        """Encrypt and store SMTP password."""
        if not plaintext:
            return
        f = Fernet(self._get_fernet_key())
        self.smtp_password_encrypted = f.encrypt(plaintext.encode('utf-8')).decode('utf-8')

    def get_password(self):
        """Decrypt and return SMTP password."""
        if not self.smtp_password_encrypted:
            return None
        f = Fernet(self._get_fernet_key())
        return f.decrypt(self.smtp_password_encrypted.encode('utf-8')).decode('utf-8')

    @classmethod
    def get_settings(cls):
        """Return the singleton settings row, or None."""
        return cls.query.first()

    @classmethod
    def get_or_create(cls):
        """Return existing settings or create a new empty row."""
        settings = cls.query.first()
        if not settings:
            settings = cls()
            db.session.add(settings)
            db.session.commit()
        return settings
