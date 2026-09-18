# Marketing site plan — selling the course booking system as a service

## State of this repo (18 Sep 2026)

The full ANTERIOR codebase was *moved* (not copied) from `X41_anterior/` into this
repo. Only `README.md` is tracked; everything else is untracked. Left behind in
`X41_anterior/` are the dotfiles: `.gitignore`, `.env`, `.env.example`, `.claude/`.

`.gitignore`, `.env.example` and `.claude/` have since been copied over (18 Sep);
`nono/mddr_key.pem`, `instance/dev.db`, `.env` verified ignored. The local dev
admin password in `README.md` stays by decision (local-only credential).

## Assumption (change if wrong)

This repo becomes the **product**: a de-branded fork of ANTERIOR that serves as
the live demo, plus a separate, static marketing page. `anteriorcourses.com`
stays a client site in its own deployment and is never touched by this work.
ANTERIOR becomes reference #1 in the marketing copy (after the client agrees).

---

## Step 0 — Repo hygiene — DONE 18 Sep (except: root `logo-anterior*` / `avenir-next-ultra-light.ttf` still to be moved out; `.venv` recreated inside this repo)

1. Move the dotfiles over: `.gitignore`, `.env.example`, `.claude/` from
   `X41_anterior/`. Do **not** bring `.env` with production secrets into a repo
   that will hold a demo; create a fresh one.
2. Verify with `git check-ignore nono/mddr_key.pem instance/dev.db` before any
   `git add`.
3. Delete `app/deploy_info 2.json` (Finder duplicate) and `logo-anterior [Recovered].ai`.
4. Rewrite `CLAUDE.md`: the copied one describes ANTERIOR; this repo needs its
   own identity (product name, that `00-reference-web-to-replicate/` is gone,
   demo-reset rules).

## Step 1 — Decisions only you can make (blocks copy and domain)

| Decision | Options | Recommendation |
|---|---|---|
| Product / brand name | Czech descriptive (`kurzyweb`, `rezervacekurzu`) vs. coined name | **Decided: business brand "Roman Solutions"**; the product is described, not named (working label: "Web pro kurzy"). |
| Domain layout | `brand.cz` (marketing) + `demo.brand.cz` (live demo) | **Decided 18 Sep: `romansolutions.cz`** (umbrella business site, this product as the flagship offer) + **`demo.romansolutions.cz`** for the live engine. Still built locally first: marketing at `http://127.0.0.1:8080`, demo at `:5000`. `anteriorcourses.com` is a separate business and is never touched. |
| Language | CZ only vs. CZ + EN | CZ first. Target is Czech lecturers/clinics; EN later only if leads come |
| Business model | bespoke build (fixed price) vs. SaaS subscription | Bespoke, fixed price. The Paudent offer already defines it: variant A (QR transfer) 45 000 Kč, variant B (+Stripe) 53 000 Kč, provoz 800–1 200 Kč/měsíc. Reuse verbatim; do not invent a third tier |
| Show prices publicly? | yes / "od 45 000 Kč" / on request | **Decided: on request.** The page explains the two variants (převod s QR / + platební brána) and the provoz model without numbers; CTA "Poptat nabídku". Numbers stay in `docs/nabidka-paudent-whatsapp.md` as the internal price list |
| ANTERIOR as reference | named case study with screenshots vs. anonymous "kurzy pro zubní lékaře" | Ask the two dentists for written consent. Fallback: anonymous. Never screenshot production (participant data, confidential second book) |
| Lead capture | WhatsApp/phone/e-mail CTA vs. form | Start with direct CTAs (WhatsApp deep link, `mailto:`, phone). Add a form later if needed |
| Analytics | GA4 vs. Plausible/Umami | Plausible or self-hosted Umami: no cookie banner needed in CZ, matches the "GDPR-clean" pitch |

## Step 2 — Architecture

Two deliverables, two deployments, one repo:

```
X45_eventBookingSystem/
├── app/                 # the engine (de-branded ANTERIOR) → demo.brand.cz
├── marketing/           # static site → brand.cz
│   ├── index.html
│   ├── css/  (tokens + partials, same @import?v= pattern as app/static/css)
│   ├── img/  (screenshots, OG image, logo)
│   └── robots.txt, sitemap.xml
└── scripts/deploy.sh    # extend: --site demo | --site marketing
```

Why static for marketing: no forms, no DB, no Python process, nothing to break
while you sell. nginx `root` + certbot, done. If a lead form is ever needed, it
becomes one small Flask route reusing `app/services/antispam.py`, not a third
app.

Why the demo is the real engine: the strongest sales argument is "click here,
register for a fake course, watch the confirmation e-mail and QR payment arrive".
Screenshots come from the demo, not from a client.

## Step 3 — De-brand the engine into a demo — DONE 18 Sep (3.5 screenshots pending)

Done: env-driven `app/branding.py` (fictional Studio Lumen defaults), books /
nature / preview routes and assets removed, GA + Cloudflare trackers removed,
`seed-events` rewritten (3 courses, 6 registrations, `--reset` for nightly
reset), `DEMO_MODE` (`app/demo.py` guard, banners, public email preview
route), favicon/OG generated from the brand name, 123 tests green.
Open: engine public copy is **English** (inherited from ANTERIOR). Czech
prospects will see an EN demo. Decide: keep EN + sell CZ localisation as an
add-on, or localise the engine (templates + emails, ~2 days) before launch.
Screenshots blocked this session (Chrome DevTools MCP profile in use) — take
them from http://127.0.0.1:5000 with the dev server running outside the sandbox.


1. **Branding from config.** `app/branding.py` is already the single source;
   make its constants read env vars with ANTERIOR-neutral defaults. Move
   `INSTAGRAM_*`, `AUTHORS`, `EMAIL_SIGNATURE` behind it.
2. **Remove ANTERIOR-only surfaces:** `/books` + inquiry + notify list
   (confidential second book lives here — must not exist in a public demo),
   `/nature-teaches-us`, `about.html` copy, `_flag_cz.html` if brand-specific,
   the hardcoded GA tag in `base.html` (make it config-driven; delete the
   unused `GA4_ID` confusion at the same time). Keep the tests that survive;
   delete `test_second_book_not_leaked` with the feature.
3. **Seed a demo catalogue.** Rewrite `seed-events` with three fictional
   courses that show range, not dentistry: a two-day workshop with waitlist
   nearly full, a course with timed registration opening (countdown visible), a
   free webinar. Use fake lecturers and fake bank account / IBAN that pass the
   validators in `app/services/payment_qr.py`.
4. **Demo safety:**
   - Stripe in test mode only (`STRIPE_SECRET_KEY` = `sk_test_…`); show test
     card `4242…` on the demo page.
   - SMTP: send to a catch-all demo mailbox, or better, add an "e-mail preview"
     route so visitors see the confirmation/payment e-mail rendered in-browser
     without receiving anything. The admin preview endpoints already render
     the same templates; expose a read-only public variant.
   - Nightly DB reset: cron on the VM restores a snapshot (`pg_restore`) and
     re-runs the seed. Add a banner "Demo se každou noc maže".
   - Demo admin login `demo@…` with a `DEMO_MODE` flag that blocks destructive
     admin actions (delete users, change SMTP settings, change password) and
     rate-limits registrations harder than production.
5. **Screenshots** (after 3 and 4): public course page (dark), admin
   registration list (light), Manage panel with the payment section, the
   payment e-mail with both QR codes, the countdown. Take them with the Chrome
   DevTools MCP at fixed viewport 1440×900 and 390×844 so they stay consistent.

## Step 4 — Marketing copy — DRAFT v1 in `marketing/copy.md` (18 Sep), review before build

Draft in `marketing/copy.md`, review, then build. Sections, in order:

1. **Hero** — headline: „Web pro vaše kurzy, který sám vybírá přihlášky, hlídá
   kapacitu a inkasuje platby." Sub: for lektory, ordinace, školicí firmy.
   Two CTAs: *Vyzkoušet demo* (primary) and *Nezávazně poptat* (WhatsApp).
2. **Problém** — the current workflow they recognise: e-mail + Excel + bankovní
   výpis, ruční párování plateb, "je ještě místo?" phone calls.
3. **Jak to funguje** — three steps with screenshots: účastník se přihlásí →
   přijde potvrzení + QR platba → vy vidíte zaplaceno v administraci.
4. **Co všechno umí** — the five pillars from your positioning, one card each:
   prodejní stránky kurzů; rezervace (kapacita, čekací listina, časované
   otevření); platby (karta, převod s QR, párování VS, zaplaceno/nezaplaceno);
   komunikace (potvrzení, platební údaje, připomínka, hromadné zprávy);
   administrace (export, audit, GDPR archiv smazaných registrací).
5. **Proč ne Eventbrite / SimplyBook / Reservio** — comparison table: provize
   z lístku (0 % vs. 3–7 %), vlastní doména, platba přímo na váš účet, QR
   platba + variabilní symbol, data v EU, žádná měsíční licence za funkce.
   Verify each competitor's current fee before publishing.
6. **Reference** — ANTERIOR (pending consent) with one sentence and a link;
   otherwise the anonymised version.
7. **Jak spolupráce probíhá** (replaces a price table) — two variants
   described in words (převod s QR / + karta online), provoz as "hosting,
   údržba, zálohy, monitoring, měsíční report", timeline "spuštění do 4–6 týdnů
   od dodání podkladů", then what the client supplies (kurzy, texty, fotky,
   logo, doména) — list from `docs/nabidka-paudent-whatsapp.md`, message 2.
   Single CTA: „Poptat nezávaznou nabídku". No numbers on the page.
8. **Co se dá přikoupit** — the add-on list from the same offer (připomínky,
   certifikáty PDF, slevové kódy, EN verze…). Honest split: which exist today
   vs. built on order.
9. **FAQ** — Kdo vlastní web a data? Co když chci změnit texty sám? Jak dlouho
   to trvá? Co když Stripe nechci? Co se stane, když přestanu platit provoz?
10. **O mně** — who builds it, one paragraph, photo, IČO in the footer.
11. **Footer** — contact, GDPR/zásady, odkaz na demo.

SEO targets (title/H1/meta): „rezervační systém pro kurzy", „registrace na kurz
s online platbou", „web pro školení a workshopy", „prodej vstupenek bez
provize".

## Step 5 — Build the page

- Static HTML + CSS, no framework, no build step; one JS file for the smooth
  scroll and the WhatsApp link. Light theme (B2B, prints well, contrasts with
  the dark demo screenshots).
- New design tokens, not ANTERIOR's (`#29ABE2` is the client's brand). Reuse the
  partial/`@import ?v=` structure from `app/static/css/style.css` because the
  same nginx 30-day cache rule will apply.
- Responsive at 390 px, Lighthouse ≥ 95 on all four scores, OG image 1200×630,
  `<link rel="canonical">`, JSON-LD `Service` + `Organization`.
- Use the `frontend-design` skill for the visual pass so it does not look like
  a template.

## Step 6 — Deploy and launch (deferred until domain is chosen)

1. DNS: `romansolutions.cz`, `www`, `demo` → `20.215.209.250`.
2. nginx: two server blocks (static root; gunicorn socket for demo), certbot
   for both. Follow the multi-site pattern in `DEPLOYMENT.md`.
3. Extend `scripts/deploy.sh` with a `--site` switch; marketing deploy is rsync
   only, no service restart.
4. Smoke: register on the demo from a phone, check the e-mail preview, check
   admin shows the row, wait for the nightly reset.
5. Google Search Console + sitemap, Firmy.cz listing, Plausible goal on the
   two CTAs.
6. First outreach: send the page to the Paudent lead as the follow-up to the
   offer already sent on 9 Sep.

## Order and rough effort

| # | Work | Depends on | Effort |
|---|---|---|---|
| 0 | Repo hygiene | — | 0.5 h |
| 1 | Decisions | — | your call |
| 3 | De-brand + demo safety + seed | 0 | 2–3 days |
| 4 | Copy | 1 | 1 day, can run parallel with 3 |
| 3.5 | Screenshots | 3 | 0.5 day |
| 5 | Build page | 4, 3.5 | 1–2 days |
| 6 | Deploy + launch | domain chosen, 5 | 0.5 day (deferred) |

Total: roughly one working week after decisions, with the demo de-branding as
the only piece that carries technical risk (tests currently assume ANTERIOR
content; expect ~18 test files to need edits).

## Not in scope (deliberately)

- Multi-tenant SaaS, self-service signup, per-client billing — the model is
  bespoke builds; revisit only after three paying clients.
- EN version of the marketing page.
- Lead-capture form with backend — direct CTAs first.
