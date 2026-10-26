# One-command clean demo start (Windows PowerShell). Same as scripts/reset-demo.sh.
#   .\scripts\reset-demo.ps1            # Docker (Postgres), offline once images are built
#   .\scripts\reset-demo.ps1 -Build     # rebuild images first
#   .\scripts\reset-demo.ps1 -Local     # local dev (SQLite) using backend\.venv
param([switch]$Build, [switch]$Local)
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

if ($Local) {
    & backend\.venv\Scripts\python.exe seed\seed.py --reset
    Write-Host "Local data reset. Start the backend (uvicorn, port 8000) and the frontend (npm run dev)."
    exit 0
}

docker compose down -v
if ($Build) { docker compose up -d --build } else { docker compose up -d }
Write-Host "Waiting for the backend to seed..."
for ($i = 0; $i -lt 60; $i++) {
    try { Invoke-WebRequest -UseBasicParsing http://localhost:5173/api/health | Out-Null; break } catch { Start-Sleep 3 }
}
Write-Host "Ready: http://localhost:5173  (all demo accounts use password demo1234)"
