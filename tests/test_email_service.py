"""
Email service: SMTP mocked, EmailLog rows, recipient routing, MIME structure.
"""

from unittest.mock import patch, MagicMock

import pytest

from app.extensions import db
from app.models import EmailLog
from app.models.email_settings import EmailSettings
from app.services.email import email_service, parse_email_list


@pytest.fixture()
def smtp_settings(app):
    settings = EmailSettings.get_or_create()
    settings.smtp_host = 'smtp.example.com'
    settings.smtp_port = 587
    settings.smtp_username = 'info@example.com'
    settings.set_password('secret-password')
    settings.smtp_use_tls = True
    settings.sender_email = 'info@example.com'
    settings.sender_name = 'Studio Lumen'
    settings.admin_email = 'admin@example.com'
    settings.client_notification_emails = 'client-a@example.com, client-b@example.com'
    settings.doctor_notification_emails = 'doctor@example.com'
    db.session.commit()
    return settings


@pytest.fixture()
def mock_smtp():
    with patch('app.services.email.smtplib.SMTP') as smtp_cls:
        server = MagicMock()
        server.sendmail.return_value = {}
        smtp_cls.return_value = server
        # `with server:` support
        server.__enter__ = MagicMock(return_value=server)
        server.__exit__ = MagicMock(return_value=False)
        yield server


class TestParseEmailList:
    def test_separators(self):
        raw = 'a@x.com, b@x.com; c@x.com\nd@x.com e@x.com'
        assert parse_email_list(raw) == ['a@x.com', 'b@x.com', 'c@x.com', 'd@x.com', 'e@x.com']

    def test_junk_filtered(self):
        assert parse_email_list('not-an-email, ok@x.com,, ') == ['ok@x.com']


class TestSendEmail:
    def test_unconfigured_smtp_fails_gracefully(self, app):
        ok, msg = email_service.send_email('to@example.com', 'Subject', '<p>Hi</p>')
        assert ok is False
        log = EmailLog.query.one()
        assert log.status == 'failed'
        assert 'not configured' in log.error_message

    def test_successful_send_logs_and_uses_starttls(self, app, smtp_settings, mock_smtp):
        ok, msg = email_service.send_email(
            'to@example.com', 'Hello', '<p>Hi</p>', text_content='Hi',
            email_type='custom')
        assert ok is True
        mock_smtp.starttls.assert_called_once()
        mock_smtp.login.assert_called_once_with('info@example.com', 'secret-password')

        log = EmailLog.query.one()
        assert log.status == 'sent'
        assert log.email_type == 'custom'
        assert log.to_email == 'to@example.com'

        # multipart/alternative with plain + html
        raw = mock_smtp.sendmail.call_args[0][2]
        assert 'multipart/alternative' in raw
        assert 'text/html' in raw

    def test_refused_recipient_logged_as_failure(self, app, smtp_settings, mock_smtp):
        mock_smtp.sendmail.return_value = {'to@example.com': (550, b'No such user')}
        ok, msg = email_service.send_email('to@example.com', 'Hello', '<p>Hi</p>')
        assert ok is False
        assert EmailLog.query.one().status == 'failed'


class TestRegistrationEmails:
    def test_confirmation_email_contains_link(self, app, smtp_settings, mock_smtp,
                                              make_event, make_registration):
        from email.parser import Parser

        reg = make_registration(make_event())
        url = f'https://example.com/registration/confirm/{reg.confirmation_token}'
        ok, _ = email_service.send_registration_confirmation(reg, url)
        assert ok is True

        # Bodies are base64-encoded — decode each MIME part before searching
        raw = mock_smtp.sendmail.call_args[0][2]
        msg = Parser().parsestr(raw)
        bodies = ''.join(
            part.get_payload(decode=True).decode('utf-8')
            for part in msg.walk() if part.get_content_maintype() == 'text'
        )
        assert reg.confirmation_token in bodies

    def test_admin_notification_goes_to_admin_list_regardless_of_category(
            self, app, smtp_settings, mock_smtp, make_event, make_registration):
        # Event category no longer routes anywhere: every booking notifies the
        # single admin_email list, which send_email splits into recipients.
        smtp_settings.admin_email = 'one@example.com, two@example.com'
        db.session.commit()
        reg = make_registration(make_event(event_category='doctor'))
        email_service.send_admin_notification(reg)

        # sendmail's recipient arg is a list of individual addresses
        recipients = [a for call in mock_smtp.sendmail.call_args_list for a in call.args[1]]
        assert 'one@example.com' in recipients
        assert 'two@example.com' in recipients
        # The old category-specific lists are no longer consulted
        assert 'client-a@example.com' not in recipients
        assert 'doctor@example.com' not in recipients


class TestPasswordEncryption:
    def test_password_round_trip(self, app, smtp_settings):
        assert smtp_settings.get_password() == 'secret-password'
        assert smtp_settings.smtp_password_encrypted != 'secret-password'
