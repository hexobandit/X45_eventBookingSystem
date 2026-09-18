# Sign in with Google — direct Google OIDC via Authlib for admin login

## Context

Admin login is currently a bcrypt password form (`app/routes/admin.py`). The user wants Google sign-in and chose **direct Google OIDC via Authlib** over Auth0 (one less external tenant). The password form stays as a break-glass fallback. No auto-provisioning: only emails already in the `users` table (active + admin) can sign in via Google — that's the allowlist. The feature is optional: with no `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` configured, the button is hidden and the routes redirect away, so the app deploys unchanged until the Google Console setup is done.

## Changes

### 1. `requirements.txt`
Add `Authlib>=1.3.0` (cryptography already present; deploy script auto-installs when requirements.txt changes).

### 2. `app/config.py`
In `Config` base, add `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` read from env, default `''`. These exact names matter — Authlib auto-loads `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` from `app.config` for a client registered as `'google'`. Do **not** add them to `ProductionConfig.validate()` (feature is optional).

### 3. `app/extensions.py`
Add:
```python
from authlib.integrations.flask_client import OAuth
oauth = OAuth()
oauth.register(
    'google',
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'},
)
```
(Config and metadata are resolved lazily — safe at import time.)

### 4. `app/__init__.py`
Import `oauth` alongside the other extensions; add `oauth.init_app(app)` after `limiter.init_app(app)` (~line 38).

### 5. `app/models/user.py`
After `password_hash` (line 17): `google_sub = db.Column(db.String(255), unique=True, nullable=True, index=True)` — bound on first Google login. `password_hash` stays NOT NULL.

### 6. Migration (`flask db migrate -m "add google_sub to users"`)
Chains from head `a3f2c1b9e8d7`: `add_column users.google_sub` + unique index. Nullable add — no table rebuild on SQLite, trivial on Postgres. Tests use `db.create_all()` so they pick it up automatically; prod applies via deploy script's `flask db upgrade`.

### 7. `app/routes/admin.py` — the core change
- Imports: add `session`, `current_app` (flask), `oauth` (extensions), `from authlib.integrations.base_client.errors import OAuthError`.
- Helper `_google_enabled()`: both config values non-empty.
- `login()`: pass `google_enabled=_google_enabled()` to **all three** `render_template` calls (lines 30, 34, 49).
- New `GET /admin/login/google` (`@limiter.limit("5 per minute")`): if authenticated → `admin.index`; if not configured → flash + redirect to login; stash `next` in `session['oauth_next']` only if it passes the existing `startswith('/admin')` guard; `oauth.google.authorize_redirect(url_for('admin_auth.google_callback', _external=True))`.
- New `GET /admin/auth/google/callback` (`@limiter.limit("10 per minute")`):
  1. If not configured → redirect to login.
  2. If `request.args.get('error')` (user cancelled the picker — arrives with no `code`) → flash + redirect. Must be checked **before** the token exchange.
  3. `token = oauth.google.authorize_access_token()` in `try/except OAuthError` (covers mismatching/replayed state, bad code) → flash + redirect on failure.
  4. Claims from `token.get('userinfo')` (Authlib ≥1.x verifies the ID token — signature, iss, aud, exp, nonce — itself; do **not** call `parse_id_token`). Require `sub`, `email`, and `email_verified` truthy.
  5. Lookup: by `google_sub == sub` first; else by lowercased email, but reject if that row has a *different* sub already bound (email-reassignment protection).
  6. Reject `None` / `not is_active` / `not is_admin` → flash "not authorized".
  7. First login: bind `user.google_sub = sub`. Then `login_user(user, remember=False)` (no checkbox in a redirect flow), `user.update_last_login()`, `db.session.commit()`, pop `oauth_next` (re-check the `/admin` prefix), redirect.
- CSRF: both routes are GET — flask-wtf doesn't validate GETs, no exemption needed; Authlib's `state` (stored in the Flask session, popped on first use) is the CSRF protection. `SameSite=Lax` cookie survives the top-level redirect hop.

### 8. `app/templates/admin/login.html`
Between `</form>` (line 147) and the back-link (line 149), inside `{% if google_enabled %}`: an "or" divider and `<a href="{{ url_for('admin_auth.google_login', next=request.args.get('next')) }}" class="btn btn-outline-dark w-100">Sign in with Google</a>`. Use Bootstrap's `btn-outline-dark` — the page's `.btn-primary` references undefined `--admin-accent` vars; don't copy it.

### 9. Tests — new `tests/test_google_auth.py`
Local fixtures (nothing else needs them): `google_configured` sets `app.config` keys directly (env is read at config import — too early for monkeypatch); `mock_google_token(userinfo)` patches `oauth.google.authorize_access_token` (`unittest.mock.patch.object`, generator style like `mock_smtp` in tests/test_email_service.py:32-42). **Never let the real `authorize_redirect`/`authorize_access_token` run — the first use fetches Google's metadata over the network.** Reuse the `admin_user` fixture (conftest.py:92). Assert login state by probing `GET /admin/` for 200 vs 302, matching tests/test_admin_auth.py.

Cases: happy path + sub bind + last_login set; lookup by bound sub (different email still logs in); email matches but different sub bound → rejected, sub unchanged; unknown email → rejected; `email_verified: False` → rejected; non-admin → rejected; inactive → rejected; `?error=access_denied` → graceful redirect, no mock needed; `OAuthError` side_effect → graceful redirect; unconfigured → login page lacks the button and `/admin/login/google` redirects, configured → button present; `next=/admin/events` carried through session to final redirect, `next=https://evil.com` falls back to `/admin/`.

### 10. Docs
- `.env.example`: append `GOOGLE_CLIENT_ID=` / `GOOGLE_CLIENT_SECRET=` with the existing per-var `#`-comment style, noting both redirect URIs.
- `DEPLOYMENT.md`: extend the env checklist (~line 413, optional vars, hand-edit server `.env` + restart — rsync excludes `.env`); add smoke-test bullet; short "Google Sign-In setup" subsection with the Console steps.

### Manual one-time Google Cloud Console steps (documented, not code)
OAuth consent screen (External + admins as test users, or Internal if Workspace; scopes only openid/email/profile — no verification review) → Credentials → OAuth client ID (Web application) → authorized redirect URIs exactly `https://anteriorcourses.com/admin/auth/google/callback` (naked domain — Google only redirects to exactly-registered URIs) and `http://127.0.0.1:5000/admin/auth/google/callback` for dev (browse via 127.0.0.1, not localhost). Put the ID/secret in `/var/www/anterior/app/.env`, restart `anterior.service`.

## Gotchas already accounted for
- `url_for(_external=True)` yields https in prod only because ProxyFix trusts `X-Forwarded-Proto` (app/__init__.py:29).
- Limiter is per-worker `memory://` — limits multiply by worker count (currently 1 worker; same as existing login limit, acceptable).
- Replayed callback → `MismatchingStateError` → caught by `OAuthError` handler.

## Verification
1. `python -m pytest tests/ -q` — full suite + new Google tests, all green.
2. `flask db upgrade` on dev DB; confirm `google_sub` column exists.
3. Launch dev server; `/admin/login` without config → no Google button; set dummy `GOOGLE_CLIENT_ID/SECRET` in `.env` → button appears; clicking it redirects toward `accounts.google.com` (full round-trip needs real Console credentials).
4. `GET /admin/auth/google/callback?error=access_denied` → clean redirect to login with flash, no 500.
