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

    def test_get_style_tolera_lo_que_no_es_str(self):
        # El id llega del JSON de la IA y de la web: un tipo raro no puede
        # tumbar la jam (CLAUDE.md 7). Antes esto era un AttributeError.
        for basura in (None, 5, True, [], {"a": 1}, 3.5, object()):
            with self.subTest(basura=basura):
                self.assertIs(style.get_style(basura),
                              style.STYLES[style.DEFAULT_STYLE_ID])

    def test_get_style_normaliza_espacios_y_mayusculas(self):
        self.assertIs(style.get_style("  ARCADE  "), style.STYLES["arcade"])


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

    def test_ninguna_tonica_trae_notas_fuera_de_su_escala(self):
        """El acorde de tonica no puede pelearse con la escala.

        La cualidad del acorde la fija la caja del numeral (harmony.parse_roman),
        no la escala, asi que un deck puede declarar una escala cuyo modo la
        contradiga. En los grados de color eso es un prestamo idiomatico; en la
        TONICA es un choque que se oye en cada compas. Esto lo caza.

        Fue un hallazgo real: arcade declaraba D_dorian y su `I` daba D-F#-A,
        una tonica mayor sobre un modo menor cuya melodia trae F natural.
        """
        for sid, deck in style.STYLES.items():
            for scale in deck.scales:
                in_scale = music_engine.pitch_classes(scale)
                for section, pool in deck.progressions.items():
                    for progression in pool:
                        for roman in progression:
                            degree, _quality = harmony.parse_roman(roman)
                            if degree != 1:
                                continue
                            pcs = harmony.chord_pitch_classes(scale, roman)
                            fuera = sorted(set(pcs) - in_scale)
                            self.assertEqual(
                                fuera, [],
                                f"{sid}/{section} {roman!r} en {scale} da "
                                f"{sorted(pcs)} y {fuera} no esta en la escala")

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
