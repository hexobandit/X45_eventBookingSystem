"""
Marketing contacts: upsert semantics and the public-form hooks.
"""

from app.extensions import db
from app.models import MarketingContact
from app.services.marketing import upsert_marketing_contact

from tests.conftest import human_form_data
from tests.test_registration_flow import registration_data


def contact_data(app, **overrides):
    data = human_form_data(
        app,
        name='John Writer',
        email='writer@example.com',
        phone='',
        subject='course',
        message='I have a question about the composite course.',
        gdpr='y',
    )
    data.update(overrides)
    return data


class TestRegistrationHook:
    def test_registration_with_marketing_creates_contact_with_consent(self, app, client, event):
        r = client.post(f'/courses/{event.slug}/register',
                        data=registration_data(app, marketing='y'))
        assert r.status_code == 302

        contact = MarketingContact.query.filter_by(email='jane@example.com').one()
        assert contact.marketing_consent is True
        assert contact.marketing_consent_date is not None
        assert contact.source == 'registration'
        assert contact.name == 'Jane Smith'
        assert contact.times_seen == 1

    def test_registration_without_marketing_leaves_consent_null(self, app, client, event):
        client.post(f'/courses/{event.slug}/register', data=registration_data(app))
        contact = MarketingContact.query.filter_by(email='jane@example.com').one()
        assert contact.marketing_consent is None

    def test_consent_never_downgrades(self, app, client, make_event):
        e1, e2 = make_event(), make_event()
        client.post(f'/courses/{e1.slug}/register',
                    data=registration_data(app, marketing='y'))
        client.post(f'/courses/{e2.slug}/register', data=registration_data(app))

        contact = MarketingContact.query.filter_by(email='jane@example.com').one()
        assert contact.times_seen == 2
        assert contact.marketing_consent is True

    def test_spam_registration_creates_no_contact(self, client, event, app):
        client.post(f'/courses/{event.slug}/register',
                    data=registration_data(app, website='spammy'))  # honeypot
        assert MarketingContact.query.count() == 0

    def test_registration_survives_broken_marketing_table(self, app, client, event):
        MarketingContact.__table__.drop(db.engine)
        r = client.post(f'/courses/{event.slug}/register',
                        data=registration_data(app))
        assert r.status_code == 302
        assert '/registration/success/' in r.headers['Location']
        # recreate so the app-context teardown drop_all doesn't complain
        MarketingContact.__table__.create(db.engine)


class TestContactHooks:
    def test_contact_form_creates_contact(self, app, client):
        r = client.post('/contact', data=contact_data(app))
        assert r.status_code == 302
        contact = MarketingContact.query.filter_by(email='writer@example.com').one()
        assert contact.source == 'contact'
        assert contact.marketing_consent is None


class TestUpsertHelper:
    def test_email_normalised(self, app):
        upsert_marketing_contact('  Jane@Example.COM ', name='Jane', source='contact')
        assert MarketingContact.query.filter_by(email='jane@example.com').count() == 1

    def test_blank_email_ignored(self, app):
        assert upsert_marketing_contact('   ') is None
        assert MarketingContact.query.count() == 0
