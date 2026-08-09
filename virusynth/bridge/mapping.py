"""Mapeo canónico sensores → parámetros musicales (tabla en docs/osc-protocol.md).

| Sensor            | Parámetro                            | Mensaje              |
|-------------------|--------------------------------------|----------------------|
| accel X           | cutoff 300–4000 Hz (log)             | /pd/set/cutoff       |
| accel Y           | índice de nota en la escala (2 oct.) | interno              |
| gyro (magnitud)   | delay ±0.25 alrededor de la base     | /pd/set/fx/delay     |
| FSR (flanco)      | trigger de nota, velocity 30–127     | /pd/trigger/note     |
| potenciómetro     | volumen master 0–1                   | /pd/set/volume       |
"""
from __future__ import annotations

import logging
import math
import time

from . import config, music_engine
from .serial_reader import SensorFrame

log = logging.getLogger("SERIAL")


class SensorMapper:
    def __init__(self, state, pd) -> None:
        self.state = state
        self.pd = pd
        self._fsr_pressed = False
        self._last_cutoff = 0.0
        self._last_volume = -1.0
        self._last_delay = -1.0
        self._last_cont_send = 0.0
        self.selected_note = state.jam.root_note

    def process(self, frame: SensorFrame) -> None:
        ax, ay, az, gx, gy, gz, fsr, pot, _btn1, _btn2 = frame
        jam = self.state.jam
        now = time.monotonic()

        # --- nota candidata según inclinación frontal (accel Y) -------------
        notes = music_engine.scale_notes(jam.scale, jam.root_note - 12, jam.root_note + 12)
        if notes:
            idx = int((max(-1.0, min(1.0, ay)) + 1.0) / 2.0 * (len(notes) - 1))
            self.selected_note = notes[idx]

        # --- trigger por flanco del FSR -------------------------------------
        if fsr >= config.FSR_TRIGGER_THRESHOLD and not self._fsr_pressed:
            self._fsr_pressed = True
            span = config.ADC_MAX - config.FSR_TRIGGER_THRESHOLD
            velocity = 30 + int((fsr - config.FSR_TRIGGER_THRESHOLD) / span * 97)
            self.pd.trigger_note(self.selected_note, min(127, velocity))
            jam.current_notes.append(self.selected_note)
            jam.last_trigger_ts = now
        elif fsr < config.FSR_TRIGGER_THRESHOLD * 0.7:   # histéresis
            self._fsr_pressed = False

        # --- botones digitales (Arduino UNO D2/D3; 0,0 en placas sin
        # botones) -- se parsean pero A PROPÓSITO no tienen acción musical
        # atada todavía (decisión explícita del equipo): punto de extensión,
        # ver docs/hardware-arduino-uno.md.

        # --- controles continuos, limitados a 20 Hz y con umbral de cambio --
        if now - self._last_cont_send < 0.05:
            return
        self._last_cont_send = now

        ratio = config.CUTOFF_MAX_HZ / config.CUTOFF_MIN_HZ
        cutoff = config.CUTOFF_MIN_HZ * math.pow(ratio, (max(-1.0, min(1.0, ax)) + 1.0) / 2.0)
        if abs(cutoff - self._last_cutoff) > cutoff * 0.02:
            self._last_cutoff = cutoff
            jam.cutoff = cutoff
            self.pd.set_param("cutoff", float(round(cutoff, 1)))

        gyro_mag = min(1.0, math.sqrt(gx * gx + gy * gy + gz * gz)
                       / config.GYRO_FULL_SCALE_DPS)
        delay = max(0.0, min(1.0, jam.fx.delay + (gyro_mag - 0.15) * 0.25))
        if abs(delay - self._last_delay) > 0.03:
            self._last_delay = delay
            self.pd.set_param("fx/delay", float(round(delay, 3)))

        volume = max(0.0, min(1.0, pot / config.ADC_MAX))
        if abs(volume - self._last_volume) > 0.015:
            self._last_volume = volume
            jam.volume = volume
            self.pd.set_param("volume", float(round(volume, 3)))
