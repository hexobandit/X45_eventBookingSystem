"""
CLI commands for database management and seeding.

Schema changes are managed by Flask-Migrate/Alembic:
    flask db migrate -m "message"
    flask db upgrade
"""

import click
from flask.cli import with_appcontext
from datetime import datetime, timedelta

from app.extensions import db
from app.models import Event, User


@click.command('send-deploy-email')
@click.option('--to', 'recipient', default=None,
              help='Override recipient(s) (default: admin email from email settings).')
@with_appcontext
def send_deploy_email_command(recipient):
    """Send a deploy notification email via the app's own email stack.

    Reads revision and commit list from app/deploy_info.json (written by
    scripts/deploy.sh before rsync). Doubles as an end-to-end SMTP test.
    Exits non-zero on failure so deploy scripts can surface it as a warning.
    """
    from flask import current_app, render_template
    from app.models.email_settings import EmailSettings
    from app.services.email import EmailService, parse_email_list
    from app.version import get_app_version

    settings = EmailSettings.get_settings()
    # admin field may hold several comma/space-separated addresses
    recipients = parse_email_list(recipient or '')
    if not recipients and settings:
        recipients = (parse_email_list(settings.admin_email or '')
                      or parse_email_list(settings.client_notification_emails or '')
                      or parse_email_list(settings.sender_email or ''))
    if not recipients:
        click.echo('No recipient: no admin/notification/sender email configured (and no --to given).')
        raise SystemExit(1)

    info = get_app_version() or {}
    revision = f"{info.get('rev', '')} {info.get('subject', '')}".strip() or 'unknown'
    changes = info.get('changes') or []
    deployed_at = datetime.now().strftime('%d.%m.%Y %H:%M')
    site_url = current_app.config.get('CANONICAL_DOMAIN') or 'http://127.0.0.1:5000'
    site = site_url.replace('https://', '').replace('http://', '')

    html = render_template(
        'emails/deploy_notification.html',
        site=site, site_url=site_url, revision=revision, changes=changes,
        deployed_at=deployed_at,
    )
    text_lines = [
        f'Deploy of {site} complete.',
        f'Time: {deployed_at}',
        f'Revision: {revision}',
    ]
    if changes:
        text_lines.append('Changes:')
        text_lines.extend(f'  - {l}' for l in changes)
    else:
        text_lines.append('No new commits — verification run only.')

    subject = f'Deploy OK: {site}' + (f" ({info['rev']})" if info.get('rev') else '')
    success, message = EmailService().send_email(
        to_email=recipients, subject=subject, html_content=html,
        text_content='\n'.join(text_lines), email_type='deploy_notification',
    )
    if success:
        click.echo(f'Deploy email sent to {", ".join(recipients)}.')
    else:
        click.echo(f'Deploy email FAILED: {message}')
        raise SystemExit(1)


@click.command('init-db')
@with_appcontext
def init_db_command():
    """Initialize the database (development convenience — production uses `flask db upgrade`)."""
    db.create_all()
    click.echo('Database initialized.')


@click.command('create-admin')
@click.option('--email', prompt='Admin email', help='Admin email address')
@click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True, help='Admin password')
@click.option('--name', prompt='Full name', default='Admin', help='Admin full name')
@with_appcontext
def create_admin_command(email, password, name):
    """Create an admin user."""
    existing = User.query.filter_by(email=email).first()
    if existing:
        click.echo(f'User with email {email} already exists.')
        return

    names = name.split(' ', 1)
    first_name = names[0]
    last_name = names[1] if len(names) > 1 else ''

    user = User(
        email=email,
        first_name=first_name,
        last_name=last_name,
        is_admin=True,
        is_active=True
    )
    user.password = password

    db.session.add(user)
    db.session.commit()

    click.echo(f'Admin user {email} created successfully.')


@click.command('seed-events')
@click.option('--reset', is_flag=True, default=False,
              help='Delete existing non-test events and registrations first (demo reset).')
@with_appcontext
def seed_events_command(reset):
    """Seed the demo catalogue: three fictional courses that show the range
    of the system (near-full course with waitlist, timed registration
    opening, free webinar) plus a handful of sample registrations."""
    from app.models import Registration
    from app.models.registration import RegistrationStatus, PaymentStatus, PaymentMethod

    if reset:
        from app.models import EmailLog
        events = Event.query.filter_by(is_test=False).all()
        ids = [e.id for e in events]
        keep_ids = [e.id for e in Event.query.filter_by(is_test=True).all()]
        # SQLite does not enforce ON DELETE CASCADE by default — clear
        # dependants explicitly (including orphans from an interrupted
        # reset) so event ids can be reused safely.
        reg_ids = [r.id for r in Registration.query.filter(
            ~Registration.event_id.in_(keep_ids) if keep_ids else True).all()]
        if reg_ids or ids:
            if reg_ids:
                EmailLog.query.filter(EmailLog.registration_id.in_(reg_ids)).update(
                    {'registration_id': None}, synchronize_session=False)
                Registration.query.filter(Registration.id.in_(reg_ids)).delete(synchronize_session=False)
            for event in events:
                db.session.delete(event)
        db.session.commit()
        click.echo(f'Removed {len(events)} existing events.')

    if Event.query.filter_by(is_test=False).count() > 0:
        click.echo('Events already exist. Skipping seed (use --reset to replace).')
        return

    now = datetime.now()

    # Fake but valid bank details so both payment QR codes render.
    bank = dict(
        payment_beneficiary='Studio Lumen s.r.o.',
        payment_bank_account='19-2000145399/0800',
        payment_sepa_iban='CZ6508000000192000145399',
        payment_sepa_bic='GIBACZPX',
        payment_due_days=10,
        payment_instructions='<p>Please pay within 10 days to keep your seat. Use the variable symbol from your email so we can match the payment automatically.</p>',
    )

    events = [
        {
            # 1. Two-day workshop, almost full: shows capacity + waitlist
            'title': 'Studio Lighting Masterclass',
            'description': '''<p>Two days in the studio with one goal: to leave knowing exactly why a photograph looks the way it does. We start with a single light and a white wall and finish with multi-light setups you can rebuild from memory on a job.</p>
<p>Six participants, two lecturers, real subjects. Every setup is shot by everyone, and every result is discussed openly.</p>''',
            'short_description': 'Two-day hands-on workshop: from one light to full multi-light portrait and product setups.',
            'event_date': now + timedelta(days=32),
            'end_date': now + timedelta(days=33),
            'location': 'Prague',
            'venue_name': 'Studio Lumen, Holešovice',
            'capacity': 6,
            'price': 12900,
            'currency': 'CZK',
            'payment_amount_czk': 12900,
            'payment_amount_eur': 520,
            'payment_variable_symbol': '2026001',
            'event_type': 'workshop',
            'event_category': 'client',
            'lecturers': '[{"name": "Klára Nováková", "role": "Lighting & portrait"}, {"name": "Marek Holub", "role": "Workflow & colour"}]',
            'program': '''<ul>
<li>Day 1 morning: reading light — direction, size, distance, fall-off</li>
<li>Day 1 afternoon: one-light portraits, modifiers side by side</li>
<li>Day 2 morning: product and still life, controlling reflections</li>
<li>Day 2 afternoon: building and documenting your own setup</li>
</ul>''',
            'what_you_learn': '''<ul>
<li>A repeatable method for lighting any subject from scratch</li>
<li>When a softbox, a beauty dish or a bare bulb is the right tool</li>
<li>How to meter, balance and mix flash with ambient light</li>
<li>A lighting diagram you can hand to an assistant</li>
</ul>''',
            'target_audience': '<p>Working or aspiring photographers who own a camera and at least one flash and want to stop guessing.</p>',
            'includes': '<p>All studio equipment, models, lunch on both days, and a PDF of every setup shot.</p>',
            'is_featured': True,
            **bank,
        },
        {
            # 2. Registration opens later: shows the countdown / timed opening
            'title': 'Portrait Weekend: Natural Light',
            'description': '''<p>A weekend outside the studio. We work with window light, open shade and the last hour of the day, and learn to shape all three with nothing more than a reflector and a piece of black foam.</p>''',
            'short_description': 'Weekend workshop on shaping natural light for portraits — no flash required.',
            'event_date': now + timedelta(days=75),
            'end_date': now + timedelta(days=76),
            'location': 'Prague',
            'venue_name': 'Letná and surroundings',
            'capacity': 8,
            'price': 7900,
            'currency': 'CZK',
            'payment_amount_czk': 7900,
            'payment_variable_symbol': '2026002',
            'event_type': 'workshop',
            'event_category': 'client',
            'lecturers': '[{"name": "Klára Nováková", "role": "Lighting & portrait"}]',
            'program': '''<ul>
<li>Saturday: window light indoors, reflectors and flags</li>
<li>Sunday: open shade, backlight, the golden hour</li>
</ul>''',
            'registration_opens_at': now + timedelta(days=3),
            'is_featured': True,
            **bank,
        },
        {
            # 3. Free online session with large capacity
            'title': 'Free Webinar: Pricing Your Photography',
            'description': '''<p>An honest 90-minute session on day rates, licensing and the quote that lands the job without giving it away. Bring your last three quotes; we will take a few apart live.</p>''',
            'short_description': 'Free 90-minute online session on day rates, licensing and quoting.',
            'event_date': now + timedelta(days=18),
            'location': 'Online',
            'venue_name': 'Zoom (link sent after registration)',
            'capacity': 100,
            'price': 0,
            'currency': 'CZK',
            'event_type': 'seminar',
            'event_category': 'client',
            'lecturers': '[{"name": "Marek Holub", "role": "Workflow & colour"}]',
            'is_featured': False,
        },
    ]

    created = []
    for event_data in events:
        event = Event(**event_data)
        db.session.add(event)
        created.append(event)
    db.session.flush()

    # Sample registrations on the masterclass: 5 of 6 seats taken, one on the waitlist.
    masterclass = created[0]
    people = [
        ('Jana', 'Dvořáková', 'jana.dvorakova@example.com', RegistrationStatus.CONFIRMED, PaymentStatus.PAID, PaymentMethod.CARD),
        ('Tomáš', 'Král', 'tomas.kral@example.com', RegistrationStatus.CONFIRMED, PaymentStatus.PAID, PaymentMethod.BANK_TRANSFER),
        ('Petra', 'Svobodová', 'petra.svobodova@example.com', RegistrationStatus.CONFIRMED, PaymentStatus.UNPAID, PaymentMethod.BANK_TRANSFER),
        ('Lukáš', 'Procházka', 'lukas.prochazka@example.com', RegistrationStatus.CONFIRMED, PaymentStatus.UNPAID, PaymentMethod.BANK_TRANSFER),
        ('Eva', 'Marková', 'eva.markova@example.com', RegistrationStatus.PENDING, PaymentStatus.UNPAID, None),
        ('Martin', 'Beneš', 'martin.benes@example.com', RegistrationStatus.WAITLIST, PaymentStatus.UNPAID, None),
    ]
    seat_count = 0
    for i, (first, last, email, status, pay_status, method) in enumerate(people):
        reg = Registration(
            event_id=masterclass.id,
            first_name=first,
            last_name=last,
            email=email,
            gdpr_consent=True,
            gdpr_consent_date=now - timedelta(days=10 - i),
            confirmation_token=Registration.generate_token(),
            status=status,
            payment_status=pay_status,
            payment_method=method,
            created_at=now - timedelta(days=10 - i),
        )
        if status == RegistrationStatus.CONFIRMED:
            reg.confirmed_at = now - timedelta(days=9 - i)
            reg.confirmation_email_sent = True
            reg.payment_email_sent = True
        if pay_status == PaymentStatus.PAID:
            reg.paid_at = now - timedelta(days=8 - i)
        if status in (RegistrationStatus.CONFIRMED, RegistrationStatus.PENDING):
            seat_count += 1
        db.session.add(reg)
        db.session.flush()
        reg.variable_symbol = f"{masterclass.payment_variable_symbol}{reg.id}"
    masterclass.registered_count = seat_count

    db.session.commit()
    click.echo(f'Created {len(created)} demo events and {len(people)} sample registrations.')


def register_commands(app):
    """Register CLI commands with the app."""
    app.cli.add_command(init_db_command)
    app.cli.add_command(create_admin_command)
    app.cli.add_command(seed_events_command)
    app.cli.add_command(send_deploy_email_command)
