$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

# Fjern arvet env fra eventuell root-.env (Docker-konfig) som ikke gjelder lokalt
Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
Remove-Item Env:REDIS_URL -ErrorAction SilentlyContinue
Remove-Item Env:UPLOAD_DIR -ErrorAction SilentlyContinue

Push-Location "$root\backend"
& ".\.venv\Scripts\python.exe" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
Pop-Location
