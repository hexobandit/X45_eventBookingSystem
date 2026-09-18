"""
Public registration form layout: payment-method cards, billing accordion,
Privacy & updates block; course editor payment note.
"""

from tests.test_admin_auth import login


def test_form_sections_with_stripe(app, client, make_event):
    app.config['STRIPE_SECRET_KEY'] = 'sk_test_x'
    e = make_event(price=469, currency='EUR')
    r = client.get(f'/courses/{e.slug}')
    assert r.status_code == 200
    html = r.data.decode()
    assert 'Payment method' in html and "Choose how you'd like to pay." in html
    assert html.count('class="pay-option"') == 2
    assert 'Secure payment via Stripe.' in html
    assert "We'll email you payment details and a QR code." in html
    assert 'Company billing details' in html and 'Optional &middot; For your invoice' in html
    assert 'Privacy &amp; updates' in html
    assert 'consent-pill-required">Required' in html
    assert 'consent-pill">Optional' in html
    assert 'href="/privacy"' in html
    assert 'You can unsubscribe at any time.' in html


def test_form_without_stripe_hides_method(app, client, make_event):
    app.config['STRIPE_SECRET_KEY'] = ''
    e = make_event(price=469, currency='EUR')
    html = client.get(f'/courses/{e.slug}').data.decode()
    assert 'class="pay-option"' not in html
    assert 'Privacy &amp; updates' in html
    assert 'href="/privacy"' in html


def test_privacy_page(client):
    r = client.get('/privacy')
    assert r.status_code == 200
    html = r.data.decode()
    assert 'Privacy policy' in html and 'Stripe' in html and 'uoou.gov.cz' in html
    assert '/privacy' in client.get('/sitemap.xml').data.decode()
    assert 'href="/privacy"' in client.get('/contact').data.decode()   # footer + form link


def test_course_editor_payment_note(client, admin_user, event):
    login(client, 'admin@example.com', 'test-password-123')
    r = client.get(f'/admin/admin_events/visual-edit/?id={event.id}')
    assert r.status_code == 200
    assert b'Payment details are managed separately.' in r.data
    assert f'/admin/admin_events/manage/?id={event.id}'.encode() in r.data
    r = client.get('/admin/admin_events/visual-edit/')
    assert b'Save the course first' in r.data
