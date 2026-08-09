# CLAUDE.md — Contrato de Arquitectura de ViruSynth

Este archivo gobierna TODO el desarrollo del proyecto. Cualquier cambio de código debe
respetar estas reglas. Si una decisión nueva las contradice, primero se actualiza este
contrato y después se escribe el código.

## 1. Visión del proyecto

ViruSynth es un instrumento musical colaborativo en tiempo real con cuatro actores
simultáneos: un **performer** local con sensores físicos (Arduino UNO — hardware
principal; ESP32 pausado temporalmente por fallas físicas/térmicas —: MPU6050 + FSR +
potenciómetro + botones), una **audiencia** remota que vota parámetros musicales desde el navegador,
**artistas remotos** que proponen patrones de notas, y una **IA Directora** (Claude) que
analiza el contexto global cada 5–10 s, sugiere mutaciones musicales coherentes y resuelve
choques armónicos. El audio se sintetiza localmente en Pure Data con latencia <20 ms; la
colaboración viaja por una capa realtime (Portal en el hackathon, con fallback local
autónomo). Es el MVP de una plataforma SaaS de performances musicales interactivas.

## 2. Arquitectura: dos loops desacoplados (REGLA CARDINAL)

**El LLM NUNCA está en el audio path.** El audio es 100% local; la IA es un loop asíncrono.

- **Loop 1 — Audio realtime (<20 ms, solo loopback)**:
  `Hardware emisor (Arduino UNO / ESP32, según HARDWARE_BOARD) →(Serial USB 115200, 50 Hz)→ Bridge (hardware_link + mapping) →(OSC UDP :9000)→ Pure Data → 🔊`
- **Loop 2 — Colaboración + IA (1–5 s de tolerancia)**:
  `Pd →(OSC :8000 telemetría)→ Bridge ↔(WS :8765 o Portal SDK)↔ Audiencia/Artistas` y
  `Bridge →(HTTPS, timeout 5 s)→ Claude → validación → OSC → Pd`

Reparto de responsabilidades (innegociable):

| Componente | Hace | NO hace |
|---|---|---|
| Bridge Python | Cerebro: secuenciador, escalas, cuantización, votos, estado, IA | Sintetizar audio |
| Pure Data | Synth + FX + telemetría de amplitud | Lógica musical, red externa, serial |
| Capa realtime (Portal/WS) | Transporte de mensajes `jam:*` | Decidir nada |
| LLM | Sugerir mutaciones (JSON validado) | Generar audio, tocar notas directamente |

## 3. Stack tecnológico

| Capa | Tecnología | Versión |
|---|---|---|
| Bridge | Python | 3.11+ (desarrollo: 3.13.5) |
| OSC | python-osc (fallback interno: `bridge/osc_mini.py` stdlib) | ≥1.8 |
| Serial | pyserial | ≥3.5 |
| Realtime | websockets | ≥12 |
| IA | anthropic (opcional en runtime) | ≥0.40 |
| Audio | Pure Data **Vanilla** | 0.46+ (instalado: 0.56-2) |
| Firmware | Arduino core vía PlatformIO (board `uno`, principal — `esp32dev`, pausado) | atmelavr / espressif32 |
| Sensores | Adafruit MPU6050 + Adafruit Unified Sensor | ^2.2 / ^1.1 |
| Web | HTML/CSS/JS vanilla + Canvas API + Web Audio API — **sin CDNs, sin frameworks** | — |

Dependencias opcionales en runtime: si falta `anthropic` → reglas locales; si falta
`websockets` → sin capa realtime; si falta `pyserial` → performer sintético automático
(`hardware_link.py`, ya no requiere `--mock-sensors` a mano); si falta `python-osc` →
codec interno `osc_mini`. **El bridge nunca muere por un import.**

**Hardware emisor (arquitectura):** cualquier placa que hable el CSV de
`docs/osc-protocol.md` es intercambiable sin tocar el bridge — `HARDWARE_BOARD` (env,
default `arduino_uno`) selecciona el perfil (`bridge/config.py:BOARD_PROFILES`) que fija
`ADC_MAX` y el voltaje lógico. Motivo del pivote actual: fallas físicas/térmicas del ESP32.

## 4. Convenciones de código

- **Python**: snake_case, type hints, `dataclasses` de stdlib (no pydantic), módulos de
  una responsabilidad. Logging con `logging` (loggers: `SEQ`, `OSC`, `SERIAL`, `PORTAL`,
  `IA`, `WEB`). Sin dependencias nuevas sin actualizar este contrato.
- **JS**: camelCase, módulos ES (`type="module"`), sin build step, sin librerías.
- **C++ (firmware)**: constantes `UPPER_SNAKE`, funciones `camelCase`, scheduling con
  `millis()` — prohibido `delay()` en el loop.
- **Pd**: un solo `main.pd`, secciones comentadas, comunicación interna por `[send]`/
  `[receive]` con nombres `vs-*` (p. ej. `vs-cutoff`). Solo objetos vanilla.
- Carpetas: `firmware/`, `pd-patches/`, `bridge/` (+`bridge/tests/`), `web/`, `docs/`,
  `scripts/`. Nombres de canal realtime: namespace `jam:*`.

## 5. Reglas de latencia

| Puede estar en el audio path | NO puede estar jamás |
|---|---|
| Serial USB local (1–5 ms) | Llamadas al LLM |
| UDP loopback (<1 ms) | WebSocket/Portal (30–150 ms) |
| DSP de Pd (1.5–6 ms, block 64 @ 44.1 kHz) | Cualquier HTTPS |
| Mapping síncrono en el bridge (<1 ms) | I/O de disco, sleeps bloqueantes |

Presupuesto total gesto→sonido: **<20 ms**. Los parámetros que llegan del Loop 2 se
aplican de forma asíncrona cuando llegan; nunca se espera por ellos.

## 6. Protocolo de comunicación

| Conexión | Transporte | Puerto | Formato |
|---|---|---|---|
| Hardware → Bridge | Serial USB 115200 | `SERIAL_PORT` (env) | CSV `ax,ay,az,gx,gy,gz,fsr,pot[,btn1,btn2]\n` @ 50 Hz — ADC 0–1023 (Arduino UNO) o 0–4095 (ESP32) según `HARDWARE_BOARD` |
| Bridge → Pd | OSC/UDP | localhost:**9000** | `/pd/set/*`, `/pd/trigger/note`, `/pd/trigger/button1`, `/pd/sensor/*` |
| Pd → Bridge | OSC/UDP | localhost:**8000** | `/pd/state/amplitude`, `/pd/state/last_note` |
| Bridge ↔ Web (WS + estática) | WebSocket / HTTP | :**8765** (o el primer libre — `start-all.ps1` autodetecta si algo más en la máquina ya lo usa, p.ej. NI Web Server) | JSON `{type, channel, data}` (incl. `jam:note_triggered` para el mini-sintetizador de audiencia) por WS; `web/` servida por HTTP en el MISMO puerto (`LocalPortalServer._process_request`) — un solo puerto/link, tunneleable con `start-all.ps1 -Tunnel` para audiencia/escenario en otra red |
| Bridge → LLM | HTTPS | — | Anthropic tool use (`propose_mutation`) |

Especificación completa: `docs/osc-protocol.md` y `docs/portal-channels.md`. Cualquier
mensaje nuevo se documenta ahí ANTES de implementarse. Acceso cruzando redes (no solo
LAN): `docs/remote-access.md` — y por qué el SDK real de "Portal" (el sponsor del
hackathon) sigue siendo un punto de extensión sin implementar (`PortalSDKAdapter`).

## 7. Errores y fallbacks para la demo en vivo

Cadena de degradación (cada eslabón se prueba antes de la demo):

| Falla | Fallback | Cómo |
|---|---|---|
| LLM lento/caído/sin key | Reglas locales de `music_engine.py` | timeout 5 s, `source: "reglas_locales"` visible en el feed |
| Decisión IA inválida | Se descarta y se usa la regla local | `music_engine.validate_decision()` |
| Portal sin SDK/credenciales | Servidor WS local `ws://localhost:8765` | mismos channels `jam:*` |
| Hardware desconectado | Performer sintético automático (`hardware_link.py`) | el show sigue sin intervención: se activa solo al no detectar hardware y se desactiva solo al reconectar; `--mock-sensors` sigue disponible para forzarlo; reconexión cada 3 s |
| Pd cerrado | `scripts/test-osc.py` (simulador que imprime) | se demuestra el flujo de control |
| Sin internet | Todo lo anterior — el sistema es 100% local | — |

Reglas: los errores se loggean y se degradan, nunca se propagan a un crash. El secuenciador
no se detiene jamás. Cooldown de cambio de escala: 20 s (coherencia musical).

## 8. Variables de entorno (`.env`, ver `.env.example`)

| Variable | Default | Uso |
|---|---|---|
| `ANTHROPIC_API_KEY` | (vacío → reglas locales) | IA Director |
| `AI_MODEL` | `claude-sonnet-5` | modelo del director |
| `HARDWARE_BOARD` | `arduino_uno` | placa activa (`bridge/config.py:BOARD_PROFILES`) — define `ADC_MAX` y voltaje lógico |
| `SERIAL_PORT` | `COM5` | puerto de la placa |
| `SERIAL_BAUD` | `115200` | baudios |
| `WS_PORT` | `8765` | servidor realtime local |
| `PD_SEND_PORT` / `PD_RECV_PORT` | `9000` / `8000` | OSC con Pd |
| `PORTAL_API_KEY`, `PORTAL_ROOM` | (vacío → WS local) | SDK real de Portal cuando exista |

## 9. Setup y ejecución

```powershell
# Setup (una vez)
cd virusynth
python -m venv .venv
.venv\Scripts\pip install -r bridge\requirements.txt

# Todo-en-uno (Pd + bridge + web, ambos en el mismo puerto)
powershell -ExecutionPolicy Bypass -File scripts\start-all.ps1
powershell -ExecutionPolicy Bypass -File scripts\start-all.ps1 -Tunnel   # + audiencia/escenario en OTRA red (ver docs/remote-access.md)

# Manual, pieza por pieza
.venv\Scripts\python -m bridge.main --mock-sensors        # bridge + web en http://localhost:8765 (fuerza performer sintético)
.venv\Scripts\python -m bridge.main --serial-port COM7    # bridge (con hardware; sin hardware, cae a mock solo)
# Pure Data: abrir pd-patches\main.pd y activar DSP

# Verificaciones
.venv\Scripts\python scripts\smoke_test.py                 # Fase 1 sin Pd ni hardware
python scripts\validate-pd.py pd-patches\main.pd           # grafo del patch
.venv\Scripts\python -m unittest discover -s bridge\tests  # lógica musical
```

Firmware: `pio run -t upload` dentro de `firmware/` compila el Arduino UNO (placa
principal, `default_envs`); `pio run -e esp32dev -t upload` compila el ESP32 pausado.
