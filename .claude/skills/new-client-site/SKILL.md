---
name: new-client-site
description: Set up a new client deployment of the course booking engine - brand strings, icons, first courses, and the production checklist. Use when starting a site for a new client, rebranding an instance, or asked what it takes to launch one.
---

# Stand up a site for a new client

The engine is deployed once per client under their own domain. Nothing in the
code is client-specific: the whole brand comes from environment variables.

## 1. Brand

Copy `.env.example` to `.env` and fill the `BRAND_*` values. They feed
`app/branding.py`, which every template, email and admin label reads through
the template context. Never hardcode a client name anywhere.

```
BRAND_SITE_NAME, BRAND_SITE_TAGLINE, BRAND_SITE_DESCRIPTION,
BRAND_SITE_TITLE_SUFFIX, BRAND_AUTHORS, BRAND_CITY,
BRAND_EMAIL_SIGNATURE, BRAND_PAYMENT_BENEFICIARY, BRAND_INSTAGRAM_URL
```

Then regenerate the icons and the social card from the new name:

```bash
.venv/bin/python scripts/gen_favicon.py
```

## 2. Database and admin

```bash
FLASK_APP=wsgi .venv/bin/flask db upgrade
FLASK_APP=wsgi .venv/bin/flask create-admin
```

Do not seed the demo catalogue on a client instance. `seed-events` exists for
the demo and would create fictional courses.

## 3. Payments

Bank details are set per course on the Payments and emails page, not in
config. Both offline methods are independent: domestic in CZK produces a Czech
QR payment, SEPA in EUR produces an EPC QR. Each needs a valid account number
or IBAN, checked by the mod-97 rules, plus an amount, or it is not offered.
Stripe card payments turn on only when `STRIPE_SECRET_KEY` is set.

## 4. Email

SMTP settings live in the database, not in config. Log into the admin, open
Email Settings, enter the mailbox details, and send a test. Set up SPF and DKIM
for the sending domain. Rotating `SECRET_KEY` later invalidates the stored SMTP
password, because it is encrypted with a key derived from it.

## 5. Production

Required before the app will start: `FLASK_CONFIG=production`, `SECRET_KEY`,
`DATABASE_URL`, plus `CANONICAL_DOMAIN` for emails and sitemap. Leave
`DEMO_MODE` off. Run behind nginx with TLS. With more than one gunicorn worker,
set `REDIS_URL` so rate limits are shared. Persist and back up
`app/static/uploads/`, which holds course images and uploaded QR codes.

`DEPLOYMENT.md` has the server layout. `scripts/deploy.sh` still targets the
first client's virtual machine and needs generalising before reuse.

## 6. Before handover

Run the `demo-qa` skill against the instance with the client's own name added
to the forbidden list reversed: this time check that the *previous* brand is
gone, for instance `--forbid "Studio Lumen"`.
