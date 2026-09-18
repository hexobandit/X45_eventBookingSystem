"""
Stripe card payments via hosted Checkout.

The card never touches this server: we create a Checkout Session and
redirect the attendee to Stripe. A webhook (checkout.session.completed)
marks the registration as paid. Card payments are offered only when
STRIPE_SECRET_KEY is configured, so the site works without Stripe too.
"""

from datetime import datetime

import stripe
from flask import current_app, url_for

# Currencies without decimal subunits are not in Event.CURRENCIES,
# so amounts are always converted to cents.


def stripe_enabled():
    """Card payments are available only when a secret key is configured."""
    return bool(current_app.config.get('STRIPE_SECRET_KEY'))


def _api_key():
    return current_app.config['STRIPE_SECRET_KEY']


def create_checkout_session(registration):
    """Create a Stripe Checkout Session for a registration.

    Returns the session (with .url to redirect to). Raises
    stripe.error.StripeError on API failure; callers turn that into
    a flash message.
    """
    event = registration.event
    amount = event.payment_amount_display
    if amount is None:
        raise ValueError(f'Event {event.id} has no payable amount')

    session = stripe.checkout.Session.create(
        api_key=_api_key(),
        mode='payment',
        line_items=[{
            'price_data': {
                'currency': (event.currency or 'EUR').lower(),
                'unit_amount': int(round(float(amount) * 100)),
                'product_data': {
                    'name': event.title,
                    'description': event.formatted_date,
                },
            },
            'quantity': 1,
        }],
        customer_email=registration.email,
        client_reference_id=str(registration.id),
        metadata={
            'registration_id': str(registration.id),
            'event_id': str(event.id),
            'variable_symbol': registration.variable_symbol or '',
        },
        success_url=url_for('main.payment_success', token=registration.confirmation_token, _external=True),
        cancel_url=url_for('main.payment_cancelled', token=registration.confirmation_token, _external=True),
    )

    registration.stripe_session_id = session.id
    return session


def verify_webhook(payload, signature_header):
    """Verify and parse a Stripe webhook. Raises on bad signature."""
    return stripe.Webhook.construct_event(
        payload,
        signature_header,
        current_app.config['STRIPE_WEBHOOK_SECRET'],
    )


def handle_checkout_completed(session, registration):
    """Apply a completed Checkout Session to its registration.

    Idempotent — Stripe retries webhooks, and the success page may race
    the webhook. Returns True if the registration was newly marked paid.
    """
    from app.models.registration import PaymentStatus

    if registration.payment_status == PaymentStatus.PAID:
        return False

    registration.payment_status = PaymentStatus.PAID
    registration.paid_at = datetime.utcnow()
    registration.stripe_payment_intent_id = session.get('payment_intent')
    registration.payment_note = 'Paid by card (Stripe)'

    # Card payment is a stronger confirmation than an email click
    if not registration.is_confirmed and not registration.is_cancelled:
        registration.confirm()

    return True
