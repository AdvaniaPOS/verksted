# Engangs-oppsett for lokal utvikling (Windows / PowerShell)
# Kjør: .\scripts\setup-local.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Write-Host "==> Backend: oppretter venv og installerer pakker" -ForegroundColor Cyan
Push-Location "$root\backend"
if (-not (Test-Path ".venv")) {
    py -3 -m venv .venv
}
& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt
Pop-Location

Write-Host "==> Frontend: npm install" -ForegroundColor Cyan
Push-Location "$root\frontend"
npm install
Pop-Location

Write-Host ""
Write-Host "Ferdig. Start tjenestene med:" -ForegroundColor Green
Write-Host "  .\scripts\run-backend.ps1     (i ett terminalvindu)"
Write-Host "  .\scripts\run-frontend.ps1    (i et annet terminalvindu)"
Write-Host ""
Write-Host "Logg inn: jon.sigurdarson@advania.no / changeme123"
