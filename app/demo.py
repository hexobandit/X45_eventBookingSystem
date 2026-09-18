"""
Demo-mode guard.

The public demo runs with DEMO_MODE=1 and a shared admin login. Visitors may
add, confirm, pay and delete registrations (the database is reseeded
nightly), but a few actions would spoil the demo for everyone else and are
refused with a flash message instead.
"""

from flask import request, flash, redirect, url_for

# Endpoints (or endpoint prefixes) whose POST requests are refused in demo mode.
BLOCKED_ENDPOINT_PREFIXES = (
    'admin_users.',            # create / edit / delete admin accounts
    'admin_change_password.',  # the shared demo password must stay known
    'admin_email_settings.',   # SMTP settings + test emails
    'admin_events.delete_view',
    'admin_events.action_view',  # bulk actions on courses (delete)
)

DEMO_MESSAGE = ('This action is disabled in the demo. Everything else — courses, '
                'registrations, payments, emails — is yours to try.')


def is_blocked(endpoint):
    if not endpoint:
        return False
    return any(endpoint.startswith(prefix) for prefix in BLOCKED_ENDPOINT_PREFIXES)


def register_demo_guard(app):
    @app.before_request
    def refuse_demo_breaking_writes():
        if request.method != 'POST':
            return None
        if not is_blocked(request.endpoint):
            return None
        flash(DEMO_MESSAGE, 'warning')
        return redirect(request.referrer or url_for('admin.index'))
