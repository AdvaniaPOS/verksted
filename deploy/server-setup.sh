#!/usr/bin/env bash
# Førstegangs-oppsett på Ubuntu/Debian server.
# Kjør én gang som root:  sudo bash deploy/server-setup.sh

set -euo pipefail

APP_DIR=/opt/gvk

echo "[1/7] Pakkeinstallasjon"
apt-get update
apt-get install -y python3 python3-venv python3-pip nginx git ufw fail2ban

echo "[2/7] Egen systembruker 'gvk'"
if ! id -u gvk >/dev/null 2>&1; then
  useradd --system --create-home --home-dir /var/lib/gvk --shell /usr/sbin/nologin gvk
fi

echo "[3/7] Mappestruktur"
mkdir -p $APP_DIR/backend $APP_DIR/frontend $APP_DIR/backend/uploads
chown -R gvk:gvk $APP_DIR

echo "[4/7] Brannmur (UFW): kun SSH inn (Cloudflare Tunnel går ut)"
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw --force enable

echo "[5/7] fail2ban for SSH"
systemctl enable --now fail2ban

echo "[6/7] Nginx config"
cp /opt/gvk/_deploy/nginx-verksted.conf /etc/nginx/sites-available/verksted
ln -sf /etc/nginx/sites-available/verksted /etc/nginx/sites-enabled/verksted
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx

echo "[7/7] systemd-unit"
cp /opt/gvk/_deploy/gvk-backend.service /etc/systemd/system/gvk-backend.service
systemctl daemon-reload
systemctl enable gvk-backend

echo
echo "FERDIG. Neste steg:"
echo "  1) Kopiér .env: cp /opt/gvk/_deploy/.env.production.example /opt/gvk/backend/.env"
echo "     redigér og fyll inn SECRET_KEY + ENCRYPTION_KEY (script viser kommandoer)."
echo "  2) chmod 600 /opt/gvk/backend/.env && chown gvk:gvk /opt/gvk/backend/.env"
echo "  3) Kjør deploy/deploy.sh for å bygge venv + frontend og starte tjenesten."
