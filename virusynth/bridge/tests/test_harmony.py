import unittest

from bridge import harmony, music_engine


class TestParseRoman(unittest.TestCase):
    def test_minusculas_son_menores(self):
        self.assertEqual(harmony.parse_roman("i"), (1, "min"))
        self.assertEqual(harmony.parse_roman("iv"), (4, "min"))

    def test_mayusculas_son_mayores(self):
        self.assertEqual(harmony.parse_roman("VI"), (6, "maj"))
        self.assertEqual(harmony.parse_roman("VII"), (7, "maj"))
        self.assertEqual(harmony.parse_roman("III"), (3, "maj"))

    def test_septimas(self):
        self.assertEqual(harmony.parse_roman("V7"), (5, "dom7"))
        self.assertEqual(harmony.parse_roman("i7"), (1, "min7"))

    def test_disminuido(self):
        self.assertEqual(harmony.parse_roman("ii°"), (2, "dim"))

    def test_roman_invalido(self):
        with self.assertRaises(harmony.HarmonyError):
            harmony.parse_roman("viii")
        with self.assertRaises(harmony.HarmonyError):
            harmony.parse_roman("")


class TestChordPitchClasses(unittest.TestCase):
    def test_tonica_menor_en_la_menor(self):
        # A minor: A C E = 9 0 4
        self.assertEqual(harmony.chord_pitch_classes("A_minor", "i"), (9, 0, 4))

    def test_sexto_grado_mayor_en_la_menor(self):
        # VI en La menor = Fa mayor: F A C = 5 9 0
        self.assertEqual(harmony.chord_pitch_classes("A_minor", "VI"), (5, 9, 0))

    def test_quinto_mayor_lleva_sensible(self):
        # V mayor en La menor = Mi mayor: E G# B = 4 8 11.
        # El G# (8) es la sensible de la menor armonica: es el medio tono
        # que empuja hacia la tonica y define el sonido de los temas de jefe.
        self.assertEqual(harmony.chord_pitch_classes("A_minor", "V"), (4, 8, 11))

    def test_escala_pentatonica_usa_el_marco_menor(self):
        # Am_pentatonic no tiene 7 grados; para acordes se usa el marco de
        # La menor natural, que es lo que haria cualquier musico.
        self.assertEqual(harmony.chord_pitch_classes("Am_pentatonic", "i"), (9, 0, 4))

    def test_escala_invalida(self):
        with self.assertRaises(harmony.HarmonyError):
            harmony.chord_pitch_classes("H_minor", "i")

    def test_dorian_usa_sus_propios_intervalos(self):
        # A_dorian: [0, 2, 3, 5, 7, 9, 10] => grados {1:0, 2:2, 3:3, 4:5, 5:7, 6:9, 7:10}
        # VI en A_dorian = grado 6 => intervalo 9 => raiz (9+9)%12=6 (F#, no F)
        # Acorde F# mayor = F# A# C# = 6 10 1
        self.assertEqual(harmony.chord_pitch_classes("A_dorian", "VI"), (6, 10, 1))

    def test_harmonic_minor_usa_sus_propios_intervalos(self):
        # A_harmonic_minor: [0, 2, 3, 5, 7, 8, 11] => grados {1:0, 2:2, 3:3, 4:5, 5:7, 6:8, 7:11}
        # VII en A_harmonic_minor = grado 7 => intervalo 11 => raiz (9+11)%12=8 (G#, no G)
        # Acorde G# mayor = G# B D# = 8 0 3
        self.assertEqual(harmony.chord_pitch_classes("A_harmonic_minor", "VII"), (8, 0, 3))


class TestChordAt(unittest.TestCase):
    def test_cicla_la_progresion(self):
        prog = ("i", "VI", "III", "VII")
        self.assertEqual(harmony.chord_at(prog, 0), "i")
        self.assertEqual(harmony.chord_at(prog, 3), "VII")
        self.assertEqual(harmony.chord_at(prog, 4), "i")
        self.assertEqual(harmony.chord_at(prog, 9), "VI")

    def test_progresion_vacia(self):
        self.assertEqual(harmony.chord_at((), 3), "i")


class TestChordNotes(unittest.TestCase):
    def test_solo_notas_del_acorde_en_el_rango(self):
        notes = harmony.chord_notes("A_minor", "i", 57, 72)
        self.assertEqual(notes, [57, 60, 64, 69, 72])

    def test_rango_invertido_da_lista_vacia(self):
        self.assertEqual(harmony.chord_notes("A_minor", "i", 72, 57), [])


class TestVoiceLead(unittest.TestCase):
    def test_elige_el_voicing_mas_cercano_al_anterior(self):
        prev = [60, 64, 67]                      # Do mayor
        result = harmony.voice_lead(prev, "A_minor", "VI", 55, 79)
        # F A C: conserva el Do (60), cambia Mi a Fa (65), Sol a La (69) -> coste 3
        self.assertEqual(result, [60, 65, 69])

    def test_sin_voicing_previo_no_revienta(self):
        result = harmony.voice_lead([], "A_minor", "i", 55, 79)
        self.assertEqual(len(result), 3)
        for note in result:
            self.assertGreaterEqual(note, 55)
            self.assertLessEqual(note, 79)

    def test_resultado_siempre_ordenado(self):
        result = harmony.voice_lead([79, 55, 60], "A_minor", "VII", 55, 79)
        self.assertEqual(result, sorted(result))

    def test_rango_estrecho_omite_clases_sin_candidatos(self):
        # Rango muy estrecho [60, 64]: solo caben Do y Mi, no Fa ni La.
        # El acorde A_minor "i" es A C E (9, 0, 4).
        # En [60, 64] estan: Do (0) en 60, 72 (solo 60); Mi (4) en 64; La (9) en 57, 69 (ninguno)
        # Resultado: acorde incompleto [60, 64] (Do y Mi)
        result = harmony.voice_lead([], "A_minor", "i", 60, 64)
        # Solo Do y Mi caben; La se omite
        self.assertEqual(len(result), 2)
        for note in result:
            self.assertGreaterEqual(note, 60)
            self.assertLessEqual(note, 64)
        for note in result:
            self.assertTrue(harmony.is_chord_tone(note, "A_minor", "i"))

    def test_prev_fuera_de_rango_no_afecta_resultado(self):
        # prev tiene notas fuera del rango nuevo
        prev = [500, 120, 50]  # todas fuera de [60, 79]
        result = harmony.voice_lead(prev, "A_minor", "i", 60, 79)
        # Resultado valido: todas las notas en [60, 79] y todas tonos del acorde
        for note in result:
            self.assertGreaterEqual(note, 60)
            self.assertLessEqual(note, 79)
            self.assertTrue(harmony.is_chord_tone(note, "A_minor", "i"))


class TestIsChordTone(unittest.TestCase):
    def test_reconoce_tonos_del_acorde_en_cualquier_octava(self):
        self.assertTrue(harmony.is_chord_tone(69, "A_minor", "i"))
        self.assertTrue(harmony.is_chord_tone(45, "A_minor", "i"))
        self.assertFalse(harmony.is_chord_tone(71, "A_minor", "i"))


class TestChordDegrees(unittest.TestCase):
    def test_triada_de_tonica_cae_en_grados_0_2_4(self):
        # En una escala de 7 notas la triada de tonica ocupa los grados 0, 2 y 4.
        self.assertEqual(harmony.chord_degrees("A_minor", "i"), (0, 2, 4))

    def test_grados_de_un_acorde_ajeno_a_la_escala(self):
        # V en La menor = Mi mayor (E G# B). E es el grado 4 y B el grado 1 de
        # la escala; el G# NO esta en La menor natural, asi que se omite en vez
        # de inventar un grado que la escala no tiene.
        self.assertEqual(harmony.chord_degrees("A_minor", "V"), (1, 4))


class TestFrameDerivation(unittest.TestCase):
    def test_grados_pentatonico_derivados_de_scale_intervals(self):
        # Garantiza que _frame no teclea literales para pentatonicas/blues.
        # Las tablas deben derivarse de music_engine.SCALE_INTERVALS, no hardcodeadas.
        # Si este test falla, es porque alguien reintrodujo dicts literales.

        # Pentatonica menor: deberia usar marco menor derivado
        minor_pent_intervals = music_engine.SCALE_INTERVALS["minor_pentatonic"]
        minor_framework = {i + 1: v for i, v in enumerate(music_engine.SCALE_INTERVALS["minor"])}
        root_pc, degrees = harmony._frame("Am_pentatonic")
        self.assertEqual(degrees, minor_framework,
                         "Pentatonica menor debe derivar del marco menor, no tener literales")

        # Pentatonica mayor: deberia usar marco mayor derivado
        major_pent_intervals = music_engine.SCALE_INTERVALS["major_pentatonic"]
        major_framework = {i + 1: v for i, v in enumerate(music_engine.SCALE_INTERVALS["major"])}
        root_pc, degrees = harmony._frame("C_pentatonic")
        self.assertEqual(degrees, major_framework,
                         "Pentatonica mayor debe derivar del marco mayor, no tener literales")

        # Blues (6 intervalos): deberia usar marco menor derivado
        root_pc, degrees = harmony._frame("Bb_blues")
        self.assertEqual(degrees, minor_framework,
                         "Blues debe derivar del marco menor, no tener literales")

    def test_modos_7_intervalos_usan_propios(self):
        # Verifica que modos de 7 intervalos (dorian, harmonic_minor, etc.)
        # derivan sus grados de sus propios intervalos, no de un marco general.
        dorian_intervals = music_engine.SCALE_INTERVALS["dorian"]
        dorian_expected = {i + 1: v for i, v in enumerate(dorian_intervals)}
        root_pc, degrees = harmony._frame("A_dorian")
        self.assertEqual(degrees, dorian_expected)

        harm_minor_intervals = music_engine.SCALE_INTERVALS["harmonic_minor"]
        harm_minor_expected = {i + 1: v for i, v in enumerate(harm_minor_intervals)}
        root_pc, degrees = harmony._frame("A_harmonic_minor")
        self.assertEqual(degrees, harm_minor_expected)


if __name__ == "__main__":
    unittest.main()
