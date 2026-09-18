"""
Anti-spam behaviour: honeypot, time token, JS check — and the
silent-success redirect that hides the detection from bots.
"""

import time
import hmac
import hashlib

from app.models import Registration
from app.models.spam_log import SpamLog

from tests.conftest import human_form_data, valid_form_token


def spam_free_data(app, **overrides):
    data = human_form_data(
        app,
        first_name='Jane', last_name='Smith', email='spam@example.com',
        phone='', organization='', notes='', gdpr='y',
    )
    data.update(overrides)
    return data


class TestHoneypot:
    def test_filled_honeypot_blocks_silently(self, app, client, event):
        r = client.post(f'/courses/{event.slug}/register',
                        data=spam_free_data(app, website='http://spam.example'))
        # Silent success: redirect as if accepted…
        assert r.status_code == 302
        # …but nothing stored, and the attempt is logged
        assert Registration.query.count() == 0
        log = SpamLog.query.one()
        assert log.reason == 'honeypot'
        assert log.form_type == 'registration'


class TestTimeToken:
    def test_missing_token_blocked(self, app, client, event):
        data = spam_free_data(app)
        del data['_form_token']
        r = client.post(f'/courses/{event.slug}/register', data=data)
        assert r.status_code == 302
        assert Registration.query.count() == 0
        assert SpamLog.query.one().reason == 'no_js_token'

    def test_forged_token_blocked(self, app, client, event):
        data = spam_free_data(app, _form_token=f'{int(time.time())}.deadbeefdeadbeef')
        client.post(f'/courses/{event.slug}/register', data=data)
        assert Registration.query.count() == 0
        assert SpamLog.query.one().reason == 'no_js_token'

    def test_too_fast_blocked(self, app, client, event):
        data = spam_free_data(app, _form_token=valid_form_token(app, age_seconds=1))
        client.post(f'/courses/{event.slug}/register', data=data)
        assert Registration.query.count() == 0
        log = SpamLog.query.one()
        assert log.reason == 'too_fast'
        assert log.time_on_page is not None and log.time_on_page < 3


class TestJsCheck:
    def test_missing_js_check_blocked(self, app, client, event):
        data = spam_free_data(app, _js_check='')
        client.post(f'/courses/{event.slug}/register', data=data)
        assert Registration.query.count() == 0
        assert SpamLog.query.one().reason == 'no_js_token'


class TestHumanPasses:
    def test_valid_submission_passes_all_checks(self, app, client, event):
        r = client.post(f'/courses/{event.slug}/register', data=spam_free_data(app))
        assert '/registration/success/' in r.headers['Location']
        assert Registration.query.count() == 1
        assert SpamLog.query.count() == 0

    def test_contact_form_spam_also_silent(self, app, client):
        r = client.post('/contact', data={
            'name': 'Bot', 'email': 'bot@example.com', 'subject': 'other',
            'message': 'Buy cheap things online now', 'gdpr': 'y',
            'website': 'gotcha', '_form_token': valid_form_token(app), '_js_check': 'human',
        })
        assert r.status_code == 302
        assert '/contact/sent' in r.headers['Location']
        assert SpamLog.query.one().form_type == 'contact'
