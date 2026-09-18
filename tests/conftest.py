"""
Shared pytest fixtures.

Each test gets a fresh app with an in-memory SQLite database
(TestingConfig), CSRF disabled and synchronous email sending
(EMAIL_ASYNC=False) so background threads never race the assertions.
"""

import hmac
import hashlib
import time as time_mod
from datetime import datetime, timedelta

import pytest

from app import create_app
from app.extensions import db as _db
from app.models import Event, Registration, User


@pytest.fixture()
def app():
    app = create_app('testing')
    with app.app_context():
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def db(app):
    return _db


def _make_event(**overrides):
    defaults = dict(
        title='Test Composite Course',
        description='<p>About the course</p>',
        event_date=datetime.now() + timedelta(days=30),
        location='Prague',
        capacity=5,
        event_type='workshop',
        event_category='doctor',
        is_active=True,
        registration_open=True,
    )
    defaults.update(overrides)
    event = Event(**defaults)
    _db.session.add(event)
    _db.session.commit()
    return event


@pytest.fixture()
def make_event(app):
    return _make_event


@pytest.fixture()
def event(make_event):
    return make_event()


def _make_registration(event, email='attendee@example.com', status=None, **overrides):
    from app.models.registration import RegistrationStatus
    reg = Registration(
        event_id=event.id,
        first_name='Test',
        last_name='Attendee',
        email=email,
        gdpr_consent=True,
        gdpr_consent_date=datetime.utcnow(),
        confirmation_token=Registration.generate_token(),
        status=status or RegistrationStatus.PENDING,
        **overrides,
    )
    _db.session.add(reg)
    _db.session.commit()
    return reg


@pytest.fixture()
def make_registration(app):
    return _make_registration


@pytest.fixture()
def admin_user(app):
    user = User(
        email='admin@example.com',
        first_name='Admin',
        last_name='User',
        is_admin=True,
        is_active=True,
    )
    user.password = 'test-password-123'
    _db.session.add(user)
    _db.session.commit()
    return user


def valid_form_token(app, age_seconds=10):
    """Build a form token that passes the anti-spam time check."""
    timestamp = str(int(time_mod.time()) - age_seconds)
    secret = app.config['SECRET_KEY']
    sig = hmac.new(secret.encode(), timestamp.encode(), hashlib.sha256).hexdigest()[:16]
    return f"{timestamp}.{sig}"


def human_form_data(app, **fields):
    """Base POST payload that passes all anti-spam checks."""
    data = {
        '_form_token': valid_form_token(app),
        '_js_check': 'human',
        'website': '',
    }
    data.update(fields)
    return data
