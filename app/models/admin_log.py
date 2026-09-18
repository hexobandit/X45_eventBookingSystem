"""
Admin audit log model for tracking admin actions.
"""

from datetime import datetime
from app.extensions import db


class AdminLog(db.Model):
    __tablename__ = 'admin_logs'

    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(100), nullable=False, index=True)
    user_email = db.Column(db.String(255), nullable=False, index=True)
    target_type = db.Column(db.String(50), nullable=True, index=True)
    target_id = db.Column(db.Integer, nullable=True)
    details = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f'<AdminLog {self.action} by {self.user_email}>'
