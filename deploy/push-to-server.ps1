## Push lokal kildekode → server via SCP/rsync (Windows / PowerShell)
##
## Forutsetning: ssh-nøkkel er satt opp (se README.deploy.md for hvordan).
##
##   ./deploy/push-to-server.ps1
##
## Kjører rsync hvis tilgjengelig (WSL / Git-Bash), ellers scp.

$ErrorActionPreference = "Stop"
$Server = "poshubadmin@192.168.163.20"
$Remote = "/opt/gvk/_src"

Write-Host "→ Lager fjern-mappe $Remote (sudo)" -ForegroundColor Cyan
ssh $Server "sudo mkdir -p $Remote && sudo chown -R `$USER $Remote"

# Foretrekk rsync hvis tilgjengelig
$rsync = Get-Command rsync -ErrorAction SilentlyContinue
if ($rsync) {
    Write-Host "→ Synkroniserer med rsync" -ForegroundColor Cyan
    rsync -avz --delete `
        --exclude='.git/' --exclude='node_modules/' `
        --exclude='backend/.venv/' --exclude='backend/__pycache__/' `
        --exclude='backend/uploads/' --exclude='backend/*.db' `
        --exclude='frontend/dist/' --exclude='frontend/node_modules/' `
        ./ "${Server}:${Remote}/"
} else {
    Write-Host "→ rsync ikke funnet – bruker scp + tar" -ForegroundColor Yellow
    $tmp = "$env:TEMP\gvk-deploy.tgz"
    tar --exclude=".git" --exclude="node_modules" --exclude="backend/.venv" `
        --exclude="backend/__pycache__" --exclude="backend/uploads" `
        --exclude="backend/*.db" --exclude="frontend/dist" --exclude="frontend/node_modules" `
        -czf $tmp .
    scp $tmp "${Server}:/tmp/gvk-deploy.tgz"
    ssh $Server "sudo rm -rf $Remote && sudo mkdir -p $Remote && sudo tar -xzf /tmp/gvk-deploy.tgz -C $Remote && sudo chown -R `$USER $Remote && rm /tmp/gvk-deploy.tgz"
    Remove-Item $tmp
}

# Speile deploy/-mappa til /opt/gvk/_deploy så server-setup.sh finner den
ssh $Server "sudo mkdir -p /opt/gvk/_deploy && sudo cp $Remote/deploy/* /opt/gvk/_deploy/"

Write-Host "✔ Kildekode pushet. Kjør på serveren:" -ForegroundColor Green
Write-Host "    sudo bash $Remote/deploy/server-setup.sh   # første gang"
Write-Host "    sudo bash $Remote/deploy/deploy.sh         # hver utrulling"
