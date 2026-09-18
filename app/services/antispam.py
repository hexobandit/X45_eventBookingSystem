"""
Anti-spam protection: honeypot, time-based check, JS token.
"""

import json
import hmac
import time
import hashlib
from flask import request, current_app
from app.extensions import db
from app.models.spam_log import SpamLog

# Minimum seconds a human needs to fill a form
MIN_SUBMIT_TIME = 3


def generate_form_token():
    """Generate a time-stamped HMAC token for form load time verification."""
    timestamp = str(int(time.time()))
    secret = current_app.config['SECRET_KEY']
    sig = hmac.new(secret.encode(), timestamp.encode(), hashlib.sha256).hexdigest()[:16]
    return f"{timestamp}.{sig}"


def verify_form_token(token):
    """Verify token and return elapsed seconds since form was loaded. Returns None if invalid."""
    if not token or '.' not in token:
        return None
    parts = token.split('.', 1)
    if len(parts) != 2:
        return None
    timestamp_str, sig = parts
    try:
        timestamp = int(timestamp_str)
    except (ValueError, TypeError):
        return None

    secret = current_app.config['SECRET_KEY']
    expected = hmac.new(secret.encode(), timestamp_str.encode(), hashlib.sha256).hexdigest()[:16]
    if not hmac.compare_digest(sig, expected):
        return None

    return time.time() - timestamp


def log_spam(form_type, reason, submitted_email=None, submitted_name=None,
             submitted_data=None, event_slug=None, time_on_page=None):
    """Log a blocked spam submission."""
    try:
        entry = SpamLog(
            form_type=form_type,
            reason=reason,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent', '')[:500],
            submitted_email=submitted_email,
            submitted_name=submitted_name,
            submitted_data=json.dumps(submitted_data, ensure_ascii=False)[:2000] if submitted_data else None,
            event_slug=event_slug,
            time_on_page=time_on_page,
        )
        db.session.add(entry)
        db.session.commit()
    except Exception:
        db.session.rollback()


def check_spam(form_type, email=None, name=None, extra_data=None, event_slug=None):
    """
    Run all anti-spam checks on the current request.
    Returns (is_spam: bool, reason: str or None).
    """
    # 1. Honeypot — field named "website" should be empty
    honeypot_value = request.form.get('website', '')
    if honeypot_value:
        log_spam(form_type, 'honeypot', email, name, extra_data, event_slug)
        return True, 'honeypot'

    # 2. Time-based check
    form_token = request.form.get('_form_token', '')
    elapsed = verify_form_token(form_token)

    if elapsed is None:
        # No valid token = likely no JS or bot
        log_spam(form_type, 'no_js_token', email, name, extra_data, event_slug)
        return True, 'no_js_token'

    if elapsed < MIN_SUBMIT_TIME:
        log_spam(form_type, 'too_fast', email, name, extra_data, event_slug,
                 time_on_page=elapsed)
        return True, 'too_fast'

    # 3. JS-generated field check — "_js_check" must equal "human"
    js_check = request.form.get('_js_check', '')
    if js_check != 'human':
        log_spam(form_type, 'no_js_token', email, name, extra_data, event_slug,
                 time_on_page=elapsed)
        return True, 'no_js_token'

    return False, None
