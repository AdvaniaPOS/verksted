#!/usr/bin/env bash
# Førstegangs-oppsett på Ubuntu/Debian server.
# TRYGT å kjøre når serveren allerede har andre apper – vi installerer
# bare det som mangler, og rører IKKE eksisterende nginx-vhosts/UFW-regler.
#
#   sudo bash deploy/server-setup.sh

set -euo pipefail

APP_DIR=/opt/gvk

echo "[1/5] Påse at nødvendige pakker er installert (uten å re-installere)"
NEEDED=(python3 python3-venv python3-pip)
MISSING=()
for p in "${NEEDED[@]}"; do
  dpkg -s "$p" >/dev/null 2>&1 || MISSING+=("$p")
done
if [ ${#MISSING[@]} -gt 0 ]; then
  apt-get update
  apt-get install -y "${MISSING[@]}"
else
  echo "  alt på plass"
fi

echo "[2/5] Egen systembruker 'gvk' (hvis ikke finnes fra før)"
if ! id -u gvk >/dev/null 2>&1; then
  useradd --system --create-home --home-dir /var/lib/gvk --shell /usr/sbin/nologin gvk
else
  echo "  finnes allerede"
fi

echo "[3/5] Mappestruktur under $APP_DIR"
mkdir -p $APP_DIR/backend $APP_DIR/frontend $APP_DIR/backend/uploads
chown -R gvk:gvk $APP_DIR/backend $APP_DIR/frontend

echo "[4/5] Nginx vhost for verksted.poshub.no (rører IKKE bakeri/default/tagly)"
if ! command -v nginx >/dev/null 2>&1; then
  echo "  FEIL: nginx er ikke installert. Avbryter for å ikke ødelegge noe."
  exit 1
fi
cp /opt/gvk/_deploy/nginx-verksted.conf /etc/nginx/sites-available/verksted
ln -sf /etc/nginx/sites-available/verksted /etc/nginx/sites-enabled/verksted
nginx -t
systemctl reload nginx

echo "[5/5] systemd-unit"
cp /opt/gvk/_deploy/gvk-backend.service /etc/systemd/system/gvk-backend.service
systemctl daemon-reload
systemctl enable gvk-backend

echo
echo "FERDIG. Neste steg:"
echo "  1) sudo cp /opt/gvk/_deploy/.env.production.example /opt/gvk/backend/.env"
echo "     sudo nano /opt/gvk/backend/.env   # fyll inn SECRET_KEY + ENCRYPTION_KEY"
echo "       SECRET_KEY    : python3 -c \"import secrets; print(secrets.token_urlsafe(48))\""
echo "       ENCRYPTION_KEY: python3 -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
echo "  2) sudo chmod 600 /opt/gvk/backend/.env && sudo chown gvk:gvk /opt/gvk/backend/.env"
echo "  3) sudo bash /opt/gvk/_src/deploy/deploy.sh   # bygger venv + frontend, starter tjenesten"
echo "  4) I Cloudflare-dashbordet: sett verksted.poshub.no  →  http://localhost:80  (Host: verksted.poshub.no)"

