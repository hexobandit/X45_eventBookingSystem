"""
Flask Configuration
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'

    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///app.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
    }

    # SEO
    CANONICAL_DOMAIN = os.environ.get('CANONICAL_DOMAIN', 'http://127.0.0.1:5000')

    # Analytics (empty = tag not rendered)
    GA4_ID = os.environ.get('GA4_ID', '')

    # Public demo instance: shows demo banners, exposes the "preview the email"
    # links on public pages, and blocks admin actions that would break the demo
    # for other visitors (users, SMTP settings, password, deleting courses).
    # The demo database is expected to be reset nightly (flask seed-events --reset).
    DEMO_MODE = os.environ.get('DEMO_MODE', '0') == '1'
    # Credentials shown in the demo banner and typed into the login form.
    # Purely informational: create the user with `flask create-admin`.
    DEMO_ADMIN_EMAIL = os.environ.get('DEMO_ADMIN_EMAIL', 'admin@example.com')
    DEMO_ADMIN_PASSWORD = os.environ.get('DEMO_ADMIN_PASSWORD', 'demo-2026')

    # Stripe card payments (empty = card option hidden, bank transfer still works)
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY', '')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', '')

    # Flask-Admin
    FLASK_ADMIN_SWATCH = 'cosmo'

    # Rate limiting
    RATELIMIT_STORAGE_URL = os.environ.get('REDIS_URL', 'memory://')

    # Emails are sent in a background thread; tests flip this off to run synchronously
    EMAIL_ASYNC = True

    # Security
    WTF_CSRF_ENABLED = True
    # Secure cookies require HTTPS; set SESSION_COOKIE_SECURE=0 only for an
    # IP-only preview deployment without TLS (breaks login/forms otherwise).
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', '1') != '0'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5MB upload limit


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///dev.db'
    SESSION_COOKIE_SECURE = False  # Allow HTTP in development
    RATELIMIT_ENABLED = False


class ProductionConfig(Config):
    """Production configuration.

    Requires SECRET_KEY and DATABASE_URL environment variables —
    validated in create_app() so that importing this module in
    development does not fail.
    """
    DEBUG = False
    PREFERRED_URL_SCHEME = os.environ.get('PREFERRED_URL_SCHEME', 'https')

    # PostgreSQL in production
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')

    # PostgreSQL-specific options for connection pooling and race condition handling
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_size': 10,
        'pool_recycle': 300,
        'max_overflow': 20,
    }

    @staticmethod
    def validate():
        missing = [var for var in ('SECRET_KEY', 'DATABASE_URL') if not os.environ.get(var)]
        if missing:
            raise RuntimeError(
                f"Production config requires environment variables: {', '.join(missing)}. "
                "Refusing to start with insecure defaults."
            )


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False
    EMAIL_ASYNC = False
    DEMO_MODE = False  # never inherit DEMO_MODE=1 from a local .env; tests opt in explicitly


# Config dictionary for easy access
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
