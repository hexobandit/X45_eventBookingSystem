"""
Flask Application Factory
Course booking engine — brand comes from app/branding.py
"""

import os
import time
from datetime import datetime
from flask import Flask, render_template
from werkzeug.middleware.proxy_fix import ProxyFix
from app.config import config
from app import branding


def create_app(config_name=None):
    """Create and configure the Flask application."""
    if config_name is None:
        config_name = os.environ.get('FLASK_CONFIG') or os.environ.get('FLASK_ENV', 'development')

    config_class = config[config_name]
    if hasattr(config_class, 'validate'):
        config_class.validate()

    app = Flask(__name__)
    app.config.from_object(config_class)

    # Trust nginx proxy headers (X-Forwarded-For, X-Forwarded-Proto, X-Forwarded-Host)
    # so url_for(_external=True) generates correct https:// URLs
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    # Initialize extensions
    from app.extensions import db, migrate, login_manager, csrf, bcrypt, limiter
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    bcrypt.init_app(app)
    limiter.init_app(app)

    # Cache-busting version (changes on each deployment/restart)
    asset_version = str(int(time.time()))

    from app.timefmt import time_ago
    app.add_template_filter(time_ago, 'time_ago')

    # Context processors
    @app.context_processor
    def inject_globals():
        """Inject global variables into all templates."""
        context = {
            'now': datetime.now,
            'current_year': datetime.now().year,
            'canonical_domain': app.config.get('CANONICAL_DOMAIN', ''),
            'ga4_id': app.config.get('GA4_ID', ''),
            'demo_mode': app.config.get('DEMO_MODE', False),
            'asset_v': asset_version,
        }
        context.update(branding.brand_context())
        return context

    # Register blueprints
    from app.routes.main import main
    app.register_blueprint(main)

    # Register admin auth blueprint
    from app.routes.admin import admin_bp
    app.register_blueprint(admin_bp)

    # Initialize Flask-Admin
    from app.admin import init_admin
    init_admin(app)

    # Register CLI commands
    from app.cli import register_commands
    register_commands(app)

    # Demo mode: refuse admin writes that would break the shared demo
    if app.config.get('DEMO_MODE'):
        from app.demo import register_demo_guard
        register_demo_guard(app)

    # Security headers
    @app.after_request
    def set_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        if not app.debug:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        return response

    # Error handlers
    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template('errors/500.html'), 500

    with app.app_context():
        # Tests build the schema directly; dev/prod use Alembic (flask db upgrade)
        # or the init-db convenience command.
        if config_name == 'testing':
            db.create_all()
        try:
            from app.models import Event
            Event.ensure_test_event()
        except Exception:
            # Tables may not exist yet on first deploy — run `flask db upgrade`,
            # and the test event will be created on next restart
            pass

    return app
