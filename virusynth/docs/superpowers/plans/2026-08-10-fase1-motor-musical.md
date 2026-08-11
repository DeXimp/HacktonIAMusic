# Fase 1 — Motor musical de género (bridge) · Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reemplazar el secuenciador monofónico de ViruSynth por un motor de composición de cinco capas (estilo → armonía → motivo → arreglo → groove) que produzca música con forma propia en el estilo Undertale/Deltarune, evaluable por el oído como archivo MIDI antes de tocar Pd o el navegador.

**Architecture:** Cinco módulos nuevos en `bridge/`, todos stdlib puro y sin I/O, apilados sobre el `music_engine.py` existente. El renderizador es una **función pura** `render_bar(ctx, bar_index) -> Bar` — esa pureza es lo que hace posibles el test dorado y la exportación a MIDI. El reloj asíncrono queda aparte, en `sequencer.py`, y despacha eventos a Pd.

**Tech Stack:** Python 3.11+ (desarrollo 3.13.5), stdlib exclusivamente (`dataclasses`, `re`, `struct`, `asyncio`, `unittest`). Cero dependencias nuevas.

## Global Constraints

Copiadas literalmente del contrato (`virusynth/CLAUDE.md`) y del spec. **Aplican a todas las tareas de este plan.**

- **El LLM NUNCA está en el audio path.** Nada de este plan hace llamadas de red.
- **Python**: `snake_case`, type hints, `dataclasses` de stdlib (no pydantic), módulos de una responsabilidad.
- **Sin dependencias nuevas sin actualizar el contrato.** Este plan no añade ninguna.
- **Logging** con `logging`; loggers existentes: `SEQ`, `OSC`, `SERIAL`, `PORTAL`, `IA`, `WEB`.
- **El bridge nunca muere por un import** y **el secuenciador no se detiene jamás**: todo error se loguea y se degrada.
- `BPM_MIN, BPM_MAX = 60, 180` · `SCALE_CHANGE_COOLDOWN_S = 20.0` · `DEFAULT_SCALE = "Am_pentatonic"` · `DEFAULT_ROOT = 69` · `DEFAULT_BPM = 112` (ver `bridge/config.py`).
- **Modos de escala válidos** (`music_engine.SCALE_INTERVALS`): `major`, `minor`, `minor_pentatonic`, `major_pentatonic`, `dorian`, `mixolydian`, `lydian`, `phrygian`, `blues`, `harmonic_minor`.
- **Tests**: `unittest` de stdlib en `bridge/tests/`, ejecutados con `.venv\Scripts\python -m unittest discover -s bridge\tests`.
- **Comandos desde `virusynth/`**, PowerShell en Windows. El intérprete es `.venv\Scripts\python.exe`.
- **Todo el texto de cara al usuario va en español** (nombres de estilos, `reasoning`, mensajes de CLI).

## Desviaciones respecto al spec (deliberadas, para que cada commit quede desplegable)

El spec §12 pone tres cosas en la Fase 1 que aquí se mueven o se matizan. Están señaladas porque son decisiones, no descuidos:

1. **`render_bar` vive en `bridge/render.py`, no en `sequencer.py`.** Son dos responsabilidades distintas: una función pura muy testeada y un reloj asíncrono casi intesteable. Separarlas mantiene los dos archivos enfocados.
2. **`validate_decision()` ampliado y el vocabulario nuevo de la IA se mueven a la Fase 2.** Si se validan aquí acciones como `set_section` sin que exista la ruta que las aplica, la IA emitiría decisiones que no hacen nada y el feed le mentiría a la audiencia. Van junto al código que las aplica.
3. **El `Sequencer` nuevo despacha a Pd solo la voz `lead`, por el `/pd/trigger/note` que ya existe.** Bajo, acordes, pad y batería se componen y salen al MIDI, pero no suenan en Pd hasta la Fase 2, que añade el OSC multivoz y las abstracciones. Así **el sistema en vivo nunca queda mudo entre fases**: al terminar la Fase 1 el escenario ya suena mejor que hoy (melodía con arco y armonía real en vez de un arpegio fijo) sobre el `main.pd` actual, sin haberlo tocado.

## Estructura de archivos

| Archivo | Responsabilidad |
|---|---|
| `bridge/harmony.py` **(nuevo)** | Grados romanos → notas del acorde, conducción de voces. No sabe de ritmo. |
| `bridge/motif.py` **(nuevo)** | El leitmotiv: motivo en grados relativos + transformaciones puras + realización a MIDI. No sabe qué acorde suena. |
| `bridge/style.py` **(nuevo)** | Presets de género (datos) + patrones de batería + registro. No decide nada. |
| `bridge/arrangement.py` **(nuevo)** | El arco de secciones. No elige notas. |
| `bridge/render.py` **(nuevo)** | `render_bar()` puro: junta las cuatro capas en un `Bar`. Sin I/O, sin tiempo real. |
| `bridge/sequencer.py` **(reescrito)** | Reloj de semicorcheas sin deriva + despacho. Sin teoría musical. |
| `bridge/main.py` **(modificado)** | Construye el `Sequencer` nuevo. |
| `scripts/render-jam.py` **(nuevo)** | Renderiza N compases a un Standard MIDI File con stdlib. |
| `bridge/tests/test_harmony.py` … `test_render.py`, `test_golden_score.py` **(nuevos)** | Tests. |
| `bridge/tests/golden/determinacion_16.txt` **(nuevo)** | Partitura de referencia del test dorado. |
| `CLAUDE.md` **(modificado)** | §2: la capa de arreglo entra en la tabla de responsabilidades. |

---

### Task 1: `harmony.py` — grados romanos y conducción de voces

**Files:**
- Create: `bridge/harmony.py`
- Test: `bridge/tests/test_harmony.py`

**Interfaces:**
- Consumes: `music_engine.parse_scale(name) -> tuple[int, str]`, `music_engine.NOTE_NAMES`, `music_engine.ScaleError` (ya existen).
- Produces:
  - `parse_roman(roman: str) -> tuple[int, str]` — `("VI") -> (6, "maj")`
  - `chord_pitch_classes(scale: str, roman: str) -> tuple[int, ...]`
  - `chord_at(progression: Sequence[str], bar: int) -> str`
  - `chord_notes(scale: str, roman: str, lo: int, hi: int) -> list[int]`
  - `voice_lead(prev: Sequence[int], scale: str, roman: str, lo: int, hi: int) -> list[int]`
  - `is_chord_tone(note: int, scale: str, roman: str) -> bool`
  - `chord_degrees(scale: str, roman: str) -> tuple[int, ...]` — posiciones del acorde **dentro de la escala**, para `motif.reharmonize`
  - `HarmonyError(ValueError)`

- [ ] **Step 1: Escribir el test que falla**

Crear `bridge/tests/test_harmony.py`:

```python
import unittest

from bridge import harmony


class TestParseRoman(unittest.TestCase):
    def test_minusculas_son_menores(self):
        self.assertEqual(harmony.parse_roman("i"), (1, "min"))
        self.assertEqual(harmony.parse_roman("iv"), (4, "min"))

    def test_mayusculas_son_mayores(self):
        self.assertEqual(harmony.parse_roman("VI"), (6, "maj"))
        self.assertEqual(harmony.parse_roman("VII"), (7, "maj"))
        self.assertEqual(harmony.parse_roman("III"), (3, "maj"))

    def test_septimas(self):
        self.assertEqual(harmony.parse_roman("V7"), (5, "dom7"))
        self.assertEqual(harmony.parse_roman("i7"), (1, "min7"))

    def test_disminuido(self):
        self.assertEqual(harmony.parse_roman("ii°"), (2, "dim"))

    def test_roman_invalido(self):
        with self.assertRaises(harmony.HarmonyError):
            harmony.parse_roman("viii")
        with self.assertRaises(harmony.HarmonyError):
            harmony.parse_roman("")


class TestChordPitchClasses(unittest.TestCase):
    def test_tonica_menor_en_la_menor(self):
        # A minor: A C E = 9 0 4
        self.assertEqual(harmony.chord_pitch_classes("A_minor", "i"), (9, 0, 4))

    def test_sexto_grado_mayor_en_la_menor(self):
        # VI en La menor = Fa mayor: F A C = 5 9 0
        self.assertEqual(harmony.chord_pitch_classes("A_minor", "VI"), (5, 9, 0))

    def test_quinto_mayor_lleva_sensible(self):
        # V mayor en La menor = Mi mayor: E G# B = 4 8 11.
        # El G# (8) es la sensible de la menor armonica: es el medio tono
        # que empuja hacia la tonica y define el sonido de los temas de jefe.
        self.assertEqual(harmony.chord_pitch_classes("A_minor", "V"), (4, 8, 11))

    def test_escala_pentatonica_usa_el_marco_menor(self):
        # Am_pentatonic no tiene 7 grados; para acordes se usa el marco de
        # La menor natural, que es lo que haria cualquier musico.
        self.assertEqual(harmony.chord_pitch_classes("Am_pentatonic", "i"), (9, 0, 4))

    def test_escala_invalida(self):
        with self.assertRaises(harmony.HarmonyError):
            harmony.chord_pitch_classes("H_minor", "i")


class TestChordAt(unittest.TestCase):
    def test_cicla_la_progresion(self):
        prog = ("i", "VI", "III", "VII")
        self.assertEqual(harmony.chord_at(prog, 0), "i")
        self.assertEqual(harmony.chord_at(prog, 3), "VII")
        self.assertEqual(harmony.chord_at(prog, 4), "i")
        self.assertEqual(harmony.chord_at(prog, 9), "VI")

    def test_progresion_vacia(self):
        self.assertEqual(harmony.chord_at((), 3), "i")


class TestChordNotes(unittest.TestCase):
    def test_solo_notas_del_acorde_en_el_rango(self):
        notes = harmony.chord_notes("A_minor", "i", 57, 72)
        self.assertEqual(notes, [57, 60, 64, 69, 72])

    def test_rango_invertido_da_lista_vacia(self):
        self.assertEqual(harmony.chord_notes("A_minor", "i", 72, 57), [])


class TestVoiceLead(unittest.TestCase):
    def test_elige_el_voicing_mas_cercano_al_anterior(self):
        prev = [60, 64, 67]                      # Do mayor
        result = harmony.voice_lead(prev, "A_minor", "VI", 55, 79)
        # F A C: desde 60,64,67 lo mas cercano es 65,69,72 -> total 15 semitonos.
        self.assertEqual(result, [65, 69, 72])

    def test_sin_voicing_previo_no_revienta(self):
        result = harmony.voice_lead([], "A_minor", "i", 55, 79)
        self.assertEqual(len(result), 3)
        for note in result:
            self.assertGreaterEqual(note, 55)
            self.assertLessEqual(note, 79)

    def test_resultado_siempre_ordenado(self):
        result = harmony.voice_lead([79, 55, 60], "A_minor", "VII", 55, 79)
        self.assertEqual(result, sorted(result))


class TestIsChordTone(unittest.TestCase):
    def test_reconoce_tonos_del_acorde_en_cualquier_octava(self):
        self.assertTrue(harmony.is_chord_tone(69, "A_minor", "i"))
        self.assertTrue(harmony.is_chord_tone(45, "A_minor", "i"))
        self.assertFalse(harmony.is_chord_tone(71, "A_minor", "i"))


class TestChordDegrees(unittest.TestCase):
    def test_triada_de_tonica_cae_en_grados_0_2_4(self):
        # En una escala de 7 notas la triada de tonica ocupa los grados 0, 2 y 4.
        self.assertEqual(harmony.chord_degrees("A_minor", "i"), (0, 2, 4))

    def test_grados_de_un_acorde_ajeno_a_la_escala(self):
        # V en La menor = Mi mayor (E G# B). E es el grado 4 y B el grado 1 de
        # la escala; el G# NO esta en La menor natural, asi que se omite en vez
        # de inventar un grado que la escala no tiene.
        self.assertEqual(harmony.chord_degrees("A_minor", "V"), (1, 4))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Ejecutar el test para verificar que falla**

Run: `.venv\Scripts\python -m unittest bridge.tests.test_harmony -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'bridge.harmony'`

- [ ] **Step 3: Implementar `bridge/harmony.py`**

```python
"""Capa armonica de ViruSynth: grados romanos -> acordes concretos.

Se apoya en music_engine.py (escalas, clases de altura) y no lo duplica.
Stdlib puro, sin I/O: todo aqui es testeable sin audio ni red.

Por que un "marco diatonico": una pentatonica no tiene siete grados, asi que
no se le pueden pedir acordes directamente. Para armonizar se usa el marco
mayor o menor natural que corresponde a la raiz de la escala -- exactamente
lo que hace un musico que toca una melodia pentatonica sobre acordes menores.
"""
from __future__ import annotations

import re
from typing import Sequence

from . import music_engine

# Semitonos de cada grado respecto a la tonica, por marco diatonico.
DEGREE_MINOR = {1: 0, 2: 2, 3: 3, 4: 5, 5: 7, 6: 8, 7: 10}
DEGREE_MAJOR = {1: 0, 2: 2, 3: 4, 4: 5, 5: 7, 6: 9, 7: 11}

# Modos que se armonizan con el marco menor; el resto, con el mayor.
MINOR_MODES = frozenset({"minor", "minor_pentatonic", "blues", "dorian",
                         "phrygian", "harmonic_minor"})

QUALITY_INTERVALS: dict[str, tuple[int, ...]] = {
    "maj": (0, 4, 7),
    "min": (0, 3, 7),
    "dim": (0, 3, 6),
    "aug": (0, 4, 8),
    "maj7": (0, 4, 7, 11),
    "min7": (0, 3, 7, 10),
    "dom7": (0, 4, 7, 10),
}

_NUMERALS = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7}
_ROMAN_RE = re.compile(r"^(b?)([ivIV]+)(°|o|\+)?(7)?$")


class HarmonyError(ValueError):
    pass


def parse_roman(roman: str) -> tuple[int, str]:
    """'VI' -> (6, 'maj'); 'i7' -> (1, 'min7'); 'ii°' -> (2, 'dim')."""
    match = _ROMAN_RE.match((roman or "").strip())
    if not match:
        raise HarmonyError(f"Grado romano invalido: {roman!r}")
    _flat, numeral, symbol, seventh = match.groups()
    degree = _NUMERALS.get(numeral.lower())
    if degree is None:
        raise HarmonyError(f"Grado romano invalido: {roman!r}")
    if symbol in ("°", "o"):
        quality = "dim"
    elif symbol == "+":
        quality = "aug"
    elif numeral.isupper():
        quality = "dom7" if seventh else "maj"
    else:
        quality = "min7" if seventh else "min"
    return degree, quality


def _frame(scale: str) -> tuple[int, dict[int, int]]:
    try:
        root_pc, mode = music_engine.parse_scale(scale)
    except music_engine.ScaleError as exc:
        raise HarmonyError(str(exc)) from exc
    return root_pc, (DEGREE_MINOR if mode in MINOR_MODES else DEGREE_MAJOR)


def chord_pitch_classes(scale: str, roman: str) -> tuple[int, ...]:
    """Clases de altura del acorde, con la fundamental primero."""
    root_pc, degrees = _frame(scale)
    degree, quality = parse_roman(roman)
    flat = 1 if (roman or "").strip().startswith("b") else 0
    chord_root = (root_pc + degrees[degree] - flat) % 12
    return tuple((chord_root + i) % 12 for i in QUALITY_INTERVALS[quality])


def chord_at(progression: Sequence[str], bar: int) -> str:
    """Que acorde toca en el compas `bar`. Progresion vacia -> tonica."""
    if not progression:
        return "i"
    return progression[bar % len(progression)]


def chord_notes(scale: str, roman: str, lo: int, hi: int) -> list[int]:
    pcs = set(chord_pitch_classes(scale, roman))
    return [n for n in range(lo, hi + 1) if n % 12 in pcs]


def is_chord_tone(note: int, scale: str, roman: str) -> bool:
    return note % 12 in set(chord_pitch_classes(scale, roman))


def voice_lead(prev: Sequence[int], scale: str, roman: str,
               lo: int, hi: int) -> list[int]:
    """Voicing del acorde lo mas cerca posible del anterior.

    Sin esto los acordes saltan de octava entre compases y suena a maquina.
    Determinista: en empate gana la nota mas grave.
    """
    pcs = chord_pitch_classes(scale, roman)
    middle = lo + (hi - lo) // 2
    anchors = list(prev) if prev else []
    while len(anchors) < len(pcs):
        anchors.append(anchors[-1] if anchors else middle)

    voicing: list[int] = []
    for pc, anchor in zip(pcs, anchors):
        candidates = [n for n in range(lo, hi + 1) if n % 12 == pc]
        voicing.append(min(candidates, key=lambda n: (abs(n - anchor), n))
                       if candidates else anchor)
    return sorted(voicing)


def chord_degrees(scale: str, roman: str) -> tuple[int, ...]:
    """Posiciones del acorde DENTRO de la escala (no en semitonos).

    Las notas del acorde que no pertenecen a la escala se omiten: es preferible
    un acorde incompleto a inventar un grado que la escala no tiene.
    """
    scale_pcs = sorted(music_engine.pitch_classes(scale))
    root_pc, _ = _frame(scale)
    order = [(pc - root_pc) % 12 for pc in scale_pcs]
    order.sort()
    chord = chord_pitch_classes(scale, roman)
    degrees = []
    for pc in chord:
        rel = (pc - root_pc) % 12
        if rel in order:
            degrees.append(order.index(rel))
    return tuple(sorted(set(degrees)))
```

- [ ] **Step 4: Ejecutar el test para verificar que pasa**

Run: `.venv\Scripts\python -m unittest bridge.tests.test_harmony -v`
Expected: PASS, 15 tests.

- [ ] **Step 5: Commit**

```bash
git add bridge/harmony.py bridge/tests/test_harmony.py
git commit -m "feat(bridge): capa armonica -- grados romanos, acordes y conduccion de voces"
```

---

### Task 2: `motif.py` — el leitmotiv

**Files:**
- Create: `bridge/motif.py`
- Test: `bridge/tests/test_motif.py`

**Interfaces:**
- Consumes: `music_engine.scale_notes(scale, low, high) -> list[int]` (ya existe).
- Produces:
  - `MotifStep(degree: int, dur: int, accent: bool = False)` — dataclass frozen
  - `Motif(steps: tuple[MotifStep, ...], name: str = "")` — frozen, con `.length -> int`
  - `transpose(m, n) -> Motif` · `invert(m, axis=0) -> Motif` · `retrograde(m) -> Motif`
  - `scale_time(m, factor: float) -> Motif` · `augment(m, f=2) -> Motif` · `diminish(m, f=2) -> Motif`
  - `octave(m, n, degrees_per_octave) -> Motif`
  - `reharmonize(m, chord_degrees, scale_size) -> Motif`
  - `ornament(m, level=1) -> Motif`
  - `fold_to_range(note, lo, hi) -> int`
  - `realize(m, scale, root, lo, hi) -> list[tuple[int, int, int, bool]]` — `(offset_16ths, midi, dur, accent)`

- [ ] **Step 1: Escribir el test que falla**

Crear `bridge/tests/test_motif.py`:

```python
import unittest

from bridge import motif as M

SEED = M.Motif(steps=(
    M.MotifStep(0, 2, True),
    M.MotifStep(2, 2, False),
    M.MotifStep(4, 4, False),
    M.MotifStep(3, 2, False),
    M.MotifStep(2, 4, True),
), name="prueba")


class TestMotifBasics(unittest.TestCase):
    def test_length_suma_las_duraciones(self):
        self.assertEqual(SEED.length, 14)

    def test_el_motivo_es_inmutable(self):
        with self.assertRaises(Exception):
            SEED.steps = ()


class TestTransformaciones(unittest.TestCase):
    def test_transpose_desplaza_todos_los_grados(self):
        result = M.transpose(SEED, 2)
        self.assertEqual([s.degree for s in result.steps], [2, 4, 6, 5, 4])

    def test_transpose_conserva_duraciones_y_acentos(self):
        result = M.transpose(SEED, 3)
        self.assertEqual([s.dur for s in result.steps], [2, 2, 4, 2, 4])
        self.assertEqual([s.accent for s in result.steps],
                         [True, False, False, False, True])

    def test_invert_refleja_el_contorno(self):
        result = M.invert(SEED, axis=0)
        self.assertEqual([s.degree for s in result.steps], [0, -2, -4, -3, -2])

    def test_invert_es_involutiva(self):
        self.assertEqual(M.invert(M.invert(SEED)), SEED)

    def test_retrograde_invierte_el_orden(self):
        result = M.retrograde(SEED)
        self.assertEqual([s.degree for s in result.steps], [2, 3, 4, 2, 0])

    def test_retrograde_es_involutiva(self):
        self.assertEqual(M.retrograde(M.retrograde(SEED)), SEED)

    def test_augment_duplica_las_duraciones(self):
        result = M.augment(SEED, 2)
        self.assertEqual([s.dur for s in result.steps], [4, 4, 8, 4, 8])
        self.assertEqual(result.length, 28)

    def test_diminish_reduce_pero_nunca_baja_de_uno(self):
        result = M.diminish(SEED, 4)
        self.assertEqual([s.dur for s in result.steps], [1, 1, 1, 1, 1])

    def test_octave_desplaza_una_octava_de_grados(self):
        result = M.octave(SEED, 1, degrees_per_octave=7)
        self.assertEqual([s.degree for s in result.steps], [7, 9, 11, 10, 9])


class TestReharmonize(unittest.TestCase):
    def test_los_pasos_acentuados_caen_en_tonos_del_acorde(self):
        # Triada de tonica en una escala de 7 notas: grados 0, 2, 4.
        result = M.reharmonize(SEED, chord_degrees=(0, 2, 4), scale_size=7)
        for step in result.steps:
            if step.accent:
                self.assertIn(step.degree % 7, (0, 2, 4))

    def test_los_pasos_sin_acento_no_se_tocan(self):
        result = M.reharmonize(SEED, chord_degrees=(0, 2, 4), scale_size=7)
        original = [s.degree for s in SEED.steps]
        for i, step in enumerate(result.steps):
            if not SEED.steps[i].accent:
                self.assertEqual(step.degree, original[i])

    def test_sin_tonos_de_acorde_devuelve_el_motivo_intacto(self):
        self.assertEqual(M.reharmonize(SEED, (), 7), SEED)


class TestOrnament(unittest.TestCase):
    def test_inserta_notas_de_paso_en_saltos_grandes(self):
        result = M.ornament(SEED, level=1)
        self.assertGreater(len(result.steps), len(SEED.steps))

    def test_conserva_la_duracion_total(self):
        result = M.ornament(SEED, level=1)
        self.assertEqual(result.length, SEED.length)

    def test_es_determinista(self):
        self.assertEqual(M.ornament(SEED, 1), M.ornament(SEED, 1))

    def test_nivel_cero_no_hace_nada(self):
        self.assertEqual(M.ornament(SEED, 0), SEED)


class TestFoldToRange(unittest.TestCase):
    def test_sube_por_octavas_lo_que_queda_grave(self):
        self.assertEqual(M.fold_to_range(40, 60, 72), 64)

    def test_baja_por_octavas_lo_que_queda_agudo(self):
        self.assertEqual(M.fold_to_range(90, 60, 72), 66)

    def test_deja_intacto_lo_que_ya_entra(self):
        self.assertEqual(M.fold_to_range(65, 60, 72), 65)

    def test_rango_mas_estrecho_que_una_octava_no_cuelga(self):
        result = M.fold_to_range(40, 60, 64)
        self.assertGreaterEqual(result, 60)
        self.assertLessEqual(result, 64)


class TestRealize(unittest.TestCase):
    def test_el_grado_cero_es_la_tonica(self):
        events = M.realize(SEED, "A_minor", root=69, lo=57, hi=81)
        self.assertEqual(events[0][1], 69)

    def test_los_offsets_se_acumulan(self):
        events = M.realize(SEED, "A_minor", root=69, lo=57, hi=81)
        self.assertEqual([e[0] for e in events], [0, 2, 4, 8, 10])

    def test_todas_las_notas_caen_en_la_escala(self):
        from bridge import music_engine
        pcs = music_engine.pitch_classes("A_minor")
        for _off, note, _dur, _acc in M.realize(SEED, "A_minor", 69, 57, 81):
            self.assertIn(note % 12, pcs)

    def test_todas_las_notas_caen_dentro_del_rango(self):
        for _off, note, _dur, _acc in M.realize(SEED, "A_minor", 69, 60, 72):
            self.assertGreaterEqual(note, 60)
            self.assertLessEqual(note, 72)

    def test_motivo_vacio_devuelve_lista_vacia(self):
        self.assertEqual(M.realize(M.Motif(steps=()), "A_minor", 69, 57, 81), [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Ejecutar el test para verificar que falla**

Run: `.venv\Scripts\python -m unittest bridge.tests.test_motif -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'bridge.motif'`

- [ ] **Step 3: Implementar `bridge/motif.py`**

```python
"""El leitmotiv de ViruSynth: un motivo y sus transformaciones.

Lo que hace que Undertale suene a Undertale no es el timbre: es que una misma
celula melodica vuelve transformada en contextos distintos. Este modulo es esa
maquina.

Los pasos guardan GRADOS RELATIVOS de la escala, no notas MIDI, para que el
motivo sobreviva a las modulaciones y a los cambios de escala que vota la
audiencia. La conversion a notas concretas ocurre solo en realize().

Todas las transformaciones son puras y deterministas: devuelven un Motif nuevo
y nunca usan azar, porque de eso depende que el test dorado sea estable.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Sequence

from . import music_engine


@dataclass(frozen=True)
class MotifStep:
    degree: int          # desplazamiento en grados de escala respecto a la tonica
    dur: int             # duracion en semicorcheas
    accent: bool = False


@dataclass(frozen=True)
class Motif:
    steps: tuple[MotifStep, ...] = ()
    name: str = ""

    @property
    def length(self) -> int:
        return sum(s.dur for s in self.steps)


def transpose(m: Motif, n: int) -> Motif:
    return replace(m, steps=tuple(replace(s, degree=s.degree + n) for s in m.steps))


def invert(m: Motif, axis: int = 0) -> Motif:
    return replace(m, steps=tuple(replace(s, degree=2 * axis - s.degree)
                                  for s in m.steps))


def retrograde(m: Motif) -> Motif:
    return replace(m, steps=tuple(reversed(m.steps)))


def scale_time(m: Motif, factor: float) -> Motif:
    """Multiplica las duraciones. Nunca deja un paso por debajo de 1."""
    return replace(m, steps=tuple(replace(s, dur=max(1, round(s.dur * factor)))
                                  for s in m.steps))


def augment(m: Motif, f: int = 2) -> Motif:
    return scale_time(m, float(f))


def diminish(m: Motif, f: int = 2) -> Motif:
    return scale_time(m, 1.0 / float(f))


def octave(m: Motif, n: int, degrees_per_octave: int) -> Motif:
    return transpose(m, n * degrees_per_octave)


def reharmonize(m: Motif, chord_degrees: Sequence[int], scale_size: int) -> Motif:
    """Ancla los pasos ACENTUADOS al tono de acorde mas cercano.

    Los pasos sin acento se dejan tal cual: son las notas de paso que dan
    movimiento. Si el acorde no aporta ningun grado, el motivo vuelve intacto.
    """
    if not chord_degrees or scale_size <= 0:
        return m
    candidates = [c + scale_size * k
                  for k in range(-3, 4) for c in chord_degrees]
    new_steps = []
    for step in m.steps:
        if step.accent:
            best = min(candidates, key=lambda c: (abs(c - step.degree), c))
            new_steps.append(replace(step, degree=best))
        else:
            new_steps.append(step)
    return replace(m, steps=tuple(new_steps))


def ornament(m: Motif, level: int = 1) -> Motif:
    """Inserta notas de paso entre grados distantes, conservando la duracion.

    Un paso se parte en dos mitades solo si dura >= 2 semicorcheas y el salto
    hasta el paso siguiente es de 2 grados o mas. Determinista por diseno.
    """
    result = m
    for _ in range(max(0, level)):
        new_steps: list[MotifStep] = []
        steps = result.steps
        for i, step in enumerate(steps):
            nxt = steps[i + 1] if i + 1 < len(steps) else None
            gap = abs(nxt.degree - step.degree) if nxt is not None else 0
            if nxt is not None and gap >= 2 and step.dur >= 2:
                first = step.dur // 2
                new_steps.append(replace(step, dur=first))
                middle = step.degree + (1 if nxt.degree > step.degree else -1)
                new_steps.append(MotifStep(degree=middle,
                                           dur=step.dur - first, accent=False))
            else:
                new_steps.append(step)
        result = replace(result, steps=tuple(new_steps))
    return result


def fold_to_range(note: int, lo: int, hi: int) -> int:
    """Pliega por octavas hasta entrar en [lo, hi]. Nunca descarta la nota."""
    if lo > hi:
        return note
    guard = 0
    while note < lo and guard < 16:
        note += 12
        guard += 1
    while note > hi and guard < 32:
        note -= 12
        guard += 1
    return max(lo, min(hi, note))


def realize(m: Motif, scale: str, root: int,
            lo: int, hi: int) -> list[tuple[int, int, int, bool]]:
    """Grados -> notas MIDI concretas. Devuelve (offset, nota, dur, accent)."""
    if not m.steps:
        return []
    notes = music_engine.scale_notes(scale, 0, 127)
    if not notes:
        return []
    base = min(range(len(notes)), key=lambda i: (abs(notes[i] - root), i))

    events: list[tuple[int, int, int, bool]] = []
    offset = 0
    for step in m.steps:
        idx = max(0, min(len(notes) - 1, base + step.degree))
        events.append((offset, fold_to_range(notes[idx], lo, hi),
                       step.dur, step.accent))
        offset += step.dur
    return events
```

- [ ] **Step 4: Ejecutar el test para verificar que pasa**

Run: `.venv\Scripts\python -m unittest bridge.tests.test_motif -v`
Expected: PASS, 22 tests.

- [ ] **Step 5: Commit**

```bash
git add bridge/motif.py bridge/tests/test_motif.py
git commit -m "feat(bridge): motor de leitmotiv -- motivo en grados relativos y transformaciones puras"
```

---

### Task 3: `style.py` — presets de género

**Files:**
- Create: `bridge/style.py`
- Test: `bridge/tests/test_style.py`

**Interfaces:**
- Consumes: `motif.Motif`, `motif.MotifStep` (Task 2); `music_engine.parse_scale`; `config.BPM_MIN`, `config.BPM_MAX`.
- Produces:
  - `VoicePatch(timbre, range_lo, range_hi, vibrato=0.0, gain=1.0)` — frozen. **No lleva campo `octave`**: el registro de cada voz ya lo fija su par `range_lo`/`range_hi`, y un segundo campo para lo mismo es configuración muerta.
  - `StyleDeck(id, name, scales, progressions, tempo_range, default_bpm, swing, voices, drum_patterns, motif_seeds, fx)` — frozen
  - `DRUM_PATTERNS: dict[str, dict[str, str]]` — 16 caracteres por instrumento, `x` golpe / `.` silencio
  - `VOICE_NAMES = ("lead", "bass", "chords", "pad")`
  - `STYLES: dict[str, StyleDeck]` con `determinacion`, `nocturno`, `arcade`
  - `DEFAULT_STYLE_ID = "determinacion"`
  - `get_style(style_id: str) -> StyleDeck` — id desconocido → `determinacion`
  - `allows_progression(style: StyleDeck, section: str, progression: Sequence[str]) -> bool`

- [ ] **Step 1: Escribir el test que falla**

Crear `bridge/tests/test_style.py`:

```python
import unittest

from bridge import config, harmony, music_engine, style


class TestRegistro(unittest.TestCase):
    def test_determinacion_es_el_estilo_por_defecto(self):
        self.assertEqual(style.DEFAULT_STYLE_ID, "determinacion")
        self.assertIn("determinacion", style.STYLES)

    def test_hay_mas_de_un_estilo(self):
        # El motor tiene que ser generico, no una envoltura de un solo preset.
        self.assertGreaterEqual(len(style.STYLES), 3)

    def test_get_style_cae_al_default_si_no_conoce_el_id(self):
        self.assertIs(style.get_style("no-existe"), style.STYLES["determinacion"])
        self.assertIs(style.get_style(""), style.STYLES["determinacion"])

    def test_get_style_devuelve_el_pedido(self):
        self.assertIs(style.get_style("arcade"), style.STYLES["arcade"])


class TestTodosLosPresetsSonValidos(unittest.TestCase):
    """Un preset roto solo se nota en vivo. Este test lo caza antes."""

    def test_las_escalas_parsean(self):
        for sid, deck in style.STYLES.items():
            self.assertTrue(deck.scales, f"{sid} no declara escalas")
            for scale in deck.scales:
                music_engine.parse_scale(scale)   # lanza si es invalida

    def test_las_progresiones_usan_grados_conocidos(self):
        for sid, deck in style.STYLES.items():
            for section, pool in deck.progressions.items():
                self.assertTrue(pool, f"{sid}/{section} tiene el pool vacio")
                for progression in pool:
                    for roman in progression:
                        harmony.parse_roman(roman)   # lanza si es invalido

    def test_el_rango_de_tempo_cabe_en_los_limites_del_sistema(self):
        for sid, deck in style.STYLES.items():
            lo, hi = deck.tempo_range
            self.assertLess(lo, hi, f"{sid} tiene el rango de tempo invertido")
            self.assertGreaterEqual(lo, config.BPM_MIN)
            self.assertLessEqual(hi, config.BPM_MAX)
            self.assertGreaterEqual(deck.default_bpm, lo)
            self.assertLessEqual(deck.default_bpm, hi)

    def test_los_patrones_de_bateria_existen_y_miden_16_pasos(self):
        for sid, deck in style.STYLES.items():
            for section, pattern_id in deck.drum_patterns.items():
                self.assertIn(pattern_id, style.DRUM_PATTERNS,
                              f"{sid}/{section} apunta a {pattern_id!r}")
        for pid, kit in style.DRUM_PATTERNS.items():
            for instrument, row in kit.items():
                self.assertEqual(len(row), 16,
                                 f"{pid}/{instrument} mide {len(row)}, no 16")
                self.assertTrue(set(row) <= {"x", "."},
                                f"{pid}/{instrument} tiene caracteres raros")

    def test_cada_estilo_define_las_cuatro_voces(self):
        for sid, deck in style.STYLES.items():
            for name in style.VOICE_NAMES:
                self.assertIn(name, deck.voices, f"{sid} no define {name}")
            for name, patch in deck.voices.items():
                self.assertLess(patch.range_lo, patch.range_hi)
                self.assertGreaterEqual(patch.range_lo, 0)
                self.assertLessEqual(patch.range_hi, 127)

    def test_cada_estilo_trae_al_menos_un_motivo_semilla(self):
        for sid, deck in style.STYLES.items():
            self.assertTrue(deck.motif_seeds, f"{sid} no trae motivos")
            for seed in deck.motif_seeds:
                self.assertGreater(seed.length, 0)

    def test_el_swing_esta_entre_0_y_dos_tercios(self):
        for sid, deck in style.STYLES.items():
            self.assertGreaterEqual(deck.swing, 0.0)
            self.assertLessEqual(deck.swing, 0.66)

    def test_los_fx_estan_normalizados(self):
        for sid, deck in style.STYLES.items():
            for name, value in deck.fx.items():
                self.assertIn(name, ("reverb", "delay", "distortion"))
                self.assertGreaterEqual(value, 0.0)
                self.assertLessEqual(value, 1.0)


class TestDeterminacion(unittest.TestCase):
    def test_cubre_todas_las_secciones_del_arco(self):
        deck = style.STYLES["determinacion"]
        for section in ("intro", "verse", "build", "drop", "break", "outro"):
            self.assertIn(section, deck.progressions)
            self.assertIn(section, deck.drum_patterns)

    def test_el_build_incluye_el_V_mayor_con_sensible(self):
        # Ese medio tono que empuja hacia la tonica es la firma del genero.
        deck = style.STYLES["determinacion"]
        romans = {r for prog in deck.progressions["build"] for r in prog}
        self.assertIn("V", romans)

    def test_el_bajo_es_triangular_y_el_lead_es_pulso(self):
        deck = style.STYLES["determinacion"]
        self.assertEqual(deck.voices["bass"].timbre, "triangle")
        self.assertEqual(deck.voices["lead"].timbre, "pulse25")


class TestAllowsProgression(unittest.TestCase):
    def test_acepta_una_progresion_del_pool(self):
        deck = style.STYLES["determinacion"]
        allowed = deck.progressions["verse"][0]
        self.assertTrue(style.allows_progression(deck, "verse", allowed))

    def test_rechaza_una_progresion_ajena(self):
        deck = style.STYLES["determinacion"]
        self.assertFalse(style.allows_progression(deck, "verse", ("V", "V", "V", "V")))

    def test_rechaza_una_seccion_desconocida(self):
        deck = style.STYLES["determinacion"]
        self.assertFalse(style.allows_progression(deck, "no-existe", ("i",)))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Ejecutar el test para verificar que falla**

Run: `.venv\Scripts\python -m unittest bridge.tests.test_style -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'bridge.style'`

- [ ] **Step 3: Implementar `bridge/style.py`**

```python
"""Presets de genero de ViruSynth. Datos, no logica.

Un StyleDeck declara la paleta con la que compone el motor: que escalas suenan
al estilo, que progresiones caben en cada seccion, en que rango de tempo vive,
con que timbres, con que bateria y con que motivos semilla. El motor
(render.py) es generico; cambiar de genero es cambiar de deck.

"determinacion" es el preset Undertale/Deltarune y el default del sistema.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from .motif import Motif, MotifStep

VOICE_NAMES = ("lead", "bass", "chords", "pad")
DEFAULT_STYLE_ID = "determinacion"

# 16 semicorcheas por patron. 'x' golpe, '.' silencio.
DRUM_PATTERNS: dict[str, dict[str, str]] = {
    "silencio": {"kick": "................",
                 "snare": "................",
                 "hat":   "................"},
    "sparse":   {"kick": "x.......x.......",
                 "snare": "................",
                 "hat":   "..x...x...x...x."},
    "basico":   {"kick": "x.......x.......",
                 "snare": "....x.......x...",
                 "hat":   "x.x.x.x.x.x.x.x."},
    "driving":  {"kick": "x..x..x.x..x....",
                 "snare": "....x.......x...",
                 "hat":   "xxxxxxxxxxxxxxxx"},
    "medio":    {"kick": "x...............",
                 "snare": "........x.......",
                 "hat":   "..x...x...x...x."},
    "fill":     {"kick": "x.......x...x...",
                 "snare": "..x.x.x.x.xx.xxx",
                 "hat":   "................"},
}


@dataclass(frozen=True)
class VoicePatch:
    # El registro de la voz lo fija el par range_lo/range_hi: no hace falta un
    # campo `octave` aparte, seria la misma informacion dos veces.
    timbre: str          # pulse25 | pulse50 | triangle | saw | bell | choir
    range_lo: int
    range_hi: int
    vibrato: float = 0.0
    gain: float = 1.0


@dataclass(frozen=True)
class StyleDeck:
    id: str
    name: str
    scales: tuple[str, ...]
    progressions: dict[str, tuple[tuple[str, ...], ...]]
    tempo_range: tuple[int, int]
    default_bpm: int
    swing: float
    voices: dict[str, VoicePatch]
    drum_patterns: dict[str, str]
    motif_seeds: tuple[Motif, ...]
    fx: dict[str, float] = field(default_factory=dict)


# --- determinacion (Undertale / Deltarune) ---------------------------------
# Armonia eolica con las cadencias caracteristicas del repertorio:
#   i-VI-III-VII      el loop de base
#   i-iv-V-V          ese V lleva sensible (menor armonica): el medio tono
#                     que empuja hacia i esta en todos los temas de jefe
#   VI-VII-i          el "lift" de los climax
_DETERMINACION = StyleDeck(
    id="determinacion",
    name="Determinacion",
    scales=("Am_pentatonic", "A_minor", "D_minor", "E_minor",
            "A_harmonic_minor", "D_dorian"),
    progressions={
        "intro":  (("i", "VI", "III", "VII"),),
        "verse":  (("i", "VI", "III", "VII"), ("i", "VII", "VI", "VII")),
        "build":  (("iv", "VII", "III", "VI"), ("i", "iv", "V", "V")),
        "drop":   (("i", "VI", "VII", "i"), ("VI", "VII", "i", "i")),
        "break":  (("VI", "III", "VII", "i"),),
        "outro":  (("i", "VI", "III", "VII"),),
    },
    tempo_range=(100, 168),
    default_bpm=124,
    swing=0.16,
    voices={
        "lead":   VoicePatch("pulse25", range_lo=64, range_hi=91,
                             vibrato=0.35, gain=1.0),
        "bass":   VoicePatch("triangle", range_lo=33, range_hi=57,
                             vibrato=0.0, gain=0.95),
        "chords": VoicePatch("pulse50", range_lo=52, range_hi=76,
                             vibrato=0.0, gain=0.6),
        "pad":    VoicePatch("choir", range_lo=48, range_hi=72,
                             vibrato=0.1, gain=0.45),
    },
    drum_patterns={
        "intro": "sparse", "verse": "basico", "build": "driving",
        "drop": "driving", "break": "medio", "outro": "sparse",
    },
    motif_seeds=(
        Motif(steps=(MotifStep(0, 2, True), MotifStep(2, 2), MotifStep(4, 4),
                     MotifStep(3, 2), MotifStep(2, 4, True)),
              name="determinacion"),
        Motif(steps=(MotifStep(4, 2, True), MotifStep(3, 2), MotifStep(2, 2),
                     MotifStep(0, 6, True), MotifStep(-3, 4)),
              name="memoria"),
    ),
    fx={"reverb": 0.38, "delay": 0.30, "distortion": 0.12},
)

# --- nocturno (lento, emotivo, sin percusion al principio) ------------------
_NOCTURNO = StyleDeck(
    id="nocturno",
    name="Nocturno",
    scales=("E_minor", "A_minor", "D_dorian", "A_harmonic_minor"),
    progressions={
        "intro":  (("i", "VI"),),
        "verse":  (("i", "VI", "iv", "VII"),),
        "build":  (("iv", "V", "VI", "VII"),),
        "drop":   (("VI", "VII", "i", "i"),),
        "break":  (("i", "i"),),
        "outro":  (("i", "VI"),),
    },
    tempo_range=(62, 96),
    default_bpm=76,
    swing=0.0,
    voices={
        "lead":   VoicePatch("bell", range_lo=64, range_hi=88,
                             vibrato=0.15, gain=0.9),
        "bass":   VoicePatch("triangle", range_lo=33, range_hi=55,
                             gain=0.85),
        "chords": VoicePatch("choir", range_lo=52, range_hi=74,
                             gain=0.5),
        "pad":    VoicePatch("saw", range_lo=45, range_hi=69,
                             gain=0.4),
    },
    drum_patterns={
        "intro": "silencio", "verse": "sparse", "build": "basico",
        "drop": "basico", "break": "silencio", "outro": "silencio",
    },
    motif_seeds=(
        Motif(steps=(MotifStep(0, 4, True), MotifStep(1, 4),
                     MotifStep(2, 8, True)), name="nocturno"),
    ),
    fx={"reverb": 0.62, "delay": 0.35, "distortion": 0.0},
)

# --- arcade (rapido, luminoso, chiptune de accion) --------------------------
_ARCADE = StyleDeck(
    id="arcade",
    name="Arcade",
    scales=("C_major", "G_mixolydian", "C_pentatonic", "D_dorian"),
    progressions={
        "intro":  (("I", "V"),),
        "verse":  (("I", "V", "vi", "IV"),),
        "build":  (("IV", "V", "IV", "V"),),
        "drop":   (("I", "IV", "V", "I"),),
        "break":  (("vi", "IV"),),
        "outro":  (("I", "V"),),
    },
    tempo_range=(132, 176),
    default_bpm=152,
    swing=0.0,
    voices={
        "lead":   VoicePatch("pulse25", range_lo=67, range_hi=95,
                             vibrato=0.2, gain=1.0),
        "bass":   VoicePatch("pulse50", range_lo=36, range_hi=57,
                             gain=0.9),
        "chords": VoicePatch("pulse50", range_lo=55, range_hi=79,
                             gain=0.55),
        "pad":    VoicePatch("saw", range_lo=48, range_hi=72,
                             gain=0.35),
    },
    drum_patterns={
        "intro": "basico", "verse": "driving", "build": "driving",
        "drop": "driving", "break": "medio", "outro": "basico",
    },
    motif_seeds=(
        Motif(steps=(MotifStep(0, 1, True), MotifStep(2, 1), MotifStep(4, 2),
                     MotifStep(2, 1), MotifStep(4, 1), MotifStep(6, 2, True)),
              name="arcade"),
    ),
    fx={"reverb": 0.22, "delay": 0.18, "distortion": 0.05},
)

STYLES: dict[str, StyleDeck] = {
    _DETERMINACION.id: _DETERMINACION,
    _NOCTURNO.id: _NOCTURNO,
    _ARCADE.id: _ARCADE,
}


def get_style(style_id: str) -> StyleDeck:
    """Un id desconocido no puede tumbar la jam: cae al default."""
    return STYLES.get((style_id or "").strip().lower(), STYLES[DEFAULT_STYLE_ID])


def allows_progression(deck: StyleDeck, section: str,
                       progression: Sequence[str]) -> bool:
    """Solo se aceptan progresiones del pool de esa seccion en ese estilo."""
    pool = deck.progressions.get(section)
    if not pool:
        return False
    return tuple(progression) in pool
```

- [ ] **Step 4: Ejecutar el test para verificar que pasa**

Run: `.venv\Scripts\python -m unittest bridge.tests.test_style -v`
Expected: PASS, 17 tests.

- [ ] **Step 5: Commit**

```bash
git add bridge/style.py bridge/tests/test_style.py
git commit -m "feat(bridge): presets de genero -- determinacion (Undertale/Deltarune), nocturno y arcade"
```

---

### Task 4: `arrangement.py` — el arco de secciones

**Files:**
- Create: `bridge/arrangement.py`
- Test: `bridge/tests/test_arrangement.py`

**Interfaces:**
- Consumes: nada del proyecto (stdlib puro).
- Produces:
  - `SECTIONS: tuple[str, ...]` = `("intro","verse","build","drop","break","outro")`
  - `SectionPlan(name, bars, voices: frozenset[str], density: float, octave: int, tempo_mode: str, fill_on_last_bar: bool)` — frozen
  - `DEFAULT_ARC: tuple[SectionPlan, ...]`
  - `Arranger(arc=DEFAULT_ARC)` con `.section -> SectionPlan`, `.bar_in_section -> int`, `.advance() -> None`, `.jump_to(name) -> bool`, `.is_last_bar() -> bool`

- [ ] **Step 1: Escribir el test que falla**

Crear `bridge/tests/test_arrangement.py`:

```python
import unittest

from bridge import arrangement as A


class TestDefaultArc(unittest.TestCase):
    def test_empieza_en_intro(self):
        self.assertEqual(A.DEFAULT_ARC[0].name, "intro")

    def test_todas_las_secciones_del_arco_son_conocidas(self):
        for plan in A.DEFAULT_ARC:
            self.assertIn(plan.name, A.SECTIONS)

    def test_todas_las_secciones_duran_al_menos_un_compas(self):
        for plan in A.DEFAULT_ARC:
            self.assertGreaterEqual(plan.bars, 1)

    def test_el_drop_es_la_seccion_mas_densa(self):
        drop = next(p for p in A.DEFAULT_ARC if p.name == "drop")
        intro = next(p for p in A.DEFAULT_ARC if p.name == "intro")
        self.assertGreater(drop.density, intro.density)

    def test_el_pad_solo_aparece_en_drop_y_outro(self):
        for plan in A.DEFAULT_ARC:
            if "pad" in plan.voices:
                self.assertIn(plan.name, ("drop", "outro"))

    def test_los_modos_de_tempo_son_validos(self):
        for plan in A.DEFAULT_ARC:
            self.assertIn(plan.tempo_mode, ("normal", "half", "double"))


class TestArranger(unittest.TestCase):
    def test_arranca_en_la_primera_seccion(self):
        arranger = A.Arranger()
        self.assertEqual(arranger.section.name, "intro")
        self.assertEqual(arranger.bar_in_section, 0)

    def test_advance_avanza_dentro_de_la_seccion(self):
        arranger = A.Arranger()
        arranger.advance()
        self.assertEqual(arranger.section.name, "intro")
        self.assertEqual(arranger.bar_in_section, 1)

    def test_al_agotar_los_compases_pasa_a_la_siguiente_seccion(self):
        arranger = A.Arranger()
        for _ in range(arranger.section.bars):
            arranger.advance()
        self.assertEqual(arranger.section.name, A.DEFAULT_ARC[1].name)
        self.assertEqual(arranger.bar_in_section, 0)

    def test_el_arco_cicla(self):
        arranger = A.Arranger()
        total = sum(p.bars for p in A.DEFAULT_ARC)
        for _ in range(total):
            arranger.advance()
        self.assertEqual(arranger.section.name, "intro")
        self.assertEqual(arranger.bar_in_section, 0)

    def test_is_last_bar_solo_en_el_ultimo_compas(self):
        arranger = A.Arranger()
        bars = arranger.section.bars
        for _ in range(bars - 1):
            self.assertFalse(arranger.is_last_bar())
            arranger.advance()
        self.assertTrue(arranger.is_last_bar())

    def test_jump_to_salta_y_reinicia_el_contador(self):
        arranger = A.Arranger()
        arranger.advance()
        self.assertTrue(arranger.jump_to("drop"))
        self.assertEqual(arranger.section.name, "drop")
        self.assertEqual(arranger.bar_in_section, 0)

    def test_jump_to_a_una_seccion_desconocida_no_cambia_nada(self):
        arranger = A.Arranger()
        arranger.advance()
        self.assertFalse(arranger.jump_to("no-existe"))
        self.assertEqual(arranger.section.name, "intro")
        self.assertEqual(arranger.bar_in_section, 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Ejecutar el test para verificar que falla**

Run: `.venv\Scripts\python -m unittest bridge.tests.test_arrangement -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'bridge.arrangement'`

- [ ] **Step 3: Implementar `bridge/arrangement.py`**

```python
"""El arco de la cancion: que seccion suena y con que voces.

Sin esto la jam es un loop infinito. Con esto tiene intro, tension, climax y
respiro -- que es lo que separa "un tema" de "un secuenciador encendido".

Este modulo NO elige notas: solo dice que voces viven en cada seccion, con que
densidad, en que octava y con que modo de tempo. Las notas las pone render.py.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

SECTIONS = ("intro", "verse", "build", "drop", "break", "outro")


@dataclass(frozen=True)
class SectionPlan:
    name: str
    bars: int
    voices: frozenset[str]
    density: float          # 0..1: cuantos pasos del compas se llenan
    octave: int             # desplazamiento global de octava
    tempo_mode: str         # normal | half | double
    fill_on_last_bar: bool


DEFAULT_ARC: tuple[SectionPlan, ...] = (
    SectionPlan("intro", 4, frozenset({"bass", "chords"}),
                0.35, 0, "normal", False),
    SectionPlan("verse", 8, frozenset({"lead", "bass", "chords"}),
                0.55, 0, "normal", False),
    SectionPlan("build", 8, frozenset({"lead", "bass", "chords"}),
                0.75, 0, "normal", True),
    SectionPlan("drop", 16, frozenset({"lead", "bass", "chords", "pad"}),
                1.0, 1, "normal", False),
    SectionPlan("break", 4, frozenset({"chords"}),
                0.3, 0, "half", False),
    SectionPlan("verse", 8, frozenset({"lead", "bass", "chords"}),
                0.6, 0, "normal", False),
    SectionPlan("drop", 16, frozenset({"lead", "bass", "chords", "pad"}),
                1.0, 1, "normal", False),
    SectionPlan("outro", 4, frozenset({"bass", "pad"}),
                0.3, 0, "normal", False),
)


class Arranger:
    """Recorre el arco compas a compas. La IA puede forzar saltos."""

    def __init__(self, arc: Sequence[SectionPlan] = DEFAULT_ARC) -> None:
        self._arc = tuple(arc) or DEFAULT_ARC
        self._index = 0
        self._bar = 0

    @property
    def section(self) -> SectionPlan:
        return self._arc[self._index]

    @property
    def bar_in_section(self) -> int:
        return self._bar

    def is_last_bar(self) -> bool:
        return self._bar == self.section.bars - 1

    def advance(self) -> None:
        self._bar += 1
        if self._bar >= self.section.bars:
            self._bar = 0
            self._index = (self._index + 1) % len(self._arc)

    def jump_to(self, name: str) -> bool:
        """Salta a la primera seccion con ese nombre. False si no existe."""
        for i, plan in enumerate(self._arc):
            if plan.name == name:
                self._index = i
                self._bar = 0
                return True
        return False
```

- [ ] **Step 4: Ejecutar el test para verificar que pasa**

Run: `.venv\Scripts\python -m unittest bridge.tests.test_arrangement -v`
Expected: PASS, 13 tests.

- [ ] **Step 5: Commit**

```bash
git add bridge/arrangement.py bridge/tests/test_arrangement.py
git commit -m "feat(bridge): arco de secciones -- intro/verso/build/drop/break/outro"
```

---

### Task 5: `render.py` — el renderizador puro

**Files:**
- Create: `bridge/render.py`
- Test: `bridge/tests/test_render.py`

**Interfaces:**
- Consumes: `harmony.chord_at`, `harmony.voice_lead`, `harmony.chord_pitch_classes`, `harmony.chord_degrees` (Task 1); `motif.reharmonize`, `motif.realize`, `motif.fold_to_range` (Task 2); `style.StyleDeck`, `style.DRUM_PATTERNS` (Task 3); `arrangement.SectionPlan` (Task 4); `music_engine.pitch_classes`.
- Produces:
  - `DRUM_IDS = {"kick": 0, "snare": 1, "hat": 2}`
  - `VoiceEvent(voice: str, step: int, notes: tuple[int, ...], velocity: int, dur_steps: int)` — frozen
  - `Bar(index: int, bpm: int, ms: int, swing: float, section: str, events: tuple[VoiceEvent, ...])` — frozen
  - `RenderContext(scale, root, bpm, deck, section, bar_in_section, progression, motif, is_last_bar, prev_voicing)` — dataclass mutable
  - `render_bar(ctx: RenderContext, bar_index: int) -> Bar`
  - `step_ms(bpm: int) -> float` · `bar_ms(bpm: int) -> int`

- [ ] **Step 1: Escribir el test que falla**

Crear `bridge/tests/test_render.py`:

```python
import unittest

from bridge import arrangement, music_engine, render, style


def make_ctx(section_name="drop", bar_in_section=0, is_last_bar=False):
    deck = style.STYLES["determinacion"]
    section = next(p for p in arrangement.DEFAULT_ARC if p.name == section_name)
    return render.RenderContext(
        scale="A_minor", root=69, bpm=124, deck=deck, section=section,
        bar_in_section=bar_in_section,
        progression=deck.progressions[section_name][0],
        motif=deck.motif_seeds[0], is_last_bar=is_last_bar,
    )


class TestTiempos(unittest.TestCase):
    def test_step_ms_es_la_semicorchea(self):
        # 124 BPM -> negra 483.87 ms -> semicorchea 120.97 ms
        self.assertAlmostEqual(render.step_ms(124), 120.967, places=2)

    def test_bar_ms_son_16_semicorcheas(self):
        self.assertEqual(render.bar_ms(120), 2000)


class TestRenderBar(unittest.TestCase):
    def test_devuelve_un_bar_con_los_metadatos_del_contexto(self):
        bar = render.render_bar(make_ctx(), 7)
        self.assertEqual(bar.index, 7)
        self.assertEqual(bar.bpm, 124)
        self.assertEqual(bar.section, "drop")
        self.assertEqual(bar.swing, 0.16)

    def test_es_determinista(self):
        self.assertEqual(render.render_bar(make_ctx(), 3),
                         render.render_bar(make_ctx(), 3))

    def test_todos_los_pasos_caen_dentro_del_compas(self):
        bar = render.render_bar(make_ctx(), 0)
        for event in bar.events:
            self.assertGreaterEqual(event.step, 0)
            self.assertLess(event.step, 16)

    def test_solo_suenan_las_voces_de_la_seccion(self):
        ctx = make_ctx("intro")     # intro = {bass, chords}, sin lead ni pad
        bar = render.render_bar(ctx, 0)
        voces = {e.voice for e in bar.events}
        self.assertNotIn("lead", voces)
        self.assertNotIn("pad", voces)
        self.assertIn("bass", voces)

    def test_el_drop_trae_pad_y_lead(self):
        bar = render.render_bar(make_ctx("drop"), 0)
        voces = {e.voice for e in bar.events}
        self.assertIn("lead", voces)
        self.assertIn("pad", voces)

    def test_la_bateria_siempre_esta_presente(self):
        bar = render.render_bar(make_ctx("verse"), 0)
        self.assertIn("drums", {e.voice for e in bar.events})

    def test_el_ultimo_compas_de_build_trae_el_fill(self):
        normal = render.render_bar(make_ctx("build", 0, is_last_bar=False), 0)
        fill = render.render_bar(make_ctx("build", 7, is_last_bar=True), 7)
        golpes_normales = len([e for e in normal.events if e.voice == "drums"])
        golpes_fill = len([e for e in fill.events if e.voice == "drums"])
        self.assertNotEqual(golpes_normales, golpes_fill)


class TestRangosYEscala(unittest.TestCase):
    def test_cada_voz_respeta_su_rango(self):
        bar = render.render_bar(make_ctx("drop"), 0)
        deck = style.STYLES["determinacion"]
        for event in bar.events:
            if event.voice == "drums":
                continue
            patch = deck.voices[event.voice]
            for note in event.notes:
                self.assertGreaterEqual(note, patch.range_lo, event.voice)
                self.assertLessEqual(note, patch.range_hi, event.voice)

    def test_las_notas_melodicas_caen_en_la_escala(self):
        bar = render.render_bar(make_ctx("drop"), 0)
        pcs = music_engine.pitch_classes("A_minor")
        for event in bar.events:
            if event.voice != "lead":
                continue
            for note in event.notes:
                self.assertIn(note % 12, pcs)

    def test_las_velocidades_son_midi_validas(self):
        bar = render.render_bar(make_ctx("drop"), 0)
        for event in bar.events:
            self.assertGreaterEqual(event.velocity, 1)
            self.assertLessEqual(event.velocity, 127)


class TestBateria(unittest.TestCase):
    def test_los_ids_de_bateria_van_en_notes(self):
        bar = render.render_bar(make_ctx("verse"), 0)
        for event in bar.events:
            if event.voice == "drums":
                self.assertEqual(len(event.notes), 1)
                self.assertIn(event.notes[0], render.DRUM_IDS.values())


class TestVoiceLeadingEntreCompases(unittest.TestCase):
    def test_el_voicing_previo_acerca_los_acordes(self):
        # Hay que AVANZAR bar_in_section entre los dos renders: si no, ambos
        # compases reciben el mismo acorde, el salto es 0 por construccion y
        # el test no probaria nada.
        ctx = make_ctx("drop", bar_in_section=0)
        primero = render.render_bar(ctx, 0)     # i
        ctx.bar_in_section = 1
        segundo = render.render_bar(ctx, 1)     # VI

        acordes_1 = [e for e in primero.events if e.voice == "chords"]
        acordes_2 = [e for e in segundo.events if e.voice == "chords"]
        self.assertTrue(acordes_1, "el drop deberia traer acordes")
        self.assertTrue(acordes_2, "el drop deberia traer acordes")

        # Guardia: el acorde cambio de verdad.
        self.assertNotEqual(acordes_1[0].notes, acordes_2[0].notes)

        # Sin conduccion de voces el voicing saltaria de octava; con ella,
        # cada voz se mueve una quinta como mucho.
        for antes, despues in zip(acordes_1[0].notes, acordes_2[0].notes):
            self.assertLessEqual(abs(despues - antes), 7,
                                 "una voz salto mas de una quinta")


class TestDensidad(unittest.TestCase):
    def test_mas_densidad_produce_mas_eventos(self):
        pocos = render.render_bar(make_ctx("break"), 0)
        muchos = render.render_bar(make_ctx("drop"), 0)
        self.assertGreater(len(muchos.events), len(pocos.events))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Ejecutar el test para verificar que falla**

Run: `.venv\Scripts\python -m unittest bridge.tests.test_render -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'bridge.render'`

- [ ] **Step 3: Implementar `bridge/render.py`**

```python
"""El renderizador: junta estilo, armonia, motivo y arreglo en un compas.

render_bar() es una FUNCION PURA -- misma entrada, misma salida, sin azar y sin
I/O. Esa pureza es lo que hace posibles el test dorado y scripts/render-jam.py,
y es la razon de que este modulo no viva dentro de sequencer.py: el reloj
asincrono es otra responsabilidad.

Un compas son 16 semicorcheas. Las duraciones se expresan en pasos, no en
milisegundos: la conversion depende del BPM y la hace quien reproduce.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import harmony, motif as M, music_engine
from .arrangement import SectionPlan
from .style import DRUM_PATTERNS, StyleDeck

STEPS_PER_BAR = 16
DRUM_IDS = {"kick": 0, "snare": 1, "hat": 2}

VELOCITY_ACCENT = 104
VELOCITY_NORMAL = 74
VELOCITY_SOFT = 56
DRUM_VELOCITY = {"kick": 112, "snare": 96, "hat": 58}


@dataclass(frozen=True)
class VoiceEvent:
    voice: str
    step: int
    notes: tuple[int, ...]
    velocity: int
    dur_steps: int


@dataclass(frozen=True)
class Bar:
    index: int
    bpm: int
    ms: int
    swing: float
    section: str
    events: tuple[VoiceEvent, ...]


@dataclass
class RenderContext:
    scale: str
    root: int
    bpm: int
    deck: StyleDeck
    section: SectionPlan
    bar_in_section: int
    progression: tuple[str, ...]
    motif: M.Motif
    is_last_bar: bool = False
    prev_voicing: list[int] = field(default_factory=list)


def step_ms(bpm: int) -> float:
    """Duracion de una semicorchea en milisegundos."""
    return 60000.0 / max(1, bpm) / 4.0


def bar_ms(bpm: int) -> int:
    return round(step_ms(bpm) * STEPS_PER_BAR)


def _scale_size(scale: str) -> int:
    return max(1, len(music_engine.pitch_classes(scale)))


def _render_bass(ctx: RenderContext, roman: str) -> list[VoiceEvent]:
    # El registro sale del propio rango de la voz: sumar la clase de altura a
    # range_lo coloca la nota en la octava mas grave que la voz admite, que es
    # justo donde tiene que estar un bajo. Sin numeros magicos.
    patch = ctx.deck.voices["bass"]
    pcs = harmony.chord_pitch_classes(ctx.scale, roman)
    root_note = M.fold_to_range(patch.range_lo + pcs[0],
                                patch.range_lo, patch.range_hi)
    fifth = M.fold_to_range(patch.range_lo + pcs[min(2, len(pcs) - 1)],
                            patch.range_lo, patch.range_hi)

    if ctx.section.tempo_mode == "half" or ctx.section.density < 0.4:
        steps = (0, 8)
    elif ctx.section.density < 0.7:
        steps = (0, 4, 8, 12)
    else:
        steps = (0, 3, 6, 8, 11, 14)

    events = []
    for i, step in enumerate(steps):
        note = root_note if i % 3 != 2 else fifth
        events.append(VoiceEvent("bass", step, (note,),
                                 VELOCITY_ACCENT if step == 0 else VELOCITY_NORMAL,
                                 2))
    return events


def _render_chords(ctx: RenderContext, roman: str) -> list[VoiceEvent]:
    patch = ctx.deck.voices["chords"]
    voicing = harmony.voice_lead(ctx.prev_voicing, ctx.scale, roman,
                                 patch.range_lo, patch.range_hi)
    ctx.prev_voicing = list(voicing)

    if ctx.section.density < 0.4:
        steps = (0,)
    elif ctx.section.density < 0.7:
        steps = (2, 10)
    else:
        steps = (2, 6, 10, 14)

    return [VoiceEvent("chords", step, tuple(voicing), VELOCITY_SOFT, 2)
            for step in steps]


def _render_pad(ctx: RenderContext, roman: str) -> list[VoiceEvent]:
    patch = ctx.deck.voices["pad"]
    voicing = harmony.voice_lead([], ctx.scale, roman,
                                 patch.range_lo, patch.range_hi)
    return [VoiceEvent("pad", 0, tuple(voicing), VELOCITY_SOFT, STEPS_PER_BAR)]


def _render_lead(ctx: RenderContext, roman: str) -> list[VoiceEvent]:
    """El motivo, rearmonizado al acorde del compas. Esto es el leitmotiv."""
    patch = ctx.deck.voices["lead"]
    degrees = harmony.chord_degrees(ctx.scale, roman)
    shaped = M.reharmonize(ctx.motif, degrees, _scale_size(ctx.scale))
    if ctx.section.density >= 0.9:
        shaped = M.ornament(shaped, 1)
    elif ctx.section.tempo_mode == "half":
        shaped = M.augment(shaped, 2)

    root = ctx.root + 12 * ctx.section.octave
    events = []
    for offset, note, dur, accent in M.realize(shaped, ctx.scale, root,
                                               patch.range_lo, patch.range_hi):
        if offset >= STEPS_PER_BAR:
            break
        events.append(VoiceEvent(
            "lead", offset, (note,),
            VELOCITY_ACCENT if accent else VELOCITY_NORMAL,
            min(dur, STEPS_PER_BAR - offset)))
    return events


def _render_drums(ctx: RenderContext) -> list[VoiceEvent]:
    pattern_id = ("fill" if (ctx.is_last_bar and ctx.section.fill_on_last_bar)
                  else ctx.deck.drum_patterns.get(ctx.section.name, "basico"))
    kit = DRUM_PATTERNS.get(pattern_id, DRUM_PATTERNS["basico"])

    events = []
    for name, row in kit.items():
        drum_id = DRUM_IDS.get(name)
        if drum_id is None:
            continue
        for step, char in enumerate(row[:STEPS_PER_BAR]):
            if char == "x":
                events.append(VoiceEvent("drums", step, (drum_id,),
                                         DRUM_VELOCITY.get(name, 90), 1))
    return events


def render_bar(ctx: RenderContext, bar_index: int) -> Bar:
    """Compone un compas completo. Puro y determinista."""
    roman = harmony.chord_at(ctx.progression, ctx.bar_in_section)
    events: list[VoiceEvent] = []

    if "bass" in ctx.section.voices:
        events += _render_bass(ctx, roman)
    if "chords" in ctx.section.voices:
        events += _render_chords(ctx, roman)
    if "pad" in ctx.section.voices:
        events += _render_pad(ctx, roman)
    if "lead" in ctx.section.voices:
        events += _render_lead(ctx, roman)
    events += _render_drums(ctx)

    events.sort(key=lambda e: (e.step, e.voice))
    return Bar(index=bar_index, bpm=ctx.bpm, ms=bar_ms(ctx.bpm),
               swing=ctx.deck.swing, section=ctx.section.name,
               events=tuple(events))
```

- [ ] **Step 4: Ejecutar el test para verificar que pasa**

Run: `.venv\Scripts\python -m unittest bridge.tests.test_render -v`
Expected: PASS, 15 tests.

- [ ] **Step 5: Commit**

```bash
git add bridge/render.py bridge/tests/test_render.py
git commit -m "feat(bridge): renderizador puro de compases -- une estilo, armonia, motivo y arreglo"
```

---

### Task 6: `sequencer.py` reescrito — reloj sin deriva

**Files:**
- Rewrite: `bridge/sequencer.py`
- Modify: `bridge/main.py:46` (construcción del `Sequencer`)
- Modify: `CLAUDE.md` §2 (tabla de responsabilidades)
- Test: `bridge/tests/test_sequencer.py`

**Interfaces:**
- Consumes: `render.render_bar`, `render.RenderContext`, `render.Bar`, `render.step_ms` (Task 5); `arrangement.Arranger` (Task 4); `style.get_style` (Task 3); `PdLink.trigger_note(note, velocity)` (existente, `bridge/osc_handler.py:59`).
- Produces:
  - `swing_offset_ms(step: int, swing: float, step_duration_ms: float) -> float`
  - `Sequencer(state, pd, style_id=style.DEFAULT_STYLE_ID)` con `.enabled: bool`, `.build_context() -> RenderContext`, `.next_bar() -> Bar`, `async .run()`

- [ ] **Step 1: Escribir el test que falla**

Crear `bridge/tests/test_sequencer.py`:

```python
import unittest

from bridge import render, sequencer, style
from bridge.state import GlobalState


class FakePd:
    def __init__(self):
        self.notes = []

    def trigger_note(self, note, velocity):
        self.notes.append((note, velocity))


class TestSwingOffset(unittest.TestCase):
    def test_los_pasos_pares_no_se_mueven(self):
        self.assertEqual(sequencer.swing_offset_ms(0, 0.5, 120.0), 0.0)
        self.assertEqual(sequencer.swing_offset_ms(4, 0.5, 120.0), 0.0)

    def test_los_pasos_impares_se_retrasan(self):
        offset = sequencer.swing_offset_ms(1, 0.6, 120.0)
        self.assertAlmostEqual(offset, 24.0, places=3)

    def test_sin_swing_no_hay_desplazamiento(self):
        self.assertEqual(sequencer.swing_offset_ms(1, 0.0, 120.0), 0.0)

    def test_el_swing_nunca_pasa_del_paso_siguiente(self):
        offset = sequencer.swing_offset_ms(1, 1.0, 120.0)
        self.assertLess(offset, 120.0)


class TestSequencer(unittest.TestCase):
    def setUp(self):
        self.state = GlobalState()
        self.pd = FakePd()
        self.seq = sequencer.Sequencer(self.state, self.pd)

    def test_arranca_con_el_estilo_por_defecto(self):
        self.assertEqual(self.seq.deck.id, style.DEFAULT_STYLE_ID)

    def test_un_estilo_desconocido_cae_al_default(self):
        seq = sequencer.Sequencer(self.state, self.pd, style_id="no-existe")
        self.assertEqual(seq.deck.id, style.DEFAULT_STYLE_ID)

    def test_build_context_usa_el_estado_de_la_jam(self):
        self.state.jam.scale = "D_minor"
        self.state.jam.bpm = 140
        ctx = self.seq.build_context()
        self.assertEqual(ctx.scale, "D_minor")
        self.assertEqual(ctx.bpm, 140)

    def test_next_bar_devuelve_un_bar_y_avanza_el_arreglo(self):
        primero = self.seq.next_bar()
        self.assertIsInstance(primero, render.Bar)
        self.assertEqual(primero.index, 0)
        segundo = self.seq.next_bar()
        self.assertEqual(segundo.index, 1)

    def test_next_bar_recorre_el_arco_completo_sin_reventar(self):
        # 68 compases = una vuelta entera al arco por defecto.
        for _ in range(68):
            self.seq.next_bar()
        self.assertEqual(self.seq.arranger.section.name, "intro")

    def test_una_escala_invalida_no_detiene_el_secuenciador(self):
        # El secuenciador no se detiene jamas (CLAUDE.md 7).
        self.state.jam.scale = "escala-rota"
        bar = self.seq.next_bar()
        self.assertIsInstance(bar, render.Bar)

    def test_dispatch_manda_el_lead_a_pd(self):
        # Fase 1: bajo, acordes, pad y bateria se componen pero todavia no
        # suenan en Pd -- eso llega en la Fase 2 con el OSC multivoz.
        self.seq.arranger.jump_to("drop")     # el drop si trae lead
        bar = self.seq.next_bar()
        lead_steps = sorted({e.step for e in bar.events if e.voice == "lead"})
        self.assertTrue(lead_steps, "el drop deberia traer lead")
        for step in lead_steps:
            self.seq.dispatch_step(bar, step)
        self.assertTrue(self.pd.notes, "no llego ninguna nota a Pd")
        for note, velocity in self.pd.notes:
            self.assertGreaterEqual(note, 21)
            self.assertLessEqual(note, 108)
            self.assertGreaterEqual(velocity, 1)
            self.assertLessEqual(velocity, 127)

    def test_dispatch_no_manda_bajo_ni_bateria_todavia(self):
        self.seq.arranger.jump_to("drop")
        bar = self.seq.next_bar()
        lead_notes = {n for e in bar.events if e.voice == "lead" for n in e.notes}
        for step in range(render.STEPS_PER_BAR):
            self.seq.dispatch_step(bar, step)
        for note, _vel in self.pd.notes:
            self.assertIn(note, lead_notes)

    def test_dispatch_de_un_paso_sin_eventos_no_hace_nada(self):
        bar = render.Bar(0, 120, 2000, 0.0, "intro", ())
        self.seq.dispatch_step(bar, 5)
        self.assertEqual(self.pd.notes, [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Ejecutar el test para verificar que falla**

Run: `.venv\Scripts\python -m unittest bridge.tests.test_sequencer -v`
Expected: FAIL con `AttributeError: module 'bridge.sequencer' has no attribute 'swing_offset_ms'`

- [ ] **Step 3: Reescribir `bridge/sequencer.py`**

Reemplazar el contenido completo del archivo:

```python
"""Secuenciador de ViruSynth: reloj de semicorcheas + despacho.

Aqui NO vive teoria musical -- eso es render.py, que es puro. Aqui vive el
tiempo: un reloj sin deriva, el swing, y el envio de cada evento a Pd en su
instante.

Por que un acumulador absoluto: la version anterior hacia
`sleep(60/bpm/2)` DESPUES de trabajar, asi que el coste de cada paso se sumaba
al intervalo y el tempo real iba siempre algo lento, empeorando con la carga.

Fase 1: a Pd solo se le manda la voz `lead`, por el /pd/trigger/note que ya
existe. Bajo, acordes, pad y bateria se componen igual (salen al MIDI y al
test dorado) pero no suenan hasta que la Fase 2 anada el OSC multivoz y las
abstracciones del patch. Asi el escenario nunca queda mudo entre fases.
"""
from __future__ import annotations

import asyncio
import logging

from . import render, style
from .arrangement import Arranger

log = logging.getLogger("SEQ")

PD_VOICE = "lead"          # la unica voz que Pd sabe tocar todavia (Fase 1)


def swing_offset_ms(step: int, swing: float, step_duration_ms: float) -> float:
    """Retraso del paso impar. 0 <= swing <= 1; nunca alcanza el paso siguiente."""
    if step % 2 == 0 or swing <= 0.0:
        return 0.0
    return step_duration_ms * min(0.66, max(0.0, swing)) / 3.0


class Sequencer:
    def __init__(self, state, pd, style_id: str = style.DEFAULT_STYLE_ID) -> None:
        self.state = state
        self.pd = pd
        self.deck = style.get_style(style_id)
        self.arranger = Arranger()
        self.enabled = True
        self._bar_index = 0
        self._prev_voicing: list[int] = []
        self._motif = self.deck.motif_seeds[0]

    # ---- composicion -------------------------------------------------------
    def build_context(self) -> render.RenderContext:
        jam = self.state.jam
        section = self.arranger.section
        pool = self.deck.progressions.get(section.name) or (("i",),)
        progression = pool[self._bar_index // max(1, section.bars) % len(pool)]
        ctx = render.RenderContext(
            scale=jam.scale, root=jam.root_note, bpm=jam.bpm, deck=self.deck,
            section=section, bar_in_section=self.arranger.bar_in_section,
            progression=progression, motif=self._motif,
            is_last_bar=self.arranger.is_last_bar())
        ctx.prev_voicing = self._prev_voicing
        return ctx

    def next_bar(self) -> render.Bar:
        """Compone el siguiente compas y avanza el arreglo. Nunca lanza."""
        index = self._bar_index
        try:
            ctx = self.build_context()
            bar = render.render_bar(ctx, index)
            self._prev_voicing = ctx.prev_voicing
        except Exception as exc:                 # nunca detener la jam
            log.error("render del compas %d fallo: %s", index, exc)
            bar = render.Bar(index, self.state.jam.bpm,
                             render.bar_ms(self.state.jam.bpm), 0.0,
                             self.arranger.section.name, ())
        self._bar_index += 1
        self.arranger.advance()
        return bar

    # ---- despacho ----------------------------------------------------------
    def dispatch_step(self, bar: render.Bar, step: int) -> None:
        """Manda a Pd los eventos de este paso (Fase 1: solo el lead)."""
        for event in bar.events:
            if event.step != step or event.voice != PD_VOICE:
                continue
            for note in event.notes:
                self.pd.trigger_note(int(note), int(event.velocity))
                self.state.jam.current_notes.append(int(note))

    # ---- reloj -------------------------------------------------------------
    async def run(self) -> None:
        log.info("Secuenciador en marcha | estilo %s | semicorcheas @ %d BPM",
                 self.deck.id, self.state.jam.bpm)
        loop = asyncio.get_running_loop()
        next_t = loop.time()
        while True:
            bar = self.next_bar()
            step_seconds = render.step_ms(bar.bpm) / 1000.0
            bar_start = next_t
            for step in range(render.STEPS_PER_BAR):
                target = (bar_start + step * step_seconds
                          + swing_offset_ms(step, bar.swing,
                                            render.step_ms(bar.bpm)) / 1000.0)
                delay = target - loop.time()
                if delay > 0:
                    await asyncio.sleep(delay)
                if not self.enabled:
                    continue
                try:
                    self.dispatch_step(bar, step)
                except Exception as exc:         # el secuenciador no se detiene
                    log.error("paso %d fallido: %s", step, exc)
            next_t = bar_start + render.STEPS_PER_BAR * step_seconds
            # Si nos atrasamos mas de un compas entero, resincronizar en vez de
            # disparar una avalancha de notas comprimidas.
            if loop.time() - next_t > render.STEPS_PER_BAR * step_seconds:
                log.warning("reloj atrasado: resincronizando al compas actual")
                next_t = loop.time()
```

- [ ] **Step 4: Ejecutar el test para verificar que pasa**

Run: `.venv\Scripts\python -m unittest bridge.tests.test_sequencer -v`
Expected: PASS, 13 tests.

- [ ] **Step 5: Verificar que no se rompió nada del resto**

Run: `.venv\Scripts\python -m unittest discover -s bridge\tests`
Expected: OK, toda la suite en verde (incluidos los tests que ya existían).

- [ ] **Step 6: Actualizar `CLAUDE.md` §2**

En la tabla "Reparto de responsabilidades" de `CLAUDE.md`, sustituir la fila del bridge:

```markdown
| Bridge Python | Cerebro: secuenciador, escalas, cuantización, votos, estado, IA | Sintetizar audio |
```

por:

```markdown
| Bridge Python | Cerebro: **arreglo** (estilo, armonía, motivo, secciones), secuenciador, escalas, cuantización, votos, estado, IA | Sintetizar audio |
```

- [ ] **Step 7: Verificar el arranque real del bridge**

Run: `.venv\Scripts\python -m bridge.main --mock-sensors --no-ai --no-portal --log-level INFO`
Expected: aparece `Secuenciador en marcha | estilo determinacion | semicorcheas @ 112 BPM` y el proceso sigue vivo. Cortar con `Ctrl+C`.

- [ ] **Step 8: Commit**

```bash
git add bridge/sequencer.py bridge/tests/test_sequencer.py CLAUDE.md
git commit -m "feat(bridge): secuenciador nuevo -- reloj sin deriva, swing y arreglo por secciones"
```

---

### Task 7: `scripts/render-jam.py` — exportar a MIDI

**Files:**
- Create: `scripts/render-jam.py`
- Test: `bridge/tests/test_midi.py`
- Create: `bridge/midi.py`

**Interfaces:**
- Consumes: `render.Bar`, `render.VoiceEvent`, `render.step_ms` (Task 5); `sequencer.Sequencer` (Task 6); `state.GlobalState` (existente).
- Produces (en `bridge/midi.py`):
  - `varint(value: int) -> bytes`
  - `CHANNELS: dict[str, int]` — `lead=0, bass=1, chords=2, pad=3, drums=9`
  - `GM_DRUMS: dict[int, int]` — id interno → nota GM (`0→36 kick`, `1→38 snare`, `2→42 hat`)
  - `bars_to_midi(bars: Sequence[Bar], ticks_per_quarter: int = 480) -> bytes`

- [ ] **Step 1: Escribir el test que falla**

Crear `bridge/tests/test_midi.py`:

```python
import struct
import unittest

from bridge import midi, render


def make_bars():
    events = (
        render.VoiceEvent("lead", 0, (69,), 100, 4),
        render.VoiceEvent("bass", 0, (45,), 110, 8),
        render.VoiceEvent("chords", 4, (57, 60, 64), 70, 4),
        render.VoiceEvent("drums", 0, (0,), 112, 1),
    )
    return [render.Bar(0, 120, 2000, 0.0, "verse", events)]


class TestVarint(unittest.TestCase):
    def test_valores_pequenos_ocupan_un_byte(self):
        self.assertEqual(midi.varint(0), b"\x00")
        self.assertEqual(midi.varint(127), b"\x7f")

    def test_valores_grandes_usan_continuacion(self):
        self.assertEqual(midi.varint(128), b"\x81\x00")
        self.assertEqual(midi.varint(480), b"\x83\x60")

    def test_los_negativos_se_tratan_como_cero(self):
        self.assertEqual(midi.varint(-5), b"\x00")


class TestBarsToMidi(unittest.TestCase):
    def setUp(self):
        self.data = midi.bars_to_midi(make_bars())

    def test_empieza_con_la_cabecera_MThd(self):
        self.assertEqual(self.data[:4], b"MThd")

    def test_la_cabecera_declara_formato_1(self):
        length, fmt, ntracks, division = struct.unpack(">IHHH", self.data[4:14])
        self.assertEqual(length, 6)
        self.assertEqual(fmt, 1)
        self.assertGreaterEqual(ntracks, 2)
        self.assertEqual(division, 480)

    def test_hay_tantas_pistas_como_declara_la_cabecera(self):
        ntracks = struct.unpack(">H", self.data[10:12])[0]
        self.assertEqual(self.data.count(b"MTrk"), ntracks)

    def test_toda_pista_termina_en_end_of_track(self):
        self.assertIn(b"\xff\x2f\x00", self.data)

    def test_la_primera_pista_lleva_el_tempo(self):
        self.assertIn(b"\xff\x51\x03", self.data)

    def test_la_bateria_va_al_canal_10(self):
        # Canal 10 en notacion humana = 9 en el protocolo: 0x99 = note on ch9.
        self.assertIn(b"\x99", self.data)

    def test_sin_compases_sigue_produciendo_un_archivo_valido(self):
        data = midi.bars_to_midi([])
        self.assertEqual(data[:4], b"MThd")
        self.assertIn(b"\xff\x2f\x00", data)


class TestGmDrums(unittest.TestCase):
    def test_los_tres_instrumentos_mapean_a_notas_gm(self):
        self.assertEqual(midi.GM_DRUMS[0], 36)   # bombo
        self.assertEqual(midi.GM_DRUMS[1], 38)   # caja
        self.assertEqual(midi.GM_DRUMS[2], 42)   # hat cerrado


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Ejecutar el test para verificar que falla**

Run: `.venv\Scripts\python -m unittest bridge.tests.test_midi -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'bridge.midi'`

- [ ] **Step 3: Implementar `bridge/midi.py`**

```python
"""Escritura de Standard MIDI Files con stdlib pura.

Para que existe: permite ESCUCHAR lo que compone el motor sin levantar Pd, el
bridge ni el navegador. Es la herramienta con la que se afina el estilo, y la
base del futuro "descarga el tema que compusimos entre todos".

Formato 1 (varias pistas sincronizadas), una pista por voz. La bateria va al
canal 10 del protocolo (indice 9), que es el canal percusivo de General MIDI.
"""
from __future__ import annotations

import struct
from typing import Sequence

from .render import Bar, STEPS_PER_BAR

CHANNELS = {"lead": 0, "bass": 1, "chords": 2, "pad": 3, "drums": 9}
GM_DRUMS = {0: 36, 1: 38, 2: 42}      # bombo, caja, hat cerrado
DEFAULT_TPQ = 480


def varint(value: int) -> bytes:
    """Delta-time de MIDI: 7 bits por byte, el bit alto marca continuacion."""
    value = max(0, int(value))
    out = bytearray([value & 0x7F])
    value >>= 7
    while value:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    return bytes(reversed(out))


def _track(events: list[tuple[int, bytes]]) -> bytes:
    """events: (tick_absoluto, payload). Devuelve un chunk MTrk completo."""
    events.sort(key=lambda e: e[0])
    body = bytearray()
    last = 0
    for tick, payload in events:
        body += varint(tick - last) + payload
        last = tick
    body += varint(0) + b"\xff\x2f\x00"          # end of track
    return b"MTrk" + struct.pack(">I", len(body)) + bytes(body)


def bars_to_midi(bars: Sequence[Bar], ticks_per_quarter: int = DEFAULT_TPQ) -> bytes:
    """Convierte compases renderizados en un archivo MIDI formato 1."""
    ticks_per_step = ticks_per_quarter // 4
    per_voice: dict[str, list[tuple[int, bytes]]] = {}
    tempo_events: list[tuple[int, bytes]] = []

    last_bpm = None
    for bar_number, bar in enumerate(bars):
        bar_tick = bar_number * STEPS_PER_BAR * ticks_per_step
        if bar.bpm != last_bpm:
            us_per_quarter = int(60_000_000 / max(1, bar.bpm))
            tempo_events.append((bar_tick, b"\xff\x51\x03"
                                 + us_per_quarter.to_bytes(3, "big")))
            last_bpm = bar.bpm
        for event in bar.events:
            channel = CHANNELS.get(event.voice, 0)
            start = bar_tick + event.step * ticks_per_step
            end = start + max(1, event.dur_steps) * ticks_per_step
            track = per_voice.setdefault(event.voice, [])
            for raw in event.notes:
                note = GM_DRUMS.get(int(raw), 36) if event.voice == "drums" else int(raw)
                note = max(0, min(127, note))
                velocity = max(1, min(127, int(event.velocity)))
                track.append((start, bytes([0x90 | channel, note, velocity])))
                track.append((end, bytes([0x80 | channel, note, 0])))

    tracks = [_track(tempo_events)]
    for voice in ("lead", "bass", "chords", "pad", "drums"):
        if voice in per_voice:
            tracks.append(_track(per_voice[voice]))

    header = b"MThd" + struct.pack(">IHHH", 6, 1, len(tracks), ticks_per_quarter)
    return header + b"".join(tracks)
```

- [ ] **Step 4: Ejecutar el test para verificar que pasa**

Run: `.venv\Scripts\python -m unittest bridge.tests.test_midi -v`
Expected: PASS, 11 tests.

- [ ] **Step 5: Implementar `scripts/render-jam.py`**

```python
"""Renderiza N compases del motor a un Standard MIDI File.

Sirve para afinar el estilo de oido sin levantar Pd, el bridge ni el navegador.

Uso:
  .venv\\Scripts\\python scripts/render-jam.py --bars 16 --out jam.mid
  .venv\\Scripts\\python scripts/render-jam.py --style arcade --scale C_major
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bridge import midi, style          # noqa: E402
from bridge.sequencer import Sequencer  # noqa: E402
from bridge.state import GlobalState    # noqa: E402


class _SilentPd:
    """El renderizado offline no manda nada a Pd."""

    def trigger_note(self, note: int, velocity: int) -> None:
        pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="render-jam", description="Renderiza la jam a un archivo MIDI")
    parser.add_argument("--bars", type=int, default=16, help="compases (default 16)")
    parser.add_argument("--style", default=style.DEFAULT_STYLE_ID,
                        choices=sorted(style.STYLES), help="estilo del preset")
    parser.add_argument("--scale", default="", help="escala (default: la del estilo)")
    parser.add_argument("--bpm", type=int, default=0, help="BPM (default: el del estilo)")
    parser.add_argument("--out", default="jam.mid", help="archivo de salida")
    args = parser.parse_args(argv)

    deck = style.get_style(args.style)
    state = GlobalState()
    state.jam.scale = args.scale or deck.scales[0]
    state.jam.bpm = args.bpm or deck.default_bpm

    sequencer = Sequencer(state, _SilentPd(), style_id=args.style)
    bars = [sequencer.next_bar() for _ in range(max(1, args.bars))]

    out = Path(args.out)
    out.write_bytes(midi.bars_to_midi(bars))
    total = sum(len(b.events) for b in bars)
    secciones = []
    for bar in bars:
        if not secciones or secciones[-1] != bar.section:
            secciones.append(bar.section)
    print(f"{out}: {len(bars)} compases, {total} eventos, "
          f"estilo {deck.name}, escala {state.jam.scale}, {state.jam.bpm} BPM")
    print("secciones: " + " -> ".join(secciones))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 6: Renderizar y escuchar de verdad**

Run: `.venv\Scripts\python scripts\render-jam.py --bars 32 --out jam.mid`
Expected: imprime algo como `jam.mid: 32 compases, 700+ eventos, estilo Determinacion, escala Am_pentatonic, 124 BPM` y la lista de secciones `intro -> verse -> build -> drop`.

Run: `start jam.mid`
Expected: se abre el reproductor por defecto. **Escucharlo.** Tiene que oírse: un bajo con ostinato, acordes en contratiempo, batería que se densifica en el `build`, y una melodía que vuelve transformada. Si suena a arpegio plano, algo del renderizador está mal — no seguir hasta que suene a música.

- [ ] **Step 7: Commit**

```bash
git add bridge/midi.py bridge/tests/test_midi.py scripts/render-jam.py
git commit -m "feat(scripts): render-jam.py -- exporta la jam a MIDI para afinar el estilo de oido"
```

---

### Task 8: Test dorado — la partitura de referencia

**Files:**
- Create: `bridge/tests/test_golden_score.py`
- Create: `bridge/tests/golden/determinacion_16.txt`

**Interfaces:**
- Consumes: `sequencer.Sequencer`, `state.GlobalState`, `render.Bar`.
- Produces: `format_score(bars: Sequence[Bar]) -> str` (dentro del propio test).

**Por qué existe:** ningún test unitario detecta que la música empeoró. El test dorado congela la salida completa de 16 compases; si un cambio la altera, el diff dice exactamente qué se movió y quien lo hizo decide si fue a mejor.

- [ ] **Step 1: Escribir el test que falla**

Crear `bridge/tests/test_golden_score.py`:

```python
"""Test dorado: congela la salida del motor para 16 compases.

Ningun test unitario ve que la musica empeoro. Este si: si algo cambia el
render, el diff dice exactamente que. Cuando el cambio es deliberado y a mejor,
se regenera el fichero con:

  .venv\\Scripts\\python -m bridge.tests.test_golden_score --update
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Sequence

from bridge import render, style
from bridge.sequencer import Sequencer
from bridge.state import GlobalState

GOLDEN = Path(__file__).parent / "golden" / "determinacion_16.txt"


class _SilentPd:
    def trigger_note(self, note: int, velocity: int) -> None:
        pass


def build_bars(bars: int = 16) -> list[render.Bar]:
    deck = style.get_style("determinacion")
    state = GlobalState()
    state.jam.scale = "A_minor"
    state.jam.bpm = deck.default_bpm
    state.jam.root_note = 69
    sequencer = Sequencer(state, _SilentPd(), style_id="determinacion")
    return [sequencer.next_bar() for _ in range(bars)]


def format_score(bars: Sequence[render.Bar]) -> str:
    lines: list[str] = []
    for bar in bars:
        lines.append(f"--- compas {bar.index:02d} | {bar.section} "
                     f"| {bar.bpm} bpm | swing {bar.swing}")
        for event in bar.events:
            notes = ",".join(str(n) for n in event.notes)
            lines.append(f"  {event.step:02d} {event.voice:<7} "
                         f"[{notes}] v{event.velocity} d{event.dur_steps}")
    return "\n".join(lines) + "\n"


class TestGoldenScore(unittest.TestCase):
    def test_la_partitura_no_cambio(self):
        actual = format_score(build_bars())
        self.assertTrue(GOLDEN.exists(),
                        f"falta {GOLDEN}; generalo con --update")
        expected = GOLDEN.read_text(encoding="utf-8")
        self.assertEqual(actual, expected,
                         "el render cambio: revisa el diff y, si es a mejor, "
                         "regenera con --update")

    def test_el_render_es_reproducible(self):
        self.assertEqual(format_score(build_bars()), format_score(build_bars()))

    def test_la_partitura_cubre_varias_secciones(self):
        secciones = {bar.section for bar in build_bars()}
        self.assertGreaterEqual(len(secciones), 2)


if __name__ == "__main__":
    if "--update" in sys.argv:
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(format_score(build_bars()), encoding="utf-8")
        print(f"actualizado {GOLDEN}")
    else:
        unittest.main()
```

- [ ] **Step 2: Ejecutar el test para verificar que falla**

Run: `.venv\Scripts\python -m unittest bridge.tests.test_golden_score -v`
Expected: FAIL en `test_la_partitura_no_cambio` con `falta ...golden/determinacion_16.txt`

- [ ] **Step 3: Generar la partitura de referencia**

Run: `.venv\Scripts\python -m bridge.tests.test_golden_score --update`
Expected: imprime `actualizado ...\golden\determinacion_16.txt`

- [ ] **Step 4: Revisar el fichero generado antes de congelarlo**

Run: `.venv\Scripts\python -c "print(open(r'bridge/tests/golden/determinacion_16.txt', encoding='utf-8').read()[:1200])"`

Comprobar a ojo, **antes de commitear**: los compases 0-3 son `intro` (sin `lead`), a partir del 4 aparece `verse` con `lead`, hay eventos de `drums` en todos los compases, y las notas de `bass` están por debajo de 58. Si algo de esto no se cumple, el renderizador tiene un bug — arreglarlo antes de congelar la referencia.

- [ ] **Step 5: Ejecutar el test para verificar que pasa**

Run: `.venv\Scripts\python -m unittest bridge.tests.test_golden_score -v`
Expected: PASS, 3 tests.

- [ ] **Step 6: Ejecutar la suite completa**

Run: `.venv\Scripts\python -m unittest discover -s bridge\tests`
Expected: OK. Este plan añade 99 tests (15+22+17+13+15+13+11+3) a los que ya existían; ninguno de los antiguos debe romperse.

- [ ] **Step 7: Commit**

```bash
git add bridge/tests/test_golden_score.py bridge/tests/golden/determinacion_16.txt
git commit -m "test(bridge): partitura dorada de 16 compases -- caza regresiones musicales"
```

---

## Self-Review

**1. Cobertura del spec (Fase 1).** Todos los módulos de la Fase 1 tienen tarea: `style.py` (T3), `harmony.py` (T1), `motif.py` (T2), `arrangement.py` (T4), `sequencer.py` reescrito (T6), `render-jam.py` (T7). El test dorado del spec §9 es T8. Los tests unitarios de §9 están en T1-T7. **Gaps deliberados y documentados arriba:** `render_bar` se movió a `render.py` y `validate_decision()` se movió a la Fase 2.

**2. Placeholders.** Ninguna tarea contiene "TBD", "similar a la tarea N" ni pasos sin código. Cada paso de implementación trae el archivo completo o el reemplazo exacto.

**3. Consistencia de tipos.** Verificado a mano entre tareas: `harmony.chord_degrees` (T1) → `motif.reharmonize(m, chord_degrees, scale_size)` (T2) → `render._render_lead` (T5). `motif.Motif` (T2) → `style.StyleDeck.motif_seeds` (T3) → `Sequencer._motif` (T6). `render.Bar`/`VoiceEvent` (T5) → `midi.bars_to_midi` (T7) → `format_score` (T8). `arrangement.SectionPlan` (T4) → `render.RenderContext.section` (T5). `PdLink.trigger_note(note, velocity)` es la firma real de `bridge/osc_handler.py:59`.

**4. Orden de dependencias.** T1 → T2 → T3 → T4 → T5 → T6 → T7 → T8. Ninguna tarea consume algo que no exista ya.

---

## Fases siguientes (planes aparte)

- **Fase 2 — Motores de audio:** `vs-voice.pd`, `vs-drums.pd`, `main.pd` reescrito con `[clone]`, OSC multivoz, `audio-engine.js` con `PeriodicWave`, canal `jam:bar`, `validate_decision()` ampliado y vocabulario nuevo de la IA, `check-pd-loads.py`.
- **Fase 3 — La sala:** `chat.py`, canales de chat, UI, `chat_pulse`, hilo unificado con la Directora en escenario.
- **Fase 4 — Extras:** Web MIDI in, descarga MIDI de la jam.
