"""OSC bidireccional con Pure Data.

Backend preferido: python-osc. Si no está instalado, cae a bridge/osc_mini.py
(codec propio en stdlib) — el bridge nunca muere por un import (CLAUDE.md §3).
"""
from __future__ import annotations

import asyncio
import logging
import socket
from typing import Any, Callable, Optional

from . import config, osc_mini

log = logging.getLogger("OSC")

try:
    from pythonosc.udp_client import SimpleUDPClient  # type: ignore
    _HAS_PYTHONOSC = True
except ImportError:
    SimpleUDPClient = None  # type: ignore
    _HAS_PYTHONOSC = False


class PdLink:
    """Envío de control a Pd (:9000) + servidor de telemetría (:8000)."""

    def __init__(self, state) -> None:
        self.state = state
        self._transport = None
        # hook opcional: JamController lo engancha para avisarle a la
        # audiencia web (canal jam:note_triggered) cada vez que suena una
        # nota — el motor de audio local nunca sabe ni le importa que esto
        # exista (CLAUDE.md §2: Pd sigue siendo la única fuente de sonido
        # "real"; esto es solo un eco de control para el navegador).
        self.on_trigger: Optional[Callable[[int, int], None]] = None
        if _HAS_PYTHONOSC:
            self._client = SimpleUDPClient(config.PD_HOST, config.PD_SEND_PORT)
            self._sock = None
        else:
            log.warning("python-osc no instalado: usando codec interno osc_mini")
            self._client = None
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # ---- salida hacia Pd ---------------------------------------------------
    def send(self, address: str, *args: Any) -> None:
        try:
            if self._client is not None:
                self._client.send_message(address, list(args) if len(args) != 1 else args[0])
            else:
                self._sock.sendto(osc_mini.encode(address, *args),
                                  (config.PD_HOST, config.PD_SEND_PORT))
        except OSError as exc:  # nunca tumbar el loop por la red
            log.debug("send %s falló: %s", address, exc)

    def set_param(self, name: str, value: Any) -> None:
        self.send(f"/pd/set/{name}", value)

    def trigger_note(self, note: int, velocity: int) -> None:
        self.send("/pd/trigger/note", int(note), int(velocity))
        if self.on_trigger is not None:
            self.on_trigger(int(note), int(velocity))

    def sync_full(self) -> None:
        """Reenvía el estado completo (al arrancar y tras reconexiones de Pd)."""
        j = self.state.jam
        self.set_param("scale", j.scale)
        self.set_param("bpm", j.bpm)
        self.set_param("root_note", j.root_note)
        self.set_param("volume", float(j.volume))
        self.set_param("cutoff", float(j.cutoff))
        self.set_param("resonance", float(j.resonance))
        self.set_param("fx/reverb", float(j.fx.reverb))
        self.set_param("fx/delay", float(j.fx.delay))
        self.set_param("fx/distortion", float(j.fx.distortion))

    # ---- telemetría desde Pd ----------------------------------------------
    def _on_amplitude(self, *args: Any) -> None:
        vals = [a for a in args if isinstance(a, (int, float))]
        if vals:
            self.state.jam.amplitude = max(0.0, min(1.5, float(vals[-1])))

    def _on_last_note(self, *args: Any) -> None:
        vals = [a for a in args if isinstance(a, (int, float))]
        if vals:
            note = int(vals[-1])
            if 0 < note < 128 and (not self.state.jam.current_notes
                                   or self.state.jam.current_notes[-1] != note):
                self.state.jam.current_notes.append(note)

    def _dispatch(self, address: str, args: list[Any]) -> None:
        if address == "/pd/state/amplitude":
            self._on_amplitude(*args)
        elif address == "/pd/state/last_note":
            self._on_last_note(*args)

    async def start_telemetry(self) -> None:
        loop = asyncio.get_running_loop()
        if _HAS_PYTHONOSC:
            from pythonosc.dispatcher import Dispatcher  # type: ignore
            from pythonosc.osc_server import AsyncIOOSCUDPServer  # type: ignore

            disp = Dispatcher()
            disp.map("/pd/state/amplitude", lambda _a, *args: self._on_amplitude(*args))
            disp.map("/pd/state/last_note", lambda _a, *args: self._on_last_note(*args))
            server = AsyncIOOSCUDPServer(("127.0.0.1", config.PD_RECV_PORT), disp, loop)
            self._transport, _ = await server.create_serve_endpoint()
        else:
            link = self

            class _Proto(asyncio.DatagramProtocol):
                def datagram_received(self, data: bytes, _addr) -> None:
                    for address, args in osc_mini.decode(data):
                        link._dispatch(address, args)

            self._transport, _ = await loop.create_datagram_endpoint(
                _Proto, local_addr=("127.0.0.1", config.PD_RECV_PORT))
        log.info("Telemetría de Pd escuchando en udp://127.0.0.1:%d", config.PD_RECV_PORT)

    def stop(self) -> None:
        if self._transport:
            self._transport.close()
