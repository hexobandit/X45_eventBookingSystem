"""
Email service using SMTP with configuration from database.
"""

import io
import os
import re
import smtplib
import sys
from datetime import timedelta
from email.mime.image import MIMEImage
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from flask import current_app, render_template, url_for

from app import branding


def parse_email_list(raw):
    """Parse a string of emails separated by comma, semicolon, space, or newline."""
    return [e.strip() for e in re.split(r'[,;\s\n]+', raw) if e.strip() and '@' in e]


class EmailService:
    """SMTP email service with DB-stored configuration."""

    def _log(self, to_email, subject, status, email_type='general',
             error_message=None, smtp_response=None, smtp_debug=None,
             registration_id=None, event_id=None):
        """Create an EmailLog entry."""
        try:
            from app.extensions import db
            from app.models.email_log import EmailLog

            log = EmailLog(
                to_email=to_email,
                subject=subject,
                email_type=email_type,
                status=status,
                error_message=error_message,
                smtp_response=smtp_response,
                smtp_debug=smtp_debug,
                registration_id=registration_id,
                event_id=event_id
            )
            db.session.add(log)
            db.session.commit()
        except Exception as e:
            current_app.logger.error(f'Failed to write email log: {e}')

    def send_email(self, to_email, subject, html_content, text_content=None,
                   email_type='general', registration_id=None, event_id=None,
                   inline_images=None):
        """
        Send an email via SMTP using settings from the database.

        Args:
            inline_images: list of dicts with keys 'cid', 'path', 'subtype'
                           e.g. [{'cid': 'qr_payment', 'path': '/abs/path.png', 'subtype': 'png'}]

        Returns:
            tuple: (success: bool, message: str)
        """
        from app.models.email_settings import EmailSettings

        settings = EmailSettings.get_settings()
        if not settings or not settings.smtp_host:
            current_app.logger.warning('SMTP not configured, email not sent')
            self._log(to_email, subject, 'failed',
                      email_type=email_type,
                      error_message='SMTP not configured',
                      registration_id=registration_id,
                      event_id=event_id)
            return False, 'Email service not configured'

        password = settings.get_password()
        if not password:
            current_app.logger.warning('SMTP password not set, email not sent')
            self._log(to_email, subject, 'failed',
                      email_type=email_type,
                      error_message='SMTP password not configured',
                      registration_id=registration_id,
                      event_id=event_id)
            return False, 'SMTP password not configured'

        # Accept a single address, a comma/semicolon/space-separated string, or a
        # list. The SMTP envelope needs a list of individual recipients; passing a
        # multi-address string as one recipient triggers a 501 malformed address.
        if isinstance(to_email, (list, tuple)):
            recipients = [e.strip() for e in to_email if e and e.strip()]
        else:
            recipients = parse_email_list(to_email or '')
        if not recipients:
            current_app.logger.warning(f'No valid recipient in "{to_email}", email not sent')
            self._log(to_email, subject, 'failed',
                      email_type=email_type,
                      error_message='No valid recipient address',
                      registration_id=registration_id,
                      event_id=event_id)
            return False, 'No valid recipient address'

        try:
            # Build MIME structure:
            # With inline images: mixed > related > alternative + images
            # Without: alternative (plain + html)
            alt_part = MIMEMultipart('alternative')
            if text_content:
                alt_part.attach(MIMEText(text_content, 'plain', 'utf-8'))
            alt_part.attach(MIMEText(html_content, 'html', 'utf-8'))

            if inline_images:
                related_part = MIMEMultipart('related')
                related_part.attach(alt_part)
                for img in inline_images:
                    # 'data' (raw bytes, e.g. generated QR) or 'path' (file on disk)
                    if img.get('data') is not None:
                        img_bytes = img['data']
                        filename = f'{img["cid"]}.{img.get("subtype", "png")}'
                    else:
                        with open(img['path'], 'rb') as f:
                            img_bytes = f.read()
                        filename = os.path.basename(img['path'])
                    mime_img = MIMEImage(img_bytes, _subtype=img.get('subtype', 'png'))
                    mime_img.add_header('Content-ID', f'<{img["cid"]}>')
                    mime_img.add_header('Content-Disposition', 'inline', filename=filename)
                    related_part.attach(mime_img)
                msg = related_part
            else:
                msg = alt_part

            msg['Subject'] = subject
            msg['From'] = f'{settings.sender_name} <{settings.sender_email}>' if settings.sender_name else settings.sender_email
            msg['To'] = ', '.join(recipients)

            # Capture SMTP debug output
            debug_buf = io.StringIO()
            old_stderr = sys.stderr

            smtp_resp_str = None
            try:
                sys.stderr = debug_buf
                # Port 465 = implicit SSL (SMTP_SSL), port 587 = STARTTLS
                if settings.smtp_port == 465:
                    server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=30)
                else:
                    server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30)
                with server:
                    server.set_debuglevel(1)
                    if settings.smtp_port != 465 and settings.smtp_use_tls:
                        server.starttls()
                    server.login(settings.smtp_username, password)
                    refused = server.sendmail(settings.sender_email, recipients, msg.as_string())
            finally:
                sys.stderr = old_stderr

            debug_output = debug_buf.getvalue()

            if refused:
                smtp_resp_str = str(refused)
                current_app.logger.warning(f'SMTP refused recipients: {refused}')
                self._log(to_email, subject, 'failed',
                          email_type=email_type,
                          error_message=f'Refused recipients: {refused}',
                          smtp_response=smtp_resp_str,
                          smtp_debug=debug_output,
                          registration_id=registration_id,
                          event_id=event_id)
                return False, f'Recipient refused: {smtp_resp_str}'

            current_app.logger.info(f'Email sent to {to_email}: {subject}')
            self._log(to_email, subject, 'sent',
                      email_type=email_type,
                      smtp_debug=debug_output,
                      registration_id=registration_id,
                      event_id=event_id)
            return True, 'Email sent successfully'

        except Exception as e:
            debug_output = debug_buf.getvalue() if 'debug_buf' in locals() else None
            current_app.logger.error(f'Email error: {str(e)}')
            self._log(to_email, subject, 'failed',
                      email_type=email_type,
                      error_message=str(e),
                      smtp_debug=debug_output,
                      registration_id=registration_id,
                      event_id=event_id)
            return False, str(e)

    def send_registration_confirmation(self, registration, confirmation_url=None):
        """Send registration confirmation email.

        Args:
            confirmation_url: Pre-built absolute URL for the confirmation link.
                              Must be passed from the request context since url_for
                              with _external=True doesn't work in background threads.
        """
        event = registration.event

        if not confirmation_url:
            # Fallback: build from CANONICAL_DOMAIN (works without request context)
            domain = current_app.config.get('CANONICAL_DOMAIN', '')
            confirmation_url = f"{domain}/registration/confirm/{registration.confirmation_token}"

        subject = f"Please confirm your registration: {event.title}"

        html_content = render_template(
            'emails/registration_confirmation.html',
            registration=registration,
            event=event,
            confirmation_url=confirmation_url
        )

        text_content = f"""
Dear {registration.first_name},

thank you for registering for "{event.title}".

Date: {event.formatted_date}
Location: {event.location}

To confirm your registration, please click the following link or copy it into your browser:
{confirmation_url}

If you have any questions, don't hesitate to contact us.

Kind regards,
{branding.EMAIL_SIGNATURE}
        """.strip()

        return self.send_email(
            registration.email, subject, html_content, text_content,
            email_type='confirmation',
            registration_id=registration.id,
            event_id=event.id
        )

    def send_registration_confirmed(self, registration):
        """Send confirmation success email after user confirms."""
        event = registration.event

        subject = f"Registration confirmed: {event.title}"

        html_content = render_template(
            'emails/registration_confirmed.html',
            registration=registration,
            event=event
        )

        text_content = f"""
Dear {registration.first_name},

your registration for "{event.title}" has been confirmed.

Date: {event.formatted_date}
Location: {event.location}
{f"Venue: {event.venue_name}" if event.venue_name else ""}

We look forward to seeing you!

Kind regards,
{branding.EMAIL_SIGNATURE}
        """.strip()

        return self.send_email(
            registration.email, subject, html_content, text_content,
            email_type='confirmed',
            registration_id=registration.id,
            event_id=event.id
        )

    def send_admin_notification(self, registration):
        """Send notification to the configured admin recipients about a new booking."""
        from app.models.email_settings import EmailSettings

        settings = EmailSettings.get_settings()
        if not settings:
            current_app.logger.warning('Email settings not configured, notification not sent')
            self._log('(settings unconfigured)',
                      f'New registration: {registration.full_name}',
                      'failed', email_type='admin_notification',
                      error_message='Email settings not configured',
                      registration_id=registration.id)
            return False, 'Email settings not configured'

        event = registration.event

        recipients = parse_email_list(settings.admin_email or '')
        if not recipients:
            current_app.logger.warning('No notification emails configured')
            self._log(settings.admin_email or '(no recipients configured)',
                      f'New registration: {registration.full_name} - {event.title}',
                      'failed', email_type='admin_notification',
                      error_message='No notification emails configured',
                      registration_id=registration.id, event_id=event.id)
            return False, 'No notification emails configured'

        from app.models.registration import RegistrationStatus
        if registration.status == RegistrationStatus.WAITLIST:
            subject = f"New waitlist signup: {registration.full_name} - {event.title}"
        else:
            subject = f"New registration: {registration.full_name} - {event.title}"
        current_app.logger.info(f'Admin notification: recipients={recipients}')

        html_content = render_template(
            'emails/admin_notification.html',
            registration=registration,
            event=event
        )

        # Send to each recipient
        last_result = (False, 'No recipients')
        for email_addr in recipients:
            last_result = self.send_email(
                email_addr, subject, html_content,
                email_type='admin_notification',
                registration_id=registration.id,
                event_id=event.id
            )
        return last_result

    def send_admin_confirmation_notice(self, registration):
        """Notify admin that a registration was confirmed by the attendee."""
        from app.models.email_settings import EmailSettings

        settings = EmailSettings.get_settings()
        if not settings:
            self._log('(settings unconfigured)',
                      f'Registration confirmed: {registration.full_name}',
                      'failed', email_type='admin_notification',
                      error_message='Email settings not configured',
                      registration_id=registration.id)
            return False, 'Email settings not configured'

        event = registration.event

        recipients = parse_email_list(settings.admin_email or '')
        if not recipients:
            self._log(settings.admin_email or '(no recipients configured)',
                      f'Registration confirmed: {registration.full_name} - {event.title}',
                      'failed', email_type='admin_notification',
                      error_message='No notification emails configured',
                      registration_id=registration.id, event_id=event.id)
            return False, 'No notification emails configured'

        subject = f"Registration confirmed: {registration.full_name} - {event.title}"

        html_content = render_template(
            'emails/admin_confirmation_notice.html',
            registration=registration,
            event=event
        )

        last_result = (False, 'No recipients')
        for email_addr in recipients:
            last_result = self.send_email(
                email_addr, subject, html_content,
                email_type='admin_notification',
                registration_id=registration.id,
                event_id=event.id
            )
        return last_result

    def send_event_reminder(self, registration, days_before=1):
        """Send event reminder email."""
        event = registration.event

        subject = f"Reminder: {event.title} - {'tomorrow' if days_before == 1 else f'in {days_before} days'}"

        html_content = render_template(
            'emails/event_reminder.html',
            registration=registration,
            event=event,
            days_before=days_before
        )

        return self.send_email(
            registration.email, subject, html_content,
            email_type='reminder',
            registration_id=registration.id,
            event_id=event.id
        )

    def send_payment_details(self, registration):
        """Send payment details email (domestic CZK and/or SEPA EUR, each with a QR)."""
        from app.services.payment_qr import registration_qr_pngs

        event = registration.event

        due_days = event.payment_due_days or 14
        due_date = registration.created_at + timedelta(days=due_days)

        subject = f"Payment details: {event.title}"

        # One inline QR per offered method. A manually uploaded QR image
        # replaces the generated domestic one.
        inline_images = []
        qr_kinds = set()
        generated = registration_qr_pngs(registration)
        custom_domestic = None
        if event.payment_qr_image and event.has_domestic_payment:
            qr_path = os.path.join(current_app.static_folder, event.payment_qr_image)
            if os.path.isfile(qr_path):
                ext = qr_path.rsplit('.', 1)[-1].lower()
                custom_domestic = {'cid': 'qr_domestic', 'path': qr_path, 'subtype': ext}
        if custom_domestic:
            inline_images.append(custom_domestic)
            qr_kinds.add('domestic')
        elif 'domestic' in generated:
            inline_images.append({'cid': 'qr_domestic', 'data': generated['domestic'], 'subtype': 'png'})
            qr_kinds.add('domestic')
        if 'sepa' in generated:
            inline_images.append({'cid': 'qr_sepa', 'data': generated['sepa'], 'subtype': 'png'})
            qr_kinds.add('sepa')

        html_content = render_template(
            'emails/payment_details.html',
            registration=registration,
            event=event,
            due_date=due_date,
            qr_kinds=qr_kinds,
            has_qr=bool(qr_kinds)
        )

        return self.send_email(
            registration.email, subject, html_content,
            email_type='payment',
            registration_id=registration.id,
            event_id=event.id,
            inline_images=inline_images or None
        )

    def send_registration_cancelled(self, registration, reason=None):
        """Tell the participant their registration was cancelled by the organiser.

        `reason` is included verbatim in the email when given.
        """
        event = registration.event
        subject = f"Registration cancelled: {event.title}"

        html_content = render_template(
            'emails/registration_cancelled.html',
            registration=registration,
            event=event,
            reason=(reason or '').strip() or None
        )

        return self.send_email(
            registration.email, subject, html_content,
            email_type='cancellation',
            registration_id=registration.id,
            event_id=event.id
        )

    def send_payment_received(self, registration):
        """Confirm a received (card) payment to the attendee."""
        event = registration.event

        subject = f"Payment received: {event.title}"

        html_content = render_template(
            'emails/payment_received.html',
            registration=registration,
            event=event
        )

        return self.send_email(
            registration.email, subject, html_content,
            email_type='payment',
            registration_id=registration.id,
            event_id=event.id
        )

    def send_custom_message(self, registration, subject, message_html):
        """Send a custom message from admin to a registrant."""
        event = registration.event

        html_content = render_template(
            'emails/custom_message.html',
            registration=registration,
            event=event,
            message_html=message_html
        )

        return self.send_email(
            registration.email, subject, html_content,
            email_type='custom',
            registration_id=registration.id,
            event_id=event.id
        )

    def send_inquiry_notification(self, inquiry):
        """Notify admin(s) about a new inquiry or notify-list signup."""
        from app.models.email_settings import EmailSettings

        settings = EmailSettings.get_settings()
        if not settings:
            current_app.logger.warning('Email settings not configured, inquiry notification not sent')
            self._log('(settings unconfigured)',
                      f'{inquiry.type.value} notification: {inquiry.name or inquiry.email}',
                      'failed', email_type='admin_notification',
                      error_message='Email settings not configured')
            return False, 'Email settings not configured'

        recipients = parse_email_list(settings.admin_email or '')
        if not recipients:
            self._log(settings.admin_email or '(no recipients configured)',
                      f'{inquiry.type.value} notification: {inquiry.name or inquiry.email}',
                      'failed', email_type='admin_notification',
                      error_message='No notification emails configured')
            return False, 'No notification emails configured'

        type_labels = {
            'book_order': 'New order interest',
            'book_notify': 'New notify-list signup',
            'contact': 'New inquiry',
        }
        label = type_labels.get(inquiry.type.value, 'New inquiry')
        subject = f"{label}: {inquiry.name or inquiry.email}"

        html_content = render_template(
            'emails/book_inquiry.html',
            inquiry=inquiry,
            label=label
        )

        last_result = (False, 'No recipients')
        for email_addr in recipients:
            last_result = self.send_email(
                email_addr, subject, html_content,
                email_type='admin_notification'
            )
        return last_result

    def send_waitlist_notification(self, registration):
        """Send one-way notification to waitlisted registrant (no confirmation link)."""
        event = registration.event

        subject = f"Waiting list: {event.title}"

        html_content = render_template(
            'emails/waitlist_notification.html',
            registration=registration,
            event=event
        )

        text_content = f"""
Dear {registration.first_name},

thank you for your interest in "{event.title}".

The course is currently fully booked. You have been added to the waiting list.
If a place becomes available, we will contact you.

Date: {event.formatted_date}
Location: {event.location}

Kind regards,
{branding.EMAIL_SIGNATURE}
        """.strip()

        return self.send_email(
            registration.email, subject, html_content, text_content,
            email_type='waitlist_notification',
            registration_id=registration.id,
            event_id=event.id
        )


# Singleton instance
email_service = EmailService()
