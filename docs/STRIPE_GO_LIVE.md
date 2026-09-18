# Stripe — Go Live on the Production Server

Step-by-step guide for switching card payments from the test sandbox to a
real (live) Stripe account on `anteriorcourses.com` (vm-webapps).

How the integration works (see also `docs/payment-flow.md`):

- The app creates a **Stripe Checkout Session** and redirects the attendee
  to Stripe's hosted payment page — no card data ever touches our server.
- Stripe calls back `POST /webhooks/stripe` with
  `checkout.session.completed`; the app verifies the signature and marks
  the registration **Paid**.
- Card payments are shown to visitors **only when `STRIPE_SECRET_KEY` is
  set** (`stripe_enabled()` in `app/services/stripe_payment.py`). Empty
  key = card option hidden. That is also the instant rollback switch.

Config needed on the server (`/var/www/anterior/app/.env`):

| Variable | Live value looks like |
|---|---|
| `STRIPE_SECRET_KEY` | `sk_live_...` or `rk_live_...` (restricted, preferred) |
| `STRIPE_WEBHOOK_SECRET` | `whsec_...` from the **production webhook endpoint** |

> The local dev values (`sk_test_...` + `stripe listen` secret) never go to
> the server. Test and live mode have separate keys, separate webhook
> secrets, and separate data.

---

## 1. Activate the Stripe account (one-time)

1. Log in at https://dashboard.stripe.com with the account that owns the
   "Anterior Courses" sandbox.
2. Click **Activate payments** (or Settings → Account) and complete the
   business profile:
   - legal entity (s.r.o. / OSVČ), IČO, registered address,
   - identity verification of the representative (ID upload),
   - **bank account for payouts** (Czech account is fine; payouts arrive
     in the account currency),
   - public business details: statement descriptor (what appears on the
     customer's card statement — e.g. `ANTERIOR COURSES`), support
     email/phone, website URL.
3. Wait for verification. Usually minutes to a couple of days. The
   Dashboard shows what is still missing under
   **Settings → Business → Verification**.

Until activation completes you cannot create live keys — everything below
depends on this step.

## 2. Create the live API key

1. Dashboard → toggle from **Sandbox/Test mode** to **Live mode**
   (top-left environment switcher).
2. Go to **Developers → API keys**.
3. Preferred: **Create restricted key** — least privilege for this app:
   - Checkout Sessions: **Write**
   - everything else: **None**
   - name it e.g. `anterior-webapp-live`.
   The result is an `rk_live_...` key; the app accepts it in
   `STRIPE_SECRET_KEY` exactly like a full `sk_live_` key.
4. Copy the key once (it is shown only at creation) into a password
   manager. Never commit it, never paste it into chat/e-mail.

## 3. Create the production webhook endpoint

The Stripe CLI (`stripe listen`) is a **local dev tool only**. Production
uses a Dashboard-registered endpoint:

1. Live mode → **Developers → Webhooks → Add endpoint**.
2. Endpoint URL: `https://anteriorcourses.com/webhooks/stripe`
3. Events to send: select only **`checkout.session.completed`**
   (the handler ignores everything else — subscribing to more just adds
   noise and retries).
4. After creation, open the endpoint and click **Reveal** on the
   **Signing secret** — that is the live `whsec_...` value.

## 4. Configure the server

SSH to the VM and edit the production env file:

```bash
ssh <admin>@20.215.209.250
sudo -u anterior nano /var/www/anterior/app/.env
```

Set:

```ini
STRIPE_SECRET_KEY=rk_live_...        # from step 2
STRIPE_WEBHOOK_SECRET=whsec_...      # from step 3 (Dashboard endpoint, NOT the CLI one)
```

Check file permissions while you are there (secrets file, app user only):

```bash
sudo chmod 600 /var/www/anterior/app/.env
sudo chown anterior:anterior /var/www/anterior/app/.env
```

Deploy the current code (includes the webhook fix and QR/dashboard work)
using the usual rsync deploy from the workstation, then restart:

```bash
sudo systemctl restart anterior
sudo systemctl status anterior
```

## 5. Verify the wiring

1. **Card option visible:** open a course registration on the live site —
   the card payment choice must now appear (it is hidden while the key is
   empty).
2. **Webhook reachable:** Dashboard → Developers → Webhooks → your
   endpoint → **Send test event** → `checkout.session.completed`. Expect
   HTTP **200** in the attempt log. A `400` means wrong
   `STRIPE_WEBHOOK_SECRET` (test vs live mix-up is the usual cause);
   a `404` means `STRIPE_SECRET_KEY` is not loaded (endpoint aborts 404
   when Stripe is disabled).
   - Note: a *test* event carries no real registration id, so the app logs
     "no registration for session" and acks 200 — that is the correct
     behaviour, not an error.
3. **App log:** `sudo journalctl -u anterior -f` while sending the test
   event — watch for the webhook line, no tracebacks.

## 6. First real payment (live smoke test)

Live mode has **no test cards** — use a real card and a small amount:

1. Create a hidden/test course with a low price (Stripe minimum is about
   15 CZK / 0.50 EUR). Mark it `is_test` so it stays off public listings,
   or deactivate it right after the test.
2. Register yourself, choose card payment, pay with a real card.
3. Confirm the full chain:
   - Stripe Dashboard (Live → Payments) shows the payment,
   - webhook attempt log shows 200,
   - admin shows the registration **Paid** with the **Stripe** badge,
   - payment-received email + admin notification arrived,
   - statement descriptor on the payment preview reads correctly.
4. **Refund** the payment from the Dashboard (Payments → ⋯ → Refund).
   The refund keeps the registration marked Paid — flip it manually in
   admin if you used a throwaway registration, or just delete the test
   registration.

## 7. Operations after launch

- **Payouts:** Settings → Payouts — default is automatic daily/weekly to
  the bank account from step 1. Set the schedule you want.
- **Receipts:** Settings → Emails — enable customer receipts for
  successful payments if you want Stripe to send them (the app already
  sends its own confirmation email).
- **Webhook health:** Stripe retries failed webhook deliveries for ~3 days
  and emails you when an endpoint keeps failing. After any server outage,
  check Developers → Webhooks → attempt log; retried events will
  re-deliver automatically (the handler is idempotent — double delivery
  is safe).
- **Monitoring:** payments that succeeded on Stripe but show Unpaid in
  admin = webhook problem; the success-page race is handled, but check
  the endpoint log first.
- **Radar / disputes:** Stripe Radar screens live payments automatically.
  Disputes/chargebacks arrive by email — respond from the Dashboard.

## 8. Security notes

- Live secret key only ever lives in the server `.env` (chmod 600) and
  the password manager — never in git, chat, logs, or client-side code.
- The restricted key from step 2 limits blast radius; if a broader key is
  ever needed, create a new restricted key with the extra permission
  instead of upgrading to the full secret key.
- **Rotation:** Dashboard → API keys → ⋯ → Roll key. Update `.env`,
  restart the service. Same for the webhook secret (endpoint → Roll
  secret — Stripe overlaps old+new for 24 h, so roll first, then update
  the server within that window).
- **Kill switch:** clearing `STRIPE_SECRET_KEY` in `.env` + restart hides
  card payments site-wide immediately; bank-transfer QR flow is
  unaffected.
