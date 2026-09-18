"""
Flask extensions initialization.
Centralized extension instances to avoid circular imports.
"""

import os

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_bcrypt import Bcrypt
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Database
db = SQLAlchemy()
migrate = Migrate()

# Authentication
login_manager = LoginManager()
login_manager.login_view = 'admin_auth.login'
login_manager.login_message = 'Pro přístup se prosím přihlaste.'
login_manager.login_message_category = 'info'

# Security
csrf = CSRFProtect()
bcrypt = Bcrypt()

# Rate limiting
# Client IPs exempt from ALL rate limits (office / admin). The RATELIMIT_WHITELIST
# env var (comma-separated) extends this list without a code change. Requires the
# ProxyFix in app/__init__.py so get_remote_address() sees the real client IP.
RATE_LIMIT_WHITELIST = {
    ip.strip()
    for ip in ('85.71.252.194,' + os.environ.get('RATELIMIT_WHITELIST', '')).split(',')
    if ip.strip()
}

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["1000 per day", "200 per hour"],
    storage_uri="memory://"
)


@limiter.request_filter
def ip_whitelist():
    """Skip rate limiting entirely for whitelisted client IPs."""
    return get_remote_address() in RATE_LIMIT_WHITELIST


@login_manager.user_loader
def load_user(user_id):
    """Load user by ID for Flask-Login."""
    from app.models import User
    return User.query.get(int(user_id))
