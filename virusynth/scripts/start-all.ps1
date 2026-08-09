# ViruSynth — arranque todo-en-uno (Windows)
#   powershell -ExecutionPolicy Bypass -File scripts\start-all.ps1
#   Flags:  -NoPd  -NoAI  -Mock  -SerialPort COM7  -WebPort 8765  -Tunnel
#
# -Tunnel expone la app a internet (para audiencia/escenario en OTRA red)
# vía ngrok, si lo tenés instalado -- ver docs/remote-access.md.
param(
    [switch]$NoPd,
    [switch]$NoAI,
    [switch]$Mock,
    [string]$SerialPort = "",
    [int]$WebPort = 8765,
    [switch]$Tunnel
)

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

# El puerto pedido puede estar ocupado por otra cosa en esta máquina (p.ej.
# National Instruments Web Server, IIS Express, otro proyecto) -- en vez de
# arrancar igual y que el navegador termine mostrándole al usuario el error
# de OTRO servicio, se busca el primer puerto libre a partir de -WebPort.
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
$OriginalWebPort = $WebPort
$WebPort = Get-FreePort -Preferred $WebPort
if ($WebPort -ne $OriginalWebPort) {
    Write-Host "[web] puerto $OriginalWebPort ocupado por otra cosa en esta máquina; usando $WebPort en su lugar" -ForegroundColor Yellow
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

# --- Bridge (también sirve la web/ en el mismo puerto -- ver
#     bridge/portal_client.py:LocalPortalServer._process_request. Un solo
#     proceso, un solo puerto, un solo link para compartir con audiencia
#     remota; ya no hace falta un `python -m http.server` aparte) ---
$bridgeArgs = @('-m', 'bridge.main')
if ($Mock -or -not $SerialPort) { $bridgeArgs += '--mock-sensors' }
if ($SerialPort) { $bridgeArgs += @('--serial-port', $SerialPort) }
if ($NoAI) { $bridgeArgs += '--no-ai' }
Write-Host "[bridge] python $($bridgeArgs -join ' ')  (WS_PORT=$WebPort)" -ForegroundColor Green
$env:WS_PORT = "$WebPort"
Start-Process $Py -ArgumentList $bridgeArgs -WorkingDirectory $Root

Write-Host "[web] http://localhost:$WebPort  (la audiencia entra con la IP de esta máquina)" -ForegroundColor Green
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

# --- Túnel a internet (gente en OTRA red, no solo tu LAN) ---
if ($Tunnel) {
    $ngrok = Get-Command ngrok -ErrorAction SilentlyContinue
    if (-not $ngrok) {
        Write-Host ""
        Write-Host "[tunnel] No encontré 'ngrok' en el PATH." -ForegroundColor Yellow
        Write-Host "         Instalalo desde https://ngrok.com/download, logueate una vez" -ForegroundColor Yellow
        Write-Host "         con 'ngrok config add-authtoken <tu-token>', y volvé a correr" -ForegroundColor Yellow
        Write-Host "         este script con -Tunnel. Ver docs/remote-access.md." -ForegroundColor Yellow
    } else {
        Write-Host ""
        Write-Host "[tunnel] Levantando ngrok en el puerto $WebPort..." -ForegroundColor Cyan
        Start-Process ngrok -ArgumentList "http $WebPort"
        Start-Sleep -Seconds 3
        try {
            $tunnels = Invoke-RestMethod -Uri "http://127.0.0.1:4040/api/tunnels" -TimeoutSec 5
            $publicUrl = ($tunnels.tunnels | Where-Object { $_.proto -eq "https" } | Select-Object -First 1).public_url
            if ($publicUrl) {
                Write-Host ""
                # Ojo: nada de em dash (—) DENTRO de un string. Este archivo se
                # guarda en UTF-8 con BOM justamente para que PS 5.1 no lo lea
                # como CP1252; sin BOM, los bytes del em dash terminan en un
                # `”` que PowerShell acepta como comilla y parte la cadena.
                Write-Host "Link publico (cualquier red) -- compartilo con audiencia/escenario remoto:" -ForegroundColor Green
                Write-Host "  Audiencia:  $publicUrl/?role=audience" -ForegroundColor Cyan
                Write-Host "  Artistas:   $publicUrl/?role=artist" -ForegroundColor Magenta
                Write-Host "  Escenario:  $publicUrl/?role=stage" -ForegroundColor Yellow
                Write-Host ""
                Write-Host "  (el link es publico: cualquiera con el enlace puede votar/proponer" -ForegroundColor DarkGray
                Write-Host "   patrones -- es el diseño de la jam colaborativa, no un descuido)" -ForegroundColor DarkGray
            } else {
                Write-Host "[tunnel] ngrok arrancó pero todavía no publicó el túnel -- mirá su ventana." -ForegroundColor Yellow
            }
        } catch {
            Write-Host "[tunnel] ngrok arrancó -- mirá su ventana para el link público (no pude consultar su API todavía)." -ForegroundColor Yellow
        }
    }
}
