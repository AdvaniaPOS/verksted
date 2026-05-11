# Deployment til poshub-server

Pakkeoversikt: nginx på port 80 (det Cloudflare Tunnel peker på i bildet ditt)
serverer SPA og proxer `/api/*` + `/uploads/*` til uvicorn på 127.0.0.1:8000.

```
verksted.poshub.no  ──Cloudflare Tunnel──▶  serverens localhost:80 (nginx)
                                              ├── /              → /opt/gvk/frontend (statisk SPA)
                                              ├── /api/*         → 127.0.0.1:8000 (uvicorn)
                                              └── /uploads/*     → 127.0.0.1:8000
```

## 0. Aller først – sikre serveren

Du delte passordet i klartekst, så *gjør dette nå*:

```bash
ssh poshubadmin@192.168.163.20
passwd                                           # bytt passord
mkdir -p ~/.ssh && chmod 700 ~/.ssh
echo "ssh-ed25519 AAAA... din@maskin" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
sudo sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo systemctl reload ssh
```

(Generer ssh-nøkkel lokalt med `ssh-keygen -t ed25519` og kopiér `~/.ssh/id_ed25519.pub`-innholdet inn over.)

## 1. Push kode til serveren (fra din Windows-maskin)

```powershell
.\deploy\push-to-server.ps1
```

Det legger kildekoden i `/opt/gvk/_src` og deploy-skriptene i `/opt/gvk/_deploy`.

## 2. Førstegangs oppsett (på serveren – kun én gang)

```bash
ssh poshubadmin@192.168.163.20
sudo bash /opt/gvk/_src/deploy/server-setup.sh
```

Det gjør:
- installerer python3, nginx, ufw, fail2ban
- oppretter system-bruker `gvk` (ingen shell-tilgang)
- åpner UFW kun for SSH (Cloudflare Tunnel går *utgående*, trenger ingen åpne porter inn)
- legger inn nginx-config + systemd-unit

## 3. Lag .env for backend

```bash
sudo cp /opt/gvk/_deploy/.env.production.example /opt/gvk/backend/.env
sudo nano /opt/gvk/backend/.env

# Generer nøklene:
python3 -c "import secrets; print(secrets.token_urlsafe(48))"            # → SECRET_KEY
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"  # → ENCRYPTION_KEY

sudo chmod 600 /opt/gvk/backend/.env
sudo chown gvk:gvk /opt/gvk/backend/.env
```

## 4. Deploy

```bash
sudo bash /opt/gvk/_src/deploy/deploy.sh
```

Bygger venv, installerer requirements, bygger frontend, restarter `gvk-backend`,
reloader nginx. Verifiser:

```bash
curl -i http://127.0.0.1/api/health
sudo journalctl -u gvk-backend -f
```

Deretter åpne `https://verksted.poshub.no` i nettleseren — Cloudflare Tunnel ruter
det rett til serverens nginx på port 80.

## 5. Cloudflare Tunnel

I bildet ditt er det allerede satt opp. Hvis ikke:

```bash
# Installer cloudflared
curl -L https://pkg.cloudflare.com/install.sh | sudo bash
sudo apt-get install -y cloudflared

# Logg inn og opprett tunnel
cloudflared tunnel login
cloudflared tunnel create poshub
# (kopiér Tunnel ID + json-credential)

sudo cloudflared service install <TUNNEL_TOKEN>
sudo systemctl enable --now cloudflared
```

I Cloudflare-dashbordet (det skjermbildet du sendte): peker `verksted.poshub.no`
til `http://localhost:80` — som er nøyaktig det vi har satt opp.

## 6. Påfølgende oppdateringer

Lokalt:
```powershell
.\deploy\push-to-server.ps1
```
På serveren:
```bash
sudo bash /opt/gvk/_src/deploy/deploy.sh
```

## 7. Sikkerhets-sjekkliste etter første deploy

- [ ] SSH passord-login er **av** (`PasswordAuthentication no`)
- [ ] UFW: bare port 22 åpen (`sudo ufw status`)
- [ ] `SECRET_KEY` er ≥ 32 tegn og **ikke** "change_me" (ellers nekter backend å starte)
- [ ] `ENCRYPTION_KEY` (Fernet) er en gyldig 44-tegn nøkkel
- [ ] `.env` har `chmod 600` og eier `gvk:gvk`
- [ ] Du har logget inn én gang og ser "Super-admin" i sidemenyen (`SEED_SUPERADMIN_EMAIL` virket)
- [ ] Bytt admin-passord ved første innlogging
- [ ] Aktivér Cloudflare WAF-regel: blokkér land/bots du ikke trenger
- [ ] Sett opp ukentlig backup av `/opt/gvk/backend/gvk.db` (eller bytt til Postgres med pg_dump-cron)

## 8. Rull tilbake hvis noe ryker

```bash
sudo systemctl status gvk-backend
sudo journalctl -u gvk-backend -n 100
# Forrige versjon ligger i git – bare push på nytt med tidligere kode.
```
