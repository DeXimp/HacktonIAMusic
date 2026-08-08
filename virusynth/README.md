# ViruSynth 🎛️

**¿Qué pasa cuando un instrumento musical tiene tres tipos de músicos
simultáneos: un humano con sensores, una multitud online y una IA directora?**

Proyecto para el Realtime Hackathon by Portal (7–9 ago 2026). Un ESP32 con
sensores toca un sintetizador en Pure Data con <20 ms de latencia; la
audiencia vota escala/tempo/FX desde su teléfono; artistas remotos inyectan
patrones; y un Director IA (Claude) arbitra cada ~7 s con musicalidad — y con
reglas locales de teoría musical si la nube falla. Ver [CLAUDE.md](CLAUDE.md)
(contrato de arquitectura) y [docs/architecture.md](docs/architecture.md).

## Quickstart (Windows)

```powershell
cd virusynth
powershell -ExecutionPolicy Bypass -File scripts\start-all.ps1        # todo mock
powershell -ExecutionPolicy Bypass -File scripts\start-all.ps1 -SerialPort COM7   # con ESP32
```

Eso abre Pure Data (o el simulador), el bridge y la web en `http://localhost:8080`.
La audiencia entra desde el móvil con la IP de la máquina: `http://<IP>:8080/?role=audience`.

Manual, pieza a pieza:

```powershell
python -m venv .venv
.venv\Scripts\pip install -r bridge\requirements.txt
.venv\Scripts\python -m bridge.main --mock-sensors     # el corazón
python -m http.server 8080 -d web                       # la web
# Pure Data: abrir pd-patches\main.pd (DSP se activa solo)
```

> ⚠️ Pd en Windows puede fallar al abrir patches en rutas con acentos/ñ. Si
> `main.pd` no abre, copia `virusynth/` a una ruta sin caracteres especiales.

`.env` (opcional, ver `.env.example`): `ANTHROPIC_API_KEY` activa al director
con Claude; sin ella decide `music_engine.py` con reglas de teoría musical —
la demo funciona igual.

## Verificaciones (sin hardware y sin Pd)

```powershell
.venv\Scripts\python scripts\smoke_test.py                  # Fase 1: mock→bridge→OSC
.venv\Scripts\python -m unittest discover -s bridge\tests -t .   # 32 tests de teoría musical
.venv\Scripts\python scripts\validate-pd.py pd-patches\main.pd   # grafo del patch
.venv\Scripts\python scripts\test-osc.py --telemetry        # simulador de Pd en vivo
```

## Guión de demo (3 minutos)

| Min | Momento | Acción |
|---|---|---|
| 0:00 | **El instrumento vive** | Performer inclina el ESP32 (timbre) y pulsa el FSR (acentos) sobre el arpegio base. Proyector en `/?role=stage`: el orbe respira con el audio real. |
| 0:40 | **La sala entra** | QR a `http://<IP>:8080/?role=audience`. Los votos de FX se sienten al instante; los votos de escala/tempo se acumulan a la vista de todos. |
| 1:20 | **El director decide** | El feed ámbar publica: *"La sala pide más energía: subo el tempo a 152 BPM, paso a paso."* El orbe ondula en ámbar con cada decisión. |
| 2:00 | **Un artista choca** | Alguien en `/?role=artist` envía un patrón con una nota fuera de escala → la IA la resuelve (p. ej. 59→60) y explica la resolución armónica en vivo. |
| 2:40 | **La prueba de fuego** | Apagar el WiFi del router: el show sigue — audio local, WS en LAN, director con reglas locales. *"ViruSynth no depende de la nube: la aprovecha."* |

**Matriz de fallbacks ensayada** — cualquier fila puede fallar en vivo:

| Falla | La demo… |
|---|---|
| API de Claude | sigue: decisiones por reglas locales (chip "reglas locales" en el feed) |
| Portal / internet | sigue: WS local en LAN (`ws://<IP>:8765`) |
| ESP32 | sigue: `--mock-sensors` (performer sintético) |
| Pure Data | sigue el flujo de control: `scripts/test-osc.py` lo imprime |

## Estructura

```
bridge/      orquestador Python (cerebro): estado, secuenciador, IA, WS, OSC
pd-patches/  main.pd — synth+FX 100 % Pd vanilla (0.46+, probado en 0.56)
web/         app de 3 roles (audiencia/artista/escenario), vanilla JS, sin CDNs
firmware/    ESP32 PlatformIO: MPU6050+FSR+pot → CSV 50 Hz (+WiFi-OSC opcional)
docs/        arquitectura · protocolo OSC · channels jam:* · hardware ESP32
scripts/     start-all, smoke test, simulador de Pd, validador de patches
```

## El pitch

ViruSynth democratiza la creación musical en vivo. No reemplaza al músico —
amplifica su capacidad creativa con la inteligencia colectiva de una audiencia
global y la co-dirección de una IA que resuelve conflictos armónicos en tiempo
real. MVP de una plataforma SaaS para performances interactivas: engagement
para artistas y streamers, capa interactiva para venues y festivales, aula
colaborativa para educación musical.
