import unittest

from bridge import arrangement, harmony, music_engine, render, style


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


# --- lo que los tests del plan no cubren -----------------------------------

class TestContratoDeEstado(unittest.TestCase):
    """render_bar NO es pura: avanza ctx.prev_voicing a proposito.

    El docstring del plan la llamaba "FUNCION PURA" y su test de determinismo
    construia un contexto nuevo en cada llamada, asi que pasaba sin ejercer la
    mutacion. Estos dos tests fijan el contrato de verdad: reproducible desde un
    contexto fresco, y con estado que avanza si se reusa el contexto.
    """

    def test_reusar_el_contexto_avanza_el_voicing(self):
        ctx = make_ctx("drop")
        self.assertEqual(ctx.prev_voicing, [])
        render.render_bar(ctx, 0)
        self.assertNotEqual(ctx.prev_voicing, [],
                            "render_bar deberia dejar el voicing para el "
                            "compas siguiente")
        acordes = [e for e in render.render_bar(ctx, 0).events
                   if e.voice == "chords"]
        self.assertEqual(tuple(ctx.prev_voicing), acordes[0].notes)

    def test_repetir_el_mismo_compas_es_idempotente(self):
        # voice_lead no mueve nada si el acorde no cambio, asi que un reintento
        # del mismo compas da lo mismo. La impureza no se nota aca.
        ctx = make_ctx("drop")
        self.assertEqual(render.render_bar(ctx, 0), render.render_bar(ctx, 0))

    def test_el_voicing_depende_de_que_compas_se_rindio_antes(self):
        # Lo que si cambia con la historia. Documentado porque el test dorado
        # depende de renderizar EN ORDEN.
        def voicing_del_VI(historia):
            ctx = make_ctx("drop", bar_in_section=historia)
            if historia is not None:
                render.render_bar(ctx, historia)
            ctx.bar_in_section = 1
            acordes = [e for e in render.render_bar(ctx, 1).events
                       if e.voice == "chords"]
            return acordes[0].notes

        tras_i = voicing_del_VI(0)      # progresion (i, VI, VII, i)
        tras_VII = voicing_del_VI(2)
        self.assertNotEqual(
            tras_i, tras_VII,
            "el VI deberia voicearse distinto segun el acorde anterior; si son "
            "iguales, la conduccion de voces entre compases no esta actuando")

    def test_reproducible_desde_un_contexto_fresco(self):
        # Lo que T7 y T8 necesitan de verdad: misma secuencia de contextos
        # frescos -> misma partitura, compas a compas.
        def correr():
            ctx = make_ctx("drop")
            salida = []
            for bar in range(8):
                ctx.bar_in_section = bar
                salida.append(render.render_bar(ctx, bar))
            return salida

        self.assertEqual(correr(), correr())


class TestElBajoTocaElAcorde(unittest.TestCase):
    """El bajo tiene que tocar notas DEL acorde, no cualquier nota en rango.

    Este es el test que le faltaba al plan. Su formula era
    `range_lo + pcs[0]`, que solo cae en la clase de altura correcta si range_lo
    es un Do. El bajo de determinacion arranca en 33, que es un La, asi que
    sobre el acorde de tonica A-C-E el bajo tocaba C#2 y F#2: ninguna de las dos
    esta en el acorde. arcade se salvaba de casualidad porque su range_lo es 36,
    un Do. El test del plan (`test_cada_voz_respeta_su_rango`) no lo veia porque
    42 SI esta dentro de 33-57.
    """

    def test_el_bajo_solo_toca_notas_del_acorde(self):
        for sid, deck in style.STYLES.items():
            for scale in deck.scales:
                for section in arrangement.DEFAULT_ARC:
                    if "bass" not in section.voices:
                        continue
                    for progresion in deck.progressions.get(section.name, ()):
                        for bar, roman in enumerate(progresion):
                            pcs = set(harmony.chord_pitch_classes(scale, roman))
                            ctx = render.RenderContext(
                                scale=scale, root=69, bpm=deck.default_bpm,
                                deck=deck, section=section, bar_in_section=bar,
                                progression=progresion,
                                motif=deck.motif_seeds[0])
                            out = render.render_bar(ctx, bar)
                            for event in out.events:
                                if event.voice != "bass":
                                    continue
                                for note in event.notes:
                                    with self.subTest(deck=sid, scale=scale,
                                                      roman=roman):
                                        self.assertIn(
                                            note % 12, pcs,
                                            f"{sid}/{scale} {roman}: el bajo "
                                            f"toca {note} (pc {note % 12}) y "
                                            f"el acorde es {sorted(pcs)}")

    def test_el_bajo_arranca_en_la_fundamental(self):
        # El primer golpe del compas es la fundamental del acorde: es lo que
        # ancla la armonia.
        deck = style.STYLES["determinacion"]
        section = next(p for p in arrangement.DEFAULT_ARC if p.name == "drop")
        for roman in ("i", "VI", "III", "VII", "iv", "V"):
            pcs = harmony.chord_pitch_classes("A_minor", roman)
            ctx = render.RenderContext(
                scale="A_minor", root=69, bpm=124, deck=deck, section=section,
                bar_in_section=0, progression=(roman,),
                motif=deck.motif_seeds[0])
            out = render.render_bar(ctx, 0)
            primero = min((e for e in out.events if e.voice == "bass"),
                          key=lambda e: e.step)
            with self.subTest(roman=roman):
                self.assertEqual(primero.step, 0)
                self.assertEqual(primero.notes[0] % 12, pcs[0],
                                 f"{roman}: el bajo arranca en "
                                 f"{primero.notes[0] % 12}, la fundamental es "
                                 f"{pcs[0]}")

    def test_el_bajo_esta_en_la_octava_mas_grave_que_admite(self):
        # No basta con que sea nota del acorde: un bajo que se va al registro
        # alto deja de ser un bajo.
        for sid, deck in style.STYLES.items():
            patch = deck.voices["bass"]
            section = next(p for p in arrangement.DEFAULT_ARC
                           if p.name == "drop")
            for roman in deck.progressions["drop"][0]:
                ctx = render.RenderContext(
                    scale=deck.scales[0], root=69, bpm=deck.default_bpm,
                    deck=deck, section=section, bar_in_section=0,
                    progression=(roman,), motif=deck.motif_seeds[0])
                out = render.render_bar(ctx, 0)
                for event in out.events:
                    if event.voice != "bass":
                        continue
                    for note in event.notes:
                        with self.subTest(deck=sid, roman=roman):
                            self.assertLess(
                                note, patch.range_lo + 12,
                                f"{sid} {roman}: {note} esta mas de una octava "
                                f"por encima de range_lo={patch.range_lo}")


class TestProgresionesCortas(unittest.TestCase):
    def test_una_progresion_de_dos_acordes_cicla(self):
        # nocturno declara progresiones de largo 2; render no puede asumir 4.
        deck = style.STYLES["nocturno"]
        section = next(p for p in arrangement.DEFAULT_ARC if p.name == "intro")
        progresion = deck.progressions["intro"][0]
        self.assertEqual(len(progresion), 2)

        vistos = []
        ctx = render.RenderContext(
            scale="A_minor", root=69, bpm=76, deck=deck, section=section,
            bar_in_section=0, progression=progresion,
            motif=deck.motif_seeds[0])
        for bar in range(4):
            ctx.bar_in_section = bar
            bar_out = render.render_bar(ctx, bar)
            bajos = [e for e in bar_out.events if e.voice == "bass"]
            vistos.append(bajos[0].notes)
        # i, VI, i, VI -> el compas 0 y el 2 comparten fundamental
        self.assertEqual(vistos[0], vistos[2])
        self.assertEqual(vistos[1], vistos[3])
        self.assertNotEqual(vistos[0], vistos[1])


class TestPatronDeArtista(unittest.TestCase):
    """El patron de un artista remoto reemplaza al leitmotiv en la voz lead.

    Regresion real: al reescribir el secuenciador, jam.active_pattern quedo sin
    lector. main.py seguia aceptando y cuantizando los patrones y la web seguia
    teniendo el boton, pero no sonaban. Estos tests fijan que vuelvan a sonar.
    """

    def test_sin_patron_suena_el_leitmotiv(self):
        bar = render.render_bar(make_ctx("drop"), 0)
        self.assertTrue([e for e in bar.events if e.voice == "lead"])

    def test_con_patron_manda_el_artista(self):
        ctx = make_ctx("drop")
        ctx.artist_pattern = [69, 72, 76]
        bar = render.render_bar(ctx, 0)
        leads = [e for e in bar.events if e.voice == "lead"]
        self.assertTrue(leads)
        # una nota por corchea = 8 en el compas
        self.assertEqual(len(leads), 8)
        self.assertEqual([e.step for e in leads],
                         [0, 2, 4, 6, 8, 10, 12, 14])
        # y las alturas son las del artista, cicladas
        alturas = [e.notes[0] for e in leads]
        self.assertEqual(alturas[:3], [69, 72, 76])
        self.assertEqual(alturas[3], 69, "el patron deberia ciclar")

    def test_el_patron_se_pliega_al_rango_de_la_voz(self):
        # resolve_pattern cuantiza a la escala pero NO acota el registro.
        ctx = make_ctx("drop")
        patch = style.STYLES["determinacion"].voices["lead"]
        ctx.artist_pattern = [12, 21, 120, 127]
        bar = render.render_bar(ctx, 0)
        for event in bar.events:
            if event.voice != "lead":
                continue
            for note in event.notes:
                self.assertGreaterEqual(note, patch.range_lo)
                self.assertLessEqual(note, patch.range_hi)

    def test_el_patron_no_toca_las_demas_voces(self):
        ctx = make_ctx("drop")
        sin = render.render_bar(make_ctx("drop"), 0)
        ctx.artist_pattern = [69, 71]
        con = render.render_bar(ctx, 0)

        def sin_lead(bar):
            return [e for e in bar.events if e.voice != "lead"]

        self.assertEqual(sin_lead(sin), sin_lead(con),
                         "el patron del artista solo debe cambiar el lead")

    def test_un_patron_vacio_no_enmudece_el_lead(self):
        # active_pattern arranca en None y puede llegar [] desde el JSON.
        for vacio in (None, []):
            ctx = make_ctx("drop")
            ctx.artist_pattern = vacio
            bar = render.render_bar(ctx, 0)
            with self.subTest(vacio=vacio):
                self.assertTrue([e for e in bar.events if e.voice == "lead"],
                                "sin patron tiene que volver el leitmotiv")

    def test_el_patron_acentua_cuando_vuelve_a_empezar(self):
        ctx = make_ctx("drop")
        ctx.artist_pattern = [69, 72]
        bar = render.render_bar(ctx, 0)
        leads = sorted((e for e in bar.events if e.voice == "lead"),
                       key=lambda e: e.step)
        # patron de 2 notas: acento en las corcheas pares (0, 4, 8, 12)
        acentuados = [e.step for e in leads
                      if e.velocity == render.VELOCITY_ACCENT]
        self.assertEqual(acentuados, [0, 4, 8, 12])


class TestCruceCompleto(unittest.TestCase):
    """Todo deck x toda seccion x toda escala del deck tiene que renderizar.

    Los tests del plan solo miran determinacion en A_minor. Un preset roto en
    otra escala solo se notaria en vivo.
    """

    def test_todo_el_cruce_produce_eventos_validos(self):
        for sid, deck in style.STYLES.items():
            for scale in deck.scales:
                for section in arrangement.DEFAULT_ARC:
                    pool = deck.progressions.get(section.name)
                    if not pool:
                        continue
                    for progresion in pool:
                        ctx = render.RenderContext(
                            scale=scale, root=69, bpm=deck.default_bpm,
                            deck=deck, section=section, bar_in_section=0,
                            progression=progresion,
                            motif=deck.motif_seeds[0])
                        for bar in range(len(progresion)):
                            ctx.bar_in_section = bar
                            out = render.render_bar(ctx, bar)
                            with self.subTest(deck=sid, scale=scale,
                                              section=section.name, bar=bar):
                                self._revisar(out, deck, section)

    def _revisar(self, out, deck, section):
        for event in out.events:
            self.assertGreaterEqual(event.step, 0)
            self.assertLess(event.step, render.STEPS_PER_BAR)
            self.assertGreaterEqual(event.velocity, 1)
            self.assertLessEqual(event.velocity, 127)
            self.assertGreaterEqual(event.dur_steps, 1)
            self.assertTrue(event.notes, "un evento sin notas no suena")
            if event.voice == "drums":
                continue
            self.assertIn(event.voice, section.voices)
            patch = deck.voices[event.voice]
            for note in event.notes:
                self.assertGreaterEqual(note, 0)
                self.assertLessEqual(note, 127)
                self.assertGreaterEqual(note, patch.range_lo)
                self.assertLessEqual(note, patch.range_hi)

    def test_el_lead_queda_en_escala_tambien_sobre_el_V(self):
        # El V presta la sensible (G# en A menor). El acorde puede traerla; la
        # melodia no, porque chord_degrees trabaja en grados de la escala.
        deck = style.STYLES["determinacion"]
        section = next(p for p in arrangement.DEFAULT_ARC if p.name == "build")
        progresion = ("i", "iv", "V", "V")
        pcs = music_engine.pitch_classes("A_minor")
        ctx = render.RenderContext(
            scale="A_minor", root=69, bpm=124, deck=deck, section=section,
            bar_in_section=2, progression=progresion,
            motif=deck.motif_seeds[0])
        out = render.render_bar(ctx, 2)
        leads = [e for e in out.events if e.voice == "lead"]
        self.assertTrue(leads, "el build deberia traer lead")
        for event in leads:
            for note in event.notes:
                self.assertIn(note % 12, pcs, f"{note} fuera de A_minor")


if __name__ == "__main__":
    unittest.main()
