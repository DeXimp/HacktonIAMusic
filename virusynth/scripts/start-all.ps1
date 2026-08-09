# ViruSynth — arranque todo-en-uno (Windows)
#   powershell -ExecutionPolicy Bypass -File scripts\start-all.ps1
#   Flags:  -NoPd  -NoAI  -Mock  -SerialPort COM7
param(
    [switch]$NoPd,
    [switch]$NoAI,
    [switch]$Mock,
    [string]$SerialPort = ""
)

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) {
    Write-Host "[setup] Creando venv e instalando dependencias..." -ForegroundColor Cyan
    python -m venv .venv
    & $Py -m pip install --quiet -r bridge\requirements.txt
}

# --- Pure Data ---
if (-not $NoPd) {
    $PdExe = "C:\Program Files\Pd\bin\pd.exe"
    if (Test-Path $PdExe) {
        Write-Host "[pd] Abriendo main.pd (activa DSP si no suena: Media > DSP On)" -ForegroundColor Green
        # Nota: si la ruta del proyecto tiene acentos y Pd no abre el patch,
        # copia la carpeta virusynth a una ruta sin caracteres especiales.
        Start-Process $PdExe -ArgumentList @('-open', (Join-Path $Root 'pd-patches\main.pd'))
    } else {
        Write-Host "[pd] Pure Data no encontrado; usa scripts\test-osc.py como simulador" -ForegroundColor Yellow
        Start-Process $Py -ArgumentList @((Join-Path $Root 'scripts\test-osc.py'), '--telemetry')
    }
}

# --- Bridge ---
$bridgeArgs = @('-m', 'bridge.main')
if ($Mock -or -not $SerialPort) { $bridgeArgs += '--mock-sensors' }
if ($SerialPort) { $bridgeArgs += @('--serial-port', $SerialPort) }
if ($NoAI) { $bridgeArgs += '--no-ai' }
Write-Host "[bridge] python $($bridgeArgs -join ' ')" -ForegroundColor Green
Start-Process $Py -ArgumentList $bridgeArgs -WorkingDirectory $Root

# --- Web ---
Write-Host "[web] http://localhost:8080  (la audiencia entra con la IP de esta máquina)" -ForegroundColor Green
Start-Process $Py -ArgumentList @('-m', 'http.server', '8080', '-d', (Join-Path $Root 'web')) -WorkingDirectory $Root

Start-Sleep -Seconds 2
Start-Process "http://localhost:8080"

$ip = (Get-NetIPAddress -AddressFamily IPv4 |
       Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } |
       Select-Object -First 1).IPAddress
if ($ip) {
    Write-Host ""
    Write-Host "Audiencia (móviles en la misma red):  http://${ip}:8080/?role=audience" -ForegroundColor Cyan
    Write-Host "Artistas:                             http://${ip}:8080/?role=artist" -ForegroundColor Magenta
    Write-Host "Proyector:                            http://localhost:8080/?role=stage" -ForegroundColor Yellow
}
