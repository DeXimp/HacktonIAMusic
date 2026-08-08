"""Secuenciador asíncrono del bridge (el 'cerebro' rítmico — Pd no secuencia).

Toca corcheas al BPM vigente: un arpegio derivado de la escala actual, o el
último patrón de artista aceptado (ya cuantizado). Nunca se detiene — es la
base sonora de la demo incluso sin performer (CLAUDE.md §7).
"""
from __future__ import annotations

import asyncio
import logging

from . import music_engine

log = logging.getLogger("SEQ")

_ARP_SHAPE = [0, 2, 4, 2, 5, 4, 2, 1]   # índices dentro de las notas de la escala


class Sequencer:
    def __init__(self, state, pd) -> None:
        self.state = state
        self.pd = pd
        self.enabled = True
        self._step = 0

    def _next_note(self) -> tuple[int, int]:
        jam = self.state.jam
        pattern = jam.active_pattern
        if pattern:
            note = int(pattern[self._step % len(pattern)])
            length = len(pattern)
        else:
            notes = music_engine.scale_notes(jam.scale, jam.root_note - 24,
                                             jam.root_note - 1)
            if not notes:
                notes = [jam.root_note - 12]
            shape = _ARP_SHAPE[self._step % len(_ARP_SHAPE)]
            note = notes[shape % len(notes)]
            length = len(_ARP_SHAPE)
        accent = self._step % length == 0
        velocity = 84 if accent else 58
        return note, velocity

    async def run(self) -> None:
        log.info("Secuenciador en marcha (corcheas @ %d BPM)", self.state.jam.bpm)
        while True:
            jam = self.state.jam
            try:
                if self.enabled:
                    note, velocity = self._next_note()
                    self.pd.trigger_note(note, velocity)
                    jam.current_notes.append(note)
                    self._step += 1
            except Exception as exc:      # el secuenciador no se detiene jamás
                log.error("paso fallido: %s", exc)
            await asyncio.sleep(60.0 / max(1, jam.bpm) / 2.0)   # corchea
