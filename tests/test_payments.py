"""
Payment system tests: QR generation, Stripe checkout flow, webhook.
"""

from datetime import datetime
from unittest.mock import patch, MagicMock

from app.extensions import db as _db
from app.models.registration import PaymentMethod, PaymentStatus, RegistrationStatus
from app.services.payment_qr import (
    czech_account_to_iban, spayd_string, epc_string, registration_qr_png
)
from app.services.stripe_payment import handle_checkout_completed
from tests.conftest import human_form_data


# --- IBAN conversion -------------------------------------------------------

def test_czech_account_to_iban_with_prefix():
    # Reference example from the CNB IBAN documentation
    assert czech_account_to_iban('19-2000145399/0800') == 'CZ6508000000192000145399'


def test_czech_account_to_iban_without_prefix():
    iban = czech_account_to_iban('1234567890/0100')
    assert iban is not None
    assert iban.startswith('CZ')
    assert iban[4:8] == '0100'
    assert iban.endswith('1234567890')


def test_iban_passthrough_and_invalid():
    assert czech_account_to_iban('CZ65 0800 0000 1920 0014 5399') == 'CZ6508000000192000145399'
    assert czech_account_to_iban('not-an-account') is None
    assert czech_account_to_iban(None) is None


# --- Payment strings -------------------------------------------------------

def test_spayd_string():
    s = spayd_string('CZ6508000000192000145399', 12490.0, 'CZK',
                     variable_symbol='2027001', message='Course')
    assert s.startswith('SPD*1.0*ACC:CZ6508000000192000145399*AM:12490.00*CC:CZK')
    assert 'X-VS:2027001' in s
    assert 'MSG:Course' in s


def test_epc_string():
    s = epc_string('ANTERIOR', 'CZ6508000000192000145399', 469.0, reference='VS 2027001')
    lines = s.split('\n')
    assert lines[0] == 'BCD'
    assert lines[3] == 'SCT'
    assert lines[5] == 'ANTERIOR'
    assert lines[6] == 'CZ6508000000192000145399'
    assert lines[7] == 'EUR469.00'
    assert 'VS 2027001' in s


# --- Registration QR -------------------------------------------------------

def test_registration_qr_per_method(app, make_event, make_registration):
    event = make_event(price=12490, currency='CZK',
                       payment_bank_account='19-2000145399/0800')
    reg = make_registration(event, variable_symbol='2027001')

    # Domestic: account + CZK amount (falls back to the fee when priced in CZK)
    assert event.has_domestic_payment
    png = registration_qr_png(reg, 'domestic')
    assert png is not None and png[:8] == b'\x89PNG\r\n\x1a\n'

    # SEPA needs an IBAN and a EUR amount — not configured yet
    assert not event.has_sepa_payment
    assert registration_qr_png(reg, 'sepa') is None

    event.payment_sepa_iban = 'CZ6508000000192000145399'
    event.payment_amount_eur = 469
    assert event.has_sepa_payment
    assert registration_qr_png(reg, 'sepa') is not None

    # Priced in EUR with no explicit CZK amount -> domestic is off
    event.currency = 'EUR'
    event.payment_amount_czk = None
    assert not event.has_domestic_payment
    assert registration_qr_png(reg, 'domestic') is None
    assert registration_qr_png(reg, 'unknown') is None


def test_qr_route(app, client, make_event, make_registration):
    event = make_event(price=469, currency='EUR',
                       payment_sepa_iban='CZ6508000000192000145399')
    reg = make_registration(event)
    resp = client.get(f'/registration/{reg.confirmation_token}/qr.png?kind=sepa')
    assert resp.status_code == 200
    assert resp.mimetype == 'image/png'
    # domestic not configured for this event
    assert client.get(f'/registration/{reg.confirmation_token}/qr.png').status_code == 404


# --- Registration with payment method / billing ----------------------------

def test_registration_saves_billing_and_method(app, client, make_event):
    event = make_event(price=469, currency='EUR')
    data = human_form_data(
        app,
        first_name='Jane', last_name='Smith', email='jane@example.com',
        gdpr='y', payment_method='bank_transfer',
        billing_name='Dental s.r.o.', billing_ico='12345678',
    )
    resp = client.post(f'/courses/{event.slug}/register', data=data)
    assert resp.status_code == 302

    from app.models import Registration
    reg = Registration.query.filter_by(email='jane@example.com').first()
    assert reg is not None
    assert reg.payment_method == PaymentMethod.BANK_TRANSFER
    assert reg.billing_name == 'Dental s.r.o.'
    assert reg.billing_ico == '12345678'


def test_card_choice_redirects_to_stripe(app, client, make_event):
    app.config['STRIPE_SECRET_KEY'] = 'sk_test_x'
    event = make_event(price=469, currency='EUR')
    data = human_form_data(
        app,
        first_name='Jane', last_name='Card', email='card@example.com',
        gdpr='y', payment_method='card',
    )
    fake_session = MagicMock(id='cs_test_123', url='https://checkout.stripe.com/pay/cs_test_123')
    with patch('app.services.stripe_payment.stripe.checkout.Session.create',
               return_value=fake_session):
        resp = client.post(f'/courses/{event.slug}/register', data=data)
    assert resp.status_code == 303
    assert resp.headers['Location'].startswith('https://checkout.stripe.com/')

    from app.models import Registration
    reg = Registration.query.filter_by(email='card@example.com').first()
    assert reg.payment_method == PaymentMethod.CARD
    assert reg.stripe_session_id == 'cs_test_123'


def test_card_choice_without_stripe_falls_back(app, client, make_event):
    app.config['STRIPE_SECRET_KEY'] = ''
    event = make_event(price=469, currency='EUR')
    data = human_form_data(
        app,
        first_name='Jane', last_name='NoStripe', email='nostripe@example.com',
        gdpr='y', payment_method='card',
    )
    resp = client.post(f'/courses/{event.slug}/register', data=data)
    assert resp.status_code == 302
    assert '/registration/success/' in resp.headers['Location']

    from app.models import Registration
    reg = Registration.query.filter_by(email='nostripe@example.com').first()
    assert reg.payment_method == PaymentMethod.BANK_TRANSFER


# --- Webhook completion ----------------------------------------------------

def test_handle_checkout_completed_marks_paid_and_confirms(app, make_event, make_registration):
    event = make_event(price=469, currency='EUR')
    reg = make_registration(event, payment_method=PaymentMethod.CARD)
    session = {'payment_intent': 'pi_123', 'id': 'cs_1'}

    assert handle_checkout_completed(session, reg) is True
    assert reg.payment_status == PaymentStatus.PAID
    assert reg.stripe_payment_intent_id == 'pi_123'
    assert reg.status == RegistrationStatus.CONFIRMED

    # Idempotent on webhook retry
    assert handle_checkout_completed(session, reg) is False


def test_webhook_route_bad_signature(app, client):
    app.config['STRIPE_SECRET_KEY'] = 'sk_test_x'
    app.config['STRIPE_WEBHOOK_SECRET'] = 'whsec_x'
    resp = client.post('/webhooks/stripe', data=b'{}',
                       headers={'Stripe-Signature': 'bad'})
    assert resp.status_code == 400


def test_webhook_route_completes_payment(app, client, make_event, make_registration):
    app.config['STRIPE_SECRET_KEY'] = 'sk_test_x'
    app.config['STRIPE_WEBHOOK_SECRET'] = 'whsec_x'
    event = make_event(price=469, currency='EUR')
    reg = make_registration(event, payment_method=PaymentMethod.CARD)

    stripe_event = {
        'type': 'checkout.session.completed',
        'data': {'object': {
            'id': 'cs_1',
            'payment_intent': 'pi_9',
            'metadata': {'registration_id': str(reg.id)},
        }},
    }
    with patch('app.services.stripe_payment.verify_webhook', return_value=stripe_event):
        resp = client.post('/webhooks/stripe', data=b'{}',
                           headers={'Stripe-Signature': 'sig'})
    assert resp.status_code == 200
    _db.session.refresh(reg)
    assert reg.payment_status == PaymentStatus.PAID
    assert reg.paid_at is not None
