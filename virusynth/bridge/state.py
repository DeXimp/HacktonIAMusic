"""Estado global compartido de ViruSynth (dataclasses stdlib, sin locks:
todas las mutaciones ocurren en el event loop; el hilo serial solo encola)."""
from __future__ import annotations

import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Optional

from . import config


@dataclass
class FxState:
    reverb: float = 0.35
    delay: float = 0.25
    distortion: float = 0.05

    def as_dict(self) -> dict[str, float]:
        return {"reverb": round(self.reverb, 3), "delay": round(self.delay, 3),
                "distortion": round(self.distortion, 3)}


@dataclass
class JamState:
    bpm: int = config.DEFAULT_BPM
    scale: str = config.DEFAULT_SCALE
    root_note: int = config.DEFAULT_ROOT
    volume: float = 0.8
    cutoff: float = 1200.0
    resonance: float = 2.0
    fx: FxState = field(default_factory=FxState)
    amplitude: float = 0.0            # telemetría real de Pd (env~)
    current_notes: deque = field(default_factory=lambda: deque(maxlen=8))
    active_pattern: Optional[list[int]] = None   # patrón de artista aceptado
    pattern_author: str = ""
    last_trigger_ts: float = 0.0
    last_scale_change_ts: float = 0.0

    @property
    def performer_active(self) -> bool:
        return (time.monotonic() - self.last_trigger_ts) < config.PERFORMER_ACTIVE_WINDOW_S


class GlobalState:
    """Raíz del estado + agregación de votos + snapshots para IA/broadcast."""

    def __init__(self) -> None:
        self.jam = JamState()
        self.session_id = uuid.uuid4().hex[:8]
        self.votes: dict[str, dict[str, Any]] = {}          # client_id -> voto parcial
        self.pending_suggestion: Optional[dict[str, Any]] = None
        self.suggestions: deque = deque(maxlen=12)
        self.ai_history: deque = deque(maxlen=24)
        self.presence: dict[str, int] = {"performers": 0, "artists": 0, "audience": 0}

    # ---- votos -------------------------------------------------------------
    def cast_vote(self, client_id: str, data: dict[str, Any]) -> None:
        vote = self.votes.setdefault(client_id, {})
        if isinstance(data.get("scale"), str):
            vote["scale"] = data["scale"]
        if isinstance(data.get("bpm"), (int, float)):
            vote["bpm"] = max(config.BPM_MIN, min(config.BPM_MAX, int(data["bpm"])))
        if isinstance(data.get("fx"), dict):
            fx = vote.setdefault("fx", {})
            for k, v in data["fx"].items():
                if k in ("reverb", "delay", "distortion") and isinstance(v, (int, float)):
                    fx[k] = max(0.0, min(1.0, float(v)))
        vote["ts"] = time.monotonic()

    def drop_voter(self, client_id: str) -> None:
        self.votes.pop(client_id, None)

    def aggregate_votes(self) -> dict[str, Any]:
        scale_votes: dict[str, int] = {}
        bpms: list[int] = []
        fx_acc: dict[str, list[float]] = {}
        for vote in self.votes.values():
            if "scale" in vote:
                scale_votes[vote["scale"]] = scale_votes.get(vote["scale"], 0) + 1
            if "bpm" in vote:
                bpms.append(vote["bpm"])
            for k, v in (vote.get("fx") or {}).items():
                fx_acc.setdefault(k, []).append(v)
        return {
            "scale_votes": dict(sorted(scale_votes.items(), key=lambda kv: -kv[1])),
            "bpm_avg": round(sum(bpms) / len(bpms)) if bpms else None,
            "fx_avg": {k: round(sum(v) / len(v), 2) for k, v in fx_acc.items()},
            "voters": len(self.votes),
        }

    # ---- snapshots ---------------------------------------------------------
    def jam_dict(self) -> dict[str, Any]:
        j = self.jam
        return {
            "bpm": j.bpm, "scale": j.scale, "root_note": j.root_note,
            "volume": round(j.volume, 2), "cutoff": round(j.cutoff, 1),
            "fx": j.fx.as_dict(), "amplitude": round(j.amplitude, 3),
            "current_notes": list(j.current_notes),
            "active_pattern": j.active_pattern, "pattern_author": j.pattern_author,
            "performer_active": j.performer_active, "session": self.session_id,
        }

    def snapshot_for_ai(self) -> dict[str, Any]:
        j = self.jam
        return {
            "scale": j.scale, "bpm": j.bpm, "root_note": j.root_note,
            "fx": j.fx.as_dict(), "amplitude": round(j.amplitude, 3),
            "current_notes": list(j.current_notes),
            "performer_active": j.performer_active,
            "votes": self.aggregate_votes(),
            "pending_suggestion": self.pending_suggestion,
            "active_pattern": j.active_pattern,
            "last_scale_change_age_s": round(
                time.monotonic() - j.last_scale_change_ts, 1),
            "recent_actions": [d.get("action") for d in list(self.ai_history)[-5:]],
            "presence": dict(self.presence),
        }
