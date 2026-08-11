# Motor musical de género + sala en tiempo real — diseño

> Fecha: 2026-08-10 · Estado: aprobado para planificar
> Alcance: `bridge/`, `pd-patches/`, `web/`, `docs/`, `scripts/`. **Sin microcontrolador**:
> el mapeo de sensores (`mapping.py`, `serial_reader.py`, `hardware_link.py`, `firmware/`)
> no se toca en este trabajo más allá de enrutar los gestos del performer a su propia voz.

## 1. Problema

ViruSynth funciona pero suena pobre, y la interacción entre las personas presentes es
puramente paramétrica: se vota escala, tempo y FX, y se mandan patrones de notas. Faltan
dos cosas:

1. **Riqueza musical.** `sequencer.py` es monofónico: corcheas infinitas sobre una única
   forma de arpegio (`_ARP_SHAPE = [0,2,4,2,5,4,2,1]`) dentro de una escala, y `main.pd`
   tiene **una sola voz** (2 sierras + seno + sub + chorus). No hay bajo, ni acordes, ni
   percusión, ni forma de canción, ni cambio de timbre, ni juego de tempo. La limitación
   no es el hardware: es el motor.
2. **Conversación.** No hay forma de que la audiencia le diga nada al performer — ni un
   pedido concreto ni un "está buenazo el concierto".

## 2. Objetivo

Un **motor de género** que produzca música con forma propia, con el estilo
Undertale/Deltarune como preset por defecto (`determinacion`), y una **sala** donde la
audiencia conversa y esa conversación entra al sistema como material musical, leída por
la IA Directora.

### Decisiones tomadas con el usuario

| Decisión | Elegido |
|---|---|
| Rol del chat | Público, visible por todos, **y la IA lo lee** y reacciona musicalmente |
| Profundidad del estilo | **Motor de estilos genérico** con `determinacion` como preset por defecto; se pueden añadir más sin tocar el motor |
| Forma de la canción | **Arco de secciones automático**, con la IA decidiendo los saltos y los juegos de tempo |
| Crecimiento del patch de Pd | **`[clone]` + abstracciones** (`vs-voice.pd`, `vs-drums.pd`) |
| Timing en el navegador | **Paquetes por compás** agendados con `start(when)`, no nota a nota |
| Transporte del chat | **Efímero + buffer de historial en el bridge** (idéntico en Portal y en el WS local) |

### Fuera de alcance (explícito)

- Integración del microcontrolador (en curso por separado).
- Modelos generativos de audio en el audio path (ver §10).
- Persistencia de chat entre sesiones (ruta de upgrade documentada en §7.4).
- Autenticación de usuarios / cuentas.

## 3. Arquitectura

### 3.1 La regla cardinal no cambia

El LLM sigue fuera del audio path (CLAUDE.md §2). Todo lo nuevo del motor musical vive en
el bridge (Loop 1 para el despacho a Pd, Loop 2 para las decisiones); Pd sigue sin lógica
musical y el navegador sigue sin recibir bytes de audio.

### 3.2 El eje del motor

Hoy el secuenciador pregunta *"¿cuál es la próxima nota?"* cada corchea. El motor nuevo
pregunta, **una vez por compás**, *"¿qué toca cada voz en cada una de las 16
semicorcheas?"*, y esa respuesta la componen cinco capas apiladas:

```
StyleDeck   ──┐  qué paleta (acordes, timbres, tempos, patrones de batería)
Harmony     ──┤  qué acorde suena en este compás
Motif       ──┼──► Arranger ──► Bar ──┬──► reloj → PdLink → Pd        (escenario)
Arrangement ──┤  qué voces, densidad, octava
Groove      ──┘  swing, medio/doble tiempo └──► jam:bar → navegador   (audiencia)
```

**Un render por compás, dos consumidores con entrega distinta:**

- **Pd** recibe cada evento en su instante exacto, despachado por el mismo reloj que
  renderizó el compás. Latencia local, sin cambios en el presupuesto de <20 ms.
- **El navegador** recibe el compás entero por adelantado (`jam:bar`) y lo agenda con
  `AudioBufferSourceNode.start(when)` / `OscillatorNode.start(when)`, que es
  sample-accurate. El ritmo deja de depender del jitter de red.

**Consecuencia deseada:** como el compás se renderiza adelantado, las decisiones de la IA
y los cambios votados aterrizan en el **tiempo fuerte del compás siguiente**, no a mitad
de frase. Es musicalmente mejor que el comportamiento actual y es un requisito, no un
efecto lateral tolerado.

**Los gestos del performer no pasan por acá.** El FSR y la inclinación siguen disparando
notas inmediatas en su propia voz (`performer`), fuera del render de compás: son
impredecibles y no se pueden agendar. Conservan la ruta de <20 ms intacta.

### 3.3 Módulos nuevos del bridge

Todo stdlib, una responsabilidad por módulo, testeable sin audio ni red (CLAUDE.md §4).

| Módulo | Hace | No hace |
|---|---|---|
| `bridge/style.py` | Presets de género: pools de progresiones por sección, rango de tempo, swing, timbres por voz, kits de batería, motivos semilla, FX por defecto | Decidir cuándo cambia nada |
| `bridge/harmony.py` | Grados romanos → notas del acorde en la escala vigente, `chord_at(bar)`, conducción de voces (inversión más cercana), tonos de acorde vs de color | Ritmo, duración |
| `bridge/motif.py` | El leitmotiv: motivo como grados relativos + transformaciones | Saber qué acorde suena |
| `bridge/arrangement.py` | El arco de secciones, voces activas, densidad, octava, fills | Elegir notas concretas |
| `bridge/sequencer.py` (reescrito) | Reloj de semicorcheas sin deriva, swing, render del compás, despacho a Pd, emisión de `jam:bar` | Teoría musical |
| `bridge/chat.py` | Buffer de historial, validación, rate limit, `chat_pulse()` | Decidir música |

`music_engine.py` se mantiene como está (escalas, cuantización, choques, validación) y
crece solo en `validate_decision()` para las acciones nuevas. `harmony.py` se apoya en él
y no lo duplica.

### 3.4 Bug que se corrige de paso

`Sequencer.run()` hace `await asyncio.sleep(60/bpm/2)` **después** de hacer el trabajo del
paso, así que acumula deriva: el tempo real va siempre algo lento y empeora con la carga.
El reloj nuevo usa tiempo absoluto:

```python
next_t = loop.time()
while True:
    ...                      # trabajo del paso
    next_t += step_seconds   # acumulador absoluto, no relativo
    await asyncio.sleep(max(0.0, next_t - loop.time()))
```

Si el bucle se atrasa más de un compás entero (garbage collection, hipo del SO), se
resincroniza al siguiente límite de compás en vez de intentar recuperar los pasos
perdidos: mejor un hueco que una avalancha de notas comprimidas.

## 4. El motor musical

### 4.1 `style.py` — presets de género

```python
@dataclass(frozen=True)
class VoicePatch:
    timbre: str          # "pulse25" | "pulse50" | "triangle" | "saw" | "bell" | "choir"
    octave: int          # desplazamiento respecto al root
    range_lo: int        # rango MIDI en el que la voz puede moverse
    range_hi: int
    vibrato: float       # 0..1
    gain: float          # mezcla relativa

@dataclass(frozen=True)
class StyleDeck:
    id: str
    name: str
    scales: tuple[str, ...]
    progressions: dict[str, tuple[tuple[str, ...], ...]]   # sección -> pool
    tempo_range: tuple[int, int]
    swing: float
    voices: dict[str, VoicePatch]                          # lead|bass|chords|pad
    drum_patterns: dict[str, str]                          # sección -> id de patrón
    motif_seeds: tuple[Motif, ...]
    fx: dict[str, float]
```

Registro: `STYLES: dict[str, StyleDeck]` con `determinacion` (default) y al menos dos más
para demostrar que el motor es genérico. Un `id` desconocido cae a `determinacion`.

### 4.2 El preset `determinacion`

Lo que hace que Undertale suene a Undertale no es el timbre: es que **un mismo motivo
vuelve transformado** en contextos distintos (*Once Upon a Time* → *Hopes and Dreams* →
*His Theme* → *Memory* son la misma célula melódica). Eso es lo que implementa
`motif.py`, y es la pieza que hoy no existe en ninguna forma en el proyecto.

**Escalas del preset:** `Am_pentatonic`, `A_minor`, `D_minor`, `E_minor`,
`A_harmonic_minor`, `D_dorian`.

**Pools de progresiones** (eólico con las cadencias características):

| Sección | Pool | Razón |
|---|---|---|
| `intro`, `verse` | `i–VI–III–VII` · `i–VII–VI–VII` | El loop eólico de base |
| `build` | `iv–VII–III–VI` · `i–iv–V–V` | Ese `V` lleva **sensible** (menor armónica): el medio tono que empuja hacia `i` está en todos los temas de jefe |
| `drop` | `i–VI–VII–i` · `VI–VII–i–i` | El "lift" de *Hopes and Dreams* |
| `break` | `VI–III–VII–i` a medio tiempo | Respirar antes de volver |
| `outro` | `i–VI–III–VII` con densidad decreciente | Cierre |

**Tempo:** rango 100–168 BPM, default 124.
**Swing:** 0.16 (sutil; el preset lo sube en `break`).

**Voces:**

| Voz | Timbre | Papel |
|---|---|---|
| `lead` | `pulse25` + vibrato + filtro ladder (`bob~`) | La melodía / el motivo |
| `bass` | `triangle` (estilo NES) | Ostinato sobre fundamentales, conduce el bajo |
| `chords` | `pulse50` ×2 desafinados | Stabs sincopados |
| `pad` | `saw` filtrada, tipo coro | Colchón, solo en `drop` y `outro` |
| `performer` | timbre del estilo, reservado | Gestos del hardware, disparo inmediato |

**Percusión:** bombo (seno con barrido de pitch), caja (ruido + `bp~` + cuerpo tonal),
hats (ruido + `hip~`). Sintetizada, sin muestras.

### 4.3 `motif.py` — el leitmotiv

El motivo guarda **grados relativos**, no notas MIDI, para sobrevivir a las modulaciones y
a los cambios de escala que vota la audiencia:

```python
@dataclass(frozen=True)
class MotifStep:
    degree: int        # desplazamiento en grados de la escala respecto a la tónica
    dur: int           # duración en semicorcheas
    accent: bool

@dataclass(frozen=True)
class Motif:
    steps: tuple[MotifStep, ...]
    name: str
```

Transformaciones (todas puras, devuelven un `Motif` nuevo):

| Operación | Efecto |
|---|---|
| `transpose(n)` | Desplaza `n` grados de la escala |
| `invert(axis)` | Refleja el contorno alrededor de un grado |
| `retrograde()` | Invierte el orden temporal |
| `augment(f)` / `diminish(f)` | Multiplica / divide las duraciones por `f ∈ {2, 4}` |
| `octave(n)` | ±1 o ±2 octavas |
| `reharmonize(chord)` | Ancla los pasos acentuados a tonos del acorde vigente |
| `ornament(level)` | Inserta notas de paso y bordaduras entre grados distantes |

Con esto, `transform_motif` de la IA puede pedir *"reexpón el motivo invertido, al doble
de duración, en la relativa mayor"*, que es literalmente la relación entre *Once Upon a
Time* y *His Theme*.

**Guardia de rango:** si una transformación deja notas fuera de `range_lo..range_hi` de la
voz, se pliegan por octavas hasta entrar. Nunca se descarta el motivo por rango.

### 4.4 `harmony.py`

- `chord_tones(scale, roman) -> list[int]` — grados romanos (`i`, `iv`, `V`, `VI`, `VII`,
  `III`, con `V` mayor forzado en contexto de menor armónica) a clases de altura.
- `chord_at(progression, bar) -> str` — qué acorde toca en el compás `bar`.
- `voice_lead(prev: list[int], chord: str, scale: str) -> list[int]` — elige la inversión
  cuya suma de distancias al voicing anterior es mínima. Sin esto, los acordes saltan.
- `is_chord_tone(note, chord, scale) -> bool` — lo usa `reharmonize` y el arreglista para
  decidir qué va en parte fuerte.

### 4.5 `arrangement.py`

```python
SECTIONS = ("intro", "verse", "build", "drop", "break", "outro")

@dataclass
class SectionPlan:
    name: str
    bars: int
    voices: frozenset[str]
    density: float          # 0..1, afecta cuántos pasos se llenan
    octave: int
    tempo_mode: str         # "normal" | "half" | "double"
    fill_on_last_bar: bool
```

Arco por defecto: `intro(4) → verse(8) → build(8) → drop(16) → break(4) → verse(8) →
drop(16) → outro(4)`, cíclico. El `Arranger` avanza solo al terminar los compases de la
sección; la IA puede forzar un salto con `set_section`, que **se aplica en el siguiente
límite de compás**, nunca a mitad.

**Juego de tempo** (lo pedido explícitamente):

- `tempo_ramp(to_bpm, bars)` — accelerando/ritardando interpolado por compás, acotado al
  `tempo_range` del estilo.
- `tempo_mode` `half`/`double` por sección — el reloj no cambia, cambia la subdivisión
  con la que el arreglista llena el compás.
- Golpe en seco (un compás de silencio con un solo acento) antes de un `drop`, marcado por
  `fill_on_last_bar` en `build`.

### 4.6 `sequencer.py` reescrito

Responsabilidad: reloj + render + despacho. Interfaz:

```python
class Sequencer:
    def render_bar(self, bar_index: int) -> Bar: ...        # puro, testeable, determinista
    async def run(self) -> None: ...                        # reloj + despacho + publish
```

`Bar` es una lista de `VoiceEvent(voice, step, note|notes, velocity, dur_ms)`. `render_bar`
es **puro dado el estado** — esa es la propiedad que hace posible el test dorado (§9) y
`render-jam.py`.

**Swing:** los pasos impares se retrasan `swing * (step_dur / 3)`. No se aplica a la
percusión de `hat` en `double` (se siente mecánico).

## 5. Pure Data

### 5.1 Estructura de archivos

Contradice CLAUDE.md §4 ("un solo `main.pd`"), así que **el contrato se actualiza antes de
escribir código** — como el propio contrato exige.

| Archivo | Contenido |
|---|---|
| `pd-patches/main.pd` | OSC in/out, routing, `[clone vs-voice 4]`, un `[vs-drums]`, mezclador por voz, cadena master, telemetría, GUI |
| `pd-patches/vs-voice.pd` | Una voz melódica. `$1` = índice de voz |
| `pd-patches/vs-drums.pd` | Bombo, caja, hats |

`main.pd` **se encoge** (~160 → ~70 objetos) y añadir una voz pasa a ser cambiar un
número. El historial del repo tiene dos bugs causados por edición manual de índices
(`2724a01`, `5088168`); esta estructura los hace estructuralmente improbables.

### 5.2 `vs-voice.pd`

Entrada (lista por el inlet de `[clone]`): `note velocity dur_ms timbre_id`.

- **Oscilador**: `[phasor~]` con tres ramas calculadas en paralelo y seleccionadas por una
  ganancia 0/1 suavizada con `[line~]` (el timbre cambia por sección/estilo, no por nota,
  así que el crossfade es gratis y evita clicks):
  - pulso con duty variable: `[phasor~] → [-~ duty] → [clip~ -0.001 0.001] → [*~ 500]`
  - triangular: `[phasor~] → [-~ 0.5] → [abs~] → [*~ 4] → [-~ 1]`
  - sierra: `[phasor~] → [-~ 0.5] → [*~ 2]`
- **Vibrato**: `[osc~ 5.5] → [*~ depth]` modulando la frecuencia antes del `[phasor~]`.
- **Envolvente**: `[vline~]` con ADSR derivado de `dur_ms`.
- **Salida**: `[throw~]` a un bus por voz. El destino se fija al cargar desde `$1`
  (`vs-bus-0` … `vs-bus-3`) mandándole un mensaje `set` al `[throw~]`. El método `set` de
  `throw~` no aparece en su help patch, así que **se verificó empíricamente** contra el Pd
  instalado: `throw~` lo acepta sin error, mientras que un método inventado produce
  `error: throw~: no method for '...'`.

Objetos verificados como vanilla en la instalación local (Pd 0.56-2): `abs~`, `max~`,
`min~`, `wrap~`, `pow~`, `expr~`, `clip~`, `cos~`, `phasor~`, `osc~`, `vline~`, `line~`,
`noise~`, `bp~`, `lop~`, `hip~`, `vcf~`, `slop~`, `biquad~`, `tabosc4~`, `tabread4~`,
`soundfiler`, `threshold~`, `env~`, `samphold~`, `delwrite~`, `delread4~`, `vd~`, `clone`,
`poly`, y en `extra/`: `bob~`, `rev1~`, `rev2~`, `rev3~`. **Cero externals, cero assets.**

### 5.3 `main.pd`

- `[catch~ vs-bus-0..3]` recoge las voces. **Solo la voz 0 (lead) pasa por `[bob~]`** —
  es un solver ODE y no vale gastarlo en el pad; el resto usa `[vcf~]`.
- Ganancia y paneo por voz.
- Cadena master: suma → distorsión (`[clip~]` con drive) → **delay sincronizado al tempo**
  (`delay_ms = 60000/bpm × 0.75`, corchea con puntillo — media identidad del género) →
  `[rev3~]` → limitador (`[clip~ -1 1]`) → `[dac~]`.
- Telemetría `[env~]` sin cambios.

### 5.4 OSC nuevo (documentar en `docs/osc-protocol.md` ANTES de implementar)

| Dirección | Argumentos |
|---|---|
| `/pd/trigger/voice` | `voice_idx note velocity dur_ms` |
| `/pd/trigger/chord` | `voice_idx note1 note2 note3 velocity dur_ms` |
| `/pd/trigger/drum` | `drum_id velocity` (0=bombo, 1=caja, 2=hat) |
| `/pd/set/voice/timbre` | `voice_idx timbre_id` |
| `/pd/set/voice/gain` | `voice_idx gain` |
| `/pd/set/style` | `style_id` |
| `/pd/set/section` | `section_name` |
| `/pd/set/swing` | `0..1` |

Se conserva `/pd/trigger/note` para los gestos del performer.

## 6. Navegador

### 6.1 `audio-engine.js` reescrito

Sigue sin dependencias, sin CDNs y sin build step (CLAUDE.md §3). Todo API nativa:

- **Pulsos con duty variable**: `PeriodicWave` con coeficientes de Fourier
  `aₙ = 2/(nπ)·sin(nπd)` para duty `d`. Banda limitada — de hecho más limpio que la
  versión de Pd, que aliasea a propósito.
- **Triangular NES**: `triangle` nativo + `WaveShaperNode` cuantizando a 16 pasos.
- **Distorsión**: `WaveShaperNode` con curva `tanh(k·x)`.
- **Percusión**: un `AudioBuffer` de ruido de 1 s reutilizado + `BiquadFilterNode` +
  envolventes de `GainNode`.
- **Master**: `DynamicsCompressorNode` + `GainNode`.
- Un `GainNode` por voz para que bajo, lead, acordes y batería tengan mezcla propia.

### 6.2 Agendado de compases

```
al recibir jam:bar:
  t0 = max(nextBarTime, ctx.currentTime + MIN_LEAD)   // MIN_LEAD = 0.12 s
  para cada evento: schedule(t0 + step * stepDur + swingOffset)
  nextBarTime = t0 + barDurationS
```

`MIN_LEAD` de 120 ms absorbe el jitter de red. Si un paquete llega tarde o se pierde,
`nextBarTime` queda en el pasado y el motor **resincroniza al compás siguiente**: se pierde
un compás, no se desfasa para siempre.

`jam:note_triggered` sigue existiendo y dispara inmediato — es el canal de los gestos del
performer.

### 6.3 Formato de `jam:bar` y presupuesto de 2 KB

Portal impone `content` ≤ 2048 B. Codificación en arrays, no en objetos:

```json
{"n":142,"bpm":124,"ms":1935,"sw":0.16,"s":"drop",
 "v":{"l":[[0,69,96,240],[3,72,72,180]],
      "b":[[0,45,110,460]],
      "c":[[0,[57,60,64],80,300]],
      "d":[[0,0,112],[4,1,96],[2,2,60]]}}
```

`n` compás · `ms` duración del compás · `sw` swing · `s` sección · voces `l`/`b`/`c`/`p`/`d`
· eventos `[step, nota, velocity, dur_ms]`.

Un compás denso de 4 voces ≈ 900–1400 B. **Guardia dura:** si el JSON supera **1900 B**,
se poda por prioridad (`pad` → `chords` → ornamentos del `lead`) y se loguea a nivel
`warning`. `PortalSDKAdapter.publish()` ya descarta lo que pase de 2048 B; esta guardia
evita llegar ahí.

## 7. La sala

### 7.1 Channels nuevos (documentar en `docs/portal-channels.md` ANTES de implementar)

| Channel | Dirección | Payload |
|---|---|---|
| `jam:chat` | cliente → bridge → rebroadcast | `{id, from, role, text, kind}` con `kind ∈ message\|hype\|request` |
| `jam:chat:typing` | cliente → bridge → rebroadcast | `{from}` — throttle 3 s, expira 5 s en el cliente |
| `jam:bar` | bridge → todos | §6.3 |

**El historial no viaja por un channel.** Un canal pub/sub no sabe dirigirse a un solo
cliente: sobre el WS local el bridge podría responderle a su socket, pero sobre Portal
haría falta el frame `direct`, que el adaptador no implementa — y difundir el historial a
toda la sala cada vez que entra alguien es un desperdicio. Se sirve por **HTTP**:
`GET /chat-history.json` desde `LocalPortalServer._process_request()`, junto a
`/portal-config.json`, que ya existe. La web lo pide una vez al cargar, sea cual sea el
transporte activo — y la página siempre se sirve desde el bridge, así que el endpoint
siempre es alcanzable.

`jam:note_triggered` se conserva **solo** para gestos del performer. Con esto el tráfico
por Portal baja: hoy una nota por mensaje a corcheas; con semicorcheas y 4 voces serían
~30 msg/s, por encima de los 18,6 msg/s medidos. Un `jam:bar` cada ~2 s lo resuelve.

### 7.2 Validación y moderación (`bridge/chat.py`)

El servidor puede quedar expuesto a internet entero con `start-all.ps1 -Tunnel`, así que
esto no es opcional:

- `text` recortado a **180 caracteres**; se descartan vacíos y solo-espacios.
- Se quitan caracteres de control (`\x00-\x1f` salvo nada; sin saltos de línea).
- **Rate limit: 1 mensaje cada 2 s por cliente** (deque de timestamps por `client_id`).
- `from` recortado a 24 caracteres y saneado.
- Buffer de historial acotado: `deque(maxlen=60)`.
- **En la web, todo texto de chat se pinta con `textContent`, nunca con `innerHTML`.**
  Esta regla se anota en CLAUDE.md §4 porque es una invariante de seguridad, no un detalle
  de estilo.

### 7.3 El chat como entrada musical

- `snapshot_for_ai()` gana
  `"chat": {"recent": [...8 últimos textos, ≤100 chars...], "pulse": {...}}`.
- `chat.chat_pulse(messages) -> {"energy": -1..1, "requests": {...}}` puntúa por palabras
  clave y emoji (`🔥`, "más fuerte", "sube", "epic" ↔ "tranqui", "suave", "bajá", "lento";
  y pedidos explícitos como "más grave", "cambia"). **Existe para que la ruta sin API key
  también reaccione al chat** — CLAUDE.md §7 exige que toda capacidad tenga fallback local.
- `rule_based_suggestion()` consulta `pulse` con prioridad entre los votos de FX y la
  variación estética: la sala pidiendo energía sube sección o densidad; pidiendo calma,
  baja a `break`.
- El `reasoning` de la IA se muestra **en el mismo hilo del chat** en la vista de escenario:
  la Directora es una participante más de la sala. Cero backend nuevo — es composición de
  UI sobre `jam:ai_director`, que ya existe.

### 7.4 Por qué efímero y no persistente en Portal

Portal ofrece mensajes persistentes (`POST /v1/channels/{id}/messages` → `{id, seq,
timestamp}`), orden por `seq`, historial (`GET /history?before={seq}&limit=50`) y un frame
`activity` nativo para "está escribiendo". Adoptar la persistencia haría de Portal la
**fuente de verdad** del chat, y CLAUDE.md §7 prohíbe que la demo dependa de un servicio
externo: el WS local no tiene persistencia, así que el buffer del bridge haría falta igual
para el camino de fallback. Un mecanismo idéntico en ambos transportes gana a dos
mecanismos divergentes.

Sí adoptamos la **semántica** de `activity` de Portal (throttle 3 s, expiración 5 s) aunque
viaje por canal propio, para que el comportamiento sea el mismo en los dos transportes.

**Ruta de upgrade** (fuera de alcance): si algún día se quiere historial entre sesiones,
`jam:chat` pasa a publicarse por el endpoint HTTP de Portal y el bridge lee `/history` al
arrancar, conservando el buffer local como caché.

## 8. Errores y fallbacks

Se añaden a la cadena de CLAUDE.md §7:

| Falla | Fallback |
|---|---|
| `style_id` desconocido o preset inválido | `determinacion` |
| Progresión propuesta por la IA que no está en el pool del estilo | se descarta; sigue la progresión vigente |
| Motivo transformado fuera del rango MIDI de la voz | se pliega por octavas hasta entrar; nunca se descarta |
| Sección desconocida | se ignora el salto, el arco sigue |
| `jam:bar` perdido o tardío | el navegador resincroniza en el compás siguiente (se pierde un compás, no el sincronismo) |
| Paquete `jam:bar` > 1900 B | poda por prioridad `pad` → `chords` → ornamentos |
| Chat inundado | rate limit por cliente + buffer acotado |
| `vs-voice.pd` / `vs-drums.pd` no cargan | `scripts/check-pd-loads.py` lo caza antes de la demo |
| Pd sin percusión | las voces melódicas siguen; el arreglo no depende de la batería |
| Reloj atrasado más de un compás | resincroniza al límite de compás, no recupera pasos |

El secuenciador sigue sin detenerse jamás.

## 9. Testing

**Unitarios nuevos** en `bridge/tests/`:

- `test_harmony.py` — grados romanos → clases de altura; `chord_at` cicla bien; la
  conducción de voces elige de verdad la inversión más cercana.
- `test_motif.py` — cada transformación conserva la longitud esperada; `retrograde` es
  involutiva; `reharmonize` deja los pasos acentuados en tonos del acorde; el plegado de
  rango nunca devuelve notas fuera de `range_lo..range_hi`.
- `test_arrangement.py` — el arco avanza y cicla; las voces se encienden y apagan por
  sección; el fill cae en el último compás.
- `test_style.py` — **todos** los presets registrados son internamente válidos: las
  escalas parsean, las progresiones usan grados conocidos, el rango de tempo cae dentro de
  `BPM_MIN..BPM_MAX`, los patrones de batería miden 16 pasos.
- `test_sequencer.py` — `render_bar` es determinista; los offsets de swing son correctos;
  el reloj no acumula deriva (simulado); **el paquete `jam:bar` más denso posible mide
  menos de 1900 B**.
- `test_chat.py` — recorte de longitud, rate limit, saneado de caracteres de control,
  replay de historial, y el scoring de `chat_pulse` en frases reales en español.

**Test dorado:** renderizar 16 compases de `determinacion` con estado y semilla fijos a una
partitura de texto y compararla con un fichero de referencia. Caza regresiones musicales
que ningún test unitario ve.

**Patches:**

- `scripts/validate-pd.py` extendido para aceptar globs (`pd-patches/*.pd`).
- `scripts/check-pd-loads.py` **nuevo** — abre cada patch en Pd headless
  (`pd -nogui -noaudio -stderr -open <patch> -send "pd quit"`) y falla si stderr contiene
  `couldn't create` o `no method for`. Esto caza objetos inexistentes y métodos mal
  escritos, que `validate-pd.py` no puede ver porque solo valida el grafo. Los flags y las
  cadenas de error están verificados contra el Pd 0.56-2 instalado.

**Herramienta de trabajo:**

- `scripts/render-jam.py` **nuevo** — renderiza N compases a un **Standard MIDI File**
  escrito con stdlib (~100 líneas; SMF formato 1 es simple). Permite iterar el estilo
  musical **sin levantar Pd, el bridge ni el navegador**, escuchándolo en cualquier
  reproductor. Es también la base del futuro "descargá el tema que compusimos entre todos".

## 10. Alternativas tecnológicas evaluadas y descartadas

| Opción | Veredicto |
|---|---|
| [Magenta RealTime 2](https://magenta.withgoogle.com/magenta-realtime-2) (2,4 B parámetros, Apache 2.0, pesos CC-BY, local) | **Fuera del audio path.** Genera audio, así que reemplazaría a Pd; su latencia de control es ~200 ms, **10× el presupuesto de 20 ms**, y en Windows exige GPU. Candidata a capa futura de "stems IA" fuera del instrumento. |
| MusicGen / AudioCraft, Stable Audio Open | Segundos a minutos por generación. Incompatible con "en vivo". |
| FluidSynth + soundfont GM | Auténtico ([Toby Fox compuso con soundfonts gratis y el 3xOsc de FL Studio](https://equipboard.com/albums/toby-fox-undertale-soundtrack)) y de baja latencia, pero es un **segundo motor de audio**, una DLL nativa en Windows y 30–150 MB de assets, con un modo de fallo nuevo justo antes de una demo. Si en el futuro se quieren muestras, Pd las carga con `soundfiler` sin motor extra. |
| `music21`, `mingus` | Dependencias pesadas para teoría que `music_engine.py` ya resuelve en stdlib y con tests. |
| Web MIDI API para artistas con teclado | **Aprobada, fase 4.** API nativa del navegador, cero dependencias. |
| Exportar la jam a MIDI | **Aprobada, fase 1** como `render-jam.py` (herramienta) y fase 4 como descarga para el público. |

## 11. Cambios al contrato (CLAUDE.md) — antes de escribir código

1. **§2** — la tabla de responsabilidades gana la capa de arreglo (sigue en el bridge; Pd
   sigue sin lógica musical).
2. **§4** — Pd deja de ser "un solo `main.pd`": pasa a `main.pd` + abstracciones
   instanciadas con `[clone]`. Se añade la invariante de que el texto de chat se pinta con
   `textContent`, nunca con `innerHTML`.
3. **§6** — mensajes OSC nuevos (§5.4), channels nuevos (§7.1) y el endpoint HTTP
   `GET /chat-history.json` junto a `/portal-config.json`.
4. **§8** — variables de entorno nuevas: `STYLE` (default `determinacion`),
   `CHAT_RATE_LIMIT_S` (2.0), `CHAT_HISTORY` (60).
5. `docs/osc-protocol.md` y `docs/portal-channels.md` se actualizan **antes** de
   implementar, como exige §6.

## 12. Fases

| Fase | Contenido | Entregable verificable |
|---|---|---|
| **1 · Motor musical** | `style.py`, `harmony.py`, `motif.py`, `arrangement.py`, `sequencer.py` reescrito, `validate_decision()` ampliado, `render-jam.py` | Tests verdes + un MIDI de 16 compases que **suene a Undertale** al reproducirlo |
| **2 · Motores de audio** | `vs-voice.pd`, `vs-drums.pd`, `main.pd` reescrito, OSC nuevo, `audio-engine.js` reescrito, `jam:bar` | Pd suena con 4 voces + batería; el navegador toca el mismo compás agendado |
| **3 · La sala** | `chat.py`, channels de chat, UI de chat, `chat_pulse`, hilo unificado con la Directora en escenario | Un mensaje de la audiencia cambia la música de forma audible |
| **4 · Extras** | Web MIDI in para artistas, descarga MIDI de la jam | Un teclado MIDI físico toca en la jam; un botón descarga el `.mid` de la sesión |

La fase 1 es la que más riesgo quita: produce música evaluable **por el oído** antes de
tocar una sola línea de Pd o del navegador.
