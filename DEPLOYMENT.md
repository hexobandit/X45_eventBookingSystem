# ANTERIOR — Deployment (vm-webapps, 20.215.209.250)

```
ssh -i nono/mddr_key.pem mfonic@20.215.209.250
```

Second/third site on the shared VM that already hosts **erikamcgregor** (and
possibly others). Same multi-site pattern: one PostgreSQL DB + one system user
+ one gunicorn socket + one nginx server block per site.

**Domain: `anteriorcourses.com`** — live. DNS A records (`@` and `www`) point at
`20.215.209.250`, and the site runs over HTTPS: nginx serves the domain and
certbot provides the TLS cert (section 6). Other domain-based sites on the VM
are unaffected — nginx routes each by its own `server_name`.

Already configured on this VM (verify, don't redo): UFW, fail2ban, SSH
hardening, timezone Europe/Prague, `/opt/scripts/backup-db.sh`, logrotate
pattern.

---

## 1. PostgreSQL

```bash
sudo -u postgres psql <<'SQL'
CREATE USER anterior WITH PASSWORD 'CHANGE_ME';
CREATE DATABASE anterior OWNER anterior;
SQL
```

> **Multi-site:** separate DB + user per site. Never share databases.

Test:

```bash
psql -U anterior -d anterior -h localhost
```

---

## 2. Application User & Directory Structure

```bash
sudo useradd -m -s /bin/bash anterior

sudo mkdir -p /var/www/anterior
sudo chown anterior:anterior /var/www/anterior
```

Resulting layout:

```
/var/www/
├── erikamcgregor/       # site 1 (existing)
└── anterior/            # this site
    ├── app/             # app code (rsynced from workstation)
    ├── venv/            # virtualenv (outside the app dir)
    └── anterior.sock
```

---

## 3. Copy the Code (rsync from workstation — no GitHub)

Code ships straight from the local project via rsync over SSH. GitHub stays
nice-to-have; a deploy key + `git clone` can replace this section later.

**Step 1 — from the Mac** (project root), rsync to a staging dir as `mfonic`
(who can't write `/var/www/anterior` directly):

```bash
cd /Users/cryptobandit/Documents/Scripts/X41_anterior

rsync -avz --delete \
  -e "ssh -i nono/mddr_key.pem" \
  --exclude '.git/' \
  --exclude '.venv/' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude '.pytest_cache/' \
  --exclude '.DS_Store' \
  --exclude '.env' \
  --exclude 'instance/' \
  --exclude 'nono/' \
  --exclude '00-reference-web-to-replicate/' \
  --exclude 'design-proposals/' \
  --exclude 'logo-anterior*.ai' \
  --exclude 'logo-anterior-2.png' \
  --exclude 'avenir-next-ultra-light.ttf' \
  ./ mfonic@20.215.209.250:~/anterior-staging/
```

**Step 2 — on the server**, move it into place with the right ownership
(`--exclude`s protect the server-side `.env` and uploaded files from
`--delete` on re-deploys):

```bash
sudo rsync -a --delete \
  --exclude '.env' \
  --exclude 'app/static/uploads/' \
  --chown=anterior:anterior \
  ~/anterior-staging/ /var/www/anterior/app/
```

> **Static assets must be world-readable.** `rsync -a` preserves source file
> modes, and nginx serves `/static/` as `www-data` (not `anterior`). A static
> file that's `600` on the Mac lands as `600` on the server and returns **403**
> — the HTML still loads (it's proxied through gunicorn as `anterior`), so only
> that one asset breaks. `git` won't catch it (it tracks only the executable
> bit). Fix at the source, then normalise on the server to be safe:
>
> ```bash
> # on the Mac — find any non-world-readable static files, then fix
> find app/static -type f ! -perm -o+r
> chmod 644 <those files>
>
> # on the server — idempotent normalise (adds read for all, +x on dirs only)
> sudo chmod -R a+rX /var/www/anterior/app/app/static
> ```

---

## 4. Deploy Application

```bash
sudo su - anterior
cd /var/www/anterior/app

python3 -m venv ../venv
source ../venv/bin/activate
pip install -r requirements.txt
pip install gunicorn psycopg2-binary

# Production .env — HTTPS on the live domain.
# NOTE: the production secure session cookie only works over HTTPS. Finish nginx
# + certbot (section 6) BEFORE testing login — over plain http the cookie is
# never stored and login/forms silently break.
cat > .env <<'EOF'
FLASK_CONFIG=production
SECRET_KEY=PASTE_OUTPUT_OF: python3 -c "import secrets; print(secrets.token_hex(32))"
DATABASE_URL=postgresql://anterior:CHANGE_ME@localhost:5432/anterior
CANONICAL_DOMAIN=https://anteriorcourses.com
GA4_ID=
EOF

# Schema (Alembic migrations — NOT the erikamcgregor init-db/db-upgrade flow)
flask --app wsgi db upgrade

# Admin account
flask --app wsgi create-admin
```

Notes vs the erikamcgregor playbook:

- Config selector is `FLASK_CONFIG` (not `FLASK_ENV`).
- Migrations: `flask --app wsgi db upgrade`. Do **not** run `init-db`
  (drops/creates outside Alembic; migrations own the schema here).
- Do not commit real secrets; `.env` lives only on the server.

---

## 5. Gunicorn (systemd service)

```bash
exit   # back to mfonic
```

```bash
sudo tee /etc/systemd/system/anterior.service <<'EOF'
[Unit]
Description=anterior gunicorn
After=network.target postgresql.service
Requires=postgresql.service

[Service]
User=anterior
Group=anterior
WorkingDirectory=/var/www/anterior/app
ExecStart=/var/www/anterior/venv/bin/gunicorn \
    --workers 1 \
    --bind unix:/var/www/anterior/anterior.sock \
    --access-logfile /var/log/anterior/access.log \
    --error-logfile /var/log/anterior/error.log \
    --timeout 120 \
    wsgi:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo mkdir -p /var/log/anterior
sudo chown anterior:anterior /var/log/anterior

sudo systemctl daemon-reload
sudo systemctl enable --now anterior
```

> `--workers 1` is deliberate: Flask-Limiter uses in-memory storage. Before
> raising workers, set `REDIS_URL` in `.env` so rate limits are shared.

Verify:

```bash
sudo systemctl status anterior
ls -la /var/www/anterior/anterior.sock
```

---

## 6. Nginx + HTTPS (live domain)

DNS already points the domain at the VM — verify before starting:

```bash
dig +short anteriorcourses.com        # → 20.215.209.250
dig +short www.anteriorcourses.com    # → 20.215.209.250
```

**Step 1 — HTTP server block** so certbot can complete the ACME challenge.
Matches by `server_name` (no `default_server` — the existing sites keep that):

```bash
sudo tee /etc/nginx/sites-available/anterior <<'NGINX'
server {
    listen 80;
    server_name anteriorcourses.com www.anteriorcourses.com;

    client_max_body_size 5M;

    access_log /var/log/nginx/anterior.access.log;
    error_log  /var/log/nginx/anterior.error.log;

    location /static/ {
        alias /var/www/anterior/app/app/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location / {
        proxy_pass http://unix:/var/www/anterior/anterior.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }

    location ~ /\. { deny all; }
}
NGINX

sudo ln -sf /etc/nginx/sites-available/anterior /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

**Step 2 — issue the TLS certificate.** certbot auto-edits the block to add the
`:443` server and an http→https redirect:

```bash
sudo certbot --nginx -d anteriorcourses.com -d www.anteriorcourses.com
sudo certbot renew --dry-run
```

**Step 3 — swap in the full production config** (Appendix A: HSTS, www→naked
canonical redirect, static caching). It references the cert certbot just issued,
so it only passes `nginx -t` *after* step 2:

```bash
sudo nano /etc/nginx/sites-available/anterior   # paste Appendix A, save
sudo nginx -t && sudo systemctl reload nginx
```

Verify:

```bash
curl -I https://anteriorcourses.com              # 200, and note HSTS header
curl -I https://www.anteriorcourses.com          # 301 → https://anteriorcourses.com
curl -I http://anteriorcourses.com               # 301 → https://anteriorcourses.com
```

> If `nginx -t` complains about a duplicate `default_server`, another site block
> already owns it — that's fine, this block doesn't need it (it matches by
> `server_name`).

---

## 7. Backups & Log Rotation

```bash
# Daily DB backup — one cron line per database (same script as erikamcgregor)
echo "10 3 * * * root /opt/scripts/backup-db.sh anterior" | sudo tee /etc/cron.d/db-backup-anterior

# Log rotation for gunicorn logs
sudo tee /etc/logrotate.d/anterior <<'EOF'
/var/log/anterior/*.log
{
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 anterior anterior
    sharedscripts
    postrotate
        systemctl reload anterior 2>/dev/null || true
    endscript
}
EOF
```

Also persisted alongside the DB: `app/app/static/uploads/` (event images,
payment QR codes).

---

## 8. Email (SPF/DKIM + SMTP)

So the "notify me" / order-interest confirmations and the admin batch-email
tool deliver reliably rather than landing in spam:

1. Add **SPF** and **DKIM** DNS records for the `@anteriorcourses.com` mailbox
   domain (values come from your mail provider).
2. In `/admin` → **Email Settings**, enter the SMTP details for that mailbox and
   use **Send test email** to confirm delivery.

DNS reference (already in place for the web side):

| Type | Name | Value            |
|------|------|------------------|
| A    | @    | `20.215.209.250` |
| A    | www  | `20.215.209.250` |

---

## 9. Deploy Updates

Deploys go **from this workstation** — local is the source of truth; GitHub is
only an off-site backup. Do **not** use the shared `/opt/scripts/deploy.sh` (it
does `git pull` + erikamcgregor's custom `flask db-upgrade`, neither of which
applies here). Instead use the repo's own script:

```bash
scripts/deploy.sh --dry-run    # preview exactly what would change (touches nothing)
scripts/deploy.sh              # deploy (prompts before touching prod)
scripts/deploy.sh --yes        # deploy without the confirmation prompt
```

What it does, with progress printed at each step:

1. **Local preflight** — verifies project root + SSH key, and auto-fixes any
   static file that isn't world-readable (the `rsync -a` → `600` → nginx 403
   trap from section 3).
2. **Connect & check** — SSHes in, confirms `anterior.service` exists and reports
   its current state.
3. **Stamp deploy info** — the server has no git checkout, so the script writes
   `app/deploy_info.json` from local git (short rev, subject, date, and the
   `git log --oneline` delta since the previously deployed rev, read back from
   the staging copy). Uncommitted local changes are marked with a `+` on the
   rev. The file is gitignored and regenerated every deploy; it feeds the
   deploy email and the version shown at the bottom of the admin sidebar
   (`app/version.py`, which falls back to local git in development).
4. **Push → staging** — `rsync` this tree into `~/anterior-staging` (same
   excludes as section 3, plus `.claude/`), printing the itemized change list.
5. **Deploy on server** (`scripts/deploy_remote.sh`, one sudo session):
   staging → `/var/www/anterior/app` with `--chown=anterior`, then verifies the
   app dir mirrors staging, re-asserts static perms, and — **only when needed** —
   runs `pip install` (if `requirements.txt` changed), backs up the DB + runs
   `flask db upgrade` and restarts the service (if any non-static code changed).
   Pure static/asset changes skip the restart (`deploy_info.json` alone doesn't
   count as a code change).
6. **Deploy email** — after the service checks pass, the VM runs
   `flask --app wsgi send-deploy-email` as the site user: the app itself mails
   the deploy summary (rev + commit list) to the admin address(es) from the
   email settings, doubling as an end-to-end SMTP test. A failure here is a
   WARN, never a deploy failure. Test by hand with
   `flask --app wsgi send-deploy-email --to you@example.com`.
7. **Verify** — checks the service is `active` and the socket exists, then from
   the Mac confirms `https://anteriorcourses.com` → 200 and the canary asset
   loads.

Any failed check aborts with a non-zero exit and a clear message; if the service
fails to come back it dumps the last 20 journal lines.

> Editing the deploy flow? Change `scripts/deploy.sh` (runs on the Mac) and
> `scripts/deploy_remote.sh` (runs on the VM) — keep server paths in sync between
> them.

---

## Quick Reference

```bash
# Status / logs
sudo systemctl status anterior
sudo journalctl -u anterior -f
sudo tail -f /var/log/anterior/error.log
sudo tail -f /var/log/nginx/anterior.error.log

# Restart
sudo systemctl restart anterior

# Nginx
sudo nginx -t && sudo systemctl reload nginx

# DB console
psql -U anterior -d anterior -h localhost
sudo -u postgres psql anterior

# Flask CLI (as site user)
sudo su - anterior
cd /var/www/anterior/app && source ../venv/bin/activate
flask --app wsgi <command>

# Backup now
sudo /opt/scripts/backup-db.sh anterior
```

---

## Checklist

### Application
- [ ] DB + user created (`anterior` / `anterior`)
- [ ] System user + `/var/www/anterior` layout
- [ ] Code rsynced from workstation into `/var/www/anterior/app` (owner `anterior`)
- [ ] venv + deps + `gunicorn psycopg2-binary`
- [ ] `.env` (FLASK_CONFIG, SECRET_KEY, DATABASE_URL,
      CANONICAL_DOMAIN=https://anteriorcourses.com)
- [ ] `flask --app wsgi db upgrade`
- [ ] `flask --app wsgi create-admin`
- [ ] anterior.service enabled + socket exists

### Web
- [ ] DNS `@` + `www` resolve to `20.215.209.250`
- [ ] nginx HTTP block for the domain, reload OK
- [ ] certbot cert issued (`certbot renew --dry-run` passes)
- [ ] Appendix A config in place (HSTS, www→bare redirect), reload OK
- [ ] `https://anteriorcourses.com` serves the site

### Operations
- [ ] Backup cron line added
- [ ] Logrotate entry added

### Smoke Test (production)
- [ ] Homepage loads at `https://anteriorcourses.com`
- [ ] `http://` and `www` both 301 → `https://anteriorcourses.com`
- [ ] Static assets load (CSS, logo, hero photo)
- [ ] `/nature-teaches-us/observe` renders
- [ ] Admin login works at `/admin/`
- [ ] Registration form on the test course works end-to-end
- [ ] SMTP configured via admin + test email sent (or consciously postponed)

---

## Appendix A — Full nginx config once HTTPS exists

Replace `/etc/nginx/sites-available/anterior` with this after certbot has
issued the certificate (domain `anteriorcourses.com`; canonical is the **naked**
domain — matching CANONICAL_DOMAIN in `.env`):

```nginx
# -------------------------------------------------------
# HTTP → HTTPS
# -------------------------------------------------------
server {
    listen 80;
    server_name anteriorcourses.com www.anteriorcourses.com;
    return 301 https://anteriorcourses.com$request_uri;
}

# -------------------------------------------------------
# www → naked domain (canonical)
# -------------------------------------------------------
server {
    listen 443 ssl http2;
    server_name www.anteriorcourses.com;

    ssl_certificate     /etc/letsencrypt/live/anteriorcourses.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/anteriorcourses.com/privkey.pem;

    return 301 https://anteriorcourses.com$request_uri;
}

# -------------------------------------------------------
# Main site — anteriorcourses.com (naked, canonical)
# -------------------------------------------------------
server {
    listen 443 ssl http2;
    server_name anteriorcourses.com;

    ssl_certificate     /etc/letsencrypt/live/anteriorcourses.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/anteriorcourses.com/privkey.pem;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    client_max_body_size 5M;

    access_log /var/log/nginx/anterior.access.log;
    error_log  /var/log/nginx/anterior.error.log;

    # Static files — served directly by nginx
    location /static/ {
        alias /var/www/anterior/app/app/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # App
    location / {
        proxy_pass http://unix:/var/www/anterior/anterior.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }

    # Block dotfiles and .env
    location ~ /\. { deny all; }
}
```
