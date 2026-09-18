"""
Admin deletion of registrations: archive row with reason, optional
cancellation email, email-log FK handling, capacity decrement, email reuse,
bulk delete and the Deleted registrations views.
"""

import email as email_lib

from app.extensions import db
from app.models import Registration, EmailLog, DeletedRegistration
from app.models.registration import RegistrationStatus, PaymentStatus
from tests.test_admin_auth import login
from tests.test_email_service import smtp_settings, mock_smtp  # noqa: F401 (fixtures)


def _login(client, admin_user):
    login(client, 'admin@example.com', 'test-password-123')


def _delete(client, reg_id, **extra):
    data = {'id': reg_id, 'url': '/admin/admin_registrations/'}
    data.update(extra)
    return client.post('/admin/admin_registrations/delete/', data=data, follow_redirects=True)


def test_delete_archives_with_reason_and_sends_email(client, admin_user, event, make_registration,
                                                      smtp_settings, mock_smtp):  # noqa: F811
    _login(client, admin_user)
    reg = make_registration(event, email='jane@example.com', status=RegistrationStatus.CONFIRMED,
                            variable_symbol='000101', payment_status=PaymentStatus.PAID)
    event.registered_count = 1
    db.session.add(EmailLog(to_email=reg.email, subject='x', email_type='confirmation',
                            status='sent', registration_id=reg.id, event_id=event.id))
    db.session.commit()
    reg_id = reg.id

    r = _delete(client, reg_id, delete_reason='Asked to cancel by phone',
                send_cancel_email='1', include_reason='1')
    assert r.status_code == 200

    assert db.session.get(Registration, reg_id) is None
    arch = DeletedRegistration.query.one()
    assert arch.registration_id == reg_id
    assert arch.email == 'jane@example.com'
    assert arch.reason == 'Asked to cancel by phone'
    assert arch.deleted_by == 'admin@example.com'
    assert arch.cancellation_email_sent is True
    assert arch.status == 'confirmed' and arch.payment_status == 'paid'
    assert arch.event_title == event.title
    assert arch.snapshot_dict['variable_symbol'] == '000101'

    # Cancellation email went out with the reason, and was logged
    raw = mock_smtp.sendmail.call_args[0][2]
    msg = email_lib.message_from_string(raw)
    assert 'Registration cancelled' in msg['Subject']
    body = ''.join(part.get_payload(decode=True).decode('utf-8')
                   for part in msg.walk() if part.get_content_type() == 'text/html')
    assert 'Asked to cancel by phone' in body
    assert 'refund' in body.lower()    # paid registration mentions the refund
    cancel_log = EmailLog.query.filter_by(email_type='cancellation').one()
    assert cancel_log.status == 'sent'

    # Old email logs survive with the FK cleared
    assert EmailLog.query.filter_by(registration_id=reg_id).count() == 0
    assert EmailLog.query.filter_by(email_type='confirmation').count() == 1

    db.session.refresh(event)
    assert event.registered_count == 0


def test_delete_without_email(client, admin_user, event, make_registration, smtp_settings, mock_smtp):  # noqa: F811
    _login(client, admin_user)
    reg = make_registration(event, email='nomail@example.com')
    _delete(client, reg.id, delete_reason='Duplicate', send_cancel_email='')
    arch = DeletedRegistration.query.one()
    assert arch.cancellation_email_sent is False and arch.reason == 'Duplicate'
    assert not mock_smtp.sendmail.called


def test_email_can_be_reused_after_delete(client, admin_user, event, make_registration):
    _login(client, admin_user)
    reg = make_registration(event, email='again@example.com')
    _delete(client, reg.id)
    # Same email, same course — the unique (event_id, email) key is free again
    make_registration(event, email='again@example.com')
    assert Registration.query.filter_by(email='again@example.com').count() == 1
    assert DeletedRegistration.query.filter_by(email='again@example.com').count() == 1


def test_bulk_delete_action_uses_same_fields(client, admin_user, event, make_registration):
    _login(client, admin_user)
    a = make_registration(event, email='a@example.com')
    b = make_registration(event, email='b@example.com')
    r = client.post('/admin/admin_registrations/action/', data={
        'action': 'delete', 'rowid': [str(a.id), str(b.id)],
        'url': '/admin/admin_registrations/',
        'delete_reason': 'Course cancelled', 'send_cancel_email': '',
    }, follow_redirects=True)
    assert r.status_code == 200
    assert Registration.query.count() == 0
    assert {d.reason for d in DeletedRegistration.query.all()} == {'Course cancelled'}


def test_deleted_registrations_views_render(client, admin_user, event, make_registration):
    _login(client, admin_user)
    reg = make_registration(event, email='gone@example.com')
    _delete(client, reg.id, delete_reason='No-show')
    arch = DeletedRegistration.query.one()

    r = client.get('/admin/admin_deleted_registrations/')
    assert r.status_code == 200
    assert b'gone@example.com' in r.data and b'No-show' in r.data

    r = client.get(f'/admin/admin_deleted_registrations/details/?id={arch.id}')
    assert r.status_code == 200
    assert b'Full record (JSON)' in r.data

    # Purge from the archive
    r = client.post('/admin/admin_deleted_registrations/delete/',
                    data={'id': arch.id, 'url': '/admin/admin_deleted_registrations/'},
                    follow_redirects=True)
    assert r.status_code == 200
    assert DeletedRegistration.query.count() == 0


def test_delete_ui_hooks_present(client, admin_user, event, make_registration):
    _login(client, admin_user)
    reg = make_registration(event)
    r = client.get('/admin/admin_registrations/')
    assert b'deleteRegModal' in r.data and b'deleteRegistrationRowHook' in r.data
    r = client.get(f'/admin/admin_registrations/edit/?id={reg.id}')
    assert b'openDeleteRegModal' in r.data
    assert b'Deleted registrations' in r.data   # sidebar link
