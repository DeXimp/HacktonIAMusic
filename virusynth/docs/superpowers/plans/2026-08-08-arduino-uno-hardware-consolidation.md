# Consolidación de Hardware Emisor: Arduino UNO — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hacer de Arduino UNO el hardware emisor principal de ViruSynth (el ESP32
queda como perfil secundario/pausado por fallas térmicas), sin romper el
contrato CSV que ya desacopla el bridge de cualquier placa concreta.

**Architecture:** El protocolo CSV por Serial ya es la frontera de abstracción
correcta (CLAUDE.md §2 — "el LLM nunca está en el audio path" aplica en
espíritu también aquí: "el bridge nunca sabe qué placa habla"). Lo que falta
es (1) que el bridge deje de asumir un ADC de 12 bits a fuego, (2) que el
parser acepte tramas de placas con o sin botones sin romperse, y (3) que la
ausencia de hardware físico dispare el performer sintético automáticamente en
vez de requerir un flag manual. Se introduce `bridge/hardware_link.py` como
nuevo punto único de esa decisión (mismo patrón que `create_portal()` en
`portal_client.py`).

**Tech Stack:** Python 3.11+ (bridge), C++ / Arduino core AVR vía PlatformIO
(firmware), unittest stdlib (tests).

## Global Constraints

- El bridge nunca debe morir por falta de hardware, de `ANTHROPIC_API_KEY`, o
  de una dependencia opcional (CLAUDE.md §3, §7) — todo cambio debe preservar
  esto.
- El protocolo CSV debe seguir aceptando tramas de 8 campos (ESP32 legado,
  sin botones) y de 10 campos (Arduino UNO, con botones) — "alternar
  dinámicamente sin romper el flujo".
- Nada de `delay()` bloqueante en el firmware (loop con `millis()`).
- Cambiar de placa es cambiar una variable de entorno (`HARDWARE_BOARD`), no
  tocar código del bridge.
- Convenciones de CLAUDE.md §4 (snake_case, type hints, dataclasses stdlib,
  loggers con nombre fijo, sin dependencias nuevas).

---

## Decisiones de diseño (para que quede registrado el porqué)

1. **`ADC_MAX` reemplaza los `4095` hardcodeados.** Se deriva de un perfil de
   placa (`BOARD_PROFILES` en `config.py`), seleccionable por
   `HARDWARE_BOARD` (default `arduino_uno`, valor `1023`) y overrideable a
   mano con `ADC_MAX` si apareciera una placa nueva no listada.
2. **`FSR_TRIGGER_THRESHOLD` se recalibra proporcionalmente** (`600/4095` del
   ESP32 original ≈ 14.65 % → 150 en la escala de 10 bits del UNO), en vez de
   quedar un valor de otra época sin sentido en la nueva escala.
3. **El parser CSV acepta 8 o 10 campos.** Placas sin botones (ESP32 legado)
   se rellenan con `btn1=0, btn2=0`. Esto es lo que permite "alternar
   dinámicamente entre placas... sin romper" tal cual pide el encargo.
4. **Botones D2/D3 del UNO — mapeo por defecto (documentado como punto de
   extensión, fácil de reasignar en `mapping.py`):**
   - `btn1` (D2): gatillo manual de nota — mismo camino que el FSR, velocity
     fija 100. Da redundancia física real si el FSR falla (motivo declarado
     del pivote: fallas físicas del hardware).
   - `btn2` (D3): mute/unmute de volumen — patrón estándar de pedal de
     footswitch; suprime (no descarta) la lectura continua del potenciómetro
     mientras está muteado, y al soltar retoma la posición actual del knob.
5. **`HardwareLink` (nuevo módulo) encapsula la fuente de sensores** —serial
   real con fallback automático y transparente a `mock_sensor_task` cuando no
   hay hardware, y vuelta atrás automática cuando reconecta. Vive fuera de
   `JamController` para que sea testeable sin construir todo el bridge.
6. **ESP32 no se borra.** Se renombra `firmware/src/main.cpp` →
   `firmware/src/main_esp32.cpp`, se agrega `firmware/src/main_uno.cpp`, y
   `platformio.ini` compila uno u otro por entorno (`build_src_filter`),
   con `uno` como `default_envs`.

---

### Task 1: Perfiles de placa en `bridge/config.py`

**Files:**
- Modify: `bridge/config.py`
- Test: `bridge/tests/test_config.py` (nuevo)

**Interfaces:**
- Produce: `config.BOARD_PROFILES: dict[str, dict]`, `config.HARDWARE_BOARD: str`,
  `config.ADC_MAX: int`, `config.LOGIC_VOLTAGE: float`,
  `config.FSR_TRIGGER_THRESHOLD: int` (ahora derivado, no fijo).

- [ ] **Step 1: Escribir el test que fija el comportamiento por defecto**

```python
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
```

- [ ] **Step 2: Ejecutar y ver que falla**

Run (desde `virusynth/`): `python -m unittest bridge.tests.test_config -v`
Expected: FAIL — `AttributeError: module 'bridge.config' has no attribute 'BOARD_PROFILES'`.

- [ ] **Step 3: Implementar en `bridge/config.py`**

Reemplazar las líneas actuales:
```python
# --- Mapeo de sensores (ver docs/osc-protocol.md y mapping.py) ---
FSR_TRIGGER_THRESHOLD = 600     # 0..4095
CUTOFF_MIN_HZ, CUTOFF_MAX_HZ = 300.0, 4000.0
```
por (insertar el bloque de placas ANTES, ya que `FSR_TRIGGER_THRESHOLD` pasa a
depender de `ADC_MAX`):
```python
# --- Placa activa (arquitectura de hardware emisor, CLAUDE.md §2) ---
# El protocolo CSV es el mismo para cualquier placa que lo hable; lo único
# que cambia entre ellas es el rango crudo del ADC (fsr/pot). Cambiar de
# hardware es cambiar HARDWARE_BOARD — nada más en el bridge se toca.
# El ESP32 queda pausado temporalmente por fallas térmicas/físicas: el
# perfil se conserva para cuando vuelva a estar en servicio.
BOARD_PROFILES = {
    "arduino_uno": {"adc_max": 1023, "logic_voltage": 5.0,
                     "label": "Arduino UNO (ATmega328P, ADC 10 bits) — principal"},
    "esp32": {"adc_max": 4095, "logic_voltage": 3.3,
              "label": "ESP32 DevKit v1 (ADC1 12 bits, atenuación 11 dB) — pausado"},
}
HARDWARE_BOARD = os.getenv("HARDWARE_BOARD", "arduino_uno").strip().lower()
if HARDWARE_BOARD not in BOARD_PROFILES:
    HARDWARE_BOARD = "arduino_uno"
_board = BOARD_PROFILES[HARDWARE_BOARD]
ADC_MAX = _int("ADC_MAX", _board["adc_max"])       # override manual posible
LOGIC_VOLTAGE = _board["logic_voltage"]

# --- Mapeo de sensores (ver docs/osc-protocol.md y mapping.py) ---
FSR_TRIGGER_RATIO = 600 / 4095      # calibrado originalmente en el ESP32 (12 bits)
FSR_TRIGGER_THRESHOLD = _int("FSR_TRIGGER_THRESHOLD", round(ADC_MAX * FSR_TRIGGER_RATIO))
CUTOFF_MIN_HZ, CUTOFF_MAX_HZ = 300.0, 4000.0
```

- [ ] **Step 4: Ejecutar y ver que pasa**

Run: `python -m unittest bridge.tests.test_config -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add bridge/config.py bridge/tests/test_config.py
git commit -m "feat(bridge): perfiles de placa (Arduino UNO/ESP32) y ADC_MAX derivado"
```

---

### Task 2: Parser CSV flexible en `bridge/serial_reader.py`

**Files:**
- Modify: `bridge/serial_reader.py`
- Test: `bridge/tests/test_serial_reader.py` (nuevo)

**Interfaces:**
- Consume: nada nuevo.
- Produce: `SensorFrame` ahora de 10 elementos (`ax,ay,az,gx,gy,gz,fsr,pot,btn1,btn2`);
  `parse_line(line: str) -> SensorFrame | None` acepta 8 o 10 campos;
  `mock_sensor_task` emite tramas de 10 elementos (`btn1=btn2=0`).

- [ ] **Step 1: Escribir los tests**

```python
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
```

- [ ] **Step 2: Ejecutar y ver que falla**

Run: `python -m unittest bridge.tests.test_serial_reader -v`
Expected: FAIL (10-field case da `None` porque hoy `parse_line` exige
exactamente `config.SENSOR_FIELDS == 8`).

- [ ] **Step 3: Implementar**

En `bridge/serial_reader.py`, reemplazar:
```python
SensorFrame = tuple[float, float, float, float, float, float, float, float]


def parse_line(line: str) -> SensorFrame | None:
    parts = line.strip().split(",")
    if len(parts) != config.SENSOR_FIELDS:
        return None
    try:
        vals = tuple(float(p) for p in parts)
    except ValueError:
        return None
    return vals  # type: ignore[return-value]
```
por:
```python
# 10 campos: ax,ay,az,gx,gy,gz,fsr,pot,btn1,btn2 (Arduino UNO). Placas sin
# botones (p.ej. ESP32 legado) mandan solo los primeros 8 — el parser los
# rellena con btn1=btn2=0. Esta flexibilidad es la abstracción de hardware:
# cualquier placa que hable este CSV es intercambiable (CLAUDE.md §2).
SensorFrame = tuple[float, float, float, float, float, float, float, float, float, float]

_CORE_FIELDS = 8    # ax,ay,az,gx,gy,gz,fsr,pot
_FULL_FIELDS = 10   # + btn1,btn2


def parse_line(line: str) -> SensorFrame | None:
    parts = line.strip().split(",")
    if len(parts) not in (_CORE_FIELDS, _FULL_FIELDS):
        return None
    try:
        vals = [float(p) for p in parts]
    except ValueError:
        return None
    if len(vals) == _CORE_FIELDS:
        vals += [0.0, 0.0]
    return tuple(vals)  # type: ignore[return-value]
```

Actualizar `config.SENSOR_FIELDS` en `bridge/config.py` (ya no se usa como
comparación exacta, pero documenta el frame completo): cambiar
`SENSOR_FIELDS = 8  # ax,ay,az,gx,gy,gz,fsr,pot` por
`SENSOR_FIELDS = 10  # ax,ay,az,gx,gy,gz,fsr,pot,btn1,btn2 (8 en placas sin botones)`.
(Nada más en el codebase lee `config.SENSOR_FIELDS` — confirmado por grep.)

También en `mock_sensor_task` (mismo archivo), la línea final:
```python
        _offer(queue, (round(ax, 3), round(ay, 3), round(az, 3),
                       round(gx, 1), round(gy, 1), round(gz, 1),
                       round(fsr), round(pot)))
```
pasa a:
```python
        _offer(queue, (round(ax, 3), round(ay, 3), round(az, 3),
                       round(gx, 1), round(gy, 1), round(gz, 1),
                       round(fsr), round(pot), 0, 0))   # performer sintético: sin botones
```

- [ ] **Step 4: Ejecutar y ver que pasa**

Run: `python -m unittest bridge.tests.test_serial_reader -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add bridge/serial_reader.py bridge/config.py bridge/tests/test_serial_reader.py
git commit -m "feat(bridge): parser CSV acepta 8 o 10 campos (compat ESP32 legado / Arduino UNO)"
```

---

### Task 3: Escalado por `ADC_MAX` + botones en `bridge/mapping.py`

**Files:**
- Modify: `bridge/mapping.py`
- Test: `bridge/tests/test_mapping.py` (nuevo)

**Interfaces:**
- Consume: `config.ADC_MAX`, `config.FSR_TRIGGER_THRESHOLD` (Task 1);
  `SensorFrame` de 10 elementos (Task 2).
- Produce: `SensorMapper.process(frame)` sin cambios de firma; nuevo estado
  interno `_btn1_prev`, `_btn2_prev`, `_muted`.

- [ ] **Step 1: Escribir los tests**

```python
"""Tests de bridge/mapping.py: escalado por ADC_MAX (10/12 bits según placa)
y botones digitales del Arduino UNO (D2/D3)."""
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


class TestButtons(unittest.TestCase):
    def test_btn1_rising_edge_triggers_manual_note(self):
        pd = _FakePd()
        mapper = SensorMapper(GlobalState(), pd)
        mapper.process(_frame(btn1=0))
        mapper.process(_frame(btn1=1))
        self.assertEqual(len(pd.triggers), 1)
        mapper.process(_frame(btn1=1))       # mantenido: no repite
        self.assertEqual(len(pd.triggers), 1)

    def test_btn2_toggles_mute_and_suppresses_pot(self):
        state = GlobalState()
        mapper = SensorMapper(state, _FakePd())
        _process(mapper, pot=config.ADC_MAX, btn2=0)
        self.assertGreater(state.jam.volume, 0.9)
        _process(mapper, pot=config.ADC_MAX, btn2=1)     # flanco: mute
        self.assertEqual(state.jam.volume, 0.0)
        _process(mapper, pot=config.ADC_MAX, btn2=1)     # mantenido
        self.assertEqual(state.jam.volume, 0.0)
        _process(mapper, pot=config.ADC_MAX, btn2=0)     # suelta (sin flanco)
        _process(mapper, pot=config.ADC_MAX, btn2=1)     # flanco: unmute
        self.assertGreater(state.jam.volume, 0.9)

    def test_boards_without_buttons_stay_inert(self):
        pd = _FakePd()
        mapper = SensorMapper(GlobalState(), pd)
        mapper.process(_frame())
        mapper.process(_frame())
        self.assertEqual(pd.triggers, [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Ejecutar y ver que falla**

Run: `python -m unittest bridge.tests.test_mapping -v`
Expected: FAIL — `ValueError: not enough values to unpack` (el `process`
actual desempaqueta 8 valores, el frame ahora trae 10).

- [ ] **Step 3: Implementar en `bridge/mapping.py`**

Reemplazar el método `process` completo por:
```python
    def __init__(self, state, pd) -> None:
        self.state = state
        self.pd = pd
        self._fsr_pressed = False
        self._btn1_prev = False
        self._btn2_prev = False
        self._muted = False
        self._last_cutoff = 0.0
        self._last_volume = -1.0
        self._last_delay = -1.0
        self._last_cont_send = 0.0
        self.selected_note = state.jam.root_note

    def process(self, frame: SensorFrame) -> None:
        ax, ay, az, gx, gy, gz, fsr, pot, btn1, btn2 = frame
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

        # --- botones digitales (Arduino UNO D2/D3; ausentes -> 0,0) ---------
        # btn1: gatillo manual, redundante al FSR (respaldo físico en vivo).
        # btn2: mute/unmute del volumen (footswitch estándar). Punto de
        # extensión: reasignar aquí si el show necesita otro control.
        btn1_pressed = bool(btn1)
        if btn1_pressed and not self._btn1_prev:
            self.pd.trigger_note(self.selected_note, 100)
            jam.current_notes.append(self.selected_note)
            jam.last_trigger_ts = now
        self._btn1_prev = btn1_pressed

        btn2_pressed = bool(btn2)
        if btn2_pressed and not self._btn2_prev:
            self._muted = not self._muted
        self._btn2_prev = btn2_pressed

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

        volume = 0.0 if self._muted else max(0.0, min(1.0, pot / config.ADC_MAX))
        if abs(volume - self._last_volume) > 0.015:
            self._last_volume = volume
            jam.volume = volume
            self.pd.set_param("volume", float(round(volume, 3)))
```

- [ ] **Step 4: Ejecutar y ver que pasa**

Run: `python -m unittest bridge.tests.test_mapping -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add bridge/mapping.py bridge/tests/test_mapping.py
git commit -m "feat(bridge): escalado por ADC_MAX + botones D2/D3 (gatillo manual, mute)"
```

---

### Task 4: `bridge/hardware_link.py` — fallback automático a performer sintético

**Files:**
- Create: `bridge/hardware_link.py`
- Modify: `bridge/serial_reader.py` (agregar callback `on_status_change` a `start_serial_thread`)
- Test: `bridge/tests/test_hardware_link.py` (nuevo)

**Interfaces:**
- Consume: `serial_reader.start_serial_thread(...)`, `serial_reader.mock_sensor_task`.
- Produce: `HardwareLink(queue: asyncio.Queue)` con `.start(loop, *, port, baud,
  force_mock, disable)` y `.stop()`.

- [ ] **Step 1: Extender `start_serial_thread` con callback de estado**

En `bridge/serial_reader.py`, la firma actual es:
```python
def start_serial_thread(loop: asyncio.AbstractEventLoop,
                        queue: asyncio.Queue,
                        port: str,
                        baud: int,
                        stop_event: threading.Event) -> threading.Thread | None:
```
Cambiar a (agregar el parámetro opcional al final para no romper llamadas
existentes en tests, y notificar en cada transición):
```python
from typing import Callable, Optional

def start_serial_thread(loop: asyncio.AbstractEventLoop,
                        queue: asyncio.Queue,
                        port: str,
                        baud: int,
                        stop_event: threading.Event,
                        on_status_change: Optional[Callable[[bool], None]] = None
                        ) -> threading.Thread | None:
    """Lanza el hilo lector. Devuelve None si pyserial no está disponible.

    on_status_change(connected: bool) se invoca (vía call_soon_threadsafe)
    cada vez que cambia el estado de la conexión física — lo usa
    HardwareLink para levantar/bajar el performer sintético automáticamente.
    """
    def _notify(connected: bool) -> None:
        if on_status_change is not None:
            loop.call_soon_threadsafe(on_status_change, connected)

    try:
        import serial  # type: ignore
    except ImportError:
        log.warning("pyserial no instalado: usa --mock-sensors")
        _notify(False)
        return None

    def _run() -> None:
        ser = None
        warned = False
        while not stop_event.is_set():
            if ser is None:
                try:
                    ser = serial.Serial(port, baud, timeout=1)
                    log.info("Hardware conectado en %s @ %d", port, baud)
                    warned = False
                    _notify(True)
                except serial.SerialException:
                    if not warned:
                        log.warning("Sin hardware en %s; reintentando cada %.0f s",
                                    port, config.SERIAL_RETRY_S)
                        warned = True
                    _notify(False)
                    stop_event.wait(config.SERIAL_RETRY_S)
                    continue
            try:
                raw = ser.readline()
            except serial.SerialException:
                log.warning("Hardware desconectado; reintentando…")
                _notify(False)
                try:
                    ser.close()
                except Exception:
                    pass
                ser = None
                continue
            frame = parse_line(raw.decode("ascii", errors="ignore"))
            if frame is not None:
                loop.call_soon_threadsafe(_offer, queue, frame)
        if ser is not None:
            ser.close()

    thread = threading.Thread(target=_run, name="serial-reader", daemon=True)
    thread.start()
    return thread
```
(Nota: `_notify(False)` corre en el hilo del bridge — no es threadsafe si se
llama desde el hilo serial, salvo la del `ImportError` que corre en el hilo
principal. Por eso usa `loop.call_soon_threadsafe` dentro de `_notify`
siempre, incluso en el caso `ImportError` — es seguro llamarlo aunque ya
estemos en el hilo del loop.)

- [ ] **Step 2: Escribir los tests de `HardwareLink`**

```python
"""Tests de bridge/hardware_link.py: fallback automático al performer
sintético cuando no hay hardware físico, y vuelta atrás al reconectar
(CLAUDE.md §7 — "el show sigue")."""
from __future__ import annotations

import asyncio
import unittest


from bridge.hardware_link import HardwareLink


class TestHardwareLinkAutoFallback(unittest.IsolatedAsyncioTestCase):
    async def test_disconnect_starts_mock_task(self):
        queue: asyncio.Queue = asyncio.Queue()
        link = HardwareLink(queue)
        self.assertIsNone(link._mock_task)
        link._on_status_change(False)
        await asyncio.sleep(0)   # deja correr el create_task
        self.assertIsNotNone(link._mock_task)
        self.assertFalse(link._mock_task.done())
        link.stop()

    async def test_reconnect_stops_mock_task(self):
        queue: asyncio.Queue = asyncio.Queue()
        link = HardwareLink(queue)
        link._on_status_change(False)
        await asyncio.sleep(0)
        mock_task = link._mock_task
        self.assertIsNotNone(mock_task)
        link._on_status_change(True)
        self.assertIsNone(link._mock_task)
        await asyncio.sleep(0)
        self.assertTrue(mock_task.cancelled() or mock_task.cancelling() > 0)

    async def test_repeated_disconnect_does_not_duplicate_task(self):
        queue: asyncio.Queue = asyncio.Queue()
        link = HardwareLink(queue)
        link._on_status_change(False)
        await asyncio.sleep(0)
        first = link._mock_task
        link._on_status_change(False)
        await asyncio.sleep(0)
        self.assertIs(link._mock_task, first)
        link.stop()

    async def test_force_mock_starts_synthetic_performer_without_serial(self):
        queue: asyncio.Queue = asyncio.Queue()
        link = HardwareLink(queue)
        link.start(asyncio.get_running_loop(), port="COM_NOPE", baud=115200,
                  force_mock=True, disable=False)
        await asyncio.sleep(0)
        self.assertIsNotNone(link._mock_task)
        link.stop()

    async def test_disable_starts_nothing(self):
        queue: asyncio.Queue = asyncio.Queue()
        link = HardwareLink(queue)
        link.start(asyncio.get_running_loop(), port="COM_NOPE", baud=115200,
                  force_mock=False, disable=True)
        await asyncio.sleep(0)
        self.assertIsNone(link._mock_task)
        self.assertIsNone(link._serial_thread)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Ejecutar y ver que falla**

Run: `python -m unittest bridge.tests.test_hardware_link -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bridge.hardware_link'`.

- [ ] **Step 4: Implementar `bridge/hardware_link.py`**

```python
"""Capa de abstracción del hardware emisor (CLAUDE.md §2/§7).

Encapsula de dónde vienen las tramas de sensores: serial real (cualquier
placa que hable el protocolo CSV — Arduino UNO por defecto, ESP32 legado) o
el performer sintético (`serial_reader.mock_sensor_task`). Si no hay
hardware físico conectado, sube el mock automáticamente y en cuanto la placa
reconecta, lo baja — sin intervención manual y sin que mapping.py/sequencer.py
sepan ni les importe de dónde vienen los frames.
"""
from __future__ import annotations

import asyncio
import logging
import threading
from typing import Optional

from .serial_reader import mock_sensor_task, start_serial_thread

log = logging.getLogger("HW")


class HardwareLink:
    def __init__(self, queue: asyncio.Queue) -> None:
        self.queue = queue
        self._stop_event = threading.Event()
        self._serial_thread: Optional[threading.Thread] = None
        self._mock_task: Optional[asyncio.Task] = None

    def start(self, loop: asyncio.AbstractEventLoop, *, port: str, baud: int,
              force_mock: bool = False, disable: bool = False) -> None:
        if disable:
            log.info("Sensores desactivados (--no-serial)")
            return
        if force_mock:
            log.info("Sensores MOCK activos (performer sintético, forzado por --mock-sensors)")
            self._start_mock()
            return
        self._serial_thread = start_serial_thread(
            loop, self.queue, port, baud, self._stop_event,
            on_status_change=self._on_status_change)

    def _on_status_change(self, connected: bool) -> None:
        if connected:
            self._stop_mock()
        else:
            self._start_mock()

    def _start_mock(self) -> None:
        if self._mock_task is not None:
            return
        log.warning("Sin hardware físico detectado: activando el performer "
                    "sintético automáticamente (OSC sigue a 50 Hz)")
        self._mock_task = asyncio.create_task(mock_sensor_task(self.queue), name="mock-auto")

    def _stop_mock(self) -> None:
        if self._mock_task is None:
            return
        log.info("Hardware físico detectado: desactivando el performer sintético")
        self._mock_task.cancel()
        self._mock_task = None

    def stop(self) -> None:
        self._stop_event.set()
        self._stop_mock()
```

- [ ] **Step 5: Ejecutar y ver que pasa**

Run: `python -m unittest bridge.tests.test_hardware_link -v`
Expected: PASS (5 tests).

- [ ] **Step 6: Commit**

```bash
git add bridge/hardware_link.py bridge/serial_reader.py bridge/tests/test_hardware_link.py
git commit -m "feat(bridge): HardwareLink — fallback automático a performer sintético sin hardware"
```

---

### Task 5: Cablear `HardwareLink` en `bridge/main.py` + flag `--board`

**Files:**
- Modify: `bridge/main.py`

**Interfaces:**
- Consume: `HardwareLink` (Task 4), `config.HARDWARE_BOARD` (Task 1).

- [ ] **Step 1: Reemplazar el manejo directo de sensores en `JamController`**

En `__init__`, agregar:
```python
        from .hardware_link import HardwareLink
        self.hardware = HardwareLink(self.sensor_queue)
```
(o el import arriba del archivo junto a los demás, siguiendo el estilo del
módulo — preferible arriba: `from .hardware_link import HardwareLink`).

Quitar `self._stop_serial = threading.Event()` (ahora vive dentro de
`HardwareLink`) y el import de `threading` si queda sin uso — sigue
usándose por `argparse.Namespace`, revisar; `threading` ya no se usa
directamente en `main.py` tras este cambio, se puede quitar el import.

En `run()`, reemplazar:
```python
        if self.args.mock_sensors:
            log.info("Sensores MOCK activos (performer sintético)")
            tasks.append(asyncio.create_task(
                mock_sensor_task(self.sensor_queue), name="mock"))
        elif not self.args.no_serial:
            start_serial_thread(asyncio.get_running_loop(), self.sensor_queue,
                                self.args.serial_port, config.SERIAL_BAUD,
                                self._stop_serial)
```
por:
```python
        self.hardware.start(asyncio.get_running_loop(), port=self.args.serial_port,
                            baud=config.SERIAL_BAUD, force_mock=self.args.mock_sensors,
                            disable=self.args.no_serial)
```

Y en el `finally` del mismo método, reemplazar `self._stop_serial.set()` por
`self.hardware.stop()`.

Quitar los imports que ya no se usan directamente en `main.py`:
`from .serial_reader import mock_sensor_task, start_serial_thread` → ya no
hace falta (vive en `hardware_link.py`).

- [ ] **Step 2: Agregar el flag `--board` (documentación en vivo, no cambia lógica —
  `HARDWARE_BOARD` ya se lee de env en `config.py` al importar)**

En `parse_args`, agregar tras `--serial-port`:
```python
    p.add_argument("--board", default=config.HARDWARE_BOARD,
                   choices=sorted(config.BOARD_PROFILES),
                   help=f"placa activa, define el rango del ADC (default {config.HARDWARE_BOARD})")
```
Y en `main()`, antes de construir `JamController`, si `args.board` difiere
del que ya cargó `config` (porque vino del env), setear la env var y
recargar `config` no es necesario para el caso común (default-igual-a-env);
para que el flag realmente pueda cambiar la placa en el mismo proceso sin
depender de reiniciar con la env var puesta, agregar al inicio de `main()`:
```python
def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    if args.board != config.HARDWARE_BOARD:
        os.environ["HARDWARE_BOARD"] = args.board
        importlib.reload(config)
    logging.basicConfig(...)
```
Requiere `import os` e `import importlib` al inicio de `bridge/main.py`
(ninguno de los dos está importado hoy — agregarlos).

- [ ] **Step 3: Verificación manual (no hay test unitario nuevo — es wiring)**

Run (desde `virusynth/`): `python -m unittest discover -s bridge/tests -t .`
Expected: todos los tests de las Tasks 1-4 y los 32 preexistentes de
`test_music_engine.py` en PASS.

Run: `python scripts/smoke_test.py`
Expected: `PASS: Fase 1 verificada (mock -> bridge -> OSC hacia Pd)` — confirma
que `HardwareLink` con `force_mock=True` (via `--mock-sensors`, que es lo que
usa `smoke_test.py`) sigue funcionando end-to-end.

- [ ] **Step 4: Commit**

```bash
git add bridge/main.py
git commit -m "refactor(bridge): usar HardwareLink en JamController + flag --board"
```

---

### Task 6: Hardening del fallback de IA (créditos/auth) + tests de `ai_director`

**Files:**
- Modify: `bridge/ai_director.py`
- Test: `bridge/tests/test_ai_director.py` (nuevo)

**Interfaces:**
- Consume: nada nuevo — refuerza el `except Exception` genérico existente en
  `AIDirector.decide()` con logging más específico (mismo comportamiento de
  fallback, mejor observabilidad en vivo).

- [ ] **Step 1: Escribir los tests (fijan el contrato de fallback ya existente
  y lo blindan contra regresiones)**

```python
"""Tests de bridge/ai_director.py: el fallback a reglas locales debe ser
100% confiable sin importar por qué falla Claude — sin API key, timeout,
error de red/auth/créditos, o decisión inválida (CLAUDE.md §7)."""
from __future__ import annotations

import unittest

from bridge import config
from bridge.ai_director import AIDirector


async def _noop_apply(decision):
    pass


class TestAIDirectorFallback(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._old_key = config.ANTHROPIC_API_KEY
        config.ANTHROPIC_API_KEY = ""   # por defecto: sin key en estos tests

    def tearDown(self):
        config.ANTHROPIC_API_KEY = self._old_key

    async def test_no_api_key_never_touches_network(self):
        director = AIDirector(object(), _noop_apply)
        self.assertIsNone(director._client)
        snapshot = {"scale": "Am_pentatonic", "bpm": 112,
                   "fx": {"reverb": 0.35, "delay": 0.25, "distortion": 0.05},
                   "amplitude": 0.4, "current_notes": [69],
                   "votes": {"scale_votes": {}, "bpm_avg": None, "fx_avg": {}, "voters": 0},
                   "pending_suggestion": None, "last_scale_change_age_s": 999.0,
                   "recent_actions": []}
        decision = await director.decide(snapshot)
        self.assertEqual(decision["source"], "reglas_locales")

    async def test_timeout_falls_back(self):
        director = AIDirector(object(), _noop_apply)
        director._client = object()   # sentinel truthy: fuerza la rama "con cliente"

        async def _hangs(snapshot):
            import asyncio
            await asyncio.sleep(10)

        director._ask_claude = _hangs
        config.AI_TIMEOUT_S, old_timeout = 0.05, config.AI_TIMEOUT_S
        try:
            decision = await director.decide({"scale": "Am_pentatonic", "bpm": 112,
                                              "votes": {}, "fx": {}})
        finally:
            config.AI_TIMEOUT_S = old_timeout
        self.assertEqual(decision["source"], "reglas_locales")

    async def test_network_or_credit_error_falls_back(self):
        director = AIDirector(object(), _noop_apply)
        director._client = object()

        async def _boom(snapshot):
            raise RuntimeError("simulated: insufficient credits / auth failure")

        director._ask_claude = _boom
        decision = await director.decide({"scale": "Am_pentatonic", "bpm": 112,
                                          "votes": {}, "fx": {}})
        self.assertEqual(decision["source"], "reglas_locales")

    async def test_invalid_decision_falls_back(self):
        director = AIDirector(object(), _noop_apply)
        director._client = object()

        async def _invalid(snapshot):
            return {"action": "not_a_real_action", "reasoning": "??"}

        director._ask_claude = _invalid
        decision = await director.decide({"scale": "Am_pentatonic", "bpm": 112,
                                          "votes": {}, "fx": {}})
        self.assertEqual(decision["source"], "reglas_locales")

    async def test_valid_decision_uses_claude_source(self):
        director = AIDirector(object(), _noop_apply)
        director._client = object()

        async def _ok(snapshot):
            return {"action": "no_change", "reasoning": "todo bien"}

        director._ask_claude = _ok
        decision = await director.decide({"scale": "Am_pentatonic", "bpm": 112,
                                          "votes": {}, "fx": {}})
        self.assertEqual(decision["source"], "claude")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Ejecutar — deberían pasar ya (el fallback ya existe)**

Run: `python -m unittest bridge.tests.test_ai_director -v`
Expected: PASS (5 tests) — esto confirma en frío que el contrato ya estaba
bien implementado; si algo falla, es una regresión real a arreglar antes de
seguir.

- [ ] **Step 3: Mejorar el logging de errores de créditos/auth en `decide()`**

En `bridge/ai_director.py`, reemplazar:
```python
            except Exception as exc:  # red, auth, rate limit… nunca tumbar el loop
                log.warning("LLM falló (%s); uso reglas locales",
                            type(exc).__name__)
```
por (detecta sin créditos / auth inválida para un log más útil en vivo, sin
cambiar el comportamiento de fallback):
```python
            except Exception as exc:  # red, auth, créditos, rate limit… nunca tumbar el loop
                status = getattr(exc, "status_code", None)
                if status in (401, 403):
                    log.warning("LLM: API key inválida o sin permisos; uso reglas locales")
                elif status == 429:
                    log.warning("LLM: rate limit / sin créditos; uso reglas locales")
                else:
                    log.warning("LLM falló (%s); uso reglas locales", type(exc).__name__)
```
(`status_code` es el atributo que expone `anthropic.APIStatusError` y sus
subclases — si el SDK no está instalado o lanza otra excepción, `getattr`
devuelve `None` y cae al `else`, así que esto es seguro incluso sin el
paquete `anthropic`.)

- [ ] **Step 4: Ejecutar de nuevo**

Run: `python -m unittest bridge.tests.test_ai_director -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add bridge/ai_director.py bridge/tests/test_ai_director.py
git commit -m "test(bridge): fijar el contrato de fallback de AIDirector + log de créditos/auth"
```

---

### Task 7: Firmware Arduino UNO + reorganización de PlatformIO

**Files:**
- Create: `firmware/src/main_uno.cpp`
- Rename: `firmware/src/main.cpp` → `firmware/src/main_esp32.cpp`
- Modify: `firmware/platformio.ini`

- [ ] **Step 1: Renombrar el firmware ESP32 existente**

```bash
git mv firmware/src/main.cpp firmware/src/main_esp32.cpp
```
Agregar al principio del archivo (tras el comentario de cabecera existente,
sin tocar el resto del código — sigue siendo válido tal cual):
```cpp
 * NOTA (consolidación Arduino UNO): este firmware queda PAUSADO temporalmente
 * por fallas físicas/térmicas del ESP32 — se conserva funcionando para
 * cuando vuelva a estar en servicio. El hardware principal ahora es
 * firmware/src/main_uno.cpp. El protocolo CSV de 8 campos que emite este
 * archivo sigue siendo válido: bridge/serial_reader.py lo acepta y rellena
 * btn1=btn2=0 (no tiene botones). Compilar con `pio run -e esp32dev`.
```

- [ ] **Step 2: Crear `firmware/src/main_uno.cpp`**

```cpp
/*
 * ViruSynth — firmware Arduino UNO (placa principal)
 *
 * Lee MPU6050 (I2C) + FSR + potenciómetro + 2 botones digitales y emite una
 * trama CSV por Serial USB a 50 Hz:
 *
 *     ax,ay,az,gx,gy,gz,fsr,pot,btn1,btn2\n
 *
 *   ax..az     aceleración en g      (2 decimales, suavizado EMA)
 *   gx..gz     giroscopio en °/s     (1 decimal)
 *   fsr,pot    crudos ADC 10 bits    (0..1023 — ver bridge/config.py:ADC_MAX)
 *   btn1,btn2  0/1 (1 = presionado; INPUT_PULLUP invertido en firmware)
 *
 * El bridge (bridge/serial_reader.py) acepta tramas de 8 O 10 campos: una
 * placa sin botones (p.ej. el ESP32 pausado, ver main_esp32.cpp) sigue
 * funcionando sin tocar el bridge — esa es la abstracción de hardware
 * (CLAUDE.md §2): cualquier placa que hable este CSV es intercambiable.
 *
 * Reglas eléctricas (CLAUDE.md / docs/hardware-arduino-uno.md):
 *   - Lógica 5 V (UNO estándar). El MPU6050 en módulo GY-521 se alimenta
 *     de 5V: el módulo regula internamente a 3.3V y ya trae pull-ups I2C en
 *     placa — no hace falta level-shifter externo.
 *   - I2C fijo por hardware en A4 (SDA) / A5 (SCL): no son pines libres.
 *   - ADC de 10 bits (0-1023) fijo por hardware: el UNO NO tiene
 *     analogReadResolution() (eso es solo ESP32/SAMD) — no se llama aquí.
 *   - Botones a GND con INPUT_PULLUP: sin resistencias externas.
 *
 * Presupuesto serial: 10 campos ≈ 40 bytes/trama; a 115200 baud (~11.5 KB/s)
 * se transmiten en ~3.5 ms — muy por debajo de los 20 ms del período de
 * trama, así que Serial.print() nunca bloquea el loop().
 *
 * Arranque resiliente: si el MPU6050 no responde, el LED parpadea rápido y
 * la trama sale igual con imu en 0 — la demo no se cae por un cable suelto.
 */

#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>

// ---------- pines (Arduino UNO) ----------
// I2C (SDA=A4, SCL=A5) es fijo por hardware: Wire.begin() no toma pines.
constexpr int PIN_POT  = A0;       // potenciómetro (cursor)
constexpr int PIN_FSR  = A1;       // sensor de presión (divisor externo a GND)
constexpr int PIN_BTN1 = 2;        // D2, INPUT_PULLUP: gatillo manual (respaldo del FSR)
constexpr int PIN_BTN2 = 3;        // D3, INPUT_PULLUP: mute/unmute de volumen
constexpr int PIN_LED  = 13;       // LED onboard: lento = OK, rápido = sin MPU

// ---------- temporización ----------
constexpr uint32_t FRAME_INTERVAL_MS = 20;   // 50 Hz, scheduling con millis()
constexpr uint32_t BAUD = 115200;
constexpr float EMA_ALPHA = 0.25f;           // suavizado de la aceleración

Adafruit_MPU6050 mpu;
bool mpuOk = false;

float axF = 0, ayF = 0, azF = 0;             // aceleración filtrada (g)
uint32_t nextFrameAt = 0;
uint32_t ledToggleAt = 0;
bool ledState = false;

void setup() {
  Serial.begin(BAUD);
  pinMode(PIN_LED, OUTPUT);
  pinMode(PIN_BTN1, INPUT_PULLUP);
  pinMode(PIN_BTN2, INPUT_PULLUP);
  // ADC: 10 bits (0-1023) es el único modo del UNO — nada que configurar.

  Wire.begin();                    // SDA=A4, SCL=A5 fijos en el UNO
  mpuOk = mpu.begin(0x68, &Wire);
  if (mpuOk) {
    mpu.setAccelerometerRange(MPU6050_RANGE_4_G);
    mpu.setGyroRange(MPU6050_RANGE_250_DEG);
    mpu.setFilterBandwidth(MPU6050_BAND_44_HZ);
  }
  // sin Serial.print de arranque: el bridge descarta líneas no numéricas,
  // pero mantener el canal limpio simplifica el debugging con el monitor

  nextFrameAt = millis();
}

void loop() {
  const uint32_t now = millis();

  // LED de estado sin delay(): lento (1 Hz) = todo bien, rápido (5 Hz) = sin MPU
  const uint32_t ledPeriod = mpuOk ? 500 : 100;
  if (now >= ledToggleAt) {
    ledToggleAt = now + ledPeriod;
    ledState = !ledState;
    digitalWrite(PIN_LED, ledState);
  }

  if (now < nextFrameAt) return;                  // scheduling: nada de delay()
  nextFrameAt += FRAME_INTERVAL_MS;
  if (now > nextFrameAt + 5 * FRAME_INTERVAL_MS)  // recupera tras un bloqueo largo
    nextFrameAt = now + FRAME_INTERVAL_MS;

  float ax = 0, ay = 0, az = 0, gx = 0, gy = 0, gz = 0;
  if (mpuOk) {
    sensors_event_t a, g, t;
    if (mpu.getEvent(&a, &g, &t)) {
      ax = a.acceleration.x / 9.80665f;
      ay = a.acceleration.y / 9.80665f;
      az = a.acceleration.z / 9.80665f;
      gx = g.gyro.x * 57.29578f;
      gy = g.gyro.y * 57.29578f;
      gz = g.gyro.z * 57.29578f;
    } else {
      mpuOk = false;                              // se cayó el I2C: seguir sin IMU
    }
  }

  axF += EMA_ALPHA * (ax - axF);
  ayF += EMA_ALPHA * (ay - ayF);
  azF += EMA_ALPHA * (az - azF);

  const int fsr  = analogRead(PIN_FSR);            // 0..1023
  const int pot  = analogRead(PIN_POT);            // 0..1023
  const int btn1 = digitalRead(PIN_BTN1) == LOW ? 1 : 0;   // INPUT_PULLUP: LOW = presionado
  const int btn2 = digitalRead(PIN_BTN2) == LOW ? 1 : 0;

  // trama CSV de 10 campos — el contrato con bridge/serial_reader.py
  Serial.print(axF, 2); Serial.print(',');
  Serial.print(ayF, 2); Serial.print(',');
  Serial.print(azF, 2); Serial.print(',');
  Serial.print(gx, 1);  Serial.print(',');
  Serial.print(gy, 1);  Serial.print(',');
  Serial.print(gz, 1);  Serial.print(',');
  Serial.print(fsr);    Serial.print(',');
  Serial.print(pot);    Serial.print(',');
  Serial.print(btn1);   Serial.print(',');
  Serial.println(btn2);
}
```

- [ ] **Step 3: Reescribir `firmware/platformio.ini`**

```ini
; ViruSynth — firmware (PlatformIO), Arduino UNO principal + ESP32 pausado
; Compilar y subir (placa principal, UNO):   pio run -t upload
; Compilar el ESP32 pausado:                 pio run -e esp32dev -t upload
; Monitor serie:                             pio device monitor

[platformio]
default_envs = uno

[env:uno]
platform = atmelavr
board = uno
framework = arduino
monitor_speed = 115200
build_src_filter = +<*> -<main_esp32.cpp>
lib_deps =
    adafruit/Adafruit MPU6050@^2.2.6
    adafruit/Adafruit Unified Sensor@^1.1.14

[env:esp32dev]
platform = espressif32
board = esp32dev
framework = arduino
monitor_speed = 115200
upload_speed = 921600
build_src_filter = +<*> -<main_uno.cpp>
lib_deps =
    adafruit/Adafruit MPU6050@^2.2.6
    adafruit/Adafruit Unified Sensor@^1.1.14
```

- [ ] **Step 4: Verificación manual**

No hay compilador de PlatformIO disponible en este entorno de desarrollo —
la verificación es de lectura: confirmar que `main_uno.cpp` no usa ninguna
función exclusiva de ESP32 (`analogReadResolution`, `analogSetPinAttenuation`,
`Wire.begin(sda, scl, freq)`, `WiFi.h`) y que `main_esp32.cpp` sigue intacto
salvo el comentario agregado. Si hay hardware disponible más adelante:
`pio run -e uno` y `pio run -e esp32dev` deben compilar ambos sin errores.

- [ ] **Step 5: Commit**

```bash
git add firmware/
git commit -m "feat(firmware): firmware Arduino UNO (placa principal) + ESP32 pausado en platformio.ini"
```

---

### Task 8: Documentación — `docs/hardware-arduino-uno.md` (nuevo)

**Files:**
- Create: `docs/hardware-arduino-uno.md`
- Modify: `docs/hardware-esp32.md` (nota de "pausado" al inicio)

- [ ] **Step 1: Crear `docs/hardware-arduino-uno.md`** con: tabla de pinout
  (A4/A5 I2C, A0 pot, A1 FSR, D2/D3 botones INPUT_PULLUP, pin 13 LED), reglas
  eléctricas (lógica 5V, ADC 10 bits fijo, I2C fijo por hardware, botones sin
  resistencias externas), diagrama de cableado ASCII (MPU6050 a 5V, FSR con
  divisor a A1, potenciómetro a A0, botones D2/D3 a GND), checklist de
  bring-up (`pio run -t upload`, `HARDWARE_BOARD=arduino_uno` en `.env` —
  opcional, es el default —, `SERIAL_PORT=COM7`) y tabla de troubleshooting
  (mismo formato que `docs/hardware-esp32.md`, adaptada: sin atenuación ADC
  que configurar, FSR clavado en 1023 si el divisor está invertido, etc.)

- [ ] **Step 2: Agregar nota al inicio de `docs/hardware-esp32.md`**, justo
  después del título `# Hardware — ESP32 DevKit v1`:

```markdown
> ⚠️ **Pausado temporalmente** por fallas físicas/térmicas recientes. El
> hardware principal de ViruSynth es ahora **Arduino UNO** — ver
> [`docs/hardware-arduino-uno.md`](hardware-arduino-uno.md). Esta guía se
> conserva vigente para cuando el ESP32 vuelva a servicio: el protocolo CSV
> es compatible con ambas placas (`bridge/serial_reader.py` acepta tramas de
> 8 o 10 campos — ver `HARDWARE_BOARD` en `bridge/config.py`).
```

- [ ] **Step 3: Commit**

```bash
git add docs/hardware-arduino-uno.md docs/hardware-esp32.md
git commit -m "docs: guía de hardware para Arduino UNO + nota de pausa en la de ESP32"
```

---

### Task 9: Actualizar `docs/osc-protocol.md`, `docs/architecture.md`, `CLAUDE.md`, `README.md`, `.env.example`

**Files:**
- Modify: `docs/osc-protocol.md` (fila de la trama CSV + tabla de botones)
- Modify: `docs/architecture.md` (diagrama: ESP32 → Arduino UNO / ESP32 pausado)
- Modify: `CLAUDE.md` (§1, §2, §3, §6, §7, §8 — ver detalle abajo)
- Modify: `README.md` (quickstart, estructura, matriz de fallbacks)
- Create: `.env.example` (no existe hoy pese a estar referenciado en CLAUDE.md §8)

- [ ] **Step 1: `docs/osc-protocol.md`** — reemplazar la sección "ESP32 →
  Bridge" por:
```markdown
## Hardware → Bridge (Serial USB · no es OSC)

CSV a 50 Hz, 115200 baud: `ax,ay,az,gx,gy,gz,fsr,pot[,btn1,btn2]\n`
(aceleración en g ×2 dec · giroscopio en °/s ×1 dec · fsr/pot crudos ADC,
rango según la placa activa — `config.ADC_MAX`: 0–1023 en Arduino UNO
(10 bits, principal), 0–4095 en ESP32 (12 bits, pausado)).
El bridge descarta en silencio cualquier línea que no tenga 8 o 10 campos
numéricos; si son 8 (placa sin botones), rellena `btn1=btn2=0`.

Arduino UNO agrega `btn1` (D2), `btn2` (D3): 0/1, `INPUT_PULLUP` (1 =
presionado). Mapeo por defecto en `bridge/mapping.py`: `btn1` dispara una
nota manual (respaldo del FSR), `btn2` alterna mute/unmute del volumen.
```
  y actualizar la sección "(Opcional) ESP32 → Bridge por WiFi" con una nota
  de que ese modo sigue siendo exclusivo del firmware ESP32 pausado.

- [ ] **Step 2: `docs/architecture.md`** — en el flowchart mermaid, cambiar
  el nodo `ESP[ESP32<br/>MPU6050 + FSR + pot]` por
  `ESP[Arduino UNO — o ESP32 pausado<br/>MPU6050 + FSR + pot + botones]`, y en
  la fila `firmware/` de "Reparto de responsabilidades" aclarar "CSV de
  sensores 50 Hz (Arduino UNO principal, ESP32 pausado — mismo protocolo)".

- [ ] **Step 3: `CLAUDE.md`** — cambios puntuales:

  §1 (Visión): `un performer local con sensores físicos (ESP32: MPU6050 +
  FSR + potenciómetro)` → `un performer local con sensores físicos (Arduino
  UNO — hardware principal; ESP32 pausado temporalmente por fallas
  físicas/térmicas —: MPU6050 + FSR + potenciómetro + botones)`.

  §2 (Loop 1): `ESP32 →(Serial USB 115200, 50 Hz)→ Bridge` → `Hardware
  emisor (Arduino UNO / ESP32, según HARDWARE_BOARD) →(Serial USB 115200,
  50 Hz)→ Bridge`.

  §3 (Stack): fila `Firmware` → cambiar de
  `ESP32 Arduino core vía PlatformIO (board esp32dev) | espressif32` a
  `Arduino core vía PlatformIO (board uno, principal — esp32dev, pausado) |
  atmelavr / espressif32`.
  Agregar una fila nueva bajo la tabla de stack:
  > **Hardware emisor (arquitectura):** cualquier placa que hable el CSV de
  > `docs/osc-protocol.md` es intercambiable sin tocar el bridge —
  > `HARDWARE_BOARD` (env, default `arduino_uno`) selecciona el perfil
  > (`bridge/config.py:BOARD_PROFILES`) que fija `ADC_MAX` y el voltaje
  > lógico. Motivo del pivote actual: fallas físicas/térmicas del ESP32.

  §6 (Protocolo): fila `ESP32 → Bridge` → `Hardware → Bridge`, con la nota
  "ADC 0–1023 (UNO, 10 bits) o 0–4095 (ESP32, 12 bits) según `HARDWARE_BOARD`;
  +2 campos de botones en UNO".

  §7 (Fallbacks): fila `ESP32 desconectado | --mock-sensors (performer
  sintético) | el show sigue; reconexión serial automática cada 3 s` →
  `Hardware desconectado | Performer sintético automático (HardwareLink) |
  el show sigue sin intervención: se activa solo al no detectar hardware y
  se desactiva solo al reconectar; --mock-sensors sigue disponible para
  forzarlo; reconexión cada 3 s`.

  §8 (env vars): agregar fila `HARDWARE_BOARD | arduino_uno | placa activa
  (bridge/config.py:BOARD_PROFILES) — define ADC_MAX y voltaje lógico` justo
  antes de la fila `SERIAL_PORT`.

  §9 (Setup): en la línea de firmware al final, cambiar
  `Firmware: pio run -t upload dentro de firmware/ (o Arduino IDE con core
  esp32).` por
  `Firmware: pio run -t upload dentro de firmware/ compila el Arduino UNO
  (placa principal, default_envs); pio run -e esp32dev -t upload compila el
  ESP32 pausado.`

- [ ] **Step 4: `README.md`** — actualizar: párrafo de apertura ("Un ESP32
  con sensores toca..." → "Un Arduino UNO con sensores toca... (o un ESP32,
  pausado temporalmente por fallas físicas — ver CLAUDE.md §3)"); línea de
  estructura `firmware/ ESP32 PlatformIO: ...` → `firmware/ PlatformIO:
  Arduino UNO (principal) + ESP32 (pausado) — MPU6050+FSR+pot+botones → CSV
  50 Hz`; fila de la matriz de fallbacks `ESP32 | sigue: --mock-sensors
  (performer sintético)` → `Hardware físico | sigue: performer sintético
  automático (o --mock-sensors a mano)`.

- [ ] **Step 5: Crear `.env.example`** (no existe hoy; referenciado desde
  CLAUDE.md §8 y README.md):
```dotenv
# ViruSynth — copiar a .env y completar lo que haga falta. Todo tiene un
# default sensato (demo-first): el bridge arranca igual sin este archivo.

# --- IA Director (opcional; sin esto decide bridge/music_engine.py) ---
ANTHROPIC_API_KEY=
AI_MODEL=claude-sonnet-5

# --- Hardware emisor (arquitectura de placas, CLAUDE.md §3) ---
# arduino_uno (default, principal) | esp32 (pausado por fallas térmicas)
HARDWARE_BOARD=arduino_uno
SERIAL_PORT=COM5
SERIAL_BAUD=115200

# --- Pure Data (OSC) ---
PD_SEND_PORT=9000
PD_RECV_PORT=8000

# --- Capa realtime local ---
WS_PORT=8765

# --- Portal SDK (cuando exista) ---
PORTAL_API_KEY=
PORTAL_ROOM=virusynth-jam
```

- [ ] **Step 6: Commit**

```bash
git add docs/osc-protocol.md docs/architecture.md CLAUDE.md README.md .env.example
git commit -m "docs: Arduino UNO como hardware principal en toda la documentación"
```

---

### Task 10: Verificación final end-to-end

- [ ] **Step 1:** `python -m unittest discover -s bridge/tests -t .` desde
  `virusynth/` → todos los tests (los 32 preexistentes + los nuevos de las
  Tasks 1, 2, 3, 4, 6) en PASS.
- [ ] **Step 2:** `python scripts/smoke_test.py` desde `virusynth/` → PASS
  (confirma `--mock-sensors` con la nueva trama de 10 campos y `ADC_MAX` de
  Arduino UNO no rompe el flujo mock → bridge → OSC).
- [ ] **Step 3:** `python -m bridge.main --no-portal --no-ai --log-level INFO`
  (sin `--mock-sensors` y sin hardware conectado) durante ~5 s, Ctrl+C →
  confirmar en el log la línea `Sin hardware físico detectado: activando el
  performer sintético automáticamente` y que llegan tramas (se puede
  verificar con `scripts/test-osc.py --telemetry` escuchando en paralelo, o
  simplemente inspeccionando que el proceso no se cuelga ni muere).
- [ ] **Step 4:** Revisar el diff completo (`git diff --stat` desde el commit
  base) contra la lista de archivos de este plan — no debe haber cambios
  fuera de `bridge/`, `firmware/`, `docs/`, `CLAUDE.md`, `README.md`,
  `.env.example`.
