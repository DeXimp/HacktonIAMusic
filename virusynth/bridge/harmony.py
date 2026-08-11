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
