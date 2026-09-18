"""
Brand constants — the single source of truth for the organisation this
instance is deployed for.

Every value can be overridden with an environment variable so the same engine
serves any client (or the public demo) without touching code. Imported by the
email service, admin portal and templates (via the `inject_branding` context
processor registered in the app factory). Change the brand here or in `.env`,
nowhere else.
"""

import os


def _env(name, default):
    value = os.environ.get(name)
    return value if value not in (None, '') else default


def _env_list(name, default):
    raw = os.environ.get(name)
    if not raw:
        return list(default)
    return [part.strip() for part in raw.split(',') if part.strip()]


# --- Defaults describe the fictional demo organisation --------------------
SITE_NAME = _env('BRAND_SITE_NAME', 'Studio Lumen')
SITE_TAGLINE = _env('BRAND_SITE_TAGLINE', 'Learn by doing. Small groups. Real light.')
SITE_DESCRIPTION = _env(
    'BRAND_SITE_DESCRIPTION',
    'Studio Lumen — hands-on workshops in studio photography and lighting '
    'for working professionals, led by Klára Nováková and Marek Holub.'
)
SITE_TITLE_SUFFIX = _env('BRAND_SITE_TITLE_SUFFIX', 'Photography & Lighting Workshops')

# People behind the organisation (lecturers, authors, signatories)
AUTHORS = _env_list('BRAND_AUTHORS', ['Klára Nováková', 'Marek Holub'])
AUTHORS_LINE = ' & '.join(AUTHORS)
AUTHORS_LINE_HTML = ' &amp; '.join(AUTHORS)

CITY = _env('BRAND_CITY', 'Prague, Czech Republic')

ADMIN_TITLE = _env('BRAND_ADMIN_TITLE', f'{SITE_NAME} Admin')

# Signature used at the bottom of transactional emails
EMAIL_SIGNATURE = _env('BRAND_EMAIL_SIGNATURE', f'{AUTHORS_LINE}\n{SITE_NAME}')
EMAIL_SIGNATURE_HTML = _env('BRAND_EMAIL_SIGNATURE_HTML', f'{AUTHORS_LINE_HTML}<br>{SITE_NAME}')

# Default beneficiary name on payment QR codes when the course has none set
PAYMENT_BENEFICIARY = _env('BRAND_PAYMENT_BENEFICIARY', SITE_NAME)

INSTAGRAM_URL = _env('BRAND_INSTAGRAM_URL', '')
INSTAGRAM_HANDLE = _env('BRAND_INSTAGRAM_HANDLE', '')


def brand_context():
    """Template context — available in every Jinja template."""
    return {
        'site_name': SITE_NAME,
        'site_tagline': SITE_TAGLINE,
        'site_description': SITE_DESCRIPTION,
        'site_title_suffix': SITE_TITLE_SUFFIX,
        'site_authors': AUTHORS,
        'site_authors_line': AUTHORS_LINE,
        'site_city': CITY,
        'admin_title': ADMIN_TITLE,
        'email_signature_html': EMAIL_SIGNATURE_HTML,
        'instagram_url': INSTAGRAM_URL,
        'instagram_handle': INSTAGRAM_HANDLE,
    }
