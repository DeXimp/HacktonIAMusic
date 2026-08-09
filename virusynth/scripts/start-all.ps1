# ViruSynth — arranque todo-en-uno (Windows)
#   powershell -ExecutionPolicy Bypass -File scripts\start-all.ps1
#   Flags:  -NoPd  -NoAI  -Mock  -SerialPort COM7  -WebPort 8080
param(
    [switch]$NoPd,
    [switch]$NoAI,
    [switch]$Mock,
    [string]$SerialPort = "",
    [int]$WebPort = 8080
)

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

# El puerto pedido puede estar ocupado por otra cosa en esta máquina (p.ej.
# National Instruments Web Server, IIS Express, otro proyecto) -- en vez de
# arrancar igual y que el navegador termine mostrándole al usuario el 404 de
# OTRO servicio, se busca el primer puerto libre a partir de -WebPort.
function Get-FreePort {
    param([int]$Preferred, [int]$MaxTries = 20)
    for ($i = 0; $i -lt $MaxTries; $i++) {
        $candidate = $Preferred + $i
        if (-not (Get-NetTCPConnection -LocalPort $candidate -ErrorAction SilentlyContinue)) {
            return $candidate
        }
    }
    return $Preferred   # no encontró ninguno libre: se rinde y devuelve el pedido
}
$WebPort = Get-FreePort -Preferred $WebPort
if ($WebPort -ne 8080) {
    Write-Host "[web] puerto 8080 ocupado por otra cosa en esta máquina; usando $WebPort en su lugar" -ForegroundColor Yellow
}

$Py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) {
    Write-Host "[setup] Creando venv e instalando dependencias..." -ForegroundColor Cyan
    python -m venv .venv
    & $Py -m pip install --quiet -r bridge\requirements.txt
}

# --- Pure Data ---
if (-not $NoPd) {
    # El instalador de Pd deja el ejecutable en distintos lugares según se
    # instaló per-user o para toda la máquina -- se prueban ambos en vez de
    # asumir uno solo (varía de una máquina del equipo a otra).
    $PdCandidates = @(
        (Join-Path $env:LOCALAPPDATA "Pd\bin\pd.exe"),
        "C:\Program Files\Pd\bin\pd.exe",
        "C:\Program Files (x86)\Pd\bin\pd.exe"
    )
    $PdExe = $PdCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($PdExe) {
        Write-Host "[pd] Abriendo main.pd (activa DSP si no suena: Media > DSP On)" -ForegroundColor Green
        # Nota: si la ruta del proyecto tiene acentos y Pd no abre el patch,
        # copia la carpeta virusynth a una ruta sin caracteres especiales.
        # IMPORTANTE: Start-Process -ArgumentList con un array NO cita los
        # elementos que traen espacios (p.ej. "Github Repositories\...") en
        # Windows PowerShell 5.1 -- el path se parte a la mitad y Pd tira
        # "can't open". Por eso acá se arma un solo string con comillas
        # explícitas alrededor del path, no un array.
        $pdPatch = Join-Path $Root 'pd-patches\main.pd'
        Start-Process $PdExe -ArgumentList "-open `"$pdPatch`""
    } else {
        Write-Host "[pd] Pure Data no encontrado; usa scripts\test-osc.py como simulador" -ForegroundColor Yellow
        $testOsc = Join-Path $Root 'scripts\test-osc.py'
        Start-Process $Py -ArgumentList "`"$testOsc`" --telemetry"
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
Write-Host "[web] http://localhost:$WebPort  (la audiencia entra con la IP de esta máquina)" -ForegroundColor Green
# Mismo cuidado que con Pd: un array en -ArgumentList no cita el path si
# trae espacios, así que http.server terminaba sirviendo desde el directorio
# equivocado (404 en / porque ahí no hay index.html) -- un solo string con
# comillas explícitas alrededor del path lo evita.
$webDir = Join-Path $Root 'web'
Start-Process $Py -ArgumentList "-m http.server $WebPort -d `"$webDir`"" -WorkingDirectory $Root

Start-Sleep -Seconds 2
Start-Process "http://localhost:$WebPort"

$ip = (Get-NetIPAddress -AddressFamily IPv4 |
       Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } |
       Select-Object -First 1).IPAddress
if ($ip) {
    Write-Host ""
    Write-Host "Audiencia (móviles en la misma red):  http://${ip}:${WebPort}/?role=audience" -ForegroundColor Cyan
    Write-Host "Artistas:                             http://${ip}:${WebPort}/?role=artist" -ForegroundColor Magenta
    Write-Host "Proyector:                            http://localhost:${WebPort}/?role=stage" -ForegroundColor Yellow
}
