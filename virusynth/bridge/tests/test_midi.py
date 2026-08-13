import struct
import unittest

from bridge import midi, render, sequencer


def make_bars():
    events = (
        render.VoiceEvent("lead", 0, (69,), 100, 4),
        render.VoiceEvent("bass", 0, (45,), 110, 8),
        render.VoiceEvent("chords", 4, (57, 60, 64), 70, 4),
        render.VoiceEvent("drums", 0, (0,), 112, 1),
    )
    return [render.Bar(0, 120, 2000, 0.0, "verse", events)]


class TestVarint(unittest.TestCase):
    def test_valores_pequenos_ocupan_un_byte(self):
        self.assertEqual(midi.varint(0), b"\x00")
        self.assertEqual(midi.varint(127), b"\x7f")

    def test_valores_grandes_usan_continuacion(self):
        self.assertEqual(midi.varint(128), b"\x81\x00")
        self.assertEqual(midi.varint(480), b"\x83\x60")

    def test_los_negativos_se_tratan_como_cero(self):
        self.assertEqual(midi.varint(-5), b"\x00")

    def test_ida_y_vuelta_para_muchos_valores(self):
        # El plan probaba 5 valores sueltos. Esto decodifica lo codificado, que
        # es lo que hace un reproductor de verdad.
        def decodificar(data):
            valor = 0
            for i, byte in enumerate(data):
                valor = (valor << 7) | (byte & 0x7F)
                if not byte & 0x80:
                    return valor, i + 1
            raise AssertionError("varint sin byte final")

        for v in (0, 1, 127, 128, 255, 480, 1000, 8192, 16383, 16384,
                  100000, 0x0FFFFFFF):
            data = midi.varint(v)
            with self.subTest(v=v):
                self.assertLessEqual(len(data), 4, "MIDI admite 4 bytes maximo")
                decodificado, consumidos = decodificar(data)
                self.assertEqual(decodificado, v)
                self.assertEqual(consumidos, len(data))


class TestBarsToMidi(unittest.TestCase):
    def setUp(self):
        self.data = midi.bars_to_midi(make_bars())

    def test_empieza_con_la_cabecera_MThd(self):
        self.assertEqual(self.data[:4], b"MThd")

    def test_la_cabecera_declara_formato_1(self):
        length, fmt, ntracks, division = struct.unpack(">IHHH", self.data[4:14])
        self.assertEqual(length, 6)
        self.assertEqual(fmt, 1)
        self.assertGreaterEqual(ntracks, 2)
        self.assertEqual(division, 480)

    def test_hay_tantas_pistas_como_declara_la_cabecera(self):
        ntracks = struct.unpack(">H", self.data[10:12])[0]
        self.assertEqual(self.data.count(b"MTrk"), ntracks)

    def test_toda_pista_termina_en_end_of_track(self):
        self.assertIn(b"\xff\x2f\x00", self.data)

    def test_la_primera_pista_lleva_el_tempo(self):
        self.assertIn(b"\xff\x51\x03", self.data)

    def test_la_bateria_va_al_canal_10(self):
        # Canal 10 en notacion humana = 9 en el protocolo: 0x99 = note on ch9.
        self.assertIn(b"\x99", self.data)

    def test_sin_compases_sigue_produciendo_un_archivo_valido(self):
        data = midi.bars_to_midi([])
        self.assertEqual(data[:4], b"MThd")
        self.assertIn(b"\xff\x2f\x00", data)

    # --- lo que los tests del plan no cubren -------------------------------

    def test_cada_pista_declara_bien_su_longitud(self):
        # Una longitud mal calculada da un archivo que algunos reproductores
        # abren igual (leen hasta el final) y otros rechazan. Esto recorre los
        # chunks como lo haria un parser estricto.
        pos = 14
        chunks = 0
        while pos < len(self.data):
            self.assertEqual(self.data[pos:pos + 4], b"MTrk",
                             f"se esperaba MTrk en el byte {pos}")
            largo = struct.unpack(">I", self.data[pos + 4:pos + 8])[0]
            cuerpo = self.data[pos + 8:pos + 8 + largo]
            self.assertEqual(len(cuerpo), largo, "la pista se corta")
            self.assertTrue(cuerpo.endswith(b"\xff\x2f\x00"),
                            "la pista no termina en end-of-track")
            pos += 8 + largo
            chunks += 1
        self.assertEqual(pos, len(self.data), "sobran bytes al final")
        self.assertEqual(chunks,
                         struct.unpack(">H", self.data[10:12])[0])

    def test_toda_nota_encendida_se_apaga(self):
        # Una nota que no se apaga queda sonando para siempre en el
        # reproductor. Se recorre cada pista contando on/off por altura.
        for pista in self._pistas():
            colgadas = {}
            for status, dato1, _dato2 in self._eventos_de_nota(pista):
                if status & 0xF0 == 0x90:
                    colgadas[dato1] = colgadas.get(dato1, 0) + 1
                elif status & 0xF0 == 0x80:
                    colgadas[dato1] = colgadas.get(dato1, 0) - 1
            for nota, saldo in colgadas.items():
                self.assertEqual(saldo, 0,
                                 f"la nota {nota} queda con saldo {saldo}")

    def test_el_tempo_corresponde_al_bpm(self):
        pos = self.data.find(b"\xff\x51\x03")
        us = int.from_bytes(self.data[pos + 3:pos + 6], "big")
        # 120 BPM = 500000 microsegundos por negra
        self.assertEqual(us, 500000)

    def test_el_swing_corre_los_pasos_impares(self):
        recto = midi.bars_to_midi(
            [render.Bar(0, 120, 2000, 0.0, "verse",
                        (render.VoiceEvent("lead", 1, (69,), 100, 1),))])
        swung = midi.bars_to_midi(
            [render.Bar(0, 120, 2000, 0.5, "verse",
                        (render.VoiceEvent("lead", 1, (69,), 100, 1),))])
        self.assertNotEqual(recto, swung,
                            "Bar.swing no esta llegando al MIDI exportado")

    def test_sin_swing_los_pasos_caen_en_la_rejilla(self):
        data = midi.bars_to_midi(
            [render.Bar(0, 120, 2000, 0.0, "verse",
                        (render.VoiceEvent("lead", 4, (69,), 100, 2),))])
        # paso 4 con tpq 480 -> 4 * 120 = 480 ticks
        ticks = self._primer_tick_de_nota(data)
        self.assertEqual(ticks, 480)

    def test_el_swing_no_alcanza_el_paso_siguiente(self):
        # Si el corrimiento llegara a un paso entero, el evento pisaria al
        # siguiente y el ritmo se desarmaria.
        for swing in (0.16, 0.33, 0.5, 0.66, 1.0):
            data = midi.bars_to_midi(
                [render.Bar(0, 120, 2000, swing, "verse",
                            (render.VoiceEvent("lead", 1, (69,), 100, 1),))])
            ticks = self._primer_tick_de_nota(data)
            with self.subTest(swing=swing):
                self.assertGreaterEqual(ticks, 120)
                self.assertLess(ticks, 240, "el swing se paso al paso 2")

    # --- utilidades ---------------------------------------------------------

    def _pistas(self):
        pos = 14
        while pos < len(self.data):
            largo = struct.unpack(">I", self.data[pos + 4:pos + 8])[0]
            yield self.data[pos + 8:pos + 8 + largo]
            pos += 8 + largo

    @staticmethod
    def _eventos_de_nota(pista):
        i = 0
        while i < len(pista):
            # delta time
            while i < len(pista) and pista[i] & 0x80:
                i += 1
            i += 1
            if i >= len(pista):
                break
            status = pista[i]
            if status == 0xFF:                      # meta
                i += 1
                tipo = pista[i]
                i += 1
                largo = pista[i]
                i += 1 + largo
                if tipo == 0x2F:
                    break
                continue
            if status & 0xF0 in (0x90, 0x80):
                yield status, pista[i + 1], pista[i + 2]
                i += 3
            else:
                i += 3

    @staticmethod
    def _primer_tick_de_nota(data):
        pos = 14
        while pos < len(data):
            largo = struct.unpack(">I", data[pos + 4:pos + 8])[0]
            cuerpo = data[pos + 8:pos + 8 + largo]
            if b"\x90" in cuerpo:
                tick = 0
                i = 0
                while i < len(cuerpo):
                    valor = 0
                    while cuerpo[i] & 0x80:
                        valor = (valor << 7) | (cuerpo[i] & 0x7F)
                        i += 1
                    valor = (valor << 7) | cuerpo[i]
                    i += 1
                    tick += valor
                    if cuerpo[i] & 0xF0 == 0x90:
                        return tick
                    if cuerpo[i] == 0xFF:
                        i += 2 + cuerpo[i + 2] + 1
                    else:
                        i += 3
            pos += 8 + largo
        raise AssertionError("no se encontro ningun note-on")


class TestGmDrums(unittest.TestCase):
    def test_los_tres_instrumentos_mapean_a_notas_gm(self):
        self.assertEqual(midi.GM_DRUMS[0], 36)   # bombo
        self.assertEqual(midi.GM_DRUMS[1], 38)   # caja
        self.assertEqual(midi.GM_DRUMS[2], 42)   # hat cerrado

    def test_el_swing_del_midi_usa_la_misma_formula_que_el_secuenciador(self):
        # Si las dos formulas se separan, el MIDI deja de sonar como la jam en
        # vivo y afinar el estilo de oido sobre el archivo pasa a enganar.
        paso_ms = render.step_ms(120)
        for swing in (0.0, 0.16, 0.5, 0.66, 1.0):
            for step in range(render.STEPS_PER_BAR):
                esperado = sequencer.swing_offset_ms(step, swing, paso_ms)
                fraccion = esperado / paso_ms
                with self.subTest(swing=swing, step=step):
                    self.assertAlmostEqual(
                        midi.swing_fraction(step, swing), fraccion, places=9)


if __name__ == "__main__":
    unittest.main()
