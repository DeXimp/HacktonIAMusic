"""Configuración central de ViruSynth. Todo tiene default sensato (demo-first)."""
from __future__ import annotations

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

try:  # .env es opcional
    from dotenv import load_dotenv

    load_dotenv(ROOT_DIR / ".env")
except ImportError:
    pass


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "") or default)
    except ValueError:
        return default


# --- OSC con Pure Data (loopback, Loop 1/2) ---
PD_HOST = os.getenv("PD_HOST", "127.0.0.1")
PD_SEND_PORT = _int("PD_SEND_PORT", 9000)   # Pd escucha aquí
PD_RECV_PORT = _int("PD_RECV_PORT", 8000)   # el bridge escucha telemetría aquí

# --- Capa realtime local (fallback de Portal) ---
WS_HOST = os.getenv("WS_HOST", "0.0.0.0")
WS_PORT = _int("WS_PORT", 8765)

# --- Portal SDK (cuando exista) ---
PORTAL_API_KEY = os.getenv("PORTAL_API_KEY", "")
PORTAL_ROOM = os.getenv("PORTAL_ROOM", "virusynth-jam")

# --- Serial ESP32 ---
SERIAL_PORT = os.getenv("SERIAL_PORT", "COM5")
SERIAL_BAUD = _int("SERIAL_BAUD", 115200)
SERIAL_RETRY_S = 3.0
SENSOR_FIELDS = 10  # ax,ay,az,gx,gy,gz,fsr,pot,btn1,btn2 (8 en placas sin botones)
SENSOR_RATE_HZ = 50.0

# --- IA Director ---
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
AI_MODEL = os.getenv("AI_MODEL", "claude-sonnet-5")
AI_INTERVAL_S = 7.0        # cadencia de decisiones (5–10 s según spec)
AI_TIMEOUT_S = 5.0         # timeout duro -> fallback reglas locales
AI_MAX_TOKENS = 600

# --- Reglas musicales ---
BPM_MIN, BPM_MAX = 60, 180
BPM_STEP_MAX = 10          # cambio máximo por decisión (gradualidad)
FX_STEP_MAX = 0.2
SCALE_CHANGE_COOLDOWN_S = 20.0
DEFAULT_BPM = 112
DEFAULT_SCALE = "Am_pentatonic"
DEFAULT_ROOT = 69          # A4

# --- Cadencias del Loop 2 ---
STATE_BROADCAST_S = 0.1    # jam:state a 10 Hz
VOTES_BROADCAST_S = 1.0    # jam:votes a 1 Hz
FX_APPLY_S = 0.5           # suavizado de FX votados hacia Pd

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
GYRO_FULL_SCALE_DPS = 250.0
PERFORMER_ACTIVE_WINDOW_S = 3.0
