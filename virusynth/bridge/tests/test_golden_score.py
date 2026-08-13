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

from bridge import music_engine, render, style
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


class TestLaPartituraTieneSentidoMusical(unittest.TestCase):
    """Las comprobaciones que el plan pedia hacer A OJO antes de congelar.

    Un test dorado solo dice "cambio" o "no cambio": congela igual de bien una
    partitura correcta que una rota. Si la referencia se genera con un bug
    dentro, el test dorado lo defiende para siempre. Estas invariantes son las
    que dicen que la referencia MERECE estar congelada, y quedan enforced en
    vez de revisadas una sola vez.
    """

    @classmethod
    def setUpClass(cls):
        cls.bars = build_bars()

    def test_los_primeros_cuatro_compases_son_intro_sin_lead(self):
        for bar in self.bars[:4]:
            self.assertEqual(bar.section, "intro", f"compas {bar.index}")
            voces = {e.voice for e in bar.events}
            self.assertNotIn("lead", voces,
                             f"el compas {bar.index} es intro y trae lead")

    def test_desde_el_compas_cuatro_entra_el_lead(self):
        # DEFAULT_ARC es intro(4) + verse(8) + build(8): en 16 compases entran
        # el intro entero, el verse entero y los 4 primeros del build. Las dos
        # ultimas secciones llevan lead.
        for bar in self.bars[4:]:
            voces = {e.voice for e in bar.events}
            self.assertIn("lead", voces,
                          f"el compas {bar.index} ({bar.section}) no trae lead")

    def test_la_partitura_recorre_intro_verse_y_build(self):
        secciones = [bar.section for bar in self.bars]
        self.assertEqual(secciones[:4], ["intro"] * 4)
        self.assertEqual(secciones[4:12], ["verse"] * 8)
        self.assertEqual(secciones[12:], ["build"] * 4)

    def test_hay_bateria_en_todos_los_compases(self):
        for bar in self.bars:
            voces = {e.voice for e in bar.events}
            self.assertIn("drums", voces,
                          f"el compas {bar.index} se queda sin bateria")

    def test_el_bajo_se_queda_en_el_registro_grave(self):
        # range_hi del bajo de determinacion es 57.
        patch = style.STYLES["determinacion"].voices["bass"]
        for bar in self.bars:
            for event in bar.events:
                if event.voice != "bass":
                    continue
                for note in event.notes:
                    self.assertLess(note, 58,
                                    f"compas {bar.index}: bajo en {note}")
                    self.assertGreaterEqual(note, patch.range_lo)

    def test_ninguna_nota_melodica_se_sale_de_la_escala(self):
        pcs = music_engine.pitch_classes("A_minor")
        for bar in self.bars:
            for event in bar.events:
                if event.voice != "lead":
                    continue
                for note in event.notes:
                    self.assertIn(note % 12, pcs,
                                  f"compas {bar.index}: {note} fuera de A_minor")

    def test_todos_los_eventos_son_midi_validos(self):
        for bar in self.bars:
            for event in bar.events:
                self.assertGreaterEqual(event.step, 0)
                self.assertLess(event.step, render.STEPS_PER_BAR)
                self.assertGreaterEqual(event.velocity, 1)
                self.assertLessEqual(event.velocity, 127)
                self.assertGreaterEqual(event.dur_steps, 1)
                self.assertTrue(event.notes)

    def test_la_partitura_congelada_describe_16_compases(self):
        # Que el fichero de referencia no se haya truncado ni duplicado.
        if not GOLDEN.exists():
            self.skipTest("todavia no hay partitura congelada")
        texto = GOLDEN.read_text(encoding="utf-8")
        cabeceras = [l for l in texto.splitlines() if l.startswith("--- compas")]
        self.assertEqual(len(cabeceras), 16)
        for i, linea in enumerate(cabeceras):
            self.assertIn(f"compas {i:02d}", linea)


if __name__ == "__main__":
    if "--update" in sys.argv:
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(format_score(build_bars()), encoding="utf-8")
        print(f"actualizado {GOLDEN}")
    else:
        unittest.main()
