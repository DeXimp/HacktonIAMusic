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
            is_last_bar=self.arranger.is_last_bar(),
            artist_pattern=jam.active_pattern)
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
