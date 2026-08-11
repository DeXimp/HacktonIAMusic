"""Capa armonica de ViruSynth: grados romanos -> acordes concretos.

Se apoya en music_engine.py (escalas, clases de altura) y no lo duplica.
Stdlib puro, sin I/O: todo aqui es testeable sin audio ni red.

Por que un "marco diatonico": una pentatonica no tiene siete grados, asi que
no se le pueden pedir acordes directamente. Para armonizar se usa el marco
mayor o menor natural que corresponde a la raiz de la escala -- exactamente
lo que hace un musico que toca una melodia pentatonica sobre acordes menores.
"""
from __future__ import annotations

import itertools
import re
from typing import Sequence

from . import music_engine

# Modos con <7 intervalos que usan el marco menor como fallback (pentatonicas, blues).
# Los modos de 7 intervalos (minor, dorian, phrygian, harmonic_minor) usan sus propios.
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
    """Raiz y tabla de grados para una escala.

    Si el modo tiene 7 intervalos propios en music_engine.SCALE_INTERVALS,
    derivar la tabla de esos intervalos. Si tiene <7 (pentatonicas, blues),
    derivar del marco mayor o menor natural segun MINOR_MODES.
    """
    try:
        root_pc, mode = music_engine.parse_scale(scale)
    except music_engine.ScaleError as exc:
        raise HarmonyError(str(exc)) from exc

    intervals = music_engine.SCALE_INTERVALS[mode]
    if len(intervals) == 7:
        # Derivar tabla de grados de los intervalos propios del modo
        degrees = {i + 1: v for i, v in enumerate(intervals)}
    else:
        # Modo con <7 notas: derivar del marco mayor o menor natural
        framework_mode = "minor" if mode in MINOR_MODES else "major"
        framework_intervals = music_engine.SCALE_INTERVALS[framework_mode]
        degrees = {i + 1: v for i, v in enumerate(framework_intervals)}

    return root_pc, degrees


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

    Se prueban todas las permutaciones de asignacion de PCs a anchors y se
    elige la de coste minimo (suma de distancias). En empate, gana el voicing
    ordenado menor. Omite clases de altura sin candidatos en el rango.
    Determinista.
    """
    pcs = chord_pitch_classes(scale, roman)
    anchors = list(prev) if prev else []

    # Para cada clase de altura, obtener candidatos en el rango
    candidates_per_pc: list[list[int]] = []
    for pc in pcs:
        candidates = [n for n in range(lo, hi + 1) if n % 12 == pc]
        candidates_per_pc.append(candidates)

    # Omitir clases de altura sin candidatos
    valid_indices = [i for i, c in enumerate(candidates_per_pc) if c]
    if not valid_indices:
        return []

    valid_pcs = [pcs[i] for i in valid_indices]
    valid_candidates = [candidates_per_pc[i] for i in valid_indices]
    num_notes = len(valid_pcs)

    # Asegurar suficientes anchors
    while len(anchors) < num_notes:
        if anchors:
            anchors.append(anchors[-1])
        else:
            anchors.append(lo + (hi - lo) // 2)

    # Probar todas las permutaciones de anchors
    best_voicing: list[int] | None = None
    best_cost = float('inf')

    for anchor_perm in itertools.permutations(anchors[:num_notes]):
        # Para esta asignacion de anchors, elegir el mejor candidato para cada PC
        voicing = []
        cost = 0
        for pc_idx, anchor in enumerate(anchor_perm):
            candidates = valid_candidates[pc_idx]
            best_candidate = min(candidates, key=lambda n: (abs(n - anchor), n))
            voicing.append(best_candidate)
            cost += abs(best_candidate - anchor)

        # Actualizar el mejor si es mejor coste, o mismo coste pero menor ordenado
        sorted_voicing = sorted(voicing)
        if cost < best_cost or (cost == best_cost and (best_voicing is None or sorted_voicing < best_voicing)):
            best_cost = cost
            best_voicing = sorted_voicing

    return best_voicing if best_voicing else []


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
