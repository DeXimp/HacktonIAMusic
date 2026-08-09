"""ViruSynth Bridge — entry point y orquestador (ver CLAUDE.md).

Uso típico:
  python -m bridge.main --mock-sensors            # sin hardware
  python -m bridge.main --serial-port COM7        # con ESP32
  python -m bridge.main --mock-sensors --no-ai --no-portal   # mínimo absoluto

Política de aplicación de votos (demo-first):
  - FX: se aplican en caliente con suavizado (la audiencia siente control inmediato).
  - Escala y BPM: los arbitra el IA Director (coherencia musical, cooldown 20 s).
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import time
from typing import Any

from . import config, music_engine
from .ai_director import AIDirector
from .hardware_link import HardwareLink
from .mapping import SensorMapper
from .osc_handler import PdLink
from .portal_client import create_portal, NullPortal
from .sequencer import Sequencer
from .state import GlobalState

log = logging.getLogger("BRIDGE")


def _nearest_root(current_root: int, target_pc: int) -> int:
    candidates = [n for n in range(36, 96) if n % 12 == target_pc]
    return min(candidates, key=lambda n: abs(n - current_root))


class JamController:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.state = GlobalState()
        self.pd = PdLink(self.state)
        self.pd.on_trigger = self._on_note_triggered
        self.portal = NullPortal() if args.no_portal else create_portal()
        self.portal.set_handler(self.on_portal_message)
        self.mapper = SensorMapper(self.state, self.pd)
        self.sequencer = Sequencer(self.state, self.pd)
        self.director = AIDirector(self.state, self.apply_ai_decision)
        self.sensor_queue: asyncio.Queue = asyncio.Queue(maxsize=64)
        self.hardware = HardwareLink(self.sensor_queue)

    # ------------------------------------------------------------------ portal
    async def on_portal_message(self, channel: str, data: dict[str, Any],
                                client: dict[str, Any]) -> None:
        if channel == "jam:votes:cast":
            self.state.cast_vote(client["id"], data)
        elif channel == "jam:artist_suggestions":
            await self._on_artist_suggestion(data, client)
        elif channel == "client:gone":
            self.state.drop_voter(data.get("client_id", ""))
        elif channel == "presence:changed":
            self.state.presence = dict(data)
            self.state.presence["performers"] = max(
                1, self.state.presence.get("performers", 0))
            await self.portal.publish("jam:presence", self.state.presence)

    async def _on_artist_suggestion(self, data: dict[str, Any],
                                    client: dict[str, Any]) -> None:
        suggestion = data.get("suggestion") or {}
        notes = suggestion.get("notes")
        if not isinstance(notes, list) or not notes:
            return
        try:
            notes = [int(n) for n in notes][:16]
        except (TypeError, ValueError):
            return
        artist_id = str(data.get("artist_id") or client.get("name")
                        or f"artist_{client['id']}")[:40]
        scale = self.state.jam.scale
        resolved, changes = music_engine.resolve_pattern(notes, scale)
        # el patrón (ya cuantizado) entra al secuenciador: todos lo oyen ya
        self.state.jam.active_pattern = resolved
        self.state.jam.pattern_author = artist_id
        # si hubo choques, queda pendiente para que la IA lo comente
        self.state.pending_suggestion = ({"artist_id": artist_id, "notes": notes}
                                         if changes else None)
        payload = {"artist_id": artist_id,
                   "suggestion": {"type": "note_pattern", "notes": notes,
                                  "resolved_notes": resolved,
                                  "changes": changes}}
        self.state.suggestions.append(payload)
        await self.portal.publish("jam:artist_suggestions", payload)
        log.info("Patrón de %s: %s -> %s", artist_id, notes, resolved)

    # ------------------------------------------------------------- audiencia
    def _on_note_triggered(self, note: int, velocity: int) -> None:
        """Eco de control hacia la audiencia web (canal jam:note_triggered)
        cada vez que PdLink dispara una nota — el audio real sigue siendo
        100% de Pd; esto solo deja que el mini-sintetizador del navegador
        (web/js/audio-engine.js) toque la misma nota casi en vivo."""
        asyncio.create_task(self.portal.publish(
            "jam:note_triggered", {"note": note, "velocity": velocity}))

    # ---------------------------------------------------------------- decisión
    async def apply_ai_decision(self, decision: dict[str, Any]) -> None:
        action, value = decision.get("action"), decision.get("value")
        jam = self.state.jam
        if action == "change_scale" and isinstance(value, str):
            cooldown = time.monotonic() - jam.last_scale_change_ts
            if cooldown < config.SCALE_CHANGE_COOLDOWN_S:
                log.info("Cambio de escala ignorado (cooldown %.0fs)", cooldown)
                return
            root_pc, _mode = music_engine.parse_scale(value)
            jam.scale = value
            jam.root_note = _nearest_root(jam.root_note, root_pc)
            jam.last_scale_change_ts = time.monotonic()
            if jam.active_pattern:
                jam.active_pattern, _ = music_engine.resolve_pattern(
                    jam.active_pattern, value)
            self.pd.set_param("scale", value)
            self.pd.set_param("root_note", jam.root_note)
        elif action == "set_bpm" and isinstance(value, int):
            jam.bpm = value
            self.pd.set_param("bpm", value)
        elif action == "set_fx" and isinstance(value, dict):
            for name, v in value.items():
                setattr(jam.fx, name, float(v))
                self.pd.set_param(f"fx/{name}", float(v))
        elif action == "harmonic_resolution":
            hr = decision.get("harmonic_resolution") or {}
            resolved = hr.get("resolved_notes")
            if isinstance(resolved, list) and resolved:
                jam.active_pattern, _ = music_engine.resolve_pattern(
                    [int(n) for n in resolved], jam.scale)
            self.state.pending_suggestion = None
        self.state.ai_history.append(decision)
        await self.portal.publish("jam:ai_director", decision)
        log.info("[%s] %s -> %s | %s", decision.get("source"), action,
                 value if value is not None else "-", decision.get("reasoning"))

    # ----------------------------------------------------------------- tareas
    async def _consume_sensors(self) -> None:
        while True:
            frame = await self.sensor_queue.get()
            try:
                self.mapper.process(frame)
            except Exception as exc:
                log.error("mapping falló: %s", exc)

    async def _broadcast_state(self) -> None:
        while True:
            await self.portal.publish("jam:state", self.state.jam_dict())
            await asyncio.sleep(config.STATE_BROADCAST_S)

    async def _broadcast_votes(self) -> None:
        while True:
            await asyncio.sleep(config.VOTES_BROADCAST_S)
            if self.state.votes:
                await self.portal.publish("jam:votes", self.state.aggregate_votes())

    async def _apply_voted_fx(self) -> None:
        """Acerca los FX al promedio votado (lerp 15% cada medio segundo)."""
        while True:
            await asyncio.sleep(config.FX_APPLY_S)
            fx_avg = self.state.aggregate_votes().get("fx_avg") or {}
            for name, target in fx_avg.items():
                current = getattr(self.state.jam.fx, name, None)
                if current is None or abs(target - current) < 0.01:
                    continue
                nuevo = round(current + (target - current) * 0.15, 3)
                setattr(self.state.jam.fx, name, nuevo)
                self.pd.set_param(f"fx/{name}", float(nuevo))

    # ------------------------------------------------------------------- run
    async def run(self) -> None:
        await self.pd.start_telemetry()
        self.pd.sync_full()
        tasks = [
            asyncio.create_task(self._consume_sensors(), name="sensors"),
            asyncio.create_task(self.sequencer.run(), name="sequencer"),
            asyncio.create_task(self._broadcast_state(), name="state"),
            asyncio.create_task(self._broadcast_votes(), name="votes"),
            asyncio.create_task(self._apply_voted_fx(), name="fx"),
        ]
        if not self.args.no_portal:
            await self.portal.start()
        if not self.args.no_ai:
            tasks.append(asyncio.create_task(self.director.run(), name="ia"))
        self.hardware.start(asyncio.get_running_loop(), port=self.args.serial_port,
                            baud=config.SERIAL_BAUD, force_mock=self.args.mock_sensors,
                            disable=self.args.no_serial)
        log.info("ViruSynth Bridge listo | placa %s (ADC_MAX=%d) | escala %s | %d BPM | OSC->%s:%d",
                 config.HARDWARE_BOARD, config.ADC_MAX,
                 self.state.jam.scale, self.state.jam.bpm,
                 config.PD_HOST, config.PD_SEND_PORT)
        try:
            await asyncio.gather(*tasks)
        finally:
            self.hardware.stop()
            await self.portal.stop()
            self.pd.stop()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="virusynth-bridge",
                                description="Orquestador central de ViruSynth")
    p.add_argument("--mock-sensors", action="store_true",
                   help="performer sintético (sin ESP32)")
    p.add_argument("--no-serial", action="store_true",
                   help="no intentar abrir el puerto serie")
    p.add_argument("--no-portal", action="store_true",
                   help="sin capa realtime (ni WS local)")
    p.add_argument("--no-ai", action="store_true",
                   help="desactivar el IA Director por completo")
    p.add_argument("--serial-port", default=config.SERIAL_PORT,
                   help=f"puerto del ESP32 (default {config.SERIAL_PORT})")
    p.add_argument("--log-level", default="INFO")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    logging.basicConfig(level=args.log_level.upper(),
                        format="%(asctime)s [%(name)s] %(message)s",
                        datefmt="%H:%M:%S")
    try:
        asyncio.run(JamController(args).run())
    except KeyboardInterrupt:
        log.info("Hasta la próxima jam.")


if __name__ == "__main__":
    main()
