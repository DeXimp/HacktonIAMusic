"""Tests de bridge/serial_reader.py: el parser CSV acepta 8 o 10 campos —
esa flexibilidad es lo que permite alternar de placa sin romper el bridge
(CLAUDE.md §2)."""
from __future__ import annotations

import unittest

from bridge.serial_reader import parse_line


class TestParseLine(unittest.TestCase):
    def test_legacy_8_fields_pads_buttons_with_zero(self):
        frame = parse_line("0.10,0.20,0.98,1.0,2.0,3.0,500,2000\n")
        self.assertEqual(frame, (0.10, 0.20, 0.98, 1.0, 2.0, 3.0, 500.0, 2000.0, 0.0, 0.0))

    def test_full_10_fields_arduino_uno(self):
        frame = parse_line("0.10,0.20,0.98,1.0,2.0,3.0,500,2000,1,0\n")
        self.assertEqual(frame, (0.10, 0.20, 0.98, 1.0, 2.0, 3.0, 500.0, 2000.0, 1.0, 0.0))

    def test_wrong_field_count_rejected(self):
        self.assertIsNone(parse_line("0.1,0.2,0.3\n"))
        self.assertIsNone(parse_line(",".join(["1"] * 9)))

    def test_non_numeric_rejected(self):
        self.assertIsNone(parse_line("a,b,c,d,e,f,g,h\n"))

    def test_blank_line_rejected(self):
        self.assertIsNone(parse_line("\n"))
        self.assertIsNone(parse_line(""))


if __name__ == "__main__":
    unittest.main()
