"""
End-to-end registration flow through the public routes.
"""

from datetime import datetime, timedelta

from app.extensions import db
from app.models import Event, Registration
from app.models.registration import RegistrationStatus

from tests.conftest import human_form_data


def registration_data(app, email='jane@example.com', **overrides):
    data = human_form_data(
        app,
        first_name='Jane',
        last_name='Smith',
        email=email,
        phone='+420 123 456 789',
        organization='Test Clinic',
        notes='',
        gdpr='y',
    )
    data.update(overrides)
    return data


class TestCourseListing:
    def test_courses_page_lists_active_future_events(self, client, make_event):
        make_event(title='Visible Course')
        make_event(title='Past Course', event_date=datetime.now() - timedelta(days=1))
        make_event(title='Inactive Course', is_active=False)
        html = client.get('/courses').get_data(as_text=True)
        assert 'Visible Course' in html
        assert 'Past Course' not in html
        assert 'Inactive Course' not in html

    def test_test_event_hidden_from_public(self, client):
        assert client.get('/courses/test-event').status_code == 404

    def test_detail_renders(self, client, event):
        r = client.get(f'/courses/{event.slug}')
        assert r.status_code == 200
        assert event.title in r.get_data(as_text=True)


class TestRegistration:
    def test_happy_path(self, app, client, event):
        r = client.post(f'/courses/{event.slug}/register',
                        data=registration_data(app))
        assert r.status_code == 302
        assert '/registration/success/' in r.headers['Location']

        reg = Registration.query.filter_by(email='jane@example.com').one()
        assert reg.status == RegistrationStatus.PENDING
        assert reg.variable_symbol
        assert event.registered_count == 1

        # success page renders with the token
        r2 = client.get(r.headers['Location'])
        assert r2.status_code == 200

    def test_duplicate_email_rejected(self, app, client, event):
        client.post(f'/courses/{event.slug}/register', data=registration_data(app))
        r = client.post(f'/courses/{event.slug}/register', data=registration_data(app))
        # redirected back to the course page, no second registration
        assert r.status_code == 302
        assert f'/courses/{event.slug}' in r.headers['Location']
        assert Registration.query.filter_by(email='jane@example.com').count() == 1
        assert event.registered_count == 1

    def test_full_event_goes_to_waitlist(self, app, client, make_event):
        event = make_event(capacity=1)
        client.post(f'/courses/{event.slug}/register',
                    data=registration_data(app, email='first@example.com'))
        r = client.post(f'/courses/{event.slug}/register',
                        data=registration_data(app, email='second@example.com'))
        assert '/registration/waitlist/' in r.headers['Location']

        reg = Registration.query.filter_by(email='second@example.com').one()
        assert reg.status == RegistrationStatus.WAITLIST
        # waitlist must not consume capacity
        assert event.registered_count == 1

    def test_confirm_via_token(self, app, client, event):
        client.post(f'/courses/{event.slug}/register', data=registration_data(app))
        reg = Registration.query.filter_by(email='jane@example.com').one()

        r = client.get(f'/registration/confirm/{reg.confirmation_token}')
        assert r.status_code == 200
        db.session.refresh(reg)
        assert reg.status == RegistrationStatus.CONFIRMED
        assert reg.confirmed_at is not None

    def test_cancel_via_token(self, app, client, event):
        client.post(f'/courses/{event.slug}/register', data=registration_data(app))
        reg = Registration.query.filter_by(email='jane@example.com').one()

        r = client.get(f'/registration/cancel/{reg.confirmation_token}')
        assert r.status_code == 302
        db.session.refresh(reg)
        assert reg.status == RegistrationStatus.CANCELLED
        assert event.registered_count == 0

    def test_reregistration_after_cancel(self, app, client, event):
        client.post(f'/courses/{event.slug}/register', data=registration_data(app))
        reg = Registration.query.filter_by(email='jane@example.com').one()
        client.get(f'/registration/cancel/{reg.confirmation_token}')

        r = client.post(f'/courses/{event.slug}/register', data=registration_data(app))
        assert '/registration/success/' in r.headers['Location']
        db.session.refresh(reg)
        assert reg.status == RegistrationStatus.PENDING
        assert Registration.query.filter_by(email='jane@example.com').count() == 1

    def test_invalid_token_404(self, client):
        assert client.get('/registration/confirm/not-a-real-token').status_code == 404

    def test_inactive_event_registration_404(self, app, client, make_event):
        event = make_event(is_active=False)
        r = client.post(f'/courses/{event.slug}/register', data=registration_data(app))
        assert r.status_code == 404

    def test_missing_gdpr_rerenders_with_error(self, app, client, event):
        data = registration_data(app)
        del data['gdpr']
        r = client.post(f'/courses/{event.slug}/register', data=data)
        assert r.status_code == 200  # re-rendered form, not redirect
        assert Registration.query.count() == 0

    def test_registration_not_yet_open(self, app, client, make_event):
        event = make_event(registration_opens_at=datetime.now() + timedelta(days=2))
        r = client.post(f'/courses/{event.slug}/register', data=registration_data(app))
        assert r.status_code == 302
        assert Registration.query.count() == 0
