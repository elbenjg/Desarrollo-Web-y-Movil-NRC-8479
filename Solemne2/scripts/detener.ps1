# Detiene todos los procesos iniciados por iniciar.ps1 (incluye los procesos hijos de "py").
$runtime = Join-Path (Split-Path -Parent $PSScriptRoot) ".runtime"
if (-not (Test-Path "$runtime\pids.txt")) { Write-Host "No hay servicios iniciados."; exit 0 }
foreach ($id in Get-Content "$runtime\pids.txt") {
    if ($id) { taskkill /T /F /PID $id *> $null }
}
Remove-Item "$runtime\pids.txt", "$runtime\vault-token" -ErrorAction SilentlyContinue
Write-Host "Servicios detenidos."
