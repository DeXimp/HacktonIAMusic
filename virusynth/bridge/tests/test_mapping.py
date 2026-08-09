"""Tests de bridge/mapping.py: escalado por ADC_MAX (10/12 bits según placa).
Los botones D2/D3 del Arduino UNO se parsean en la trama pero NO tienen
acción musical atada todavía (decisión explícita: punto de extensión inerte,
ver docs/hardware-arduino-uno.md) — solo se verifica que no rompan nada."""
from __future__ import annotations

import unittest

from bridge import config
from bridge.mapping import SensorMapper
from bridge.state import GlobalState


class _FakePd:
    def __init__(self):
        self.params = []
        self.triggers = []

    def set_param(self, name, value):
        self.params.append((name, value))

    def trigger_note(self, note, velocity):
        self.triggers.append((note, velocity))


def _frame(ax=0.0, ay=0.0, az=1.0, gx=0.0, gy=0.0, gz=0.0,
          fsr=0, pot=0, btn1=0, btn2=0):
    return (ax, ay, az, gx, gy, gz, fsr, pot, btn1, btn2)


def _process(mapper, **kwargs):
    mapper._last_cont_send = 0.0   # fuerza el bloque continuo (20 Hz) en el test
    mapper.process(_frame(**kwargs))


class TestAdcScaling(unittest.TestCase):
    def test_volume_uses_configured_adc_max(self):
        mapper = SensorMapper(GlobalState(), _FakePd())
        _process(mapper, pot=config.ADC_MAX)
        self.assertAlmostEqual(mapper.state.jam.volume, 1.0, places=2)

    def test_fsr_trigger_velocity_scales_with_adc_max(self):
        pd = _FakePd()
        mapper = SensorMapper(GlobalState(), pd)
        mapper.process(_frame(fsr=config.ADC_MAX))
        self.assertEqual(len(pd.triggers), 1)
        self.assertEqual(pd.triggers[0][1], 127)


class TestButtonsAreInert(unittest.TestCase):
    """Los botones se parsean (frame de 10 campos) pero mapping.py no les
    ata ninguna acción todavía — punto de extensión documentado."""

    def test_button_presses_produce_no_trigger_or_param(self):
        pd = _FakePd()
        mapper = SensorMapper(GlobalState(), pd)
        mapper.process(_frame(btn1=0, btn2=0))
        mapper.process(_frame(btn1=1, btn2=1))   # flanco de subida de ambos
        mapper.process(_frame(btn1=1, btn2=0))
        mapper.process(_frame(btn1=0, btn2=1))
        self.assertEqual(pd.triggers, [])

    def test_boards_without_buttons_stay_inert(self):
        pd = _FakePd()
        mapper = SensorMapper(GlobalState(), pd)
        mapper.process(_frame())
        mapper.process(_frame())
        self.assertEqual(pd.triggers, [])


if __name__ == "__main__":
    unittest.main()
