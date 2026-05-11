#!/usr/bin/env bash
# Bygg venv + npm-build + (re)start backend.
# Kjør på serveren etter at koden er overført til /opt/gvk/_src.
#   sudo bash deploy/deploy.sh

set -euo pipefail

SRC=/opt/gvk/_src
APP=/opt/gvk

echo "[1/5] Sync backend-kode → $APP/backend (uten å overskrive .env / uploads / db)"
rsync -a --delete \
  --exclude='.venv/' --exclude='.env' --exclude='uploads/' --exclude='*.db' --exclude='__pycache__/' \
  "$SRC/backend/" "$APP/backend/"
chown -R gvk:gvk "$APP/backend"

echo "[2/5] Python venv + dependencies"
sudo -u gvk bash -c "
  cd $APP/backend
  python3 -m venv .venv
  .venv/bin/pip install --upgrade pip wheel
  .venv/bin/pip install -r requirements.txt
"

echo "[3/5] Bygg frontend (på dev-maskinen er bedre, men funker også her)"
if command -v npm >/dev/null 2>&1; then
  pushd "$SRC/frontend" >/dev/null
  npm ci
  npm run build
  popd >/dev/null
  rsync -a --delete "$SRC/frontend/dist/" "$APP/frontend/"
else
  echo "  (npm ikke installert – pre-bygg på dev-maskinen og rsync dist/ til $APP/frontend/)"
fi

echo "[4/5] Restart backend"
systemctl restart gvk-backend
systemctl status --no-pager gvk-backend | head -n 10

echo "[5/5] Reload nginx"
nginx -t && systemctl reload nginx

echo "OK – sjekk: curl -i http://127.0.0.1/api/health"
