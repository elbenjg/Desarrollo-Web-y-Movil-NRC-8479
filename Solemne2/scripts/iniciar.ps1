# Inicia todo el backend de Frío Natural en local (Windows PowerShell 5.1).
# Requisitos: MongoDB corriendo en localhost:27017, Python con requirements.txt, Node.js, Vault.
# Uso: powershell -ExecutionPolicy Bypass -File scripts\iniciar.ps1 [-Reset]
param([switch]$Reset)
$ErrorActionPreference = "Continue"

$raiz = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $raiz "backend"
$runtime = Join-Path $raiz ".runtime"
$vault = if ($env:VAULT_EXE) { $env:VAULT_EXE } else { "C:\Hashicorp\Vault\vault.exe" }
$python = if ($env:PYTHON_EXE) { $env:PYTHON_EXE } else { "py" }
$openssl = if ($env:OPENSSL_EXE) { $env:OPENSSL_EXE } else { "C:\Program Files\Git\mingw64\bin\openssl.exe" }

if (Test-Path "$runtime\pids.txt") { & "$PSScriptRoot\detener.ps1" }
New-Item -ItemType Directory -Force $runtime | Out-Null

function NuevoSecreto {
    $bytes = New-Object byte[] 32
    [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    ($bytes | ForEach-Object { $_.ToString("x2") }) -join ""
}

function Iniciar($nombre, $exe, $argumentos, $variables) {
    foreach ($k in $variables.Keys) { Set-Item "env:$k" $variables[$k] }
    $p = Start-Process $exe -ArgumentList $argumentos -WorkingDirectory $backend -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput "$runtime\$nombre.out.log" -RedirectStandardError "$runtime\$nombre.log"
    foreach ($k in $variables.Keys) { Remove-Item "env:$k" }
    Add-Content "$runtime\pids.txt" $p.Id
    Write-Host "  $nombre (pid $($p.Id))"
}

function Uvicorn($modulo, $puerto) {
    @("-m", "uvicorn", "$modulo`:app", "--host", "127.0.0.1", "--port", $puerto, "--no-access-log")
}

Write-Host "Iniciando Vault..."
$rootToken = NuevoSecreto
Iniciar "vault" $vault @("server", "-dev", "-dev-root-token-id=$rootToken", "-dev-listen-address=127.0.0.1:8200") @{}
$env:VAULT_ADDR = "http://127.0.0.1:8200"
$env:VAULT_TOKEN = $rootToken
for ($i = 0; $i -lt 30; $i++) {
    & $vault status *> $null
    if ($LASTEXITCODE -eq 0) { break }
    Start-Sleep -Milliseconds 500
}

$s = @{ auth = NuevoSecreto; inventory = NuevoSecreto; orders = NuevoSecreto; clients = NuevoSecreto;
        payments = NuevoSecreto; graphql = NuevoSecreto; analytics = NuevoSecreto }
& $vault kv put secret/gateway auth=$($s.auth) inventory=$($s.inventory) orders=$($s.orders) `
    clients=$($s.clients) payments=$($s.payments) graphql=$($s.graphql) analytics=$($s.analytics) `
    grpc_gateway=$(NuevoSecreto) | Out-Null
& $vault kv put secret/payments provider_webhook_secret=$(NuevoSecreto) | Out-Null
& $vault kv put secret/analytics grpc_analytics=$(NuevoSecreto) | Out-Null

& $vault policy write gateway-read "$PSScriptRoot\gateway-read.hcl" | Out-Null
$gatewayToken = & $vault token create -policy=gateway-read -ttl=24h -field=token
Set-Content "$runtime\vault-token" $rootToken -NoNewline

function Leer($ruta, $campo) { & $vault kv get "-field=$campo" $ruta }

$tls = Join-Path $runtime "tls"
New-Item -ItemType Directory -Force $tls | Out-Null
& $openssl req -x509 -newkey rsa:2048 -nodes -days 2 -subj "/CN=orders-grpc" `
    -addext "subjectAltName=IP:127.0.0.1,DNS:localhost" -keyout "$tls\orders.key" -out "$tls\orders.crt" 2> $null

Write-Host "Preparando MongoDB..."
Push-Location $backend
if ($Reset) { & $python seed.py --reset } else { & $python seed.py }
Pop-Location

Write-Host "Iniciando servicios..."
Iniciar "auth" $python (Uvicorn "auth_service.main" 8100) @{ AUTH_SECRET = (Leer secret/gateway auth) }
Iniciar "inventory" $python (Uvicorn "inventory.main" 8001) @{ INVENTORY_SECRET = (Leer secret/gateway inventory) }
Iniciar "clients" $python (Uvicorn "clients.main" 8003) @{
    CLIENTS_SECRET = (Leer secret/gateway clients); AUTH_SECRET = (Leer secret/gateway auth) }
Iniciar "orders" $python (Uvicorn "orders.main" 8002) @{
    ORDERS_SECRET = (Leer secret/gateway orders); INVENTORY_SECRET = (Leer secret/gateway inventory)
    CLIENTS_SECRET = (Leer secret/gateway clients); GRPC_GATEWAY_SECRET = (Leer secret/gateway grpc_gateway)
    GRPC_ANALYTICS_SECRET = (Leer secret/analytics grpc_analytics)
    GRPC_TLS_CERT = "$tls\orders.crt"; GRPC_TLS_KEY = "$tls\orders.key" }
Iniciar "payments" $python (Uvicorn "payments.main" 8004) @{
    PAYMENTS_SECRET = (Leer secret/gateway payments); ORDERS_SECRET = (Leer secret/gateway orders)
    PROVIDER_WEBHOOK_SECRET = (Leer secret/payments provider_webhook_secret) }
Iniciar "analytics" $python (Uvicorn "analytics.main" 8006) @{
    ANALYTICS_SECRET = (Leer secret/gateway analytics); GRPC_ANALYTICS_SECRET = (Leer secret/analytics grpc_analytics)
    GRPC_TLS_CA = "$tls\orders.crt" }
Iniciar "graphql" "node" @("graphql_gateway\server.js") @{
    GRAPHQL_SECRET = (Leer secret/gateway graphql); ORDERS_SECRET = (Leer secret/gateway orders)
    INVENTORY_SECRET = (Leer secret/gateway inventory); PAYMENTS_SECRET = (Leer secret/gateway payments)
    ANALYTICS_SECRET = (Leer secret/gateway analytics) }
Iniciar "gateway" $python (Uvicorn "gateway.main" 8000) @{
    VAULT_ADDR = $env:VAULT_ADDR; VAULT_TOKEN = $gatewayToken; GRPC_TLS_CA = "$tls\orders.crt" }


$checks = @(
    @("gateway", "http://127.0.0.1:8000/health", ""), @("auth", "http://127.0.0.1:8100/health", $s.auth),
    @("inventory", "http://127.0.0.1:8001/health", $s.inventory), @("orders", "http://127.0.0.1:8002/health", $s.orders),
    @("clients", "http://127.0.0.1:8003/health", $s.clients), @("payments", "http://127.0.0.1:8004/health", $s.payments),
    @("graphql", "http://127.0.0.1:8005/health", $s.graphql), @("analytics", "http://127.0.0.1:8006/health", $s.analytics))
foreach ($c in $checks) {
    $ok = $false
    for ($i = 0; $i -lt 40 -and -not $ok; $i++) {
        try {
            Invoke-RestMethod $c[1] -Headers @{ "X-Internal-Secret" = $c[2] } -TimeoutSec 2 | Out-Null
            $ok = $true
        } catch { Start-Sleep -Milliseconds 500 }
    }
    if ($ok) { Write-Host "  [OK] $($c[0])" } else { Write-Host "  [FALLA] $($c[0]) - revisa .runtime\$($c[0]).log" }
}
Write-Host "Backend listo. API Gateway: http://127.0.0.1:8000/api/v1  (detener: scripts\detener.ps1)"
