import asyncio
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

    def test_ningun_paso_se_pasa_del_siguiente_con_swing_extremo(self):
        # El plan probaba un solo paso con swing=1.0. Esto barre los 16 pasos y
        # varios swings: si un offset alcanzara la duracion del paso, el evento
        # caeria encima del siguiente y el ritmo se desarmaria.
        paso_ms = 120.0
        for swing in (0.0, 0.16, 0.33, 0.5, 0.66, 0.9, 1.0, 5.0, -1.0):
            for step in range(render.STEPS_PER_BAR):
                offset = sequencer.swing_offset_ms(step, swing, paso_ms)
                with self.subTest(swing=swing, step=step):
                    self.assertGreaterEqual(offset, 0.0)
                    self.assertLess(offset, paso_ms)


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

    # --- lo que los tests del plan no cubren -------------------------------

    def test_los_ids_de_bateria_nunca_llegan_a_pd_como_notas(self):
        # Los golpes de bateria llevan notes=(0,), (1,) o (2,), que como MIDI
        # serian notas subgraves inaudibles. Si el filtro de voz se rompiera,
        # esto lo caza.
        self.seq.arranger.jump_to("drop")
        bar = self.seq.next_bar()
        self.assertTrue([e for e in bar.events if e.voice == "drums"])
        for step in range(render.STEPS_PER_BAR):
            self.seq.dispatch_step(bar, step)
        for note, _vel in self.pd.notes:
            self.assertGreater(note, 20, "llego un id de bateria como nota MIDI")

    def test_el_bpm_de_la_jam_manda_en_el_compas(self):
        self.state.jam.bpm = 90
        bar = self.seq.next_bar()
        self.assertEqual(bar.bpm, 90)
        self.assertEqual(bar.ms, render.bar_ms(90))

    def test_el_indice_de_compas_no_se_reinicia_al_ciclar_el_arco(self):
        for _ in range(70):
            bar = self.seq.next_bar()
        self.assertEqual(bar.index, 69)

    def test_el_patron_del_artista_llega_al_contexto_y_a_pd(self):
        # El secuenciador viejo era el unico lector de jam.active_pattern. Si
        # esto se rompe, la UI de artista vuelve a quedar muda.
        self.state.jam.active_pattern = [69, 72, 76]
        ctx = self.seq.build_context()
        self.assertEqual(ctx.artist_pattern, [69, 72, 76])

        self.seq.arranger.jump_to("drop")
        bar = self.seq.next_bar()
        for step in range(render.STEPS_PER_BAR):
            self.seq.dispatch_step(bar, step)
        self.assertTrue(self.pd.notes, "el patron del artista no llego a Pd")
        enviadas = {n for n, _v in self.pd.notes}
        self.assertTrue(enviadas <= {69, 72, 76},
                        f"llegaron notas ajenas al patron: {enviadas}")

    def test_sin_patron_el_secuenciador_manda_el_leitmotiv(self):
        self.assertIsNone(self.state.jam.active_pattern)
        self.seq.arranger.jump_to("drop")
        bar = self.seq.next_bar()
        for step in range(render.STEPS_PER_BAR):
            self.seq.dispatch_step(bar, step)
        self.assertTrue(self.pd.notes)

    def test_next_bar_sobrevive_a_un_deck_sin_progresion_para_la_seccion(self):
        # build_context cae a (("i",),) si la seccion no tiene pool.
        self.seq.deck = style.STYLES["determinacion"]
        self.seq.arranger.jump_to("break")
        bar = self.seq.next_bar()
        self.assertIsInstance(bar, render.Bar)


class TestRelojSinDeriva(unittest.IsolatedAsyncioTestCase):
    """La razon de existir de T6: el reloj no acumula deriva.

    El plan probaba swing_offset_ms aislado, pero nunca que run() agende los
    pasos sobre una rejilla absoluta. La version vieja hacia sleep(60/bpm/2)
    DESPUES de trabajar, asi que el coste de cada paso se sumaba al intervalo.
    Esto corre run() contra un reloj falso que solo avanza cuando se duerme, y
    compara los instantes de despacho con la rejilla teorica.
    """

    async def test_los_pasos_caen_en_la_rejilla_absoluta(self):
        state = GlobalState()
        state.jam.bpm = 120          # semicorchea = 125 ms exactos
        pd = FakePd()
        seq = sequencer.Sequencer(state, pd)
        seq.arranger.jump_to("drop")

        reloj = {"t": 1000.0}
        despachos = []
        PASOS_A_MEDIR = 40

        # BaseException a proposito: run() envuelve dispatch_step en un
        # `except Exception` (no se detiene jamas, CLAUDE.md 7), asi que una
        # senal de corte derivada de Exception se la traga y el test cuelga.
        class Basta(BaseException):
            pass

        class LoopFalso:
            @staticmethod
            def time():
                return reloj["t"]

        async def sleep_falso(delay):
            # Un trabajo que tarda: es justo lo que hacia derivar al viejo.
            reloj["t"] += max(0.0, delay) + 0.007

        original_dispatch = seq.dispatch_step

        def dispatch_espia(bar, step):
            despachos.append((bar.index, step, reloj["t"]))
            if len(despachos) >= PASOS_A_MEDIR:
                raise Basta()
            return original_dispatch(bar, step)

        seq.dispatch_step = dispatch_espia
        real_sleep = asyncio.sleep
        real_loop = asyncio.get_running_loop
        asyncio.sleep = sleep_falso
        asyncio.get_running_loop = lambda: LoopFalso()
        try:
            with self.assertRaises(Basta):
                await seq.run()
        finally:
            asyncio.sleep = real_sleep
            asyncio.get_running_loop = real_loop

        self.assertGreaterEqual(len(despachos), PASOS_A_MEDIR)
        paso_s = render.step_ms(120) / 1000.0
        base = despachos[0][2]
        for indice, step, t in despachos:
            esperado = (base + indice * render.STEPS_PER_BAR * paso_s
                        + step * paso_s
                        + sequencer.swing_offset_ms(
                            step, seq.deck.swing, render.step_ms(120)) / 1000.0)
            # El reloj falso solo puede LLEGAR TARDE (el trabajo tarda), nunca
            # temprano, y el retraso no puede acumularse compas a compas.
            with self.subTest(bar=indice, step=step):
                self.assertGreaterEqual(t, esperado - 1e-9)
                self.assertLess(
                    t - esperado, 0.050,
                    f"compas {indice} paso {step} llego {1000*(t-esperado):.1f} "
                    f"ms tarde: el reloj esta derivando")

    async def test_el_reloj_no_deriva_ni_despues_de_muchos_compases(self):
        # Si el error creciera con el tiempo, el ultimo compas medido llegaria
        # mucho mas tarde que el primero. Esto lo compara de punta a punta.
        state = GlobalState()
        state.jam.bpm = 120
        pd = FakePd()
        seq = sequencer.Sequencer(state, pd)

        reloj = {"t": 0.0}
        despachos = []

        # BaseException a proposito: run() envuelve dispatch_step en un
        # `except Exception` (no se detiene jamas, CLAUDE.md 7), asi que una
        # senal de corte derivada de Exception se la traga y el test cuelga.
        class Basta(BaseException):
            pass

        class LoopFalso:
            @staticmethod
            def time():
                return reloj["t"]

        async def sleep_falso(delay):
            reloj["t"] += max(0.0, delay) + 0.003

        original = seq.dispatch_step

        def espia(bar, step):
            despachos.append((bar.index, step, reloj["t"]))
            if len(despachos) >= 16 * 12:
                raise Basta()
            return original(bar, step)

        seq.dispatch_step = espia
        real_sleep, real_loop = asyncio.sleep, asyncio.get_running_loop
        asyncio.sleep = sleep_falso
        asyncio.get_running_loop = lambda: LoopFalso()
        try:
            with self.assertRaises(Basta):
                await seq.run()
        finally:
            asyncio.sleep = real_sleep
            asyncio.get_running_loop = real_loop

        paso_s = render.step_ms(120) / 1000.0
        base = despachos[0][2]

        def error(entrada):
            indice, step, t = entrada
            esperado = (base + indice * render.STEPS_PER_BAR * paso_s
                        + step * paso_s
                        + sequencer.swing_offset_ms(
                            step, seq.deck.swing, render.step_ms(120)) / 1000.0)
            return t - esperado

        primeros = [error(e) for e in despachos[:16]]
        ultimos = [error(e) for e in despachos[-16:]]
        crecimiento = max(ultimos) - max(primeros)
        self.assertLess(
            crecimiento, 0.020,
            f"el error crecio {1000*crecimiento:.1f} ms entre el primer compas "
            f"y el ultimo: hay deriva acumulativa")


if __name__ == "__main__":
    unittest.main()
