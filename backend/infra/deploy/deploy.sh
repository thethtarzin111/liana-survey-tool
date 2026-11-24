#!/usr/bin/env bash
# Installs one release on the demo server. Run as the `liana` user by the
# "Deploy demo" GitHub workflow, from inside the unpacked release:
#
#   bash backend/infra/deploy/deploy.sh
#
# Installs the Python packages, applies new migrations (and the demo data),
# switches `current` to this release, restarts the app and checks it answers.
# If the check fails, it switches back to the previous release.
set -euo pipefail

APP_DIR=/opt/lianasurvey
CONF_DIR=/etc/lianasurvey
RELEASE="$(pwd)"
# Each release has its own Python environment, so going back really goes back.
VENV="$RELEASE/.venv"

[[ -f "$RELEASE/frontend/dist/index.html" ]] || { echo "No built frontend in $RELEASE" >&2; exit 1; }

echo "== Python packages"
python3.12 -m venv "$VENV"
"$VENV/bin/python" -m pip install --quiet --upgrade pip
"$VENV/bin/python" -m pip install --quiet \
  "./backend/packages/shared-py[web]" \
  ./backend/services/survey-manager \
  ./backend/services/respondent \
  ./backend/services/data-analyzer \
  ./backend/services/worker \
  ./backend/services/liana-connector

echo "== Database"
set -a
# shellcheck source=/dev/null
. "$CONF_DIR/owner.env"
set +a
"$VENV/bin/python" -m backend.scripts.prepare_db

echo "== Release settings"
# Defaults for settings that servers set up before they existed do not have in
# app.env. The app reads .env from its working directory (this release); app.env
# still wins for anything it sets. No secrets here.
# LianaAutomation: each organisation's own connection from the Integrations page
# (nothing is sent until an admin connects one), instead of the log-only mock.
printf 'LIANA_ADAPTER=lianaautomation\n' > "$RELEASE/.env"

echo "== Switch to this release"
previous="$(readlink -f "$APP_DIR/current" 2>/dev/null || true)"
ln -sfn "$RELEASE" "$APP_DIR/current.new"
mv -T "$APP_DIR/current.new" "$APP_DIR/current"
sudo /usr/bin/systemctl restart lianasurvey

healthy=false
for _ in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8000/health/ready >/dev/null 2>&1; then
    healthy=true
    break
  fi
  sleep 2
done
if [[ $healthy != true ]]; then
  echo "The new release did not start." >&2
  if [[ -n "$previous" && "$previous" != "$RELEASE" ]]; then
    echo "Going back to $previous" >&2
    ln -sfn "$previous" "$APP_DIR/current.new"
    mv -T "$APP_DIR/current.new" "$APP_DIR/current"
    sudo /usr/bin/systemctl restart lianasurvey
  fi
  exit 1
fi

echo "== Keep the last 3 releases"
ls -1dt "$APP_DIR"/releases/*/ | tail -n +4 | xargs -r rm -rf

echo "Deployed $(basename "$RELEASE")."
