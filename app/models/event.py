"""
Event model for training courses and workshops.
"""

import json
from datetime import datetime, timedelta
from slugify import slugify
from app.extensions import db
from app import branding

TEST_EVENT_SLUG = 'test-event'
WAITLIST_LIMIT = 10


class Event(db.Model):
    """Training event model."""

    __tablename__ = 'events'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(220), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)
    short_description = db.Column(db.String(300))

    # Event details
    event_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime)  # For multi-day events
    location = db.Column(db.String(200), nullable=False)
    venue_name = db.Column(db.String(200))  # e.g., "Dental Office H33"

    # Capacity management
    capacity = db.Column(db.Integer, nullable=False, default=12)
    registered_count = db.Column(db.Integer, nullable=False, default=0)

    # Pricing
    price = db.Column(db.Numeric(10, 2))  # NULL = "On request"
    currency = db.Column(db.String(3), nullable=False, default='EUR', server_default='EUR')
    price_includes_vat = db.Column(db.Boolean, nullable=False, default=False, server_default='0')
    price_note = db.Column(db.String(100))  # e.g., "early bird", "student discount"

    # Payment details (managed via the course Manage panel, not the editor)
    # Shared
    payment_variable_symbol = db.Column(db.String(20))  # VS base, e.g. "2024001"
    payment_amount = db.Column(db.Numeric(10, 2))  # course fee in `currency`; falls back to price (Stripe uses this)
    payment_due_days = db.Column(db.Integer, default=14)  # days after registration
    payment_instructions = db.Column(db.Text)  # free-form payment note
    payment_beneficiary = db.Column(db.String(70))  # account holder name (SEPA/EPC QR requires it)
    # Offline method 1 — domestic Czech transfer in CZK (SPAYD "QR platba")
    payment_bank_account = db.Column(db.String(50))  # "[prefix-]number/bank" or CZ IBAN
    payment_amount_czk = db.Column(db.Numeric(10, 2))  # falls back to payment_amount when currency is CZK
    payment_qr_image = db.Column(db.String(500))  # uploaded QR image; replaces the generated domestic QR
    # Offline method 2 — SEPA credit transfer in EUR (EPC QR)
    payment_sepa_iban = db.Column(db.String(34))
    payment_sepa_bic = db.Column(db.String(11))
    payment_amount_eur = db.Column(db.Numeric(10, 2))  # falls back to payment_amount when currency is EUR

    # Lecturers (JSON array: [{"name": "...", "role": "..."}, ...])
    lecturers = db.Column(db.Text)

    # Content
    program = db.Column(db.Text)  # JSON or markdown for program details
    what_you_learn = db.Column(db.Text)  # JSON or markdown
    target_audience = db.Column(db.Text)
    includes = db.Column(db.Text)  # What's included in the price

    # Media
    image_url = db.Column(db.String(500))
    body_image_url = db.Column(db.String(500))
    image_position_y = db.Column(db.Integer, default=50)  # 0=top, 50=center, 100=bottom

    # External registration (delegates signup to a partner site, e.g. Patakovo.cz)
    external_registration_url = db.Column(db.String(500))  # NULL = internal registration

    # Event type and category
    event_type = db.Column(db.String(50), default='workshop')  # workshop, seminar, course
    event_category = db.Column(db.String(20), default='client')  # client, doctor

    # Status
    is_active = db.Column(db.Boolean, default=True, index=True)
    is_featured = db.Column(db.Boolean, default=False)
    is_test = db.Column(db.Boolean, default=False, index=True)
    registration_open = db.Column(db.Boolean, default=True)
    registration_opens_at = db.Column(db.DateTime)  # NULL = immediately open

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Version for optimistic locking (race condition prevention)
    version = db.Column(db.Integer, nullable=False, default=1)

    # Relationships
    registrations = db.relationship('Registration', back_populates='event', lazy='dynamic',
                                     cascade='all, delete-orphan', passive_deletes=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.slug and self.title:
            self.slug = self.generate_slug()

    def generate_slug(self):
        """Generate URL-friendly slug from title."""
        base_slug = slugify(self.title, lowercase=True)
        slug = base_slug
        counter = 1
        while Event.query.filter_by(slug=slug).first():
            slug = f"{base_slug}-{counter}"
            counter += 1
        return slug

    @property
    def spots_left(self):
        """Return number of available spots."""
        return max(0, self.capacity - self.registered_count)

    @property
    def is_full(self):
        """Check if event is at capacity."""
        return self.registered_count >= self.capacity

    @property
    def waitlist_count(self):
        """Return number of waitlisted registrations."""
        from app.models.registration import Registration, RegistrationStatus
        return Registration.query.filter_by(
            event_id=self.id,
            status=RegistrationStatus.WAITLIST
        ).count()

    @property
    def can_join_waitlist(self):
        """Check if waitlist registration is possible."""
        return (
            self.is_active and
            self.is_registration_open and
            self.is_full and
            self.waitlist_count < WAITLIST_LIMIT and
            not self.registration_not_yet_open and
            self.event_date > datetime.now()
        )

    @property
    def registration_not_yet_open(self):
        """Check if registration hasn't opened yet."""
        return (
            self.registration_opens_at is not None and
            datetime.now() < self.registration_opens_at
        )

    @property
    def is_registration_open(self):
        """Check if registration is open (combining manual toggle and timed opening)."""
        # If a timed opening is set and time has passed, registration is open
        if self.registration_opens_at is not None and datetime.now() >= self.registration_opens_at:
            return True
        # Otherwise use the manual toggle
        return self.registration_open

    @property
    def can_register(self):
        """Check if registration is possible."""
        return (
            self.is_active and
            self.is_registration_open and
            not self.is_full and
            not self.registration_not_yet_open and
            self.event_date > datetime.now()
        )

    @property
    def is_past(self):
        """Check if event has already occurred."""
        return self.event_date < datetime.now()

    @property
    def formatted_date(self):
        """Return formatted date string, e.g. '14 March 2027'."""
        return self.event_date.strftime('%-d %B %Y')

    @property
    def month_display(self):
        """Return month name (uppercase) for card display."""
        return self.event_date.strftime('%B').upper()

    @property
    def payment_amount_display(self):
        """Return payment amount, falling back to price."""
        return self.payment_amount if self.payment_amount is not None else self.price

    @property
    def domestic_amount(self):
        """CZK amount for the domestic transfer (explicit, else the fee when priced in CZK)."""
        if self.payment_amount_czk is not None:
            return self.payment_amount_czk
        if (self.currency or 'EUR').upper() == 'CZK':
            return self.payment_amount_display
        return None

    @property
    def sepa_amount(self):
        """EUR amount for the SEPA transfer (explicit, else the fee when priced in EUR)."""
        if self.payment_amount_eur is not None:
            return self.payment_amount_eur
        if (self.currency or 'EUR').upper() == 'EUR':
            return self.payment_amount_display
        return None

    @property
    def domestic_account_valid(self):
        """Account number parses as a Czech domestic account or IBAN."""
        from app.services.payment_qr import czech_account_to_iban
        return bool(self.payment_bank_account) and czech_account_to_iban(self.payment_bank_account) is not None

    @property
    def sepa_iban_valid(self):
        """IBAN passes the ISO 7064 check (a wrong IBAN would only produce a dead QR)."""
        from app.services.payment_qr import normalize_iban
        return bool(self.payment_sepa_iban) and normalize_iban(self.payment_sepa_iban) is not None

    @property
    def has_domestic_payment(self):
        """Domestic CZK transfer is offered (valid account + CZK amount)."""
        return self.domestic_account_valid and self.domestic_amount is not None

    @property
    def has_sepa_payment(self):
        """SEPA EUR transfer is offered (valid IBAN + EUR amount)."""
        return self.sepa_iban_valid and self.sepa_amount is not None

    @property
    def has_payment_details(self):
        """At least one offline payment method is fully configured."""
        return self.has_domestic_payment or self.has_sepa_payment

    @property
    def formatted_domestic_amount(self):
        amount = self.domestic_amount
        return f"{amount:,.0f} Kč".replace(',', ' ') if amount is not None else None

    @property
    def formatted_sepa_amount(self):
        amount = self.sepa_amount
        return f"{amount:,.2f} €".replace(',', ' ') if amount is not None else None

    @property
    def payment_beneficiary_name(self):
        """Account holder name for SEPA (EPC) QR codes."""
        return self.payment_beneficiary or branding.PAYMENT_BENEFICIARY

    @property
    def has_external_registration(self):
        """Check if registration is delegated to an external partner."""
        return bool(self.external_registration_url)

    # Currencies offered in the admin; first entry is the default
    CURRENCIES = ['EUR', 'CZK', 'USD', 'GBP']
    CURRENCY_SYMBOLS = {'EUR': '€', 'CZK': 'Kč', 'USD': '$', 'GBP': '£'}

    @property
    def currency_symbol(self):
        return self.CURRENCY_SYMBOLS.get(self.currency or 'EUR', self.currency)

    def _format_amount(self, amount):
        return f"{amount:,.0f} {self.currency_symbol}".replace(',', ' ')

    @property
    def formatted_price(self):
        """Return formatted price or 'On request'."""
        if self.price is None:
            return "On request"
        formatted = self._format_amount(self.price)
        if self.price_includes_vat:
            formatted += " incl. VAT"
        return formatted

    @property
    def formatted_payment_amount(self):
        """Formatted payment amount (falls back to price), or None."""
        amount = self.payment_amount_display
        return self._format_amount(amount) if amount is not None else None

    @property
    def lecturers_list(self):
        """Return parsed lecturers list from JSON."""
        if not self.lecturers:
            return []
        try:
            return json.loads(self.lecturers)
        except (json.JSONDecodeError, TypeError):
            return []

    def increment_registration(self):
        """
        Safely increment registration count with optimistic locking.
        Returns True if successful, False if event is full or version conflict.
        """
        if self.is_full:
            return False

        # Store current version for optimistic lock check
        current_version = self.version

        # Attempt update with version check
        result = db.session.execute(
            db.update(Event)
            .where(Event.id == self.id)
            .where(Event.version == current_version)
            .where(Event.registered_count < Event.capacity)
            .values(
                registered_count=Event.registered_count + 1,
                version=Event.version + 1
            )
        )

        if result.rowcount == 0:
            # Version conflict or capacity reached
            db.session.rollback()
            return False

        # Refresh the instance to get updated values
        db.session.refresh(self)
        return True

    def decrement_registration(self):
        """Safely decrement registration count."""
        if self.registered_count <= 0:
            return False

        current_version = self.version

        result = db.session.execute(
            db.update(Event)
            .where(Event.id == self.id)
            .where(Event.version == current_version)
            .where(Event.registered_count > 0)
            .values(
                registered_count=Event.registered_count - 1,
                version=Event.version + 1
            )
        )

        if result.rowcount == 0:
            db.session.rollback()
            return False

        db.session.refresh(self)
        return True

    @classmethod
    def ensure_test_event(cls):
        """Create the permanent test event if it doesn't exist."""
        existing = cls.query.filter_by(slug=TEST_EVENT_SLUG).first()
        if existing:
            return existing

        test_event = cls(
            title='[TEST] Test Course',
            slug=TEST_EVENT_SLUG,
            description=(
                '<p>This course exists solely for testing the registration system, '
                'email notifications and other functionality.</p>'
                '<p>It is not visible to the public — only logged-in administrators can access it.</p>'
            ),
            short_description='Internal test course for verifying system functionality.',
            event_date=datetime.now() + timedelta(days=365),
            location='Test Location',
            venue_name='Test',
            capacity=100,
            price=1000,
            event_type='workshop',
            event_category='client',
            is_active=True,
            is_featured=False,
            is_test=True,
            registration_open=True,
        )
        db.session.add(test_event)
        db.session.commit()
        return test_event

    def __str__(self):
        return self.title

    def __repr__(self):
        return f'<Event {self.title}>'
