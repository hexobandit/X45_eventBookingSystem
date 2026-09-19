"""Attendee sheet (printable welcome-desk list) for a course."""

from app.models import Registration
from app.models.registration import RegistrationStatus, PaymentStatus
from app.extensions import db


def _login(client):
    return client.post('/admin/login', data={'email': 'admin@example.com', 'password': 'test-password-123'})


def _reg(event, first, last, status, paid=False, **kw):
    r = Registration(event_id=event.id, first_name=first, last_name=last,
                     email=f'{first}.{last}@example.com'.lower(), status=status,
                     payment_status=PaymentStatus.PAID if paid else PaymentStatus.UNPAID,
                     gdpr_consent=True, **kw)
    db.session.add(r)
    db.session.commit()
    return r


def test_attendee_sheet_requires_login(client, make_event):
    event = make_event()
    r = client.get(f'/admin/admin_events/attendee-sheet/?id={event.id}')
    assert r.status_code in (302, 401, 403)


def test_attendee_sheet_lists_expected_and_waitlist_not_cancelled(client, admin_user, make_event):
    event = make_event(title='Sheet Course')
    _reg(event, 'Zed', 'Alpha', RegistrationStatus.CONFIRMED, paid=True, organization='Clinic A', phone='+420 111')
    _reg(event, 'Amy', 'Beta', RegistrationStatus.PENDING)
    _reg(event, 'Wai', 'Gamma', RegistrationStatus.WAITLIST)
    _reg(event, 'Gone', 'Delta', RegistrationStatus.CANCELLED)
    _login(client)

    r = client.get(f'/admin/admin_events/attendee-sheet/?id={event.id}')
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'Sheet Course' in html
    assert 'Alpha Zed' in html and 'Clinic A' in html and '+420 111' in html
    assert 'Beta Amy' in html and 'Not confirmed' in html
    assert 'Gamma Wai' in html and 'Waiting list' in html
    assert 'Delta Gone' not in html
    # sorted by surname: Alpha before Beta
    assert html.index('Alpha Zed') < html.index('Beta Amy')
    # meta strip counts: 2 expected, 1 paid
    assert '>2 <small>of' in html
    assert '>1 <small>of 2</small>' in html


def test_detail_page_links_to_attendee_sheet(client, admin_user, make_event):
    event = make_event()
    _login(client)
    r = client.get(f'/admin/admin_events/details/?id={event.id}')
    assert f'/admin/admin_events/attendee-sheet/?id={event.id}' in r.get_data(as_text=True)
