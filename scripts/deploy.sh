#!/usr/bin/env bash
#
# Deploy ANTERIOR from this workstation to the production VM.
# Local is the source of truth; GitHub is only an off-site backup.
#
# Pipeline: Mac  --rsync-->  ~/anterior-staging (server)  --sudo rsync-->  /var/www/anterior/app
# then (server-side) migrate + restart ONLY when needed, and verify.
#
# Usage:
#   scripts/deploy.sh              deploy (asks to confirm before touching prod)
#   scripts/deploy.sh --dry-run    show what WOULD change, deploy nothing
#   scripts/deploy.sh --yes        skip the confirmation prompt
#   scripts/deploy.sh --help       this help
#
set -euo pipefail

# ---------- config (local side) ----------
SERVER="mfonic@20.215.209.250"
SSH_KEY="nono/mddr_key.pem"
STAGING="anterior-staging"                 # directory in mfonic's home on the server
DOMAIN="https://anteriorcourses.com"
ASSET_CHECK="/static/img/logo-eae.png"     # a static file that must be world-readable (403 canary)

# ---------- args ----------
DRY_RUN=0; ASSUME_YES=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    -y|--yes)  ASSUME_YES=1 ;;
    -h|--help) awk 'NR==1{next} /^set /{exit} /^#/{sub(/^# ?/,"");print}' "$0"; exit 0 ;;
    *) echo "Unknown option: $arg (try --help)" >&2; exit 2 ;;
  esac
done

# ---------- pretty logging ----------
if [ -t 1 ]; then
  B=$'\033[1m'; R=$'\033[0m'; G=$'\033[32m'; Y=$'\033[33m'; C=$'\033[36m'; RD=$'\033[31m'
else B=""; R=""; G=""; Y=""; C=""; RD=""; fi
step(){ printf '\n%s==> %s%s\n' "$C$B" "$*" "$R"; }
ok(){   printf '%s    ok  %s%s\n' "$G" "$*" "$R"; }
warn(){ printf '%s    !   %s%s\n' "$Y" "$*" "$R"; }
die(){  printf '%s    x   %s%s\n' "$RD$B" "$*" "$R" >&2; exit 1; }
trap 'die "deploy aborted (line $LINENO)"' ERR

# resolve project root (parent of scripts/) regardless of where we're called from
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SSH="ssh -i $SSH_KEY -o ConnectTimeout=10"

MAC_EXCLUDES=(
  --exclude '.git/' --exclude '.venv/' --exclude '__pycache__/' --exclude '*.pyc'
  --exclude '.pytest_cache/' --exclude '.DS_Store' --exclude '.env'
  --exclude '.claude/' --exclude 'instance/' --exclude 'nono/'
  --exclude '00-reference-web-to-replicate/' --exclude 'design-proposals/'
  --exclude 'logo-anterior*.ai' --exclude 'logo-anterior-2.png'
  --exclude 'avenir-next-ultra-light.ttf'
)

# ---------- 1. local preflight ----------
step "Local preflight"
[ -f wsgi.py ] && [ -f requirements.txt ] || die "not in project root ($ROOT)"
[ -f "$SSH_KEY" ] || die "SSH key not found: $SSH_KEY"
# guard the static-perms 403 class of bug: rsync -a preserves modes, nginx serves as www-data
BAD=$(find app/static -type f ! -perm -o+r 2>/dev/null || true)
if [ -n "$BAD" ]; then
  warn "static files not world-readable (would 403 via nginx) — fixing to 644:"
  printf '        %s\n' $BAD
  chmod 644 $BAD
fi
ok "project root, ssh key, static perms"

# ---------- 2. connectivity + remote preflight ----------
step "Connecting to $SERVER"
$SSH "$SERVER" 'echo ok' >/dev/null || die "cannot SSH to $SERVER (check $SSH_KEY / network)"
$SSH "$SERVER" 'systemctl cat anterior >/dev/null 2>&1' || die "anterior.service not found on server"
$SSH "$SERVER" 'test -d /var/www/anterior/app'          || die "/var/www/anterior/app missing on server"
BEFORE=$($SSH "$SERVER" 'systemctl is-active anterior' || true)
ok "reachable — anterior currently: ${BEFORE:-unknown}"

# ---------- 3. dry run OR push to staging ----------
if [ "$DRY_RUN" -eq 1 ]; then
  step "Dry run — changes that WOULD sync to staging"
  OUT=$(rsync -azn -i --delete -e "$SSH" "${MAC_EXCLUDES[@]}" ./ "$SERVER:~/$STAGING/")
  if [ -n "$OUT" ]; then printf '%s\n' "$OUT" | sed 's/^/        /'; else ok "nothing would change"; fi
  ok "dry run complete — production untouched"
  exit 0
fi

# ---------- 3b. stamp deploy info (server has no git checkout) ----------
step "Stamping deploy info (app/deploy_info.json)"
# previously deployed rev, read from the staging copy left by the last deploy
PREV_REV=$($SSH "$SERVER" "sed -nE 's/.*\"rev\": *\"([0-9a-f]+)\\+?\".*/\1/p' ~/$STAGING/app/deploy_info.json 2>/dev/null" || true)
DEPLOY_REV=$(git log -1 --format=%h)
DEPLOY_SUBJECT=$(git log -1 --format=%s)
DEPLOY_DATE=$(git log -1 --format=%cd --date=format:'%d.%m.%Y %H:%M')
DEPLOY_DIRTY=0
[ -n "$(git status --porcelain)" ] && DEPLOY_DIRTY=1
DEPLOY_CHANGES=""
if [ -n "$PREV_REV" ] && [ "$PREV_REV" != "$DEPLOY_REV" ] && git cat-file -e "$PREV_REV" 2>/dev/null; then
  DEPLOY_CHANGES=$(git log --oneline "$PREV_REV..HEAD")
fi
DEPLOY_REV="$DEPLOY_REV" DEPLOY_SUBJECT="$DEPLOY_SUBJECT" DEPLOY_DATE="$DEPLOY_DATE" \
DEPLOY_DIRTY="$DEPLOY_DIRTY" DEPLOY_CHANGES="$DEPLOY_CHANGES" python3 - <<'PY'
import json, os
dirty = os.environ['DEPLOY_DIRTY'] == '1'
info = {
    'rev': os.environ['DEPLOY_REV'] + ('+' if dirty else ''),
    'subject': os.environ['DEPLOY_SUBJECT'] + (' (+ uncommitted changes)' if dirty else ''),
    'date': os.environ['DEPLOY_DATE'],
    'changes': [l for l in os.environ['DEPLOY_CHANGES'].splitlines() if l.strip()],
}
with open('app/deploy_info.json', 'w', encoding='utf-8') as f:
    json.dump(info, f, ensure_ascii=False, indent=2)
PY
if [ -n "$DEPLOY_CHANGES" ]; then
  echo "    Incoming commits (since deployed ${PREV_REV}):"
  printf '%s\n' "$DEPLOY_CHANGES" | sed 's/^/      /'
else
  ok "no commit delta recorded (first stamped deploy, same rev, or unknown previous rev)"
fi
ok "stamped $DEPLOY_REV ($DEPLOY_DATE)"

step "Pushing code -> staging (~/$STAGING)"
OUT=$(rsync -az -i --delete -e "$SSH" "${MAC_EXCLUDES[@]}" ./ "$SERVER:~/$STAGING/")
if [ -n "$OUT" ]; then printf '%s\n' "$OUT" | sed 's/^/        /'; else ok "staging already matched local"; fi
ok "staged"

# ---------- confirmation ----------
if [ "$ASSUME_YES" -ne 1 ]; then
  printf '\n%s    Deploy staged code to PRODUCTION and restart if needed? [y/N] %s' "$B" "$R"
  read -r reply
  [[ "$reply" =~ ^[Yy]$ ]] || die "aborted by user (staging was updated, prod untouched)"
fi

# ---------- 4. server-side deploy (single sudo session) ----------
step "Deploying on server (sudo password may be requested once)"
scp -q -i "$SSH_KEY" scripts/deploy_remote.sh "$SERVER:/tmp/anterior_deploy_remote.sh"
ssh -t -i "$SSH_KEY" "$SERVER" 'bash /tmp/anterior_deploy_remote.sh; rc=$?; rm -f /tmp/anterior_deploy_remote.sh; exit $rc' \
  || die "server-side deploy failed (see output above)"

# ---------- 5. external verification ----------
step "Verifying public site"
code=$(curl -fsS -o /dev/null -w '%{http_code}' "$DOMAIN" || true)
[ "$code" = "200" ] && ok "$DOMAIN -> 200" || die "$DOMAIN returned ${code:-no-response}"
acode=$(curl -fsS -o /dev/null -w '%{http_code}' "$DOMAIN$ASSET_CHECK" || true)
[ "$acode" = "200" ] && ok "asset $ASSET_CHECK -> 200" || warn "asset $ASSET_CHECK returned ${acode:-no-response}"

printf '\n%s==> Deploy complete%s\n' "$G$B" "$R"
