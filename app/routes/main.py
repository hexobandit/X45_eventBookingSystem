"""
Main public routes for the website.
"""

import threading
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, current_app, Response

from flask_login import current_user
from sqlalchemy.exc import IntegrityError

from app import branding
from app.extensions import db, limiter, csrf
from app.models import Event, Registration
from app.models.registration import RegistrationStatus, PaymentStatus, PaymentMethod
from app.forms import RegistrationForm, ContactForm
from app.services.email import email_service
from app.services.antispam import check_spam, generate_form_token
from app.services.marketing import upsert_marketing_contact
from app.services import stripe_payment
from app.services.payment_qr import registration_qr_png

main = Blueprint('main', __name__)


@main.route('/')
def index():
    """Homepage."""
    # Next 3 upcoming events (is_featured is reserved for a future
    # "highlighted courses" feature and intentionally ignored here)
    upcoming_events = Event.query.filter(
        Event.is_active == True,
        Event.is_test != True,
        Event.event_date > datetime.utcnow()
    ).order_by(Event.event_date.asc()).limit(3).all()

    return render_template('index.html', events=upcoming_events)


@main.route('/about')
def about():
    """About page."""
    return render_template('about.html')


@main.route('/courses')
def courses():
    """Course listing page."""
    events = Event.query.filter(
        Event.is_active == True,
        Event.is_test != True,
        Event.event_date > datetime.utcnow()
    ).order_by(Event.event_date.asc()).all()

    return render_template('courses.html', events=events)


@main.route('/courses/<slug>')
def course_detail(slug):
    """Single course detail page. Inactive courses show an archived banner."""
    event = Event.query.filter_by(slug=slug).first_or_404()

    # Test events are only visible to logged-in admins
    if event.is_test and not (current_user.is_authenticated and current_user.is_admin):
        abort(404)

    archived = not event.is_active
    form = RegistrationForm()
    form.event_slug.data = slug

    # Pre-fill form with test data for admin on test event
    if event.is_test and current_user.is_authenticated and current_user.is_admin:
        form.first_name.data = 'Test'
        form.last_name.data = 'User'
        form.email.data = current_user.email
        form.phone.data = '+420 123 456 789'
        form.organization.data = 'Test Practice'
        form.notes.data = 'Test registration'

    now_iso = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    form_token = generate_form_token()
    return render_template('course_detail.html', event=event, form=form, archived=archived, now_iso=now_iso, form_token=form_token)


@main.route('/courses/<slug>/register', methods=['POST'])
@limiter.limit("5 per minute")
def register_for_event(slug):
    """Handle course registration."""
    event = Event.query.filter_by(slug=slug, is_active=True).first_or_404()

    # Test events are only accessible to logged-in admins
    if event.is_test and not (current_user.is_authenticated and current_user.is_admin):
        abort(404)

    # External-registration events have no internal POST endpoint
    if event.has_external_registration:
        abort(404)

    form = RegistrationForm()

    # Skip anti-spam for test events (admin is authenticated; prevents false positives)
    if not event.is_test:
        is_spam, spam_reason = check_spam(
            form_type='registration',
            email=request.form.get('email', ''),
            name=f"{request.form.get('first_name', '')} {request.form.get('last_name', '')}",
            event_slug=slug
        )
        if is_spam:
            flash('Your registration has been received! A confirmation email is on its way.', 'success')
            return redirect(url_for('main.course_detail', slug=slug))

    is_waitlist_registration = False
    if not event.can_register:
        if event.is_full and event.can_join_waitlist:
            is_waitlist_registration = True
        elif event.is_full:
            flash('Unfortunately this course is fully booked and the waiting list is full.', 'warning')
            return redirect(url_for('main.course_detail', slug=slug))
        elif event.is_past:
            flash('This course has already taken place.', 'warning')
            return redirect(url_for('main.course_detail', slug=slug))
        elif event.registration_not_yet_open:
            flash('Registration for this course has not opened yet.', 'warning')
            return redirect(url_for('main.course_detail', slug=slug))
        else:
            flash('Registration for this course is currently not possible.', 'warning')
            return redirect(url_for('main.course_detail', slug=slug))

    if form.validate_on_submit():
        target_status = RegistrationStatus.WAITLIST if is_waitlist_registration else RegistrationStatus.PENDING

        # Card is offered only when Stripe is configured and the event has a payable
        # amount; anything else falls back to bank transfer
        wants_card = (
            form.payment_method.data == 'card'
            and stripe_payment.stripe_enabled()
            and event.payment_amount_display is not None
            and not is_waitlist_registration
        )
        chosen_method = PaymentMethod.CARD if wants_card else PaymentMethod.BANK_TRANSFER

        # Check for existing registration
        existing = Registration.query.filter_by(
            event_id=event.id,
            email=form.email.data.lower()
        ).first()

        if existing:
            if existing.is_cancelled:
                # Allow re-registration if previously cancelled
                existing.status = target_status
                existing.first_name = form.first_name.data
                existing.last_name = form.last_name.data
                existing.phone = form.phone.data
                existing.organization = form.organization.data
                existing.notes = form.notes.data
                existing.gdpr_consent = True
                existing.gdpr_consent_date = datetime.utcnow()
                existing.confirmation_token = Registration.generate_token()
                existing.cancelled_at = None
                existing.cancellation_reason = None
                existing.payment_method = chosen_method
                existing.billing_name = form.billing_name.data
                existing.billing_ico = form.billing_ico.data
                existing.billing_dic = form.billing_dic.data
                existing.billing_street = form.billing_street.data
                existing.billing_city = form.billing_city.data
                existing.billing_zip = form.billing_zip.data
                registration = existing
            else:
                flash('This email address is already registered for this course.', 'info')
                return redirect(url_for('main.course_detail', slug=slug))
        else:
            # Create new registration
            registration = Registration(
                event_id=event.id,
                first_name=form.first_name.data,
                last_name=form.last_name.data,
                email=form.email.data.lower(),
                phone=form.phone.data,
                organization=form.organization.data,
                notes=form.notes.data,
                gdpr_consent=True,
                gdpr_consent_date=datetime.utcnow(),
                confirmation_token=Registration.generate_token(),
                status=target_status,
                payment_method=chosen_method,
                billing_name=form.billing_name.data,
                billing_ico=form.billing_ico.data,
                billing_dic=form.billing_dic.data,
                billing_street=form.billing_street.data,
                billing_city=form.billing_city.data,
                billing_zip=form.billing_zip.data
            )

        # Waitlist registrations do NOT increment the event count.
        # NOTE: the admin manual add (manage_view 'add_registration' branch in
        # app/admin/__init__.py) mirrors the semantics below — keep them in sync.
        if not is_waitlist_registration:
            # Try to increment event registration count with retry on version conflict
            registered = False
            for _attempt in range(5):
                if event.increment_registration():
                    registered = True
                    break
                # Refresh event to get latest version
                db.session.refresh(event)
            if not registered:
                flash('The course filled up while you were registering. Please try again.', 'warning')
                return redirect(url_for('main.course_detail', slug=slug))

        try:
            if not existing:
                db.session.add(registration)
            db.session.flush()

            # Generate unique variable symbol from registration ID (race-safe)
            base = event.payment_variable_symbol or f"{event.id:04d}"
            registration.variable_symbol = f"{base}{registration.id}"

            db.session.commit()

            # Marketing contact upsert — after the registration commit so it can
            # never touch registration data; covers new, waitlist and reactivated paths
            upsert_marketing_contact(
                email=registration.email,
                name=registration.full_name,
                phone=registration.phone,
                source='registration',
                consent=True if form.marketing.data else None
            )

            app = current_app._get_current_object()
            reg_id = registration.id

            if is_waitlist_registration:
                # Send waitlist notification (one-way, no confirmation link)
                def send_waitlist_emails_bg(app, reg_id):
                    with app.app_context():
                        try:
                            reg = db.session.get(Registration, reg_id)
                            if reg:
                                email_service.send_waitlist_notification(reg)
                                email_service.send_admin_notification(reg)
                        except Exception as e:
                            app.logger.error(f'Background waitlist email failed for registration {reg_id}: {e}')

                if current_app.config.get('EMAIL_ASYNC', True):
                    threading.Thread(
                        target=send_waitlist_emails_bg,
                        args=(app, reg_id),
                        daemon=True
                    ).start()
                else:
                    send_waitlist_emails_bg(app, reg_id)

                flash('You have been added to the waiting list! A confirmation email is on its way.', 'info')
                return redirect(url_for('main.waitlist_success', token=registration.confirmation_token))
            else:
                # Build confirmation URL while we still have a request context
                confirmation_url = url_for(
                    'main.confirm_registration',
                    token=registration.confirmation_token,
                    _external=True
                )

                # Send emails in background thread to avoid blocking the response
                def send_emails_bg(app, reg_id, confirmation_url):
                    with app.app_context():
                        try:
                            reg = db.session.get(Registration, reg_id)
                            if reg:
                                email_service.send_registration_confirmation(reg, confirmation_url)
                                email_service.send_admin_notification(reg)
                        except Exception as e:
                            app.logger.error(f'Background email send failed for registration {reg_id}: {e}')

                if current_app.config.get('EMAIL_ASYNC', True):
                    threading.Thread(
                        target=send_emails_bg,
                        args=(app, reg_id, confirmation_url),
                        daemon=True
                    ).start()
                else:
                    send_emails_bg(app, reg_id, confirmation_url)

                # Card payers go straight to Stripe Checkout (like layered.cz);
                # on failure they land on the success page with a pay link instead
                if wants_card:
                    try:
                        session = stripe_payment.create_checkout_session(registration)
                        db.session.commit()
                        return redirect(session.url, code=303)
                    except Exception as e:
                        current_app.logger.error(
                            f'Stripe checkout creation failed for registration {reg_id}: {e}')

                flash('Your registration has been received! A confirmation email is on its way.', 'success')
                return redirect(url_for('main.registration_success', token=registration.confirmation_token))

        except IntegrityError:
            db.session.rollback()
            event.decrement_registration()
            flash('Something went wrong with your registration. Please try again.', 'error')
            return redirect(url_for('main.course_detail', slug=slug))

    # Form validation failed — re-render with errors and entered data
    form_token = generate_form_token()
    return render_template('course_detail.html', event=event, form=form, archived=False, form_token=form_token)


@main.route('/registration/success/<token>')
def registration_success(token):
    """Registration success page."""
    registration = Registration.query.filter_by(confirmation_token=token).first_or_404()
    return render_template('registration_success.html', registration=registration)


@main.route('/registration/waitlist/<token>')
def waitlist_success(token):
    """Waitlist registration success page."""
    registration = Registration.query.filter_by(confirmation_token=token).first_or_404()
    return render_template('waitlist_success.html', registration=registration)


@main.route('/registration/<token>/pay')
@limiter.limit("10 per minute")
def pay_registration(token):
    """Start a card payment for an existing registration (link in emails)."""
    registration = Registration.query.filter_by(confirmation_token=token).first_or_404()
    event = registration.event

    if registration.is_paid:
        flash('This registration is already paid. Thank you!', 'info')
        return redirect(url_for('main.registration_success', token=token))
    if registration.is_cancelled:
        flash('This registration has been cancelled.', 'warning')
        return redirect(url_for('main.course_detail', slug=event.slug))
    if not stripe_payment.stripe_enabled() or event.payment_amount_display is None:
        flash('Card payment is currently not available. Please pay by bank transfer.', 'warning')
        return redirect(url_for('main.registration_success', token=token))

    try:
        session = stripe_payment.create_checkout_session(registration)
        db.session.commit()
        return redirect(session.url, code=303)
    except Exception as e:
        current_app.logger.error(f'Stripe checkout creation failed for registration {registration.id}: {e}')
        flash('Card payment could not be started. Please try again or pay by bank transfer.', 'error')
        return redirect(url_for('main.registration_success', token=token))


@main.route('/payment/success/<token>')
def payment_success(token):
    """Return page from Stripe Checkout. Payment state comes via webhook."""
    registration = Registration.query.filter_by(confirmation_token=token).first_or_404()
    return render_template('payment_success.html', registration=registration)


@main.route('/payment/cancelled/<token>')
def payment_cancelled(token):
    """Attendee backed out of Stripe Checkout."""
    registration = Registration.query.filter_by(confirmation_token=token).first_or_404()
    flash('Card payment was cancelled. You can try again below, or pay by bank transfer.', 'info')
    return redirect(url_for('main.registration_success', token=registration.confirmation_token))


@main.route('/registration/<token>/qr.png')
def registration_qr(token):
    """Generated payment QR: ?kind=domestic (SPAYD, CZK) or ?kind=sepa (EPC, EUR)."""
    registration = Registration.query.filter_by(confirmation_token=token).first_or_404()
    kind = request.args.get('kind', 'domestic')
    png = registration_qr_png(registration, kind)
    if png is None:
        abort(404)
    return Response(png, mimetype='image/png', headers={'Cache-Control': 'private, max-age=3600'})


@main.route('/registration/<token>/email/<kind>')
def registration_email_preview(token, kind):
    """Demo only: render the transactional email the attendee would have
    received, so a visitor can see the flow without a mailbox.

    kind: confirmation | payment | reminder
    """
    if not current_app.config.get('DEMO_MODE'):
        abort(404)
    registration = Registration.query.filter_by(confirmation_token=token).first_or_404()
    event = registration.event

    if kind == 'confirmation':
        html = render_template(
            'emails/registration_confirmation.html',
            registration=registration, event=event,
            confirmation_url=url_for('main.confirm_registration', token=token, _external=True)
        )
    elif kind == 'payment':
        from datetime import timedelta
        due_date = (registration.created_at or datetime.utcnow()) + timedelta(days=event.payment_due_days or 14)
        qr_kinds = {k for k in ('domestic', 'sepa') if getattr(event, f'has_{k}_payment')}
        qr_src = {k: url_for('main.registration_qr', token=token, kind=k) for k in qr_kinds}
        html = render_template(
            'emails/payment_details.html',
            registration=registration, event=event, due_date=due_date,
            qr_kinds=qr_kinds, qr_src=qr_src, has_qr=bool(qr_kinds)
        )
    elif kind == 'reminder':
        html = render_template(
            'emails/event_reminder.html',
            registration=registration, event=event, days_before=1
        )
    else:
        abort(404)

    resp = Response(html)
    resp.headers['X-Robots-Tag'] = 'noindex, nofollow'
    return resp


@main.route('/webhooks/stripe', methods=['POST'])
@csrf.exempt
@limiter.exempt
def stripe_webhook():
    """Stripe webhook: marks registrations paid on checkout.session.completed."""
    if not stripe_payment.stripe_enabled():
        abort(404)

    try:
        stripe_event = stripe_payment.verify_webhook(
            request.get_data(),
            request.headers.get('Stripe-Signature', '')
        )
    except Exception as e:
        current_app.logger.warning(f'Stripe webhook signature verification failed: {e}')
        return Response(status=400)

    if stripe_event['type'] == 'checkout.session.completed':
        # StripeObject attribute access raises on dict methods like .get();
        # a plain dict keeps the handler simple.
        obj = stripe_event['data']['object']
        session = obj.to_dict() if hasattr(obj, 'to_dict') else dict(obj)
        reg_id = (session.get('metadata') or {}).get('registration_id')
        registration = db.session.get(Registration, int(reg_id)) if reg_id else None
        if registration is None:
            current_app.logger.error(
                f"Stripe webhook: no registration for session {session.get('id')}")
            return Response(status=200)  # ack anyway; nothing to retry into

        if stripe_payment.handle_checkout_completed(session, registration):
            db.session.commit()
            try:
                email_service.send_payment_received(registration)
                email_service.send_admin_notification(registration)
            except Exception as e:
                current_app.logger.error(
                    f'Post-payment email failed for registration {registration.id}: {e}')

    return Response(status=200)


@main.route('/registration/confirm/<token>')
def confirm_registration(token):
    """Confirm registration via email link."""
    registration = Registration.query.filter_by(confirmation_token=token).first_or_404()

    if registration.is_confirmed:
        flash('Your registration has already been confirmed.', 'info')
    elif registration.is_cancelled:
        flash('This registration has been cancelled.', 'warning')
    else:
        registration.confirm()
        db.session.commit()

        # Send confirmed email to attendee
        email_service.send_registration_confirmed(registration)

        # Notify admin that registration was confirmed
        email_service.send_admin_confirmation_notice(registration)

        # Bank-transfer payers get payment details (with QR) right away
        if (registration.payment_method == PaymentMethod.BANK_TRANSFER
                and not registration.is_paid
                and not registration.payment_email_sent
                and registration.event.has_payment_details):
            success, _ = email_service.send_payment_details(registration)
            if success:
                registration.payment_email_sent = True
                registration.payment_email_sent_at = datetime.utcnow()
                db.session.commit()

        flash('Your registration has been confirmed!', 'success')

    return render_template('registration_confirmed.html', registration=registration)


@main.route('/registration/cancel/<token>')
def cancel_registration(token):
    """Cancel registration via email link."""
    registration = Registration.query.filter_by(confirmation_token=token).first_or_404()

    if registration.is_cancelled:
        flash('This registration has already been cancelled.', 'info')
    else:
        registration.cancel(reason='Cancelled by attendee')
        db.session.commit()
        flash('Your registration has been cancelled.', 'success')

    return redirect(url_for('main.index'))


@main.route('/privacy')
def privacy():
    """Privacy policy (linked from the registration/contact forms and footer)."""
    return render_template('privacy.html', updated='18 September 2026')


@main.route('/contact', methods=['GET', 'POST'])
@limiter.limit("10 per hour", methods=['POST'])
def contact():
    """Contact page with form handling."""
    form = ContactForm()

    if form.validate_on_submit():
        # Anti-spam check
        is_spam, spam_reason = check_spam(
            form_type='contact',
            email=form.email.data,
            name=form.name.data,
            extra_data={'subject': form.subject.data, 'message': form.message.data[:200]}
        )
        if is_spam:
            return redirect(url_for('main.contact_success',
                                    name=form.name.data, email=form.email.data))

        # Contact messages are not stored — but the sender goes into marketing contacts
        upsert_marketing_contact(
            email=form.email.data,
            name=form.name.data,
            phone=form.phone.data,
            source='contact',
            consent=True if form.marketing.data else None
        )

        # Send contact email to admin
        subject = f"Contact form: {form.subject.data or 'General inquiry'}"

        html_content = render_template(
            'emails/contact_message.html',
            name=form.name.data,
            email=form.email.data,
            phone=form.phone.data,
            subject=form.subject.data,
            message=form.message.data
        )

        from app.models.email_settings import EmailSettings
        from app.services.email import parse_email_list
        settings = EmailSettings.get_settings()

        # All notification recipients (send_email splits the comma-separated list)
        recipients = parse_email_list(settings.admin_email or '') if settings else []

        if recipients:
            email_service.send_email(
                to_email=recipients,
                subject=subject,
                html_content=html_content
            )

        # Send copy to the sender
        copy_html = render_template(
            'emails/contact_copy.html',
            name=form.name.data,
            subject=form.subject.data,
            message=form.message.data
        )
        email_service.send_email(
            to_email=form.email.data,
            subject=f'Copy of your message - {branding.SITE_NAME}',
            html_content=copy_html
        )

        return redirect(url_for('main.contact_success',
                                name=form.name.data, email=form.email.data))

    form_token = generate_form_token()
    return render_template('contact.html', form=form, form_token=form_token)


@main.route('/contact/sent')
def contact_success():
    """Contact form success page."""
    name = request.args.get('name', '')
    email = request.args.get('email', '')
    return render_template('contact_success.html', name=name, email=email)


@main.route('/robots.txt')
def robots_txt():
    """Serve robots.txt for search engine crawlers."""
    content = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /admin/\n"
        "Disallow: /registration/\n"
        "\n"
        f"Sitemap: {current_app.config['CANONICAL_DOMAIN']}/sitemap.xml\n"
    )
    return Response(content, mimetype='text/plain')


@main.route('/sitemap.xml')
def sitemap_xml():
    """Generate sitemap.xml with static and dynamic pages."""
    domain = current_app.config['CANONICAL_DOMAIN']

    static_paths = ['/', '/about', '/courses', '/contact', '/privacy']

    # Active future events (exclude test events)
    events = Event.query.filter(
        Event.is_active == True,
        Event.is_test != True,
        Event.event_date > datetime.utcnow()
    ).all()

    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'

    for path in static_paths:
        xml += f'  <url><loc>{domain}{path}</loc></url>\n'

    for event in events:
        xml += f'  <url><loc>{domain}/courses/{event.slug}</loc></url>\n'

    xml += '</urlset>\n'

    return Response(xml, mimetype='application/xml')
