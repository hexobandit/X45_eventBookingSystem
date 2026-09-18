"""
Authentication forms.
"""

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField
from wtforms.validators import DataRequired, Email, Length, EqualTo


class LoginForm(FlaskForm):
    """Admin login form."""

    email = StringField(
        'Email',
        validators=[
            DataRequired(message='Email is required'),
            Email(message='Enter a valid email address')
        ]
    )

    password = PasswordField(
        'Password',
        validators=[
            DataRequired(message='Password is required')
        ]
    )

    remember = BooleanField('Remember me')


class ChangePasswordForm(FlaskForm):
    """Change password form for logged-in users."""

    current_password = PasswordField(
        'Current password',
        validators=[DataRequired(message='Enter your current password')]
    )

    new_password = PasswordField(
        'New password',
        validators=[
            DataRequired(message='Enter a new password'),
            Length(min=6, message='Password must be at least 6 characters')
        ]
    )

    confirm_password = PasswordField(
        'Confirm new password',
        validators=[
            DataRequired(message='Confirm the new password'),
            EqualTo('new_password', message='Passwords do not match')
        ]
    )
