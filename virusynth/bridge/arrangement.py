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
