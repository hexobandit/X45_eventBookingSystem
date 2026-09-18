"""
Marketing contacts upsert.

Deliberately defensive: this is a side effect of registration/contact flows and
must NEVER break them. Callers invoke it only AFTER their own db.session.commit(),
so a rollback here cannot touch the caller's data.
"""

from datetime import datetime

from flask import current_app
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import MarketingContact


def upsert_marketing_contact(email, name=None, phone=None, source='registration', consent=None):
    """Get-or-create a MarketingContact by email. Never raises.

    consent semantics: True = ticked the marketing checkbox (sets flag + date),
    None/False = no opt-in signal; an existing True is never downgraded.
    """
    try:
        email = (email or '').strip().lower()
        if not email:
            return None
        return _upsert(email, name, phone, source, consent)
    except IntegrityError:
        # Concurrent insert of the same email — retry once as an update
        db.session.rollback()
        try:
            return _upsert(email, name, phone, source, consent)
        except Exception as e:
            db.session.rollback()
            current_app.logger.warning(f'Marketing contact upsert retry failed for {email}: {e}')
    except Exception as e:
        db.session.rollback()
        current_app.logger.warning(f'Marketing contact upsert failed for {email}: {e}')
    return None


def _upsert(email, name, phone, source, consent):
    now = datetime.utcnow()
    contact = MarketingContact.query.filter_by(email=email).first()

    if contact:
        contact.last_seen_at = now
        contact.times_seen = (contact.times_seen or 0) + 1
        if name:
            contact.name = name
        if phone:
            contact.phone = phone
    else:
        contact = MarketingContact(
            email=email,
            name=name or None,
            phone=phone or None,
            source=source,
            first_seen_at=now,
            last_seen_at=now,
            times_seen=1,
        )
        db.session.add(contact)

    # Consent only upgrades — never True -> False/None
    if consent is True and contact.marketing_consent is not True:
        contact.marketing_consent = True
        contact.marketing_consent_date = now

    db.session.commit()
    return contact
