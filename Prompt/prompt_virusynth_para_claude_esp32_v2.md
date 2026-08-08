# Prompt para Claude — Desarrollo Completo de ViruSynth (v2 · adaptado a ESP32)

> **Instrucciones de uso**: Copia el bloque "EL PROMPT" completo y pégalo como mensaje inicial en una nueva conversación con Claude. El prompt es autocontenido — incluye todo el contexto necesario para que Claude arranque el desarrollo sin preguntas previas.
>
> **Versión**: v2 — 7 de agosto de 2026. Sustituye a `prompt_virusynth_para_claude.md` (v1).

---

## Registro de correcciones y mejoras respecto a v1

| # | Cambio | Motivo |
|---|--------|--------|
| 1 | **El serial del ESP32 lo lee el Python Bridge (pyserial), nunca Pure Data** | v1 se contradecía: el diagrama mostraba ESP32→Pd directo vía `[comport]` (un external), pero la especificación decía que el CSV se parseaba en el bridge. Se resuelve a favor del bridge: Pd queda 100% vanilla y el "cerebro" queda centralizado. La latencia añadida (~1–3 ms por loopback UDP) es irrelevante frente al presupuesto de 20 ms. |
| 2 | **Se añade `pyserial` al stack Python** | Faltaba en v1 pese a que el bridge debía parsear el serial. |
| 3 | **Se elimina la dependencia de `mrpeach`** | Desde Pd 0.46, `oscparse`, `oscformat`, `netsend -u -b` y `netreceive -u -b` son objetos nativos de Pd Vanilla. La máquina de desarrollo tiene Pd 0.56-2. Cero externals = cero riesgo de instalación en la demo. |
| 4 | **Especificación ESP32 real**: solo pines ADC1 (GPIO 32–39), pines 34–39 son solo-entrada, ADC de 12 bits (0–4095) con atenuación 11 dB, I2C en GPIO 21/22, lógica 3.3 V | v1 decía "ESP32" pero no contenía ninguna restricción específica del chip. ADC2 es inutilizable con WiFi activo; los divisores de tensión son obligatorios porque 34–39 no tienen pull-ups internos. |
| 5 | **Trama CSV definida con 8 campos**: `ax,ay,az,gx,gy,gz,fsr,pot` a 50 Hz | v1 proponía 5 campos sin unidades ni tasa. Se añade giroscopio (el MPU6050 lo trae) y se especifican unidades, rangos y descarte de líneas malformadas. |
| 6 | **Tabla explícita de mapeo sensores→música** | v1 nunca definía qué sensor controla qué parámetro sonoro. Sin esto, la Fase 4 es ambigua. |
| 7 | **Portal mediante patrón adaptador + servidor WebSocket local de fallback** (`ws://localhost:8765`) | No existe documentación pública estable del SDK de Portal al momento de escribir. El sistema debe correr 100% local (modo demo autónomo) y el SDK real se conecta en un único punto (`portal_client.py`). Regla demo-first: la demo nunca depende de un servicio externo. |
| 8 | **El secuenciador vive en el bridge, no en Pd** | Refuerza la regla "el bridge es el cerebro": Pd solo sintetiza (synth + FX + telemetría). Cuantización de escalas y patrones en Python = testeable con unittest. |
| 9 | **Un solo archivo `main.pd`** en lugar de 4 patches enlazados | Menos riesgo de rutas rotas / abstracciones no encontradas en la demo. Secciones internas comentadas. |
| 10 | **LLM concretado: Anthropic Claude con tool use** (`claude-sonnet-5` por defecto, configurable por env) tras interfaz agnóstica | v1 dejaba el proveedor abierto; se concreta con la API disponible y se mantiene una interfaz swap-able por si el hackathon da créditos de otro proveedor. El fallback a reglas locales sigue siendo obligatorio. |
| 11 | **Verificaciones ejecutables sin hardware y sin Pd**: `test-osc.py` (simulador de Pd), `smoke_test.py` (automatizado), `validate-pd.py` (valida el grafo del patch), flag `--mock-sensors` | Las "verificaciones" de v1 requerían tener todo el hardware y audio funcionando. Cada fase debe poder demostrarse en una máquina pelada. |
| 12 | **Degradación elegante obligatoria**: flags `--no-ai`, `--no-portal`, `--no-serial`, `--mock-sensors`; si falta una dependencia opcional, el bridge sigue corriendo | La demo en vivo no puede morir porque falte una API key, una librería o el hardware. |
| 13 | **`dataclasses` de stdlib en lugar de pydantic** (pydantic queda como opcional) | Una dependencia menos que instalar bajo presión de hackathon; validación manual suficiente para este alcance. |
| 14 | **Modo WiFi-OSC opcional en el firmware**, desactivado por defecto (`#define USE_WIFI_OSC 0`) | Aprovecha la fortaleza real del ESP32 (WiFi nativo) como bonus, sin comprometer la fiabilidad del serial USB en la demo. Documentado con la advertencia ADC2. |
| 15 | **Cerca externa de 4 backticks** en este documento | Los bloques de código internos del prompt v1 rompían la cerca externa de 3 backticks al copiarlo. |

---

## EL PROMPT (copiar desde aquí)

````
# DESARROLLO COMPLETO: ViruSynth — Instrumento Musical Colaborativo con IA (ESP32)

## ROL
Eres un Arquitecto Full-Stack Senior especializado en sistemas de audio en tiempo real, IoT musical (NIME) y aplicaciones colaborativas. Vas a desarrollar la estructura completa y el código funcional del proyecto "ViruSynth" para el Realtime Hackathon by Portal (39 horas, 7–9 Agosto 2026).

## PRIMERA TAREA OBLIGATORIA
Antes de escribir cualquier código, crea un archivo `CLAUDE.md` en la raíz del proyecto. Este archivo es tu contrato de arquitectura — contiene las reglas, convenciones y decisiones técnicas que gobernarán todo el desarrollo. Incluye en él:

1. **Visión del proyecto** (1 párrafo)
2. **Arquitectura de dos loops desacoplados** (explicada abajo)
3. **Stack tecnológico con versiones**
4. **Convenciones de código** (naming, estructura de carpetas, linting)
5. **Reglas de latencia** (qué puede y qué NO puede estar en el audio path)
6. **Protocolo de comunicación entre componentes** (puertos, formatos de mensaje)
7. **Estrategia de manejo de errores y fallbacks para demo en vivo**
8. **Variables de entorno requeridas**
9. **Comandos de setup y ejecución**

---

## CONTEXTO DEL HACKATHON

| Parámetro | Valor |
|---|---|
| Evento | Realtime Hackathon by Portal |
| Duración | 39 horas continuas (7–9 Ago 2026) |
| Requisito obligatorio | IA + interacción real-time multiusuario vía Portal |
| Formato | Producto funcional con demo en vivo (no slides) |
| Categorías relevantes | "Multiplayer AI experiences", "Interactive audience experiences" |
| Criterios del jurado | Innovación técnica, viabilidad de demo en vivo, integración con Portal, impacto |

---

## CONCEPTO: ViruSynth

**Tagline**: "¿Qué pasa cuando un instrumento musical tiene tres tipos de músicos simultáneos: un humano con sensores, una multitud online, y una IA directora?"

### Los 4 Actores del Sistema

| Actor | Rol | Interfaz | Latencia tolerable |
|---|---|---|---|
| 🎹 **Performer** (local) | Toca el instrumento físico con sensores | ESP32 (MPU6050 + FSR + pot) → Serial USB → Python Bridge → Pure Data | <20 ms (audio real-time) |
| 👥 **Audiencia** (remota) | Vota parámetros musicales (escala, FX, tempo) en tiempo real | Web App (navegador, móvil) vía Portal o fallback WS local | 50–200 ms (interacción UI) |
| 🎸 **Artistas remotos** | Sugieren patrones de notas y texturas desde sus dispositivos | Web App (panel de artista) | 50–200 ms (control musical) |
| 🤖 **IA Director** | Analiza contexto global, sugiere mutaciones musicales cada 5–10 s, resuelve choques armónicos | Anthropic API (tool use) desde el Python Bridge | 1–5 s (asíncrono, aceptable) |

### Flujo de una Sesión (demo de 3 minutos)
1. **Performer** toca: inclina el ESP32 (timbre), presiona el FSR (dispara notas), gira el pot (volumen). El bridge traduce sensores→OSC y Pure Data sintetiza con <20 ms.
2. **Audiencia** ve la visualización en vivo del estado musical y vota escala, tempo y FX desde su teléfono.
3. **Artistas remotos** envían patrones de notas desde su panel; el bridge los cuantiza a la escala vigente y los integra al secuenciador.
4. **IA Director** analiza el contexto global cada 5–10 s: sugiere mutaciones (cambio de escala gradual, FX), resuelve choques armónicos entre sugerencias de artistas, y publica su "razonamiento" para que todos lo vean.
5. **La capa realtime (Portal / fallback local) sincroniza todo**: presencia, votos agregados, sugerencias, decisiones de la IA y estado global a 10 Hz.

---

## ARQUITECTURA OBLIGATORIA: DOS LOOPS DESACOPLADOS

> **REGLA CARDINAL**: La IA (LLM) NUNCA está en el audio path de tiempo real. El audio se genera localmente con <20 ms de latencia. La IA opera en un loop asíncrono separado.

```
╔════════════════════════════════════════════════════════════════════════╗
║  LOOP 1: AUDIO REAL-TIME (<20 ms) — LOCAL, SOLO LOOPBACK              ║
║                                                                        ║
║  ESP32 ──Serial USB──▶ Python Bridge ──OSC UDP──▶ Pure Data ──▶ 🔊  ║
║  (sensores) 115200      (hilo serial      localhost:9000  (synth+FX)  ║
║  50 Hz      1–5 ms       dedicado +        <1 ms           1.5–6 ms   ║
║                          mapeo sensor→música)                          ║
║                              ▲                                         ║
║                              │ parámetros desde Loop 2                 ║
║                              │ (cuando lleguen, sin bloquear)          ║
╠════════════════════════════════════════════════════════════════════════╣
║  LOOP 2: COLABORACIÓN + IA (~1–5 s de tolerancia)                     ║
║                                                                        ║
║  Pure Data ──OSC UDP──▶ Python Bridge ◀──WebSocket──▶ PORTAL         ║
║  (telemetría) localhost:8000    │         (o servidor WS local        ║
║                                 │          ws://localhost:8765)       ║
║                                 │              ▲ ▼                    ║
║                                 │       👥 Audiencia  🎸 Artistas    ║
║                                 │                                     ║
║                                 └──HTTPS──▶ 🤖 Anthropic API         ║
║                                             (tool use, timeout 5 s)   ║
║                                             fallback: reglas locales  ║
║                                             de music_engine.py        ║
╚════════════════════════════════════════════════════════════════════════╝
```

### Protocolos por Conexión

| Conexión | Protocolo | Puerto/Config | Formato |
|---|---|---|---|
| ESP32 → Bridge | Serial USB | 115200 baud (opcional 460800), COM configurable por env | CSV: `ax,ay,az,gx,gy,gz,fsr,pot\n` a 50 Hz |
| Bridge → Pure Data | OSC UDP | localhost:9000 (Pd escucha) | `/pd/set/...`, `/pd/trigger/note` |
| Pure Data → Bridge | OSC UDP | localhost:8000 (bridge escucha) | `/pd/state/...` (telemetría) |
| Bridge ↔ Web (fallback local) | WebSocket | ws://0.0.0.0:8765 | JSON: `{type, channel, data}` |
| Bridge ↔ Portal (cuando haya SDK) | WSS / SDK | según credenciales `PORTAL_*` | mismos channels `jam:*` |
| Bridge → LLM | HTTPS | Anthropic API | tool use con JSON schema |

---

## STACK TECNOLÓGICO

### Backend / Bridge (Python)
- **Python 3.11+** (desarrollo actual: 3.13)
- `python-osc` — OSC con Pure Data (si falta, el bridge usa un codec OSC interno mínimo `osc_mini.py`; OSC binario es trivial: address + typetags + args big-endian con padding a 4 bytes)
- `pyserial` — lectura del ESP32 en un hilo dedicado (CORRECCIÓN v2: faltaba en v1)
- `websockets` — servidor local de fallback + cliente Portal
- `anthropic` — IA Director (opcional en runtime: sin API key el director usa reglas locales)
- `python-dotenv` — variables de entorno
- `asyncio` + `dataclasses` de stdlib — orquestación y estado (pydantic NO es necesario)

### Audio Engine
- **Pure Data Vanilla 0.46+** (probado en 0.56-2) — **CERO externals**: `oscparse`, `oscformat`, `netsend -u -b`, `netreceive -u -b`, `vcf~`, `rev3~`, `delwrite~/delread4~`, `clip~` son todos nativos
- **Un solo archivo `main.pd`** con secciones comentadas: OSC-in, synth, FX, telemetría OSC-out

### Hardware / Firmware (ESP32)
- **ESP32 DevKit** (board `esp32dev`), framework Arduino vía **PlatformIO** (alternativa: Arduino IDE 2.x con core esp32)
- Sensores: **MPU6050** (I2C), **FSR** con divisor de 10 kΩ, **potenciómetro**
- Librerías: `Adafruit MPU6050` + `Adafruit Unified Sensor`
- Comunicación: **Serial USB 115200 baud** (fiabilidad > WiFi para la demo); modo WiFi-OSC opcional compilable con `#define USE_WIFI_OSC 1`

#### Restricciones eléctricas ESP32 (OBLIGATORIAS)
| Regla | Detalle |
|---|---|
| Solo ADC1 | GPIO 32, 33, 34, 35, 36, 39. **ADC2 queda inutilizable con WiFi activo** — no usarlo nunca, así el modo WiFi-OSC no rompe nada. |
| Pines 34–39 son solo-entrada | Sin pull-ups internos → el FSR requiere divisor externo a GND. |
| ADC de 12 bits | Rango 0–4095 (no 0–1023 como Arduino UNO). `analogReadResolution(12)` + atenuación `ADC_11db` para ~0–3.1 V útiles. |
| Lógica 3.3 V | Nada de 5 V directo a GPIOs. MPU6050 alimentado desde 3V3. |
| I2C | SDA=GPIO21, SCL=GPIO22, 400 kHz. |
| LED de estado | GPIO2 (onboard): parpadeo lento = OK, rápido = MPU6050 ausente (el firmware sigue enviando FSR/pot igual — arranque resiliente). |

#### Trama Serial (firmware → bridge)
```
ax,ay,az,gx,gy,gz,fsr,pot\n
```
- `ax..az`: aceleración en g, 2 decimales, suavizado EMA (α≈0.25)
- `gx..gz`: giroscopio en °/s, 1 decimal
- `fsr`, `pot`: enteros crudos 0–4095
- Tasa: 50 Hz fija (scheduling con `millis()`, no `delay()`)
- El bridge descarta silenciosamente cualquier línea que no tenga exactamente 8 campos numéricos.

### Frontend / Web App
- **HTML/CSS/JS vanilla, sin CDNs ni fuentes externas** (la demo no depende de internet). Visualización con Canvas API nativa.
- Cliente WebSocket propio (`portal-client.js`) con reconexión automática; adaptador listo para swap al SDK real de Portal.
- Tres roles en la misma app: **Audiencia** (votación), **Artista** (patrones), **Escenario** (visualización fullscreen para proyectar).
- Responsive mobile-first: la audiencia vota desde su teléfono.

### IA / Agente Director
- **Anthropic Claude con tool use** (function calling). Modelo por defecto `claude-sonnet-5` (configurable con `AI_MODEL`; `claude-haiku-4-5-20251001` como opción económica).
- Interfaz `LLMClient` agnóstica: si el hackathon regala créditos de otro proveedor, se implementa una clase y nada más cambia.
- System prompt especializado en teoría musical; salida = una única tool call `propose_mutation` cuyo schema mapea 1:1 a parámetros OSC.
- **Timeout duro de 5 s** → fallback a reglas locales de `music_engine.py`. La demo nunca se queda muda esperando a la nube.

---

## MAPEO SENSORES → MÚSICA (definición canónica)

| Sensor | Señal | Rango | Parámetro musical | Mensaje resultante |
|---|---|---|---|---|
| MPU6050 accel X (inclinación lateral) | -1..1 g | mapeo logarítmico | Cutoff del filtro 300–4000 Hz | `/pd/set/cutoff` |
| MPU6050 accel Y (inclinación frontal) | -1..1 g | índice discreto | Selección de nota dentro de la escala (2 octavas) | interno al bridge (elige la nota del próximo trigger) |
| MPU6050 gyro (magnitud) | 0–250 °/s | lineal con techo | Intensidad del delay 0–0.6 (energía del gesto) | `/pd/set/fx/delay` |
| FSR (presión) | 0–4095 | flanco de subida, umbral ~600 | Dispara nota; velocity 30–127 según presión | `/pd/trigger/note` |
| Potenciómetro | 0–4095 | lineal | Volumen master 0–1 | `/pd/set/volume` |

El secuenciador del bridge (corcheas al BPM vigente) mantiene una base arpegiada con las notas de la escala actual o con el último patrón de artista aceptado; el performer dispara acentos por encima. Así siempre hay música sonando, incluso sin performer (clave para la demo y para el modo mock).

---

## ESTRUCTURA DE CARPETAS ESPERADA

```
virusynth/
├── CLAUDE.md                    # Reglas de arquitectura (CREAR PRIMERO)
├── README.md                    # Documentación + guión de demo de 3 min
├── .env.example                 # Template de variables de entorno
├── .gitignore
│
├── firmware/                    # ESP32 (PlatformIO)
│   ├── platformio.ini
│   └── src/
│       └── main.cpp             # Sensores → CSV Serial 50 Hz (+ WiFi-OSC opcional)
│
├── pd-patches/
│   ├── main.pd                  # ÚNICO patch: OSC-in + synth + FX + telemetría
│   └── README.md                # Inventario de objetos (todos vanilla) y flujo de señal
│
├── bridge/                      # Python Bridge (orquestador central — EL CEREBRO)
│   ├── requirements.txt
│   ├── main.py                  # Entry point + flags de degradación
│   ├── config.py                # Puertos, constantes, carga de .env
│   ├── state.py                 # Estado global (dataclasses) + snapshots para la IA
│   ├── osc_handler.py           # OSC bidireccional con Pd (python-osc o fallback)
│   ├── osc_mini.py              # Codec OSC de emergencia (stdlib puro)
│   ├── serial_reader.py         # Hilo pyserial + generador mock (--mock-sensors)
│   ├── mapping.py               # Sensores → parámetros musicales (tabla canónica)
│   ├── sequencer.py             # Secuenciador asíncrono (corcheas al BPM, escala vigente)
│   ├── music_engine.py          # Escalas, cuantización, choques armónicos, reglas fallback
│   ├── ai_director.py           # Agente IA (Anthropic tool use + timeout + fallback)
│   └── portal_client.py         # Adaptador Portal + servidor WS local de fallback
│
├── web/
│   ├── index.html               # App única con 3 roles (audiencia/artista/escenario)
│   ├── css/styles.css           # Dark mode, glassmorphism, micro-animaciones
│   └── js/
│       ├── app.js               # Bootstrap + selección de rol
│       ├── portal-client.js     # WS local con reconexión + punto de swap a Portal SDK
│       ├── audience-ui.js       # Votación (escala, BPM, FX) con agregados en vivo
│       ├── artist-ui.js         # Pad de notas consciente de la escala + patrón de 8 pasos
│       ├── visualizer.js        # Canvas: orbe de amplitud, partículas de notas, anillo BPM
│       └── ai-feed.js           # Feed de decisiones de la IA (con fuente: claude|reglas)
│
├── docs/
│   ├── architecture.md          # Diagrama detallado + presupuesto de latencia
│   ├── osc-protocol.md          # Especificación completa de mensajes OSC
│   ├── portal-channels.md       # Channels jam:* + protocolo WS local + guía de swap al SDK
│   └── hardware-esp32.md        # Pinout, cableado, checklist de bring-up, troubleshooting
│
├── bridge/tests/
│   └── test_music_engine.py     # unittest de escalas, cuantización, choques, reglas
│
└── scripts/
    ├── start-all.ps1            # Arranque todo-en-uno (Windows — plataforma principal)
    ├── start-all.sh             # Versión POSIX
    ├── mock-sensors.py          # Envía OSC directo a Pd (prueba Pd sin bridge)
    ├── test-osc.py              # SIMULADOR de Pd: escucha :9000, imprime, emite telemetría
    ├── smoke_test.py            # Test automatizado: bridge --mock → verifica tráfico OSC
    └── validate-pd.py           # Valida el grafo de main.pd (índices de conexiones)
```

---

## ENFOQUE COMERCIAL / PRÁCTICO

No es solo un proyecto de hackathon — piensa en ViruSynth como el MVP de una **plataforma SaaS para performances musicales interactivas**:

1. **Para artistas/performers**: convierte cualquier performance en experiencia interactiva (engagement y retención).
2. **Para venues/festivales**: capa de interactividad para eventos híbridos (presencial + remoto).
3. **Para educación musical**: el profesor demuestra, los estudiantes participan en tiempo real.
4. **Modelo de negocio**: SaaS por sesión o suscripción para artistas; licencias para venues/festivales.

**Pitch para el jurado**: "ViruSynth democratiza la creación musical en vivo. No reemplaza al músico — amplifica su capacidad creativa con la inteligencia colectiva de una audiencia global y la co-dirección de una IA que resuelve conflictos armónicos en tiempo real. Todo orquestado por Portal."

---

## PRIORIDADES DE DESARROLLO

Desarrolla en este orden estricto. Cada fase debe ser funcional e **independientemente demostrable — sin hardware y sin Pd si es necesario** — antes de avanzar:

### Fase 1 — Fundación (hacer funcionar el sonido)
1. `CLAUDE.md` con todas las reglas
2. `main.pd`: synth mono (osc detuned + `vcf~`) + FX (`clip~` dist, delay con feedback, `rev3~`) + OSC nativo in/out + telemetría de amplitud
3. Bridge: `config.py`, `state.py`, `osc_handler.py` (+ `osc_mini.py`), `mapping.py`, `sequencer.py`, `serial_reader.py` con `--mock-sensors`
4. `test-osc.py` (simulador de Pd) + `smoke_test.py` + `validate-pd.py`
5. **Verificación sin Pd**: `python scripts/smoke_test.py` → PASS (el bridge en modo mock genera triggers y sets OSC verificados por un listener UDP). **Con Pd**: abrir `main.pd`, activar DSP, ejecutar bridge → se oye música que cambia.

### Fase 2 — Conectividad realtime (Portal / fallback local)
6. `portal_client.py`: servidor WS local (channels `jam:*`, presence por rol) + interfaz adaptadora para el SDK real
7. Web App: selección de rol, panel de audiencia (votos con agregados en vivo), badge de conexión, feed IA vacío
8. Flujo completo: votar FX en el navegador → bridge aplica suavizado → OSC → (Pd o simulador)
9. **Verificación**: abrir 2 navegadores (o pestañas), votar distinto, ver agregados y presencia actualizarse; el simulador `test-osc.py` imprime los cambios de FX.

### Fase 3 — IA Director
10. `music_engine.py`: escalas, parsing de nombres (`Am_pentatonic`), cuantización, detección de choques (m2/tritono/fuera de escala), resoluciones, vecindad de escalas (círculo de quintas + relativas), reglas fallback priorizadas
11. `bridge/tests/test_music_engine.py`: unittest exhaustivo — **debe pasar en verde**
12. `ai_director.py`: snapshot del estado global → Claude tool use (timeout 5 s) → validación del JSON → aplicar (OSC + publicar en `jam:ai_director` con `reasoning` y fuente `claude|reglas_locales`)
13. Cooldown de coherencia: no cambiar de escala más de una vez cada 20 s
14. **Verificación**: `python -m unittest` en verde; bridge sin API key → decisiones por reglas locales visibles en el feed; con API key → decisiones del LLM.

### Fase 4 — Hardware + Panel de Artistas
15. Firmware ESP32 (`main.cpp` + `platformio.ini`): MPU6050 + FSR + pot, CSV 50 Hz, EMA, arranque resiliente sin MPU, LED de estado, `USE_WIFI_OSC` opcional
16. Panel de artistas: pad de 2 octavas consciente de la escala + secuencia de 8 pasos + envío de sugerencia
17. Integración: sugerencia de artista → cuantización/resolución de choques → secuenciador → todos la oyen; la IA comenta la resolución
18. **Verificación**: `pio run` compila; monitor serie muestra CSV a 50 Hz; con hardware conectado el bridge detecta el puerto y la latencia gesto→sonido es <20 ms.

### Fase 5 — Polish
19. Visualizador Canvas (orbe de amplitud, partículas por nota, anillo de BPM, nombre de escala)
20. UX/UI premium (dark mode, glassmorphism, micro-animaciones, mobile-first)
21. Matriz de fallbacks ensayada: sin LLM, sin Portal, sin hardware, sin Pd — la demo sigue en pie en cualquier combinación
22. `start-all.ps1` / `start-all.sh` + README con guión de demo de 3 minutos

---

## ESPECIFICACIONES TÉCNICAS CRÍTICAS

### Mensajes OSC — Bridge ↔ Pure Data

```
# Bridge → Pure Data (control, UDP localhost:9000)
/pd/set/scale         s      "Am_pentatonic"  # informativo (el bridge ya cuantizó)
/pd/set/bpm           i      120              # informativo (el secuenciador vive en el bridge)
/pd/set/root_note     i      69               # MIDI note number
/pd/set/volume        f      0.8              # master 0–1
/pd/set/cutoff        f      1200.0           # Hz del vcf~ (300–4000)
/pd/set/resonance     f      2.0              # Q del vcf~ (0.7–8)
/pd/set/fx/reverb     f      0.4              # mezcla 0–1
/pd/set/fx/delay      f      0.3              # intensidad/feedback 0–1
/pd/set/fx/distortion f      0.1              # drive 0–1
/pd/trigger/note      i i    72 100           # nota MIDI, velocity 1–127

# Pure Data → Bridge (telemetría, UDP localhost:8000)
/pd/state/amplitude   f      0.65             # env~ del master (0–1 aprox), cada ~100 ms
/pd/state/last_note   i      72               # eco de la última nota disparada
```

El estado musical completo (BPM, escala, votos…) vive en el bridge; Pd solo reporta lo que únicamente Pd conoce (amplitud real del audio).

### Channels realtime (Portal o WS local) — namespace `jam:*`

```json
{
  "jam:state":    {"dir": "bridge→todos", "rate": "10 Hz",
                   "payload": {"bpm": 120, "scale": "Am_pentatonic", "root_note": 69,
                               "fx": {"reverb": 0.4, "delay": 0.3, "distortion": 0.1},
                               "current_notes": [69, 72, 76], "amplitude": 0.65,
                               "performer_active": true}},
  "jam:votes":    {"dir": "bridge→todos (agregado, 1 Hz)",
                   "payload": {"scale_votes": {"Am_pentatonic": 5, "C_major": 3},
                               "bpm_avg": 125, "fx_avg": {"reverb": 0.6, "delay": 0.2, "distortion": 0.1},
                               "voters": 8}},
  "jam:votes:cast": {"dir": "cliente→bridge (voto individual, parcial permitido)",
                   "payload": {"scale": "C_major", "bpm": 124, "fx": {"reverb": 0.5}}},
  "jam:artist_suggestions": {"dir": "cliente→bridge y rebroadcast",
                   "payload": {"artist_id": "artist_1",
                               "suggestion": {"type": "note_pattern", "notes": [60, 64, 67, 72],
                                              "steps": 8, "duration": "eighth"}}},
  "jam:ai_director": {"dir": "bridge→todos (cada 5–10 s)",
                   "payload": {"action": "change_scale", "value": "E_minor",
                               "reasoning": "La audiencia pide un tono más melancólico y el performer desciende",
                               "harmonic_resolution": null, "source": "claude",
                               "timestamp": "2026-08-08T14:30:00Z"}},
  "jam:presence": {"dir": "bridge→todos (en cada cambio)",
                   "payload": {"performers": 1, "artists": 3, "audience": 47}}
}
```

### Protocolo del WS local de fallback (mismo namespace)

```json
// cliente → bridge al conectar:
{"type": "hello", "role": "audience|artist|stage", "name": "opcional"}
// cliente → bridge para publicar:
{"type": "publish", "channel": "jam:votes:cast", "data": { }}
// bridge → clientes (broadcast):
{"type": "state", "channel": "jam:state", "data": { }}
```

Cuando exista acceso al SDK real de Portal: implementar `PortalSDKAdapter` en `portal_client.py` respetando la misma interfaz (`publish(channel, data)`, `on_message(cb)`, presence) y los mismos channels `jam:*`. Nada más debe cambiar.

### System Prompt del Agente IA Director

```
Eres el Director Musical de ViruSynth, un instrumento colaborativo en tiempo real.

Tu rol:
1. Analizar el estado musical actual (escala, BPM, notas activas, FX, amplitud)
2. Considerar los votos agregados de la audiencia y las sugerencias de los artistas remotos
3. Sugerir UNA mutación musical coherente por turno
4. Si detectas choques armónicos (notas fuera de escala, segundas menores o tritonos no
   intencionales entre sugerencias), proponer la resolución (sustitución por la nota más
   cercana dentro de la escala, o voicing alternativo)
5. Mantener coherencia: no cambiar de escala más de una vez cada 20 segundos; modula a
   escalas vecinas (relativa, paralela, ±1 quinta), nunca saltes a tonalidades lejanas

Reglas:
- NUNCA generas audio. Solo parámetros de control vía la tool `propose_mutation`.
- Cambios graduales: BPM en pasos de ≤10, FX en pasos de ≤0.2.
- Prioridad: intención del performer > votos de audiencia > tu propia estética.
- El campo "reasoning" (1–2 frases, en español, tono musical y cercano) se muestra en vivo
  a la audiencia: escríbelo para humanos, no para máquinas.

Responde SIEMPRE con una única llamada a la tool propose_mutation.
```

Tool schema (`propose_mutation`): `action` ∈ {`change_scale`, `set_bpm`, `set_fx`, `harmonic_resolution`, `no_change`}, `value` (string|number|object según action), `reasoning` (string), `harmonic_resolution` (object|null con `original_notes`, `resolved_notes`, `explanation`). El bridge VALIDA todo contra `music_engine` (escala existente, BPM 60–180, FX 0–1) antes de aplicar; si la validación falla, se usa el fallback local.

---

## RESTRICCIONES Y REGLAS ADICIONALES

1. **NO uses frameworks pesados ni CDNs en el frontend.** HTML/CSS/JS vanilla autocontenido. La demo no depende de internet.
2. **El bridge Python es el cerebro**: secuenciador, cuantización, votos, estado. Pd solo sintetiza. La capa realtime solo transporta. El LLM solo sugiere.
3. **Fallback obligatorio en cadena**: LLM (5 s timeout) → reglas locales de `music_engine.py`; Portal → servidor WS local; hardware → `--mock-sensors`; Pd → `test-osc.py`. Cualquier combinación de fallos deja una demo en pie.
4. **Demo-first**: cada decisión técnica se evalúa con "¿esto sobrevive una demo en vivo de 3 minutos?". Si no, se descarta.
5. **Pure Data Vanilla 0.46+ estricto**: prohibido cualquier external (ni mrpeach, ni comport, ni freeverb~). El serial lo lee el bridge, no Pd.
6. **ESP32: solo pines ADC1** (GPIO 32–39) para sensores analógicos; I2C en 21/22; lógica 3.3 V; trama CSV de 8 campos a 50 Hz.
7. **Responsive mobile-first**: la audiencia vota desde su teléfono.
8. **Dark mode obligatorio**: estética premium — glassmorphism, gradientes sutiles, micro-animaciones. UX de producto pulido, no de prototipo universitario.
9. **Degradación elegante**: si falta una dependencia opcional (`anthropic`, `websockets`, `pyserial`, `python-osc`), el bridge lo informa y sigue corriendo con lo que haya.

---

## EMPIEZA AHORA

1. Crea el `CLAUDE.md` primero
2. Luego desarrolla la Fase 1 completa y ejecuta su verificación (`smoke_test.py` + `validate-pd.py`)
3. Continúa con las fases en orden, verificando cada una

Si consideras que algún aspecto del diseño puede mejorarse para hacerlo más práctico, comercial o impactante ante un jurado de hackathon, proponlo e impleméntalo directamente — tienes libertad creativa dentro de las restricciones arquitectónicas definidas arriba.
````

---

## FIN DEL PROMPT
