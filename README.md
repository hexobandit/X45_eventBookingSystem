# Course booking engine

Web + registration + payment system for people who run a few courses or
workshops a year: lecturers, clinics, training companies. One Flask app per
client, on the client's own domain, with payments going straight to the
client's bank account (bank transfer with QR) or card via Stripe. No ticket
commission.

This repository is the **product**: the generic engine plus a public demo
instance. The first production deployment of this engine is the ANTERIOR
course site; that site lives in its own deployment and is not touched here.

- Local dev admin: `admin@example.com` / `local-dev-2026`
- URL: http://127.0.0.1:5000, admin at http://127.0.0.1:5000/admin
- Demo brand (fictional): **Studio Lumen**, photography workshops in Prague

## What the engine does

- **Course pages** — listing + detail pages with program, lecturers, what
  you learn, price; visual editor in the admin (no form-filling)
- **Bookings** — capacity with optimistic locking, waiting list, timed
  registration opening with a countdown, external-partner registration links
- **Registration flow** — pending → email confirmation link → confirmed;
  cancellation links; variable symbol assigned per registration
- **Payments** — Stripe Checkout (card), domestic CZK transfer with SPAYD QR,
  SEPA EUR transfer with EPC QR; paid / unpaid tracking, VS matching
- **Emails** — confirmation, payment details with inline QR, reminders,
  custom and batch messages; every send logged with the SMTP transcript
- **Admin** — dashboard, registrations (confirm / paid / cancel / remind,
  CSV/XLSX/PDF export), deleted-registration archive (GDPR), inquiries and
  notify list, marketing contacts, users, audit log, encrypted SMTP settings
- **Anti-spam** — honeypot, HMAC time token, JS check, rate limiting; blocks
  logged, bots see a fake success

## Branding

All brand strings come from `app/branding.py`, and every value can be
overridden with a `BRAND_*` environment variable (see `.env.example`). The
defaults describe the fictional demo organisation. A new client deployment
is: set the `BRAND_*` variables, run `python scripts/gen_favicon.py`, add
courses in the admin.

## Demo mode

`DEMO_MODE=1` turns an instance into the public demo:

- a banner on the public site and in the admin
- after registering, the attendee sees links to the confirmation, payment
  (with QR) and reminder emails rendered in the browser, so no mailbox is
  needed to follow the flow
- admin actions that would break the demo for other visitors are refused:
  creating or editing users, changing the password, SMTP settings, deleting
  courses. Registrations, payments and emails stay fully live.
- the data is meant to be reseeded nightly:
  `flask --app wsgi seed-events --reset`

## Development setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

cp .env.example .env          # set DEMO_MODE=1 for the demo look

flask --app wsgi db upgrade   # create schema (SQLite instance/dev.db)
flask --app wsgi seed-events  # three demo courses + sample registrations
flask --app wsgi create-admin # interactive admin creation

flask --app wsgi run --debug
```

Run tests:

```bash
python -m pytest -q
```

Smoke scripts (HTTP form submitters against a running server):

```bash
BASE_URL=http://127.0.0.1:5000 python scripts/test_forms.py both
SMTP_HOST=... SMTP_USER=... SMTP_PASS=... TO_EMAIL=you@example.com python scripts/test_smtp.py
```

## Production deployment

1. **Provision PostgreSQL** and create a database.
2. **Environment** — production refuses to start without these:
   ```bash
   FLASK_CONFIG=production
   SECRET_KEY=<python -c "import secrets; print(secrets.token_hex(32))">
   DATABASE_URL=postgresql://courses:...@localhost:5432/courses
   CANONICAL_DOMAIN=https://example.com
   BRAND_SITE_NAME=...        # and the other BRAND_* values
   ```
3. **Schema + admin:**
   ```bash
   flask --app wsgi db upgrade
   flask --app wsgi create-admin
   ```
4. **Run behind nginx** (TLS termination + proxy headers; ProxyFix is enabled):
   ```bash
   gunicorn -w 1 -b 127.0.0.1:8000 wsgi:app
   ```
   Flask-Limiter uses in-memory storage by default — with more than one
   worker (`-w 2+`), set `REDIS_URL` so rate limits are shared across processes.
5. **Email setup** — log in to `/admin`, open **Email Settings**, enter the
   SMTP details, and use **Send test email**. Configure SPF/DKIM DNS records
   for the sending domain.
6. **Uploads** — `app/static/uploads/` (event images, payment QR codes) must
   be persisted and backed up along with the database.

`DEPLOYMENT.md` and `scripts/deploy*.sh` still describe the first client's
VM layout and are being generalised (see `MARKETING_SITE_PLAN.md`).

### Things to know

- Rotating `SECRET_KEY` invalidates the Fernet-encrypted SMTP password stored
  in the database — re-enter it in Email Settings afterwards.
- Schema changes go through Alembic: `flask --app wsgi db migrate -m "..."`
  then `flask --app wsgi db upgrade`.
- A permanent hidden **test course** (`/courses/test-event`) exists for
  logged-in admins to test the full registration + email flow safely.

## Project layout

```
app/
├── branding.py        # brand constants, env-overridable
├── demo.py            # DEMO_MODE admin guard
├── config.py          # Dev/Prod/Testing configs (prod validates env)
├── models/            # Event, Registration, User, Inquiry, EmailSettings, logs
├── routes/            # public site + admin auth
├── services/          # email (SMTP + log), antispam, payment QR, Stripe
├── admin/             # Flask-Admin portal
├── templates/         # public pages, emails/, admin/
└── static/            # css/ (token-based design system), js/, fonts/ (self-hosted), img/
marketing/             # standalone marketing page for the service (static)
migrations/            # Alembic
tests/                 # pytest suite
scripts/               # HTTP smoke tests, SMTP check, favicon/OG generator, deploy
docs/                  # payment flow, Stripe go-live, sales offer template
```
