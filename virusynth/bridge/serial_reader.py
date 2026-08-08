"""Entrada de sensores: hilo pyserial (ESP32) o generador mock (--mock-sensors).

El hilo NUNCA toca el estado: solo encola tramas crudas hacia el event loop.
Trama esperada (CSV, 8 campos): ax,ay,az,gx,gy,gz,fsr,pot
"""
from __future__ import annotations

import asyncio
import logging
import math
import random
import threading
import time

from . import config

log = logging.getLogger("SERIAL")

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


def start_serial_thread(loop: asyncio.AbstractEventLoop,
                        queue: asyncio.Queue,
                        port: str,
                        baud: int,
                        stop_event: threading.Event) -> threading.Thread | None:
    """Lanza el hilo lector. Devuelve None si pyserial no está disponible."""
    try:
        import serial  # type: ignore
    except ImportError:
        log.warning("pyserial no instalado: usa --mock-sensors")
        return None

    def _run() -> None:
        ser = None
        warned = False
        while not stop_event.is_set():
            if ser is None:
                try:
                    ser = serial.Serial(port, baud, timeout=1)
                    log.info("ESP32 conectado en %s @ %d", port, baud)
                    warned = False
                except serial.SerialException:
                    if not warned:
                        log.warning("Sin ESP32 en %s; reintentando cada %.0f s",
                                    port, config.SERIAL_RETRY_S)
                        warned = True
                    stop_event.wait(config.SERIAL_RETRY_S)
                    continue
            try:
                raw = ser.readline()
            except serial.SerialException:
                log.warning("ESP32 desconectado; reintentando…")
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


def _offer(queue: asyncio.Queue, frame: SensorFrame) -> None:
    """Encola descartando lo viejo si el consumidor va lento (latencia > backlog)."""
    if queue.full():
        try:
            queue.get_nowait()
        except asyncio.QueueEmpty:
            pass
    queue.put_nowait(frame)


async def mock_sensor_task(queue: asyncio.Queue,
                           rate_hz: float = config.SENSOR_RATE_HZ) -> None:
    """Performer sintético: balancea el 'instrumento' y pulsa el FSR con groove."""
    t0 = time.monotonic()
    period = 1.0 / rate_hz
    next_press = 1.0
    press_until = 0.0
    while True:
        t = time.monotonic() - t0
        ax = 0.65 * math.sin(t * 0.23) + random.uniform(-0.02, 0.02)   # timbre
        ay = 0.80 * math.sin(t * 0.11 + 1.3) + random.uniform(-0.02, 0.02)  # nota
        az = 0.98 + random.uniform(-0.01, 0.01)
        swing = abs(math.sin(t * 0.9))
        gx = 40.0 * swing + random.uniform(0, 6)
        gy = 25.0 * math.sin(t * 0.7) + random.uniform(-4, 4)
        gz = random.uniform(-5, 5)
        if t >= next_press:                       # pulsos de FSR con acentos
            press_until = t + random.uniform(0.08, 0.22)
            next_press = t + random.choice([0.5, 0.5, 0.75, 1.0, 1.5])
        fsr = random.uniform(1500, 3800) if t < press_until else random.uniform(0, 120)
        pot = 3300 + 500 * math.sin(t * 0.05)
        _offer(queue, (round(ax, 3), round(ay, 3), round(az, 3),
                       round(gx, 1), round(gy, 1), round(gz, 1),
                       round(fsr), round(pot)))
        await asyncio.sleep(period)
