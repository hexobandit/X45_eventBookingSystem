"""
Admin authentication routes.
"""

from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.extensions import db, limiter
from app.models import User, AdminLog
from app.forms.auth import LoginForm

admin_bp = Blueprint('admin_auth', __name__, url_prefix='/admin')


def _log_login(action, email, details=None):
    """Record a login/logout event in the admin audit log, with client IP."""
    try:
        ip = request.remote_addr or 'unknown'
        db.session.add(AdminLog(
            action=action,
            user_email=(email or 'unknown').lower(),
            target_type='auth',
            details=f'{details} — IP {ip}' if details else f'IP {ip}'
        ))
        db.session.commit()
    except Exception:
        db.session.rollback()


@admin_bp.app_errorhandler(429)
def rate_limit_exceeded(e):
    """Log rate-limit hits on admin auth routes (they bypass the route handler)."""
    if request.path.startswith('/admin'):
        email = request.form.get('email') if request.method == 'POST' else None
        _log_login('Login rate limited', email or request.remote_addr,
                   f'Limit: {e.description}')
        flash('Too many login attempts. Please wait a minute and try again.', 'error')
        return render_template('admin/login.html', form=LoginForm()), 429
    return e


@admin_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    """Admin login page."""
    if current_user.is_authenticated:
        return redirect(url_for('admin.index'))

    form = LoginForm()

    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower()).first()

        if user and user.check_password(form.password.data):
            if not user.is_active:
                _log_login('Login failed', form.email.data, 'Account deactivated')
                flash('This account has been deactivated.', 'error')
                return render_template('admin/login.html', form=form)

            if not user.is_admin:
                _log_login('Login failed', form.email.data, 'No admin permission')
                flash('You do not have permission to access the admin.', 'error')
                return render_template('admin/login.html', form=form)

            login_user(user, remember=form.remember.data)
            user.update_last_login()
            db.session.commit()
            _log_login('Login success', user.email)

            flash('Signed in successfully.', 'success')

            next_page = request.args.get('next')
            if next_page and next_page.startswith('/admin'):
                return redirect(next_page)
            return redirect(url_for('admin.index'))

        _log_login('Login failed', form.email.data,
                   'Unknown email' if user is None else 'Wrong password')
        flash('Invalid email or password.', 'error')

    return render_template('admin/login.html', form=form)


@admin_bp.route('/logout')
@login_required
def logout():
    """Admin logout."""
    email = current_user.email
    logout_user()
    _log_login('Logout', email)
    flash('You have been signed out.', 'info')
    return redirect(url_for('admin_auth.login'))
