"""
Two offline payment methods (domestic CZK + SEPA EUR): model properties,
QR builders, manage-panel save/validation, Generate-QR endpoint and the
payment email carrying one QR per method.
"""

from unittest.mock import patch, MagicMock

import pytest

from app.extensions import db
from app.models import EmailLog
from app.services.payment_qr import (
    normalize_iban, normalize_bic, domestic_qr_string, sepa_qr_string,
    event_test_qr_png, registration_qr_pngs,
)
from app.services.email import email_service
from tests.test_admin_auth import login
from tests.test_email_service import smtp_settings, mock_smtp  # noqa: F401 (fixtures)


IBAN = 'CZ6508000000192000145399'


# --- helpers ---------------------------------------------------------------

def test_normalize_iban_and_bic():
    assert normalize_iban('cz65 0800 0000 1920 0014 5399') == IBAN
    assert normalize_iban('CZ6508000000192000145398') is None  # bad check digits
    assert normalize_iban('') is None
    assert normalize_bic('gibaczpx') == 'GIBACZPX'
    assert normalize_bic('GIBACZPXXXX') == 'GIBACZPXXXX'
    assert normalize_bic('GIBA') is None


def test_domestic_and_sepa_strings():
    d = domestic_qr_string('19-2000145399/0800', 12490, vs='2027001', message='Course Jan')
    assert d.startswith('SPD*1.0*ACC:CZ65')
    assert '*AM:12490.00*CC:CZK*X-VS:2027001*MSG:Course Jan' in d
    assert domestic_qr_string('not-an-account', 100) is None
    assert domestic_qr_string('19-2000145399/0800', None) is None

    s = sepa_qr_string(IBAN, 469, 'ANTERIOR', vs='2027001', message='Jan', bic='GIBACZPX')
    lines = s.split('\n')
    assert lines[:4] == ['BCD', '002', '1', 'SCT']
    assert lines[4] == 'GIBACZPX'
    assert lines[6] == IBAN
    assert lines[7] == 'EUR469.00'
    assert lines[10] == 'VS 2027001 Jan'
    assert sepa_qr_string('CZ00', 469, 'X') is None


# --- Event properties -------------------------------------------------------

def test_event_method_properties(make_event):
    e = make_event(price=469, currency='EUR')
    assert not e.has_domestic_payment and not e.has_sepa_payment
    assert not e.has_payment_details

    e.payment_sepa_iban = IBAN               # EUR amount falls back to the fee
    assert e.sepa_amount == 469 and e.has_sepa_payment and e.has_payment_details

    e.payment_bank_account = '1234567890/0100'
    assert not e.has_domestic_payment        # no CZK amount for an EUR course
    e.payment_amount_czk = 11900
    assert e.has_domestic_payment
    assert e.formatted_domestic_amount == '11 900 Kč'
    assert e.formatted_sepa_amount == '469.00 €'


def test_event_test_qr_with_overrides(make_event):
    e = make_event(title='Composite Masterclass', price=469, currency='EUR')
    assert event_test_qr_png(e, 'domestic') is None
    png = event_test_qr_png(e, 'domestic', {'account': '1234567890/0100', 'amount': 11900.0})
    assert png and png[:4] == b'\x89PNG'
    assert event_test_qr_png(e, 'sepa', {'iban': IBAN}) is not None   # amount from fee
    assert event_test_qr_png(e, 'sepa', {'iban': 'XX'}) is None


def test_registration_qr_pngs_lists_offered_methods(make_event, make_registration):
    e = make_event(price=469, currency='EUR', payment_sepa_iban=IBAN,
                   payment_bank_account='1234567890/0100', payment_amount_czk=11900)
    reg = make_registration(e, variable_symbol='000101')
    assert set(registration_qr_pngs(reg)) == {'domestic', 'sepa'}
    e.payment_bank_account = None
    assert set(registration_qr_pngs(reg)) == {'sepa'}


# --- Admin manage panel -----------------------------------------------------

def _login(client, admin_user):
    login(client, 'admin@example.com', 'test-password-123')


def test_manage_save_both_methods(client, admin_user, make_event):
    _login(client, admin_user)
    e = make_event(price=469, currency='EUR')
    r = client.post(f'/admin/admin_events/manage/?id={e.id}', data={
        'action': 'save_payment',
        'payment_amount': '469',
        'payment_variable_symbol': '2027001',
        'payment_due_days': '10',
        'payment_beneficiary': 'Anterior Courses',
        'payment_bank_account': '19-2000145399/0800',
        'payment_amount_czk': '11 900'.replace(' ', ''),
        'payment_sepa_iban': 'cz65 0800 0000 1920 0014 5399',
        'payment_sepa_bic': 'gibaczpx',
        'payment_amount_eur': '',
    }, follow_redirects=True)
    assert r.status_code == 200
    db.session.refresh(e)
    assert e.payment_sepa_iban == IBAN
    assert e.payment_sepa_bic == 'GIBACZPX'
    assert float(e.payment_amount_czk) == 11900
    assert e.payment_amount_eur is None and e.sepa_amount == 469
    assert e.has_domestic_payment and e.has_sepa_payment
    assert b'Domestic and SEPA transfers set' in r.data


def test_manage_save_rejects_invalid_iban(client, admin_user, make_event):
    _login(client, admin_user)
    e = make_event(price=469, currency='EUR')
    r = client.post(f'/admin/admin_events/manage/?id={e.id}', data={
        'action': 'save_payment',
        'payment_sepa_iban': 'CZ6508000000192000145398',
    }, follow_redirects=True)
    assert b'IBAN is not valid' in r.data
    db.session.refresh(e)
    assert e.payment_sepa_iban is None


def test_manage_page_renders_two_methods(client, admin_user, make_event):
    _login(client, admin_user)
    e = make_event(price=469, currency='EUR', payment_sepa_iban=IBAN)
    r = client.get(f'/admin/admin_events/manage/?id={e.id}')
    assert r.status_code == 200
    assert b'Domestic transfer &middot; CZK' in r.data
    assert b'SEPA transfer &middot; EUR' in r.data
    assert r.data.count(b'Generate QR code') == 2


def test_manage_test_qr_endpoint_with_unsaved_values(client, admin_user, make_event):
    _login(client, admin_user)
    e = make_event(price=469, currency='EUR')
    base = f'/admin/admin_events/manage/test-qr.png?id={e.id}'
    assert client.get(base + '&kind=domestic').status_code == 404
    r = client.get(base + '&kind=domestic&account=1234567890/0100&amount=11900&vs=2027')
    assert r.status_code == 200 and r.mimetype == 'image/png'
    r = client.get(base + f'&kind=sepa&iban={IBAN}&beneficiary=Anterior&amount=469')
    assert r.status_code == 200
    assert client.get(base + '&kind=bogus').status_code == 404


def test_email_preview_renders_both_sections(client, admin_user, make_event, make_registration):
    _login(client, admin_user)
    e = make_event(price=469, currency='EUR', payment_sepa_iban=IBAN,
                   payment_bank_account='1234567890/0100', payment_amount_czk=11900)
    reg = make_registration(e, variable_symbol='000101')
    r = client.get(f'/admin/admin_events/email-preview/?reg_id={reg.id}&type=payment')
    assert r.status_code == 200
    assert b'Option 1' in r.data and b'Option 2' in r.data
    assert b'test-qr.png' in r.data     # preview swaps cid: images for the test QR URLs


# --- Payment email ------------------------------------------------------------

def test_payment_email_has_one_qr_per_method(app, smtp_settings, mock_smtp, make_event, make_registration):  # noqa: F811
    e = make_event(price=469, currency='EUR', payment_sepa_iban=IBAN,
                   payment_bank_account='1234567890/0100', payment_amount_czk=11900,
                   payment_variable_symbol='2027')
    reg = make_registration(e, variable_symbol='2027001')
    ok, _ = email_service.send_payment_details(reg)
    assert ok
    raw = mock_smtp.sendmail.call_args[0][2]
    assert 'Content-ID: <qr_domestic>' in raw
    assert 'Content-ID: <qr_sepa>' in raw
    log = EmailLog.query.filter_by(email_type='payment').first()
    assert log and log.status == 'sent'


def test_payment_email_single_method(app, smtp_settings, mock_smtp, make_event, make_registration):  # noqa: F811
    e = make_event(price=469, currency='EUR', payment_sepa_iban=IBAN)
    reg = make_registration(e)
    ok, _ = email_service.send_payment_details(reg)
    assert ok
    raw = mock_smtp.sendmail.call_args[0][2]
    assert 'Content-ID: <qr_sepa>' in raw
    assert 'qr_domestic' not in raw


def test_invalid_saved_iban_disables_sepa(client, admin_user, make_event):
    """A malformed IBAN (e.g. copied over by the migration) must not count as configured."""
    _login(client, admin_user)
    e = make_event(price=1, currency='EUR', payment_sepa_iban='CZ842010000000002803576870')  # 26 chars
    assert not e.sepa_iban_valid and not e.has_sepa_payment and not e.has_payment_details
    r = client.get(f'/admin/admin_events/manage/?id={e.id}')
    assert b'fails the check-digit test' in r.data
    e.payment_sepa_iban = 'CZ8420100000002803576870'
    assert e.sepa_iban_valid and e.has_sepa_payment


def test_manage_page_qr_url_joins_query_correctly(client, admin_user, make_event):
    """url_for already carries ?id=; the JS must append with & (was a 500: id='2?kind=sepa')."""
    _login(client, admin_user)
    e = make_event(price=469, currency='EUR')
    html = client.get(f'/admin/admin_events/manage/?id={e.id}').data.decode()
    assert f'/manage/test-qr.png?id={e.id}' in html
    assert "QR_URL.indexOf('?') === -1 ? '?' : '&'" in html
    # a malformed id must be a 404, never a 500
    assert client.get('/admin/admin_events/manage/test-qr.png?id=2%3Fkind%3Dsepa').status_code == 404
