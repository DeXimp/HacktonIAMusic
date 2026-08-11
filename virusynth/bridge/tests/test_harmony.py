import unittest

from bridge import harmony


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
        # F A C: desde 60,64,67 lo mas cercano es 65,69,72 -> total 15 semitonos.
        self.assertEqual(result, [65, 69, 72])

    def test_sin_voicing_previo_no_revienta(self):
        result = harmony.voice_lead([], "A_minor", "i", 55, 79)
        self.assertEqual(len(result), 3)
        for note in result:
            self.assertGreaterEqual(note, 55)
            self.assertLessEqual(note, 79)

    def test_resultado_siempre_ordenado(self):
        result = harmony.voice_lead([79, 55, 60], "A_minor", "VII", 55, 79)
        self.assertEqual(result, sorted(result))


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


if __name__ == "__main__":
    unittest.main()
