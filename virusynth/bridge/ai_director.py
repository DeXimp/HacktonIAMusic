"""IA Director de ViruSynth — Claude con tool use + fallback a reglas locales.

Regla cardinal (CLAUDE.md §2): el LLM NUNCA está en el audio path. Este módulo
corre en el Loop 2 con cadencia AI_INTERVAL_S y timeout duro AI_TIMEOUT_S; si
la nube falla por cualquier motivo, decide music_engine.rule_based_suggestion.
"""
from __future__ import annotations

import asyncio
import datetime as _dt
import json
import logging
from typing import Any, Awaitable, Callable, Optional

from . import config, music_engine

log = logging.getLogger("IA")

SYSTEM_PROMPT = """Eres el Director Musical de ViruSynth, un instrumento colaborativo en tiempo real.

Tu rol:
1. Analizar el estado musical actual (escala, BPM, notas activas, FX, amplitud)
2. Considerar los votos agregados de la audiencia y las sugerencias de los artistas remotos
3. Sugerir UNA mutación musical coherente por turno
4. Si detectas choques armónicos (notas fuera de escala, segundas menores o tritonos no
   intencionales entre sugerencias), proponer la resolución (sustitución por la nota más
   cercana dentro de la escala)
5. Mantener coherencia: no cambies de escala si last_scale_change_age_s < 20; modula a
   escalas vecinas (relativa, paralela, ±1 quinta), nunca saltes a tonalidades lejanas

Reglas:
- NUNCA generas audio. Solo parámetros de control vía la tool propose_mutation.
- Cambios graduales: BPM en pasos de <=10, FX en pasos de <=0.2.
- Prioridad: intención del performer > votos de audiencia > tu propia estética.
- Las escalas usan nombres como "Am_pentatonic", "C_major", "D_dorian", "E_minor",
  "G_mixolydian", "Am_blues". Modos válidos: major, minor, minor_pentatonic,
  major_pentatonic, dorian, mixolydian, lydian, phrygian, blues, harmonic_minor.
- El campo "reasoning" (1-2 frases, en español, tono musical y cercano) se muestra en
  vivo a la audiencia: escríbelo para humanos, no para máquinas.
- Si nada amerita cambio, usa action "no_change" con un reasoning observacional breve.

Responde SIEMPRE con una única llamada a la tool propose_mutation."""

PROPOSE_MUTATION_TOOL = {
    "name": "propose_mutation",
    "description": "Propone la próxima mutación musical del instrumento colaborativo.",
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["change_scale", "set_bpm", "set_fx",
                         "harmonic_resolution", "no_change"],
            },
            "value": {
                "description": ("change_scale: string (p.ej. 'E_minor'); set_bpm: int "
                                "60-180; set_fx: objeto {reverb|delay|distortion: 0-1}; "
                                "harmonic_resolution y no_change: null"),
            },
            "reasoning": {
                "type": "string",
                "description": "1-2 frases en español para mostrar a la audiencia",
            },
            "harmonic_resolution": {
                "description": ("Solo para action=harmonic_resolution: objeto con "
                                "original_notes (int[]), resolved_notes (int[]) y "
                                "explanation (string). En otro caso null."),
            },
        },
        "required": ["action", "reasoning"],
    },
}


class AIDirector:
    """Genera una decisión cada AI_INTERVAL_S y la entrega vía apply_cb."""

    def __init__(self, state,
                 apply_cb: Callable[[dict[str, Any]], Awaitable[None]]) -> None:
        self.state = state
        self.apply_cb = apply_cb
        self._client = self._make_client()

    @staticmethod
    def _make_client():
        if not config.ANTHROPIC_API_KEY:
            log.warning("Sin ANTHROPIC_API_KEY: el director usará reglas locales")
            return None
        try:
            from anthropic import AsyncAnthropic  # type: ignore
        except ImportError:
            log.warning("SDK 'anthropic' no instalado: reglas locales")
            return None
        log.info("Director conectado a %s (timeout %.1fs)",
                 config.AI_MODEL, config.AI_TIMEOUT_S)
        return AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY,
                              timeout=config.AI_TIMEOUT_S, max_retries=0)

    async def _ask_claude(self, snapshot: dict[str, Any]) -> Optional[dict[str, Any]]:
        response = await self._client.messages.create(
            model=config.AI_MODEL,
            max_tokens=config.AI_MAX_TOKENS,
            system=SYSTEM_PROMPT,
            # Latencia primero (cadencia 5-10 s): sin thinking + effort low es la
            # combinación válida más rápida; tool_choice forzado garantiza tool_use.
            thinking={"type": "disabled"},
            output_config={"effort": "low"},
            tools=[PROPOSE_MUTATION_TOOL],
            tool_choice={"type": "tool", "name": "propose_mutation"},
            messages=[{
                "role": "user",
                "content": ("Estado global de la jam (JSON):\n"
                            + json.dumps(snapshot, ensure_ascii=False)
                            + "\nPropón la próxima mutación."),
            }],
        )
        if response.stop_reason == "refusal":
            log.warning("El modelo declinó la petición; uso reglas locales")
            return None
        for block in response.content:
            if block.type == "tool_use" and block.name == "propose_mutation":
                return dict(block.input)
        return None

    async def decide(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        """Claude con timeout duro → validación → fallback a reglas locales."""
        if self._client is not None:
            try:
                raw = await asyncio.wait_for(self._ask_claude(snapshot),
                                             timeout=config.AI_TIMEOUT_S)
                decision = music_engine.validate_decision(raw) if raw else None
                if decision is not None:
                    decision["source"] = "claude"
                    return decision
                log.warning("Decisión del LLM inválida; uso reglas locales")
            except asyncio.TimeoutError:
                log.warning("LLM superó %.1fs; uso reglas locales", config.AI_TIMEOUT_S)
            except Exception as exc:  # red, auth, créditos, rate limit… nunca tumbar el loop
                status = getattr(exc, "status_code", None)
                if status in (401, 403):
                    log.warning("LLM: API key inválida o sin permisos; uso reglas locales")
                elif status == 429:
                    log.warning("LLM: rate limit / posible falta de créditos; uso reglas locales")
                else:
                    log.warning("LLM falló (%s); uso reglas locales", type(exc).__name__)
        decision = music_engine.rule_based_suggestion(snapshot)
        return decision

    async def run(self) -> None:
        log.info("IA Director en marcha (cada %.0fs, fuente: %s)",
                 config.AI_INTERVAL_S,
                 "claude+reglas" if self._client else "reglas locales")
        while True:
            await asyncio.sleep(config.AI_INTERVAL_S)
            try:
                snapshot = self.state.snapshot_for_ai()
                decision = await self.decide(snapshot)
                decision["timestamp"] = _dt.datetime.now(
                    _dt.timezone.utc).isoformat(timespec="seconds")
                await self.apply_cb(decision)
            except Exception as exc:
                log.error("ciclo del director falló: %s", exc)
