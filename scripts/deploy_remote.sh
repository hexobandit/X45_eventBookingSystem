#!/usr/bin/env bash
#
# Runs ON the production VM. Moves staged code into the live app dir, installs
# deps / migrates / restarts ONLY when needed, then verifies. Invoked over SSH
# by scripts/deploy.sh — not meant to be run by hand.
#
set -euo pipefail

APP=/var/www/anterior/app
VENV=/var/www/anterior/venv
SOCKET=/var/www/anterior/anterior.sock
SERVICE=anterior
SITE_USER=anterior
STAGING="$HOME/anterior-staging/"

say(){ printf '        %s\n' "$*"; }

[ -d "$STAGING" ] || { echo "staging dir missing: $STAGING"; exit 1; }

# 1. sync staging -> live app dir, capturing itemized changes
say "Syncing staging -> $APP"
CHANGES=$(sudo rsync -a -i --delete \
  --exclude '.env' --exclude 'app/static/uploads/' \
  --chown="$SITE_USER:$SITE_USER" \
  "$STAGING" "$APP/")
if [ -n "$CHANGES" ]; then printf '%s\n' "$CHANGES" | sed 's/^/          /'; else say "(no file changes)"; fi

# 2. verify the app dir now mirrors staging (dry-run must be empty).
#    Must mirror step-1 flags incl. --chown, else preserved owner/group (mfonic
#    on staging vs anterior in the app dir) shows up as a false pending diff.
PENDING=$(sudo rsync -ain --delete \
  --exclude '.env' --exclude 'app/static/uploads/' \
  --chown="$SITE_USER:$SITE_USER" \
  "$STAGING" "$APP/" | grep -vE '^$' || true)
[ -z "$PENDING" ] && say "verify: app dir in sync" || { echo "VERIFY FAILED, still pending:"; echo "$PENDING"; exit 1; }

# 3. defensive: static assets must stay world-readable (nginx serves as www-data)
sudo chmod -R a+rX "$APP/app/static"

# 4. figure out what actually changed.
#    Count only real FILE changes (itemize 2nd char 'f') and deletions — ignore
#    directory-only entries like ".d..t....... ./" that appear on every run.
FILES=$(printf '%s\n' "$CHANGES" | awk '
  /^\*deleting/       { print $NF; next }
  substr($0,2,1)=="f" { print $NF }
')
# deploy_info.json is restamped every deploy — alone it must not trigger a restart
NONSTATIC=$(printf '%s\n' "$FILES" | grep -vE '^app/static/' | grep -v 'app/deploy_info.json' | grep -vE '^$' || true)
REQS=$(printf '%s\n'      "$FILES" | grep -E 'requirements\.txt' || true)

# 5. dependencies — only if requirements.txt changed
if [ -n "$REQS" ]; then
  say "requirements.txt changed -> pip install"
  sudo -u "$SITE_USER" "$VENV/bin/pip" install -r "$APP/requirements.txt" --quiet
fi

# 6. migrate + restart — only if code (non-static) changed
if [ -n "$NONSTATIC" ]; then
  if [ -x /opt/scripts/backup-db.sh ]; then
    say "DB backup before migrating"
    sudo /opt/scripts/backup-db.sh anterior || say "(backup script returned non-zero; continuing)"
  fi
  say "Applying migrations (flask db upgrade)"
  sudo -u "$SITE_USER" bash -lc "cd $APP && $VENV/bin/flask --app wsgi db upgrade"
  say "Restarting $SERVICE"
  sudo systemctl restart "$SERVICE"
else
  say "Only static/asset changes -> no migrate, no restart needed"
fi

# 7. verify service + socket are healthy
sleep 1
STATE=$(systemctl is-active "$SERVICE" || true)
if [ "$STATE" = "active" ]; then
  say "service: active"
else
  echo "service NOT active: $STATE"; sudo journalctl -u "$SERVICE" -n 20 --no-pager; exit 1
fi
[ -S "$SOCKET" ] && say "socket present" || { echo "socket missing: $SOCKET"; exit 1; }

# 8. deploy notification email through the app's own SMTP stack.
#    Doubles as an end-to-end email test. Failure is a WARN, never a deploy
#    failure — broken SMTP must not fail a finished deploy.
say "Sending deploy notification email"
if sudo -u "$SITE_USER" bash -lc "cd $APP && $VENV/bin/flask --app wsgi send-deploy-email" | sed 's/^/          /'; then
  say "deploy email OK"
else
  say "WARN: deploy email failed — check admin email + SMTP settings in the admin panel"
fi

say "server-side deploy OK"
