# GVK – Gullsmed Verksted & Kundekontroll

Multi-tenant SaaS for gullsmeder, basert på prosjektplanen.

## Stack
- **Backend**: FastAPI (Python 3.12), SQLAlchemy 2, PostgreSQL, Redis, JWT-auth.
- **Frontend**: React 18 + TypeScript + Vite + TailwindCSS + React Query + React Router.
- **Multi-tenancy**: `tenant_id` på alle ressurser; auth-token bærer `tid` claim.
- **Deploy**: Docker Compose + Nginx reverse proxy.

## Komme i gang (lokalt med Docker)

```powershell
# 1. (Valgfritt) Kopier .env.example til .env og rediger SECRET_KEY etc.
# 2. Bygg og start alt
docker compose up --build
```

Tjenester:
- Frontend:   http://localhost:5173
- Backend:    http://localhost:8000  (Swagger: http://localhost:8000/docs)
- Postgres:   localhost:5432
- Redis:      localhost:6379

## Innlogging (seedet ved første oppstart)
- E-post: `jon.sigurdarson@advania.no`
- Passord: `changeme123`
- Rolle: `admin`, tenant: **Advania Demo**

> Endre passord straks i produksjon. Verdiene styres via `.env` (`SEED_ADMIN_*`, `SEED_TENANT_*`).

## Implementerte funksjoner
- **Auth**: login, JWT, `/auth/me`, rollesjekk (admin/seller/goldsmith).
- **Kunder**: opprett, søk, list (med Susoft-ID-felt klart for integrasjon).
- **Lokasjoner**: hierarkiske (Skap → Hylle → Boks), QR-token per lokasjon.
- **Jobber**: opprett med metall/stein/vekt/tilstand/pris, autogenerert jobbnummer + 6-sifret hentekode + QR-token.
- **Statusflyt**: `registered → in_transit → awaiting → in_progress → waiting_parts → done → delivered` (kan også cancelles).
- **Audit-logg**: automatisk på status-, lokasjon- og bilde-endringer (hvem/hva/når).
- **Bildeopplastning**: per jobb, lagres under `/uploads/{tenant}/{job}/...`, eksponert via `/uploads/...`.
- **QR-skanning**: `POST /api/jobs/{id}/scan` flytter en jobb til lokasjon basert på lokasjons-QR-token.
- **Dashboard-oppsummering**: jobber per status, totaler.

## Arkitektur (mappestruktur)
```
backend/
  app/
    main.py            FastAPI-init, CORS, statiske /uploads, startup-seed
    config.py          Pydantic settings (.env)
    database.py        SQLAlchemy engine + Base + get_db()
    models.py          Tenant, User, Customer, Location, Job, JobImage, JobLog
    schemas.py         Pydantic I/O-modeller
    security.py        bcrypt + JWT, get_current_user, require_admin
    seed.py            Lager Base.metadata + seed admin/tenant
    utils.py           job-nr, hentekode, QR-token
    routers/
      auth.py          POST /auth/login, GET /auth/me
      customers.py     CRUD + søk
      locations.py     hierarki + QR
      jobs.py          CRUD + bilder + scan + audit
      dashboard.py     /dashboard/summary
frontend/
  src/
    api.ts             axios + token-interceptor
    auth.tsx           AuthProvider/useAuth
    App.tsx            Routes
    components/Layout.tsx
    pages/Login,Dashboard,Customers,Jobs,JobDetail,NewJob,Locations
docker-compose.yml
.env / .env.example
nginx/gvk.conf.example
```

## Susoft-integrasjon (TODO – stubbet)
Settings finnes i `app/config.py` (`SUSOFT_BASE_URL`, `SUSOFT_API_KEY`).
Planlagte endepunkter (jf. prosjektplan):
- `GET /customers` → opprett synk-job som henter kundedata.
- `POST /orders/park` ved status = `done`.
- `PUT /inventory/move` ved lokasjon-endring.

Forslag: opprett `backend/app/integrations/susoft.py` som httpx-klient + Redis-caching.

## Sikkerhet (jf. prosjektplan §5)
- Passord hashes med bcrypt.
- JWT med 8-timers gyldighet (justerbart via `ACCESS_TOKEN_EXPIRE_MINUTES`).
- Multi-tenant isolasjon: hver query filtrerer på `tenant_id` fra JWT.
- Bildeopplastning validerer MIME-type (`jpeg/png/webp`).
- CORS er åpen i `development`; lukkes automatisk i `production` – legg til whitelisten i `main.py`.
- TODO før produksjon:
  - 2FA (TOTP) – `users.totp_secret`-felt finnes allerede.
  - Bytt `SECRET_KEY` til ekte random verdi.
  - Steng PostgreSQL-port (fjern port-mapping i `docker-compose.yml`).
  - Sett opp Backblaze/S3 backup av `postgres_data` og `uploads`-volume.

## Produksjon (Linux-server)
1. `git clone` på serveren, opprett `.env` med ekte verdier.
2. `docker compose up -d --build`.
3. Kopier `nginx/gvk.conf.example` til `/etc/nginx/sites-available/gvk`, rediger domene, symlink til `sites-enabled`.
4. `sudo certbot --nginx -d gvk.dittdomene.no`.
5. UFW: `sudo ufw allow 22,80,443/tcp && sudo ufw enable`.

## Neste steg (forslag)
- Susoft API-klient og synkronisering.
- SMS/E-post-varsler (Twilio / SMTP) ved status-endring.
- 2FA-aktivering for admin/seller/goldsmith.
- Alembic-migrasjoner (nå kjøres `Base.metadata.create_all` ved oppstart – greit for utvikling, ikke for skjemaendringer i prod).
- Endepunkt for QR-PDF-generering (qrcode er allerede i `requirements.txt`).
