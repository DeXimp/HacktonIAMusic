# Traspaso — Fase 1 del motor musical (COMPLETA 2026-08-13)

> Este archivo existe para que una sesión nueva retome exactamente donde se paró,
> sin volver a deducir nada. Leelo entero antes de tocar código.

## ⛔ LO ÚNICO QUE FALTA: escuchar `jam.mid`

Las 8 tareas están implementadas, revisadas y committeadas, y la suite está en
**266 tests verdes** (baseline 81). Pero el criterio de aceptación de la Fase 1
que fijó el equipo no son los tests: es **escuchar**. Eso no lo puede hacer un
agente.

```powershell
cd "C:\Users\Administrador\Documents\Github Repositories\HacktonIAMusic\HacktonIAMusic-fase1\virusynth"
.\.venv\Scripts\python scripts\render-jam.py --bars 32 --out jam.mid
start jam.mid
```

Tiene que oírse: un **bajo con ostinato**, **acordes en contratiempo**, **batería
que se densifica** hacia el build, y una **melodía que vuelve transformada**. Si
suena a arpegio plano, hay un bug en el renderizador: arreglarlo y **regenerar la
partitura dorada** (`python -m bridge.tests.test_golden_score --update`).

Las cuatro cosas se verificaron midiéndolas sobre los datos (están en el ledger,
sección Task 7) y todas están presentes. Lo que falta es el juicio de oído.

Después de escuchar, cerrar la rama: `feature/motor-musical-fase1` va 8 commits
por delante de `main` y **sin pushear** (los de T1 y T2 ya están en `main`).

## Dónde está todo

| Cosa | Ruta |
|---|---|
| **Spec aprobado** | `virusynth/docs/superpowers/specs/2026-08-10-motor-musical-y-sala-design.md` |
| **Plan de la Fase 1** | `virusynth/docs/superpowers/plans/2026-08-10-fase1-motor-musical.md` |
| **Ledger de ejecución** | `.superpowers/sdd/2026-08-10-fase1-motor-musical/progress.md` (git-ignored, vive solo en el worktree) |
| **Briefs e informes** | misma carpeta: `task-N-brief.md`, `task-N-report.md`, `review-*.diff` |
| **Worktree de trabajo** | `C:\Users\Administrador\Documents\Github Repositories\HacktonIAMusic\HacktonIAMusic-fase1` |
| **Rama** | `feature/motor-musical-fase1` (base `497aab9`) |
| **venv** | `virusynth/.venv` dentro del worktree, Python 3.13.5, deps instaladas |

El worktree se creó con `git worktree add` como directorio **hermano** del repo (no dentro
de `.claude/`, que no está en `.gitignore` y se acabaría commiteando). Sigue en disco.

## Estado: 8 de 8 tareas

| Tarea | Estado | Commits |
|---|---|---|
| T1 · `harmony.py` | ✅ **completa, revisión limpia** | `8c8495c` → `783c019` → `0a961d1` |
| T2 · `motif.py` | ✅ **completa, hallazgos cerrados** | `1659bf7` → `b416bb6` |
| T3 · `style.py` | ✅ completa | `883de9f` |
| T4 · `arrangement.py` | ✅ completa | `901f84e` |
| T5 · `render.py` | ✅ completa (1 defecto **crítico** del plan) | `49fca13` |
| T6 · `sequencer.py` | ✅ completa (+ regresión cerrada) | `c0cd4f8` → `27c344b` |
| T7 · `midi.py` + `render-jam.py` | ✅ código completo, **falta escuchar** | `1a28511` |
| T8 · test dorado | ✅ completa | `6a21b81` |

Tests: baseline 81 → **266 en verde**. Nada roto. El plan estimaba 99 tests nuevos;
los reales son 185, porque a cada tarea se le agregaron los que le faltaban.

### Los dos hallazgos que más importan de esta tanda

**T5 · CRÍTICO · el bajo tocaba notas que no estaban en el acorde.** La fórmula del
plan era `patch.range_lo + pcs[0]`, y `pcs[0]` es una clase de altura absoluta
(0=Do): sumarla a `range_lo` solo cae bien si `range_lo` es un Do. El bajo de
determinacion arranca en 33, que es un **La**, así que sobre la tónica A-C-E el bajo
tocaba **C#2 y F#2**, ninguna de las dos en el acorde. Los 8 acordes de los dos decks
menores mal; `arcade` se salvaba de casualidad porque su `range_lo` es 36, un Do.
Ningún test lo veía: el del plan solo comprobaba que la nota cayera dentro de 33-57,
y 42 cae. Fix: `_lowest_with_pc`, que mide el intervalo desde `range_lo` y no desde
Do. Ahora hay tres tests que exigen que el bajo toque el acorde.

**T6 · regresión propia · los patrones de artistas remotos dejaron de sonar.** El
secuenciador viejo era el **único** lector de `jam.active_pattern`. Al reescribirlo
quedó huérfano: `main.py` seguía aceptándolos y recuantizándolos y la web seguía
teniendo su botón, pero no sonaba nada. Cerrado el mismo día por
`RenderContext.artist_pattern` (ruling de Bruce), así que además entra al MIDI
exportado. **No suena en intro/break/outro**, porque esas secciones no llevan lead.

### Hallazgo 1 — Important — ✅ CERRADO — `diminish(m, f=0)` lanzaba `ZeroDivisionError`
`bridge/motif.py`. Guarda `f <= 0 → devolver el motivo intacto`, calcada de la que
`reharmonize` ya tenía para `scale_size`. Se **extendió a `augment`** por el mismo motivo de
Fase 2: no crasheaba, pero con `f=0` aplastaba todas las duraciones a 1 en silencio, que
para un motor musical es peor que fallar. Esa extensión es una desviación deliberada
respecto al hallazgo, que solo mencionaba `diminish`.

### Hallazgo 2 — Important — ✅ CERRADO — `reharmonize` rompía "el tono de acorde más cercano"
La ventana de candidatos era fija, `range(-3, 4)`: con `chord_degrees=(0,2,4)` y
`scale_size=7` solo cubría grados `[-21, 25]`, y fuera de ahí mentía —
`27 → 25` (correcto 28), `-23 → -21` (correcto -24), y en el peor caso `32 → 25`
**moviendo una octava entera un grado que ya era tono del acorde** (vía `realize`:
MIDI 112 → 100, daño real y audible). El grado 32 lo produce algo tan común como
`octave(m, 4, 7)`.

**No se arregló como decía el informe.** El informe proponía "derivar la ventana del rango
real de grados del motivo"; eso sigue siendo una ventana, solo que más grande, y hay que
calcularla. En vez de eso se eliminó: por cada grado del acorde solo **dos** candidatos
pueden ganar, los que enmarcan al grado, y salen de una división entera
(`k = (degree - c) // scale_size`). Exacto para grados arbitrariamente lejanos y O(1) por
paso en vez de O(ventana). Helper privado `_nearest_chord_tone`; la superficie pública no
cambió.

Verificación **independiente de los tests**, en un proceso aparte y contra fuerza bruta
(la lección de T1: el mismo agente escribe test e implementación, y si comparten el error
de concepto pasan igual): 16 227 casos (`scale_size` 5/6/7/12 × 8 formas de acorde,
incluyendo duplicadas y desordenadas × grados −300..300) → **0 desacuerdos con el óptimo**;
grados 10⁶ y 10¹² → distancia ≤ 3 y siempre en el acorde; 401 tonos de acorde → 0 se
movieron; y los 47 grados de la ventana vieja `[-21, 25]` → **0 cambios de comportamiento**,
o sea cero regresión en lo que ya funcionaba.

### Hallazgo 3 — Minor (diferido, sigue abierto, no bloquea) — `fold_to_range` pierde la clase de altura
`bridge/motif.py:117-126`. Los contadores de guarda (16 y 32 iteraciones) se agotan para
notas a más de 192 semitonos de `lo`, y entonces el `max(lo, min(hi, note))` final hace un
clamp silencioso que rompe la promesa del docstring. **No cuelga y nunca devuelve fuera de
rango** — eso quedó verificado. Inalcanzable hoy porque el único llamador (`realize`)
alimenta desde `scale_notes(scale, 0, 127)`.

## Lección que cambió cómo hay que trabajar aquí

**El texto del plan tiene errores de aritmética musical.** No es hipotético: T1 llegó a
revisión con cuatro defectos que venían del plan, no del implementador — incluido uno
crítico que emitía notas MIDI inválidas, y un test que consagraba una respuesta incorrecta
como correcta.

Consecuencias prácticas para la sesión que siga:

1. **A los revisores hay que pedirles explícitamente que verifiquen la aritmética a mano**,
   no que confíen en que los tests pasan. Tests e implementación los escribe el mismo
   agente desde el mismo brief: si comparten el error de concepto, pasan igual.
2. **A los implementadores hay que decirles que paren y pregunten** si un valor esperado no
   les cuadra, en vez de forzar la implementación para que el test pase.
3. Los conteos del proceso están mal, van 3 de 3: el plan decía 15 tests en T1 → eran 20,
   y 22 en T2 → eran 27; el informe del review de T2 contó "12 símbolos públicos" en
   `motif.py` → son 13 (se le pasó `scale_time`). Ninguno fue sustantivo, pero no cites
   esos números: contalos vos y reportá el real.

## Decisiones ya tomadas (no volver a preguntarlas)

- **Chat**: público, visible por todos, **y la IA lo lee** y reacciona musicalmente.
- **Estilo**: motor de estilos genérico, `determinacion` (Undertale/Deltarune) por defecto.
- **Forma**: arco de secciones automático, la IA decide los saltos y los juegos de tempo.
- **Pd**: crece con `[clone]` + abstracciones, no editando índices a mano.
- **Navegador**: compases por adelantado (`jam:bar`) agendados con `start(when)`.
- **Chat/transporte**: efímero + buffer de historial en el bridge (no la persistencia de
  Portal, que haría de un servicio externo la fuente de verdad).
- **API sin cablear**: se mantienen `motif.transpose/invert/retrograde/diminish/octave`,
  `style.allows_progression` y `Arranger.jump_to` aunque en la Fase 1 no tengan llamador —
  son la costura de la Fase 2. **Avisale a cada revisor** para que no gaste rondas.

## Tres desviaciones deliberadas respecto al spec

1. `render_bar` vive en `bridge/render.py`, no en `sequencer.py`.
2. `validate_decision()` ampliado y el vocabulario nuevo de la IA se movieron a la Fase 2,
   junto al código que los aplica.
3. El secuenciador nuevo despacha a Pd **solo la voz `lead`** por el `/pd/trigger/note`
   existente, para que el escenario no quede mudo entre fases.

## Cómo retomar, paso a paso

```powershell
cd "C:\Users\Administrador\Documents\Github Repositories\HacktonIAMusic\HacktonIAMusic-fase1\virusynth"
.\.venv\Scripts\python -m unittest discover -s bridge\tests    # debe dar 266 OK
```

1. **Escuchar `jam.mid`** (arriba). Es lo único pendiente.
2. Cerrar la rama con `superpowers:finishing-a-development-branch`.
3. Después, la Fase 2. El ledger
   `.superpowers/sdd/2026-08-10-fase1-motor-musical/progress.md` manda sobre tu memoria.

**Sobre el proceso:** T1 y T2 se hicieron con `superpowers:subagent-driven-development`
(implementadores en `haiku`, revisores en `sonnet` — los revisores encontraron todos los
defectos reales). T3 a T8 se hicieron **inline, sin subagentes**, por instrucción de
sesión de Bruce de no despachar agentes. Lo que hizo el trabajo en las dos modalidades no
fue el subagente sino la **verificación independiente**: recalcular la aritmética musical
en un proceso aparte, contra fuerza bruta o contra un modelo de referencia escrito por
separado, en vez de confiar en que los tests pasen. Los tests los escribe el mismo que
implementa; si comparten el error de concepto, pasan igual. Así salieron el crítico del
bajo en T5, la deriva del reloj en T6 y los dos Important de T2.

**Y probar los tests en las dos direcciones.** Cada fix se validó rompiéndolo a mano para
confirmar que el test nuevo lo caza: el bajo (falla con el repro exacto), el reloj (528 ms
de deriva en 12 compases), el test dorado (un punto de velocity), la tónica de arcade.
Un test que no se vio fallar no prueba nada.

## Después de la Fase 1

- **Fase 2 — motores de audio:** `vs-voice.pd`, `vs-drums.pd`, `main.pd` con `[clone]`, OSC
  multivoz, `audio-engine.js` con `PeriodicWave`, canal `jam:bar`, `validate_decision()`
  ampliado, `check-pd-loads.py`.
- **Fase 3 — la sala:** `chat.py`, canales de chat, UI, `chat_pulse`, hilo unificado con la
  Directora en escenario.
- **Fase 4 — extras:** Web MIDI in, descarga MIDI de la jam.

El microcontrolador sigue fuera de alcance por decisión del equipo: la integración va por
separado y se retoma después.
