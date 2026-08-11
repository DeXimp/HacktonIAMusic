# Traspaso — Fase 1 del motor musical (sesión interrumpida 2026-08-10)

> Este archivo existe para que una sesión nueva retome exactamente donde se paró,
> sin volver a deducir nada. Leelo entero antes de tocar código.

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

## Estado: 2 de 8 tareas

| Tarea | Estado | Commits |
|---|---|---|
| T1 · `harmony.py` | ✅ **completa, revisión limpia** | `8c8495c` → `783c019` → `0a961d1` |
| T2 · `motif.py` | ⚠️ **implementada, revisión CON HALLAZGOS SIN ARREGLAR** | `1659bf7` |
| T3 · `style.py` | pendiente | — |
| T4 · `arrangement.py` | pendiente | — |
| T5 · `render.py` | pendiente | — |
| T6 · `sequencer.py` | pendiente | — |
| T7 · `midi.py` + `render-jam.py` | pendiente | — |
| T8 · test dorado | pendiente | — |

Tests: baseline 81 → **134 en verde** ahora mismo. Nada roto.

## ⛔ Punto exacto de reanudación

**T2 tiene tres hallazgos abiertos que NADIE arregló todavía.** El siguiente paso es
un *fix round 1/5*: retomar un implementador con estos hallazgos, y después una
re-revisión acotada del diff del fix.

### Hallazgo 1 — Important — `diminish(m, f=0)` lanza `ZeroDivisionError`
`bridge/motif.py:63`. `reharmonize` sí guarda su análogo (`scale_size <= 0`), `diminish`
no. Hoy es inalcanzable (nada la llama), **pero la Fase 2 la expone a la IA vía
`transform_motif`**, donde `f` puede venir de una decisión del modelo o de un voto sin
validar. Choca con CLAUDE.md §7 ("los errores se degradan, nunca se propagan a un
crash"). Fix trivial: acotar `f` antes de dividir.

### Hallazgo 2 — Important — `reharmonize` rompe "el tono de acorde más cercano"
`bridge/motif.py:78-79`. La ventana de candidatos es fija, `range(-3, 4)`, así que con
`chord_degrees=(0,2,4)` y `scale_size=7` solo cubre grados `[-21, 25]`. Fuera de ahí
devuelve algo que **no** es el más cercano:

```
degree=27  -> devuelve 25 (dist 2), el correcto es 28 (dist 1)
degree=-23 -> devuelve -21 (dist 2), el correcto es -24 (dist 1)
degree=32  -> devuelve 25, ¡pero 32 YA era tono del acorde! (una octava entera de error)
```

El grado 32 sale de algo tan normal como `octave(m, 4, 7)` sobre un motivo con un paso
acentuado en el grado 4. Verificado de punta a punta: vía `realize` produce **notas MIDI
distintas y peores** que no rearmonizar. Fix: derivar la ventana del rango real de grados
del motivo en vez de fijarla en ±3 octavas.

Ningún test lo detecta porque el invariante que sí testean (`best % scale_size` cae en
`chord_degrees`) se cumple siempre por construcción, incluso con el bug.

### Hallazgo 3 — Minor (diferido, no bloquea) — `fold_to_range` pierde la clase de altura
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
3. Los conteos de tests del plan están mal (decía 15 en T1 → eran 20; 22 en T2 → eran 27).
   Ignorá esos números y reportá el real.

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
.\.venv\Scripts\python -m unittest discover -s bridge\tests    # debe dar 134 OK
```

1. Invocá `superpowers:subagent-driven-development`. El ledger en
   `.superpowers/sdd/2026-08-10-fase1-motor-musical/progress.md` manda sobre tu memoria.
2. **Arrancá por el fix round 1/5 de T2** con los hallazgos 1 y 2 de arriba. El hallazgo 3
   va al ledger como diferido, no al loop.
3. Re-revisión acotada del diff del fix (`scripts/review-package PLAN BASE HEAD`).
4. Recién entonces seguí con T3.

Los scripts del proceso están en
`C:\Users\Administrador\.claude\plugins\cache\claude-plugins-official\superpowers\6.2.0\skills\subagent-driven-development\scripts\`
(`task-brief`, `review-package`, `sdd-workspace`).

**Modelos que funcionaron:** `haiku` para implementadores (el brief trae el código
completo, es transcripción + tests), `sonnet` para revisores. Los revisores en sonnet
encontraron todos los defectos reales; no bajes de ahí.

## El hito que importa

La Tarea 7 tiene un paso que no es opcional: renderizar 32 compases a `jam.mid` y
**escucharlo**. Si suena a arpegio plano en vez de a música con bajo, contratiempos y una
melodía que vuelve transformada, el renderizador tiene un bug y no hay que seguir hasta
arreglarlo. Ese es el criterio de éxito real de la Fase 1, no que los tests estén verdes.

## Después de la Fase 1

- **Fase 2 — motores de audio:** `vs-voice.pd`, `vs-drums.pd`, `main.pd` con `[clone]`, OSC
  multivoz, `audio-engine.js` con `PeriodicWave`, canal `jam:bar`, `validate_decision()`
  ampliado, `check-pd-loads.py`.
- **Fase 3 — la sala:** `chat.py`, canales de chat, UI, `chat_pulse`, hilo unificado con la
  Directora en escenario.
- **Fase 4 — extras:** Web MIDI in, descarga MIDI de la jam.

El microcontrolador sigue fuera de alcance por decisión del equipo: la integración va por
separado y se retoma después.
