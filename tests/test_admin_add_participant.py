"""
Manual "Add participant" on the admin event Manage page.
"""

from app.extensions import db
from app.models import Registration, MarketingContact, AdminLog
from app.models.registration import RegistrationStatus
from app.models.event import WAITLIST_LIMIT

from tests.test_admin_auth import login

MANAGE = '/admin/admin_events/manage/'


def add_data(**overrides):
    data = {
        'action': 'add_registration',
        'first_name': 'Manual',
        'last_name': 'Attendee',
        'email': 'manual@example.com',
        'phone': '',
        'organization': '',
        'admin_note': '',
        'status': 'PENDING',
    }
    data.update(overrides)
    return data


class TestAddParticipant:
    def test_add_pending(self, client, admin_user, event):
        login(client, 'admin@example.com', 'test-password-123')
        r = client.post(f'{MANAGE}?id={event.id}', data=add_data())
        assert r.status_code == 302

        reg = Registration.query.filter_by(email='manual@example.com').one()
        assert reg.status == RegistrationStatus.PENDING
        assert reg.variable_symbol
        assert reg.gdpr_consent is False
        assert 'Added by admin (admin@example.com)' in reg.admin_note
        assert event.registered_count == 1
        assert AdminLog.query.filter_by(action='Manually added participant').count() == 1
        # marketing contact recorded without consent
        contact = MarketingContact.query.filter_by(email='manual@example.com').one()
        assert contact.marketing_consent is None

    def test_add_confirmed_sets_confirmed_at(self, client, admin_user, event):
        login(client, 'admin@example.com', 'test-password-123')
        client.post(f'{MANAGE}?id={event.id}', data=add_data(status='CONFIRMED'))
        reg = Registration.query.filter_by(email='manual@example.com').one()
        assert reg.status == RegistrationStatus.CONFIRMED
        assert reg.confirmed_at is not None

    def test_duplicate_email_rejected(self, client, admin_user, event, make_registration):
        make_registration(event, email='manual@example.com')
        login(client, 'admin@example.com', 'test-password-123')
        client.post(f'{MANAGE}?id={event.id}', data=add_data())
        assert Registration.query.filter_by(email='manual@example.com').count() == 1

    def test_cancelled_row_reactivated(self, client, admin_user, event, make_registration):
        reg = make_registration(event, email='manual@example.com',
                                status=RegistrationStatus.CANCELLED)
        login(client, 'admin@example.com', 'test-password-123')
        client.post(f'{MANAGE}?id={event.id}', data=add_data(first_name='Re'))

        assert Registration.query.filter_by(email='manual@example.com').count() == 1
        db.session.refresh(reg)
        assert reg.status == RegistrationStatus.PENDING
        assert reg.first_name == 'Re'
        assert reg.cancelled_at is None
        assert event.registered_count == 1

    def test_full_event_goes_to_waitlist(self, client, admin_user, make_event):
        event = make_event(capacity=1)
        login(client, 'admin@example.com', 'test-password-123')
        client.post(f'{MANAGE}?id={event.id}', data=add_data(email='a@example.com'))
        client.post(f'{MANAGE}?id={event.id}', data=add_data(email='b@example.com'))

        b = Registration.query.filter_by(email='b@example.com').one()
        assert b.status == RegistrationStatus.WAITLIST
        assert event.registered_count == 1  # waitlist consumes no capacity

    def test_full_waitlist_rejected(self, client, admin_user, make_event, make_registration):
        event = make_event(capacity=0)
        for i in range(WAITLIST_LIMIT):
            make_registration(event, email=f'w{i}@example.com',
                              status=RegistrationStatus.WAITLIST)
        login(client, 'admin@example.com', 'test-password-123')
        client.post(f'{MANAGE}?id={event.id}', data=add_data())
        assert Registration.query.filter_by(email='manual@example.com').count() == 0

    def test_missing_fields_rejected(self, client, admin_user, event):
        login(client, 'admin@example.com', 'test-password-123')
        client.post(f'{MANAGE}?id={event.id}', data=add_data(email='not-an-email'))
        client.post(f'{MANAGE}?id={event.id}', data=add_data(first_name=''))
        assert Registration.query.count() == 0
