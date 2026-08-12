import unittest

from bridge import motif as M

SEED = M.Motif(steps=(
    M.MotifStep(0, 2, True),
    M.MotifStep(2, 2, False),
    M.MotifStep(4, 4, False),
    M.MotifStep(3, 2, False),
    M.MotifStep(2, 4, True),
), name="prueba")


class TestMotifBasics(unittest.TestCase):
    def test_length_suma_las_duraciones(self):
        self.assertEqual(SEED.length, 14)

    def test_el_motivo_es_inmutable(self):
        with self.assertRaises(Exception):
            SEED.steps = ()


class TestTransformaciones(unittest.TestCase):
    def test_transpose_desplaza_todos_los_grados(self):
        result = M.transpose(SEED, 2)
        self.assertEqual([s.degree for s in result.steps], [2, 4, 6, 5, 4])

    def test_transpose_conserva_duraciones_y_acentos(self):
        result = M.transpose(SEED, 3)
        self.assertEqual([s.dur for s in result.steps], [2, 2, 4, 2, 4])
        self.assertEqual([s.accent for s in result.steps],
                         [True, False, False, False, True])

    def test_invert_refleja_el_contorno(self):
        result = M.invert(SEED, axis=0)
        self.assertEqual([s.degree for s in result.steps], [0, -2, -4, -3, -2])

    def test_invert_es_involutiva(self):
        self.assertEqual(M.invert(M.invert(SEED)), SEED)

    def test_retrograde_invierte_el_orden(self):
        result = M.retrograde(SEED)
        self.assertEqual([s.degree for s in result.steps], [2, 3, 4, 2, 0])

    def test_retrograde_es_involutiva(self):
        self.assertEqual(M.retrograde(M.retrograde(SEED)), SEED)

    def test_augment_duplica_las_duraciones(self):
        result = M.augment(SEED, 2)
        self.assertEqual([s.dur for s in result.steps], [4, 4, 8, 4, 8])
        self.assertEqual(result.length, 28)

    def test_diminish_reduce_pero_nunca_baja_de_uno(self):
        result = M.diminish(SEED, 4)
        self.assertEqual([s.dur for s in result.steps], [1, 1, 1, 1, 1])

    def test_diminish_con_factor_cero_no_revienta(self):
        # La Fase 2 expone f a la IA via transform_motif: un 0 no puede crashear.
        self.assertEqual(M.diminish(SEED, 0), SEED)

    def test_diminish_con_factor_negativo_devuelve_el_motivo_intacto(self):
        self.assertEqual(M.diminish(SEED, -3), SEED)

    def test_augment_con_factor_cero_devuelve_el_motivo_intacto(self):
        # Sin guarda aplastaba todas las duraciones a 1 en silencio.
        self.assertEqual(M.augment(SEED, 0), SEED)

    def test_augment_con_factor_negativo_devuelve_el_motivo_intacto(self):
        self.assertEqual(M.augment(SEED, -2), SEED)

    def test_octave_desplaza_una_octava_de_grados(self):
        result = M.octave(SEED, 1, degrees_per_octave=7)
        self.assertEqual([s.degree for s in result.steps], [7, 9, 11, 10, 9])


class TestReharmonize(unittest.TestCase):
    def test_los_pasos_acentuados_caen_en_tonos_del_acorde(self):
        # Triada de tonica en una escala de 7 notas: grados 0, 2, 4.
        result = M.reharmonize(SEED, chord_degrees=(0, 2, 4), scale_size=7)
        for step in result.steps:
            if step.accent:
                self.assertIn(step.degree % 7, (0, 2, 4))

    def test_los_pasos_sin_acento_no_se_tocan(self):
        result = M.reharmonize(SEED, chord_degrees=(0, 2, 4), scale_size=7)
        original = [s.degree for s in SEED.steps]
        for i, step in enumerate(result.steps):
            if not SEED.steps[i].accent:
                self.assertEqual(step.degree, original[i])

    def test_sin_tonos_de_acorde_devuelve_el_motivo_intacto(self):
        self.assertEqual(M.reharmonize(SEED, (), 7), SEED)

    def test_ancla_al_mas_cercano_muy_por_encima_del_registro(self):
        # Con la ventana fija range(-3, 4) el candidato mas alto era 25.
        m = M.Motif(steps=(M.MotifStep(27, 4, True),))
        result = M.reharmonize(m, chord_degrees=(0, 2, 4), scale_size=7)
        self.assertEqual(result.steps[0].degree, 28)

    def test_ancla_al_mas_cercano_muy_por_debajo_del_registro(self):
        m = M.Motif(steps=(M.MotifStep(-23, 4, True),))
        result = M.reharmonize(m, chord_degrees=(0, 2, 4), scale_size=7)
        self.assertEqual(result.steps[0].degree, -24)

    def test_un_grado_que_ya_es_tono_del_acorde_no_se_mueve(self):
        # El grado 32 sale de octave(m, 4, 7); 32 % 7 == 4, ya era tono del
        # acorde, y la ventana fija lo desplazaba una octava entera hasta 25.
        m = M.Motif(steps=(M.MotifStep(32, 4, True),))
        result = M.reharmonize(m, chord_degrees=(0, 2, 4), scale_size=7)
        self.assertEqual(result.steps[0].degree, 32)

    def test_coincide_con_la_fuerza_bruta_en_todo_el_rango_util(self):
        chord, size = (0, 2, 4), 7
        wide = [c + size * k for k in range(-60, 61) for c in chord]
        for degree in range(-90, 91):
            m = M.Motif(steps=(M.MotifStep(degree, 4, True),))
            got = M.reharmonize(m, chord, size).steps[0].degree
            expected = min(wide, key=lambda c: (abs(c - degree), c))
            self.assertEqual(got, expected, f"grado {degree}")

    def test_octave_alto_y_reharmonize_no_baja_la_nota_una_octava(self):
        # Regresion de punta a punta: rearmonizar un tono de acorde no puede
        # producir notas MIDI peores que no rearmonizar.
        base = M.Motif(steps=(M.MotifStep(4, 4, True), M.MotifStep(2, 4, False)))
        up = M.octave(base, 4, degrees_per_octave=7)
        sin_rearmonizar = M.realize(up, "A_minor", 57, 0, 127)
        con_rearmonizar = M.realize(M.reharmonize(up, (0, 2, 4), 7),
                                    "A_minor", 57, 0, 127)
        self.assertEqual(con_rearmonizar, sin_rearmonizar)


class TestOrnament(unittest.TestCase):
    def test_inserta_notas_de_paso_en_saltos_grandes(self):
        result = M.ornament(SEED, level=1)
        self.assertGreater(len(result.steps), len(SEED.steps))

    def test_conserva_la_duracion_total(self):
        result = M.ornament(SEED, level=1)
        self.assertEqual(result.length, SEED.length)

    def test_es_determinista(self):
        self.assertEqual(M.ornament(SEED, 1), M.ornament(SEED, 1))

    def test_nivel_cero_no_hace_nada(self):
        self.assertEqual(M.ornament(SEED, 0), SEED)


class TestFoldToRange(unittest.TestCase):
    def test_sube_por_octavas_lo_que_queda_grave(self):
        self.assertEqual(M.fold_to_range(40, 60, 72), 64)

    def test_baja_por_octavas_lo_que_queda_agudo(self):
        self.assertEqual(M.fold_to_range(90, 60, 72), 66)

    def test_deja_intacto_lo_que_ya_entra(self):
        self.assertEqual(M.fold_to_range(65, 60, 72), 65)

    def test_rango_mas_estrecho_que_una_octava_no_cuelga(self):
        result = M.fold_to_range(40, 60, 64)
        self.assertGreaterEqual(result, 60)
        self.assertLessEqual(result, 64)


class TestRealize(unittest.TestCase):
    def test_el_grado_cero_es_la_tonica(self):
        events = M.realize(SEED, "A_minor", root=69, lo=57, hi=81)
        self.assertEqual(events[0][1], 69)

    def test_los_offsets_se_acumulan(self):
        events = M.realize(SEED, "A_minor", root=69, lo=57, hi=81)
        self.assertEqual([e[0] for e in events], [0, 2, 4, 8, 10])

    def test_todas_las_notas_caen_en_la_escala(self):
        from bridge import music_engine
        pcs = music_engine.pitch_classes("A_minor")
        for _off, note, _dur, _acc in M.realize(SEED, "A_minor", 69, 57, 81):
            self.assertIn(note % 12, pcs)

    def test_todas_las_notas_caen_dentro_del_rango(self):
        for _off, note, _dur, _acc in M.realize(SEED, "A_minor", 69, 60, 72):
            self.assertGreaterEqual(note, 60)
            self.assertLessEqual(note, 72)

    def test_motivo_vacio_devuelve_lista_vacia(self):
        self.assertEqual(M.realize(M.Motif(steps=()), "A_minor", 69, 57, 81), [])


if __name__ == "__main__":
    unittest.main()
