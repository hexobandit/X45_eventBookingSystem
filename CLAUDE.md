# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

The **course booking engine** as a product: a Flask course-registration + payment site that is deployed once per client under their own domain, plus (a) a public demo instance of the engine and (b) a standalone static marketing page selling the build service (`marketing/`, Czech). The engine was extracted from the ANTERIOR client site (anteriorcourses.com), which now runs on its own and is never edited from here. `MARKETING_SITE_PLAN.md` is the working plan; `docs/nabidka-paudent-whatsapp.md` is the internal price list (prices are never shown on the marketing page).

Light "daylight studio" public theme (white ground, blue `#2F5BFF` for interactive elements, tungsten amber `#FFC24D` reserved for the light motif, Outfit display + Inter body, pill buttons), light Flask-Admin portal, PostgreSQL in production (SQLite `instance/dev.db` locally). Public site copy is English; Czech localisation of the engine is an open decision.

## Commands

```bash
source .venv/bin/activate
pip install -r requirements-dev.txt

flask --app wsgi db upgrade            # apply Alembic migrations (never use init-db for prod)
flask --app wsgi seed-events           # demo catalogue: 3 courses + 6 sample registrations
flask --app wsgi seed-events --reset   # wipe non-test events/registrations and reseed (nightly demo reset)
flask --app wsgi create-admin          # interactive admin user
flask --app wsgi run --debug           # http://127.0.0.1:5000, admin at /admin (admin@example.com / local-dev-2026)
python scripts/gen_favicon.py          # regenerate favicons + OG card from the brand name

python -m pytest -q                              # full suite (~25 s)
python -m pytest -q tests/test_demo.py           # one file
```

Local `.env` sets `DEMO_MODE=1`. The dev server cannot bind a port inside the Claude sandbox; run it outside the sandbox.

Schema change: edit the model, then `flask --app wsgi db migrate -m "..."` and review the generated file in `migrations/versions/` (hand-written migrations are the norm; use `op.batch_alter_table` so SQLite dev DBs upgrade too). Check `flask --app wsgi db heads` shows one head.

Deploy: `scripts/deploy.sh` and `DEPLOYMENT.md` still target the first client's VM (paths/service named `anterior`); they are to be generalised with a `--site` switch once the product domain is chosen. Only the SSH key in `nono/` (gitignored) can deploy.

Tests use `create_app('testing')`: in-memory SQLite, CSRF off, `EMAIL_ASYNC=False`. Fixtures in `tests/conftest.py`: `make_event`, `make_registration`, `admin_user`, `human_form_data(app, ...)`. Admin tests log in with `tests.test_admin_auth.login(client, 'admin@example.com', 'test-password-123')`. Demo-mode tests build their own app with `TestingConfig.DEMO_MODE` monkeypatched (`tests/test_demo.py`). SMTP is mocked via `smtp_settings` + `mock_smtp` in `tests/test_email_service.py`.

## Architecture

**Branding** `app/branding.py` is the single source of brand strings; every constant reads a `BRAND_*` env var with the fictional demo organisation (Studio Lumen, photography workshops) as default. Injected into all templates via `brand_context()` (`site_name`, `site_authors_line`, `site_title_suffix`, `email_signature_html`, …). Never hardcode a client name in a template, email, or admin label; `PAYMENT_BENEFICIARY` is the QR fallback name.

**Demo mode** (`DEMO_MODE=1`, `app/demo.py`): a `before_request` guard refuses POSTs to the endpoints in `BLOCKED_ENDPOINT_PREFIXES` (users, password, SMTP settings, course delete/bulk actions) with a flash; everything else stays live. Public route `/registration/<token>/email/<confirmation|payment|reminder>` renders the transactional emails in the browser (404 outside demo mode) and `registration_success.html` links to them. Banners in `base.html` and `admin/master.html` key off `demo_mode`.

**App factory** `app/__init__.py` → `create_app(config_name)`; config classes in `app/config.py` (production `validate()` refuses to start without `SECRET_KEY` and `DATABASE_URL`). Blueprints: `app/routes/main.py` (public site) and `app/routes/admin.py` (admin login/logout, blueprint name `admin_auth`). Everything else admin lives in `app/admin/__init__.py`, a single ~2400-line Flask-Admin module.

**Registration lifecycle** (`app/models/registration.py`): `PENDING → CONFIRMED` via an emailed token link, or `WAITLIST` when full (limit 10, waitlist rows do not consume capacity), or `CANCELLED`. Capacity uses optimistic locking on `Event.version`; callers retry up to 5 times. The public route `register_for_event` and the admin "Add participant" branch in `manage_view` mirror each other; keep them in sync. A cancelled row with the same email is reactivated rather than duplicated (unique `(event_id, email)`). `variable_symbol` = event VS base + registration id.

**Admin deletion** hard-deletes after copying into `deleted_registrations` (`DeletedRegistration.from_registration`); `email_logs.registration_id` is nulled first because the FK has no `ON DELETE`. The seed `--reset` does the same cleanup manually because SQLite does not enforce cascades.

**Payments** (`docs/payment-flow.md`): Stripe Checkout (`app/services/stripe_payment.py`, webhook `/webhooks/stripe`, enabled only when `STRIPE_SECRET_KEY` is set) or bank transfer with two offline methods per course: domestic CZK (`payment_bank_account` + `payment_amount_czk` → SPAYD QR) and SEPA EUR (`payment_sepa_iban`/`bic` + `payment_amount_eur` → EPC QR). `Event.has_domestic_payment` / `has_sepa_payment` require the account/IBAN to validate (`app/services/payment_qr.py`); the Czech account `19-2000145399/0800` (IBAN `CZ6508000000192000145399`) passes and is used by the seed and tests. Payment details are edited only on `admin_events.manage_view`.

**Emails** (`app/services/email.py`): SMTP settings in the DB (`EmailSettings`, password Fernet-encrypted with a key derived from `SECRET_KEY`). Every send is logged. Templates in `templates/emails/` extend `base_email.html`; signatures use `site_authors_line`. Public routes send in a background thread unless `EMAIL_ASYNC` is False.

**Course action vocabulary** (`docs/UPDATE.md` is the original handoff): every place a course appears offers the same four actions, icon-first, via the macro in `admin/_course_actions.html` — Registrations (`details_view`), Edit page (`visual_edit_view`), Payments & emails (`manage_view`), Delete, plus View on website. Flask-Admin list rows get them from `admin/model/row_actions.html` (overrides the bootstrap4 macros, so every `ModelView` picks the style up) and `EventModelView.get_list_row_actions()`. Icons are CSS masks (`.ra-icon` + `--ra-svg` data-URI) in `admin/_components.css`, never an icon font; tooltips come from `[data-tip]` handled by one fixed bubble created in `master.html`. Buttons show a spinner through `admin/_busy_buttons.html` (`window.setLoading`), included by `master.html` and `panel_base.html`; the confirm modal stays open and spins while the action runs.

**Attendee sheet**: `EventModelView.attendee_sheet()` at `/admin/admin_events/attendee-sheet/?id=` renders `admin/event_attendee_sheet.html`, a standalone A4 welcome-desk list (expected + waitlist, cancelled excluded, tick boxes, paid pills). Print and "Save as PDF" both call `window.print()`; "Download PNG" uses the vendored `static/js/vendor/html2canvas.min.js`. Tests in `tests/test_admin_attendee_sheet.py`.

**Course editor** is not a Flask-Admin form: `EventModelView.create_view`/`edit_view` redirect to `visual_edit_view`, posting JSON to `visual_edit_save` (`static/js/visual-edit.js`). `lecturers`/`program` are JSON in Text columns. A permanent hidden test course (`slug = test-event`, `is_test=True`) cannot be deleted and skips anti-spam.

**Anti-spam** (`app/services/antispam.py`): honeypot `website`, HMAC time token `_form_token` (min 3 s), `_js_check`; blocks logged to `spam_logs`. Any new public form needs all three hidden inputs plus `check_spam()`.

**Inquiries** (`Inquiry`, `InquiryType`): the enum values `book_order` / `book_notify` are legacy names kept for DB compatibility; the admin labels them "Order interest" / "Notify list". No public form currently creates them (the client-specific book pages were removed); the admin views and batch email remain as a product feature.

## Conventions and gotchas

- CSS is split into partials imported by `static/css/style.css` (public) and `static/css/admin.css` (admin); `base.html` links the public partials directly with `?v={{ asset_v }}`. nginx caches `/static/` for 30 days, so bump the `?v=` date on the `@import` lines when editing an admin partial. Public tokens in `_variables.css` (light theme; `--light`/`--light-soft` are the amber light colours, never used for buttons); admin tokens in `admin/_variables.css` (same daylight blue as the public site). The home hero (`index.html`, hero block in `_pages.css`, last section of `main.js`) is the interactive "cursor is the key light" scene: JS writes `--lx`/`--ly` on `#hero`, CSS derives the light pool, sphere highlight, cast shadow and headline shadow; modifier chips set `data-mod`. Touch devices get a CSS orbit animation, reduced motion a static lamp. Sentence-case labels everywhere; no uppercase micro-type.
- Flask-Admin's native `confirm()` dialogs are replaced by the site modal (`_confirm_modal.html`, `window.showConfirm`); registration views register `window.deleteRegistrationRowHook` / `deleteRegistrationBulkHook`.
- Jinja autoescapes HTML entities in expressions: write `'✓'`, not `'&#10003;'`, inside `{{ }}`.
- `url_for('.manage_test_qr', id=...)` already contains `?id=`; append further params with `&`.
- Analytics: only the `GA4_ID` config renders a tag; there is no hardcoded tracker.
- Root-level `logo-anterior*` and `avenir-next-ultra-light.ttf` are the first client's assets that came along with the move; they do not belong to the product and should not be committed.
- Never commit `.env`, `nono/`, or anything under `instance/`.
