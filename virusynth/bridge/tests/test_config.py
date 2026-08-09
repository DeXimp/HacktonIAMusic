"""Tests de bridge/config.py: selección de placa y derivación del ADC."""
from __future__ import annotations

import importlib
import os
import unittest


class TestBoardProfiles(unittest.TestCase):
    def setUp(self):
        self._old_board = os.environ.pop("HARDWARE_BOARD", None)
        self._old_adc = os.environ.pop("ADC_MAX", None)

    def tearDown(self):
        if self._old_board is not None:
            os.environ["HARDWARE_BOARD"] = self._old_board
        else:
            os.environ.pop("HARDWARE_BOARD", None)
        if self._old_adc is not None:
            os.environ["ADC_MAX"] = self._old_adc
        else:
            os.environ.pop("ADC_MAX", None)
        from bridge import config
        importlib.reload(config)

    def test_default_board_is_arduino_uno(self):
        from bridge import config
        importlib.reload(config)
        self.assertEqual(config.HARDWARE_BOARD, "arduino_uno")
        self.assertEqual(config.ADC_MAX, 1023)
        self.assertEqual(config.LOGIC_VOLTAGE, 5.0)

    def test_esp32_profile_selectable(self):
        os.environ["HARDWARE_BOARD"] = "esp32"
        from bridge import config
        importlib.reload(config)
        self.assertEqual(config.ADC_MAX, 4095)
        self.assertEqual(config.LOGIC_VOLTAGE, 3.3)

    def test_unknown_board_falls_back_to_uno(self):
        os.environ["HARDWARE_BOARD"] = "arduino_mega_9000"
        from bridge import config
        importlib.reload(config)
        self.assertEqual(config.HARDWARE_BOARD, "arduino_uno")
        self.assertEqual(config.ADC_MAX, 1023)

    def test_adc_max_env_override_wins(self):
        os.environ["HARDWARE_BOARD"] = "arduino_uno"
        os.environ["ADC_MAX"] = "2047"
        from bridge import config
        importlib.reload(config)
        self.assertEqual(config.ADC_MAX, 2047)

    def test_fsr_threshold_scales_with_adc_max(self):
        from bridge import config
        importlib.reload(config)
        # ~14.65% del fondo de escala, igual que el 600/4095 original del ESP32
        self.assertEqual(config.FSR_TRIGGER_THRESHOLD, round(1023 * 600 / 4095))


if __name__ == "__main__":
    unittest.main()
