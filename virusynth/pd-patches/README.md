# pd-patches — main.pd

Un solo patch (menos riesgo en demo). **100% Pure Data Vanilla 0.46+** (probado
en 0.56-2): cero externals — ni mrpeach, ni comport, ni freeverb (tampoco
`expr~`, aunque viene con toda instalación vanilla, para no romper la
convención "solo objetos vanilla" de CLAUDE.md §4).

> ⚠️ **Antes de esta revisión el patch sonaba silencioso al abrirlo solo**:
> `vs-cutoff` y `vs-vol` alimentan `line~` que arrancan en 0 y nunca se
> movían sin el bridge enviando `/pd/set/*`. Los sliders GUI nuevos (abajo)
> lo arreglan: al abrir el patch ya hay cutoff/volumen/ADSR con valores
> sensatos, sin depender de nada externo.

## Flujo de señal

```
bridge/GUI/simulado (udp 9000)                       bridge (udp 8000)
      │                                                    ▲
[netreceive -u -b 9000] → [oscparse] → [route ...]         │ [netsend -u -b]
      │ /pd/set/* → [s vs-*]   /pd/trigger/note|button1 → [s vs-note]/[vs-fire]
      │ /pd/sensor/pot|fsr|ax → [vs-vol]/[vs-fire]/[vs-cutoff] (Etapa 2, preview)
      ▼
 SYNTH: nota → [mtof] → phasor~ ×3 (detune ±) + osc~ sub, mezcla rebalanceada
        → [vcf~] (cutoff = vs-cutoff con rampa 30 ms, Q = vs-res)
        → envolvente ADSR real (vs-a/vs-d/vs-s/vs-r, gate = vs-gate o
          disparo de un solo golpe con auto-release a 400 ms)
 FX:    → drive [*~ 1+dist·8] → [clip~ -0.85 0.85]        (distorsión)
        → [delwrite~/delread4~ 300 ms] con feedback = vs-del·0.65
        → [rev2~] con mezcla wet = vs-rev
        → chorus: [vd~] modulado por un LFO lento (vs-chorus = mezcla)
 MASTER:→ [*~ vs-vol con rampa 50 ms] → [clip~ -1 1] → [dac~]
 TELEM: [env~] → (dB−40)/60 → /pd/state/amplitude cada 100 ms
        nota disparada → /pd/state/last_note
 BOOT:  [loadbang] → "connect 127.0.0.1 8000" + "; pd dsp 1"
```

## Envolvente ADSR (nuevo)

Un único gate (`vs-gate`, 0/1) y cuatro parámetros (`vs-a`/`vs-d`/`vs-s`/`vs-r`,
en ms/ms/0–1/ms) controlan un `vline~` compartido:

- **Gate manual** (toggle `gate_manual` de la GUI): 1 = ataque→decay→sostiene
  en el nivel de sustain indefinidamente; 0 = release. Es la forma de
  escuchar el ADSR completo al probar a mano.
- **Disparo de un solo golpe** (`/pd/trigger/note`, `/pd/trigger/button1`,
  flanco de `/pd/sensor/fsr`, o el `bng` "disparo_manual" de la GUI): dispara
  ataque→decay→sustain y agenda un release automático 400 ms después (no hay
  mensaje de "note off" en el protocolo actual, así que el auto-release es
  fijo, no proporcional a Attack/Decay — mantenerlo simple redujo mucho el
  riesgo de la implementación).

El "peak" de la envolvente (`vs-peak`) lo escribe: el slider "velocity" de
la GUI, la velocity normalizada de `/pd/trigger/note` (divide/127), o un
valor fijo (0.85–0.9) para los disparos que no traen su propia velocity
(botón/FSR).

## Etapa 2 — entrada OSC de sensores "crudos" (preview / futuro hardware)

Nueva rama de `route`, en paralelo a `/pd/set/*` (no la reemplaza):

| Address | Tipo | Contrato | Efecto en el patch |
|---|---|---|---|
| `/pd/sensor/pot` | float | **normalizado 0–1** (igual convención que `/pd/set/volume`) | → `vs-vol` directo |
| `/pd/sensor/fsr` | float | normalizado 0–1 | cruce de umbral (>0.3) con detección de flanco → dispara nota (peak≈0.9) |
| `/pd/sensor/ax` | float | mismo rango ±g que ya usa el CSV | escalado lineal → `vs-cutoff` (300–4000 Hz) |
| `/pd/trigger/button1` | bang | — | dispara nota (peak≈0.85), mismo mecanismo que el `bng` de la GUI |

Esto es **acondicionamiento de señal simple** (umbral, escalado lineal), no
lógica musical — la cuantización de escala y las decisiones armónicas reales
siguen viviendo exclusivamente en `bridge/mapping.py` (regla cardinal de
CLAUDE.md §2). Cuando el Arduino UNO físico se conecte (firmware ya escrito
en `firmware/src/main_uno.cpp`, ver `docs/hardware-arduino-uno.md`), el
bridge podrá relayear sus lecturas por estas mismas direcciones sin tocar
este patch — la normalización 0–1 de `pot`/`fsr` sigue siendo responsabilidad
de quien envía el OSC (nunca de Pd), igual que ya corrigió el bridge en
`bridge/config.py:ADC_MAX` para no hardcodear la escala del ADC de una placa
concreta.

## GUI de prueba local (nuevo)

Sliders y toggles en la esquina inferior del patch escriben directo a los
mismos buses `vs-*` que usan tanto `/pd/set/*` como `/pd/sensor/*` — un solo
motor de síntesis, tres entradas en paralelo (GUI, OSC "inteligente" del
bridge, OSC "crudo" de sensores/preview). Incluye nota, velocity, cutoff,
resonancia, reverb, delay, distorsión, chorus, volumen, A/D/S/R, el toggle
de gate y el bang de disparo manual.

## Mensajes que entiende (ver docs/osc-protocol.md)

| Address | Args | Efecto |
|---|---|---|
| `/pd/trigger/note` | int nota, int velocity | dispara la voz |
| `/pd/trigger/button1` | bang | dispara la voz (Etapa 2) |
| `/pd/set/cutoff` | float Hz | filtro `vcf~` (rampa 30 ms) |
| `/pd/set/resonance` | float Q | resonancia del filtro |
| `/pd/set/volume` | float 0–1 | master (rampa 50 ms) |
| `/pd/set/fx/reverb` | float 0–1 | mezcla de reverb |
| `/pd/set/fx/delay` | float 0–1 | nivel+feedback del delay |
| `/pd/set/fx/distortion` | float 0–1 | drive de la distorsión |
| `/pd/set/scale`, `/pd/set/bpm`, `/pd/set/root_note` | — | informativos (el cerebro es el bridge) |
| `/pd/sensor/pot` \| `fsr` \| `ax` | float | ver tabla de Etapa 2 arriba |

## Probarlo sin bridge

```
python scripts/mock-sensors.py     # arpegio + barridos + sensores crudos simulados a :9000
```

O directo en el patch: abrí `main.pd`, subí el slider "velocity", tocá el
`bng` "disparo_manual" o prendé el toggle "gate_manual" — no hace falta
Python ni bridge para escuchar el synth.

## Verificación estructural

```
python scripts/validate-pd.py pd-patches/main.pd
```

DSP se activa solo al abrir (`; pd dsp 1`). Si no suena: Media → DSP On,
y revisa el dispositivo de salida en Media → Audio Settings.
