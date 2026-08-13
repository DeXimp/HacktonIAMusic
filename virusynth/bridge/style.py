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
# El pool de escalas de un deck se cruza con su pool de progresiones, y en
# harmony.parse_roman la CUALIDAD del acorde sale de la caja del numeral, no de
# la escala: la escala solo aporta la fundamental. Por eso aca solo entran
# escalas mayores. Las dos que se probaron y se cayeron:
#   D_dorian     -> `I` daba D-F#-A, una tonica MAYOR sobre un modo menor, con
#                   la melodia pudiendo tocar F natural contra el F#. En
#                   intro/verse/drop/outro, o sea siempre.
#   G_mixolydian -> `V` daba D-F#-A, y ese F# borra el b7 (F natural) que es la
#                   unica razon para elegir mixolydian. Todas las progresiones
#                   del deck llevan V, asi que el modo no llegaba a sonar nunca.
# No se puede arreglar por escala con el prefijo `b`: el pool de progresiones es
# compartido por todas las escalas del deck (`bVII` es G en menor armonica pero
# F# en menor natural).
_ARCADE = StyleDeck(
    id="arcade",
    name="Arcade",
    scales=("C_major", "C_pentatonic"),
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
    """Un id desconocido no puede tumbar la jam: cae al default.

    Acepta cualquier cosa, no solo str: el id llega del JSON de la IA y de la
    web, y CLAUDE.md 7 pide degradar en vez de propagar el crash. Un `5` o un
    `{"a": 1}` caen al default igual que un id que no existe.
    """
    if not isinstance(style_id, str):
        return STYLES[DEFAULT_STYLE_ID]
    return STYLES.get(style_id.strip().lower(), STYLES[DEFAULT_STYLE_ID])


def allows_progression(deck: StyleDeck, section: str,
                       progression: Sequence[str]) -> bool:
    """Solo se aceptan progresiones del pool de esa seccion en ese estilo."""
    pool = deck.progressions.get(section)
    if not pool:
        return False
    return tuple(progression) in pool
