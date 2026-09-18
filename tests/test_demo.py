"""
Demo mode (DEMO_MODE=1): public email previews, banners, and the admin guard
that refuses actions which would break the shared demo.
"""

import pytest

from app import create_app
from app.config import TestingConfig
from app.extensions import db as _db
from tests.conftest import _make_event, _make_registration
from tests.test_admin_auth import login


@pytest.fixture()
def demo_app(monkeypatch):
    monkeypatch.setattr(TestingConfig, 'DEMO_MODE', True, raising=False)
    app = create_app('testing')
    with app.app_context():
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def demo_client(demo_app):
    return demo_app.test_client()


@pytest.fixture()
def demo_admin(demo_app):
    from app.models import User
    user = User(email='admin@example.com', first_name='Admin', last_name='User',
                is_admin=True, is_active=True)
    user.password = 'test-password-123'
    _db.session.add(user)
    _db.session.commit()
    return user


class TestPublicPreview:
    def test_preview_hidden_outside_demo(self, client, event, make_registration):
        reg = make_registration(event)
        r = client.get(f'/registration/{reg.confirmation_token}/email/confirmation')
        assert r.status_code == 404
        assert 'demo-banner' not in client.get('/').get_data(as_text=True)

    def test_preview_renders_each_kind(self, demo_client):
        event = _make_event(payment_bank_account='19-2000145399/0800',
                            payment_amount_czk=1000, currency='CZK', price=1000)
        reg = _make_registration(event)
        for kind, marker in (('confirmation', 'confirm'), ('payment', 'qr.png?kind=domestic'),
                             ('reminder', event.title)):
            r = demo_client.get(f'/registration/{reg.confirmation_token}/email/{kind}')
            assert r.status_code == 200, kind
            assert marker in r.get_data(as_text=True), kind
            assert r.headers['X-Robots-Tag'] == 'noindex, nofollow'

    def test_unknown_kind_404(self, demo_client):
        reg = _make_registration(_make_event())
        assert demo_client.get(f'/registration/{reg.confirmation_token}/email/nope').status_code == 404

    def test_banner_and_success_links(self, demo_client):
        event = _make_event()
        reg = _make_registration(event)
        assert 'demo-banner' in demo_client.get('/').get_data(as_text=True)
        body = demo_client.get(f'/registration/success/{reg.confirmation_token}').get_data(as_text=True)
        assert f'/registration/{reg.confirmation_token}/email/payment' in body


class TestAdminGuard:
    def test_user_creation_refused(self, demo_client, demo_admin):
        from app.models import User
        login(demo_client, 'admin@example.com', 'test-password-123')
        r = demo_client.post('/admin/admin_users/new/', data={
            'email': 'new@example.com', 'first_name': 'N', 'last_name': 'U',
            'is_admin': 'y', 'is_active': 'y', 'new_password': 'x' * 12,
        })
        assert r.status_code == 302
        assert User.query.filter_by(email='new@example.com').count() == 0

    def test_password_change_refused(self, demo_client, demo_admin):
        login(demo_client, 'admin@example.com', 'test-password-123')
        r = demo_client.post('/admin/change-password/', data={
            'current_password': 'test-password-123',
            'new_password': 'another-password-1', 'confirm_password': 'another-password-1'})
        assert r.status_code == 302
        assert demo_admin.check_password('test-password-123')

    def test_registration_edits_still_allowed(self, demo_client, demo_admin):
        """Only demo-breaking actions are blocked; the interesting flows stay live."""
        from app.models import Registration
        event = _make_event()
        reg = _make_registration(event)
        login(demo_client, 'admin@example.com', 'test-password-123')
        r = demo_client.post(f'/admin/admin_registrations/delete/', data={'id': reg.id, 'url': '/admin/admin_registrations/'})
        assert r.status_code == 302
        assert Registration.query.get(reg.id) is None
