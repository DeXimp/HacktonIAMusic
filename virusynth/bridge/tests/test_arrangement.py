import unittest

from bridge import arrangement as A
from bridge import style


class TestDefaultArc(unittest.TestCase):
    def test_empieza_en_intro(self):
        self.assertEqual(A.DEFAULT_ARC[0].name, "intro")

    def test_todas_las_secciones_del_arco_son_conocidas(self):
        for plan in A.DEFAULT_ARC:
            self.assertIn(plan.name, A.SECTIONS)

    def test_todas_las_secciones_duran_al_menos_un_compas(self):
        for plan in A.DEFAULT_ARC:
            self.assertGreaterEqual(plan.bars, 1)

    def test_el_drop_es_la_seccion_mas_densa(self):
        drop = next(p for p in A.DEFAULT_ARC if p.name == "drop")
        intro = next(p for p in A.DEFAULT_ARC if p.name == "intro")
        self.assertGreater(drop.density, intro.density)

    def test_el_pad_solo_aparece_en_drop_y_outro(self):
        for plan in A.DEFAULT_ARC:
            if "pad" in plan.voices:
                self.assertIn(plan.name, ("drop", "outro"))

    def test_los_modos_de_tempo_son_validos(self):
        for plan in A.DEFAULT_ARC:
            self.assertIn(plan.tempo_mode, ("normal", "half", "double"))

    def test_las_voces_del_arco_existen_en_los_decks(self):
        """Una voz mal escrita no falla: enmudece.

        arrangement.py es stdlib puro a proposito, no importa style, asi que
        nada le impide declarar "leed" en vez de "lead". render.py buscaria esa
        voz en deck.voices, no la encontraria, y la seccion sonaria incompleta
        sin un solo error en el log. Este test es el unico lugar donde los dos
        vocabularios se cruzan.
        """
        for plan in A.DEFAULT_ARC:
            for voice in plan.voices:
                self.assertIn(voice, style.VOICE_NAMES,
                              f"{plan.name} declara la voz {voice!r}, que no "
                              f"esta en style.VOICE_NAMES")

    def test_la_densidad_esta_normalizada(self):
        # render.py la usa como fraccion de pasos que se llenan: fuera de 0..1
        # o no suena nada o desborda el compas.
        for plan in A.DEFAULT_ARC:
            self.assertGreaterEqual(plan.density, 0.0, plan.name)
            self.assertLessEqual(plan.density, 1.0, plan.name)

    def test_toda_seccion_tiene_al_menos_una_voz(self):
        # Una seccion sin voces es silencio absoluto en el escenario.
        for plan in A.DEFAULT_ARC:
            self.assertTrue(plan.voices, f"{plan.name} no declara ninguna voz")


class TestArranger(unittest.TestCase):
    def test_arranca_en_la_primera_seccion(self):
        arranger = A.Arranger()
        self.assertEqual(arranger.section.name, "intro")
        self.assertEqual(arranger.bar_in_section, 0)

    def test_advance_avanza_dentro_de_la_seccion(self):
        arranger = A.Arranger()
        arranger.advance()
        self.assertEqual(arranger.section.name, "intro")
        self.assertEqual(arranger.bar_in_section, 1)

    def test_al_agotar_los_compases_pasa_a_la_siguiente_seccion(self):
        arranger = A.Arranger()
        for _ in range(arranger.section.bars):
            arranger.advance()
        self.assertEqual(arranger.section.name, A.DEFAULT_ARC[1].name)
        self.assertEqual(arranger.bar_in_section, 0)

    def test_el_arco_cicla(self):
        arranger = A.Arranger()
        total = sum(p.bars for p in A.DEFAULT_ARC)
        for _ in range(total):
            arranger.advance()
        self.assertEqual(arranger.section.name, "intro")
        self.assertEqual(arranger.bar_in_section, 0)

    def test_is_last_bar_solo_en_el_ultimo_compas(self):
        arranger = A.Arranger()
        bars = arranger.section.bars
        for _ in range(bars - 1):
            self.assertFalse(arranger.is_last_bar())
            arranger.advance()
        self.assertTrue(arranger.is_last_bar())

    def test_jump_to_salta_y_reinicia_el_contador(self):
        arranger = A.Arranger()
        arranger.advance()
        self.assertTrue(arranger.jump_to("drop"))
        self.assertEqual(arranger.section.name, "drop")
        self.assertEqual(arranger.bar_in_section, 0)

    def test_jump_to_a_una_seccion_desconocida_no_cambia_nada(self):
        arranger = A.Arranger()
        arranger.advance()
        self.assertFalse(arranger.jump_to("no-existe"))
        self.assertEqual(arranger.section.name, "intro")
        self.assertEqual(arranger.bar_in_section, 1)

    def test_un_arco_vacio_cae_al_default(self):
        # El arco es un parametro publico y la Fase 2 lo expone a la IA.
        self.assertEqual(A.Arranger(arc=()).section.name, "intro")

    def test_recorre_el_arco_entero_en_orden(self):
        # El test del ciclo prueba que vuelve al principio, no que pase por
        # todas las secciones en el camino. Esto si.
        arranger = A.Arranger()
        visto = []
        for _ in range(sum(p.bars for p in A.DEFAULT_ARC)):
            if arranger.bar_in_section == 0:
                visto.append(arranger.section.name)
            arranger.advance()
        self.assertEqual(visto, [p.name for p in A.DEFAULT_ARC])

    def test_jump_to_no_rompe_el_recorrido_posterior(self):
        # Tras un salto el arco sigue desde ahi, no desde donde estaba.
        arranger = A.Arranger()
        arranger.jump_to("break")
        indice_break = [p.name for p in A.DEFAULT_ARC].index("break")
        for _ in range(A.DEFAULT_ARC[indice_break].bars):
            arranger.advance()
        self.assertEqual(arranger.section.name,
                         A.DEFAULT_ARC[indice_break + 1].name)


if __name__ == "__main__":
    unittest.main()
