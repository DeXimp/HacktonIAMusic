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
