"""
Registration and contact forms.
"""

from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, BooleanField, SelectField, HiddenField, RadioField
from wtforms.validators import DataRequired, Email, Length, Optional, ValidationError, Regexp

PHONE_REGEX = r'^\+?[\d\s\-\(\)]{6,20}$'
PHONE_MSG = 'Enter a valid phone number (digits, spaces, +, -, parentheses only)'


class RegistrationForm(FlaskForm):
    """Event registration form."""

    first_name = StringField(
        'First name',
        validators=[
            DataRequired(message='First name is required'),
            Length(min=2, max=100, message='First name must be 2-100 characters')
        ]
    )

    last_name = StringField(
        'Last name',
        validators=[
            DataRequired(message='Last name is required'),
            Length(min=2, max=100, message='Last name must be 2-100 characters')
        ]
    )

    email = StringField(
        'Email',
        validators=[
            DataRequired(message='Email is required'),
            Email(message='Enter a valid email address'),
            Length(max=255)
        ]
    )

    phone = StringField(
        'Phone',
        validators=[
            Optional(),
            Length(max=20, message='Phone number can have at most 20 characters'),
            Regexp(PHONE_REGEX, message=PHONE_MSG)
        ]
    )

    organization = StringField(
        'Organisation / Practice',
        validators=[
            Optional(),
            Length(max=200, message='Organisation can have at most 200 characters')
        ]
    )

    notes = TextAreaField(
        'Notes',
        validators=[
            Optional(),
            Length(max=1000, message='Notes can have at most 1000 characters')
        ]
    )

    payment_method = RadioField(
        'Payment method',
        choices=[
            ('card', 'Card'),
            ('bank_transfer', 'Bank transfer')
        ],
        default='bank_transfer',
        validators=[Optional()]
    )

    # Billing details — optional, for an invoice with company details
    billing_name = StringField(
        'Company name',
        validators=[Optional(), Length(max=200)]
    )
    billing_ico = StringField(
        'Company ID (IČO)',
        validators=[Optional(), Length(max=20)]
    )
    billing_dic = StringField(
        'VAT ID (DIČ)',
        validators=[Optional(), Length(max=20)]
    )
    billing_street = StringField(
        'Street',
        validators=[Optional(), Length(max=200)]
    )
    billing_city = StringField(
        'City',
        validators=[Optional(), Length(max=100)]
    )
    billing_zip = StringField(
        'ZIP',
        validators=[Optional(), Length(max=20)]
    )

    gdpr = BooleanField(
        'I consent to the processing of my personal data.',
        validators=[
            DataRequired(message='You must consent to the processing of personal data to register')
        ]
    )

    marketing = BooleanField(
        'Email me about upcoming courses and publications.',
        validators=[Optional()]
    )

    # Hidden field for event slug
    event_slug = HiddenField()


class ContactForm(FlaskForm):
    """General contact form."""

    name = StringField(
        'Full name',
        validators=[
            DataRequired(message='Name is required'),
            Length(min=2, max=200, message='Name must be 2-200 characters')
        ]
    )

    email = StringField(
        'Email',
        validators=[
            DataRequired(message='Email is required'),
            Email(message='Enter a valid email address'),
            Length(max=255)
        ]
    )

    phone = StringField(
        'Phone',
        validators=[
            Optional(),
            Length(max=20),
            Regexp(PHONE_REGEX, message=PHONE_MSG)
        ]
    )

    subject = SelectField(
        'Subject',
        choices=[
            ('', 'Choose a subject'),
            ('course', 'Course inquiry'),
            ('book', 'Book inquiry'),
            ('cooperation', 'Cooperation'),
            ('other', 'Other')
        ],
        validators=[Optional()]
    )

    message = TextAreaField(
        'Message',
        validators=[
            DataRequired(message='Message is required'),
            Length(min=10, max=5000, message='Message must be 10-5000 characters')
        ]
    )

    gdpr = BooleanField(
        'I consent to the processing of my personal data',
        validators=[
            DataRequired(message='You must consent to the processing of personal data to send the message')
        ]
    )

    marketing = BooleanField(
        'I would like to receive news about upcoming courses and publications',
        validators=[Optional()]
    )
