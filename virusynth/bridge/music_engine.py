"""Motor de teoría musical de ViruSynth (stdlib puro, 100% testeable).

Aquí vive TODA la inteligencia musical local: escalas, cuantización, detección de
choques armónicos, resoluciones, vecindad de escalas y las reglas fallback que
sustituyen al LLM cuando no responde (CLAUDE.md §7).
"""
from __future__ import annotations

import re
from typing import Any, Optional

from . import config

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
_FLATS = {"Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#", "Bb": "A#", "Cb": "B", "Fb": "E"}

SCALE_INTERVALS: dict[str, list[int]] = {
    "major":            [0, 2, 4, 5, 7, 9, 11],
    "minor":            [0, 2, 3, 5, 7, 8, 10],
    "minor_pentatonic": [0, 3, 5, 7, 10],
    "major_pentatonic": [0, 2, 4, 7, 9],
    "dorian":           [0, 2, 3, 5, 7, 9, 10],
    "mixolydian":       [0, 2, 4, 5, 7, 9, 10],
    "lydian":           [0, 2, 4, 6, 7, 9, 11],
    "phrygian":         [0, 1, 3, 5, 7, 8, 10],
    "blues":            [0, 3, 5, 6, 7, 10],
    "harmonic_minor":   [0, 2, 3, 5, 7, 8, 11],
}

# Intervalos (mod 12) que tratamos como choque no intencional entre dos notas
_CLASH_INTERVALS = {1, 6, 11}  # 2ª menor, tritono, 7ª mayor

_SCALE_RE = re.compile(r"^([A-G])([#b]?)(m?)_([a-z_]+)$")


class ScaleError(ValueError):
    pass


def parse_scale(name: str) -> tuple[int, str]:
    """'Am_pentatonic' -> (9, 'minor_pentatonic'); 'C_major' -> (0, 'major')."""
    m = _SCALE_RE.match(name.strip())
    if not m:
        raise ScaleError(f"Nombre de escala inválido: {name!r}")
    letter, accidental, minor_flag, mode = m.groups()
    pc_name = letter + accidental
    pc_name = _FLATS.get(pc_name, pc_name)
    if pc_name not in NOTE_NAMES:
        raise ScaleError(f"Raíz inválida: {pc_name!r}")
    root_pc = NOTE_NAMES.index(pc_name)

    if mode == "pentatonic":
        mode = "minor_pentatonic" if minor_flag else "major_pentatonic"
    elif minor_flag and mode == "blues":
        mode = "blues"
    elif minor_flag:
        raise ScaleError(f"Sufijo 'm' solo aplica a pentatónica/blues: {name!r}")
    if mode not in SCALE_INTERVALS:
        raise ScaleError(f"Modo desconocido: {mode!r}")
    return root_pc, mode


def scale_name(root_pc: int, mode: str) -> str:
    """Inversa de parse_scale, con nombre canónico."""
    root = NOTE_NAMES[root_pc % 12]
    if mode == "minor_pentatonic":
        return f"{root}m_pentatonic"
    if mode == "major_pentatonic":
        return f"{root}_pentatonic"
    return f"{root}_{mode}"


def pitch_classes(scale: str) -> set[int]:
    root_pc, mode = parse_scale(scale)
    return {(root_pc + i) % 12 for i in SCALE_INTERVALS[mode]}


def scale_notes(scale: str, low: int = 45, high: int = 85) -> list[int]:
    pcs = pitch_classes(scale)
    return [n for n in range(low, high + 1) if n % 12 in pcs]


def is_in_scale(note: int, scale: str) -> bool:
    return note % 12 in pitch_classes(scale)


def quantize(note: int, scale: str) -> int:
    """Nota MIDI más cercana dentro de la escala (en empate, hacia abajo)."""
    if is_in_scale(note, scale):
        return note
    pcs = pitch_classes(scale)
    for dist in range(1, 7):
        if (note - dist) % 12 in pcs:
            return note - dist
        if (note + dist) % 12 in pcs:
            return note + dist
    return note  # inalcanzable: toda escala tiene ≥5 clases


def find_clashes(notes: list[int], scale: str,
                 context: tuple[int, ...] = ()) -> list[dict[str, Any]]:
    """Choques armónicos: notas fuera de escala + pares a 2ªm/tritono/7ªM."""
    clashes: list[dict[str, Any]] = []
    for n in notes:
        if not is_in_scale(n, scale):
            clashes.append({"type": "out_of_scale", "notes": [n]})
    pool = list(notes) + list(context)
    for i, a in enumerate(pool):
        for b in pool[i + 1:]:
            if abs(a - b) % 12 in _CLASH_INTERVALS and abs(a - b) != 0:
                # solo lo reportamos si involucra alguna nota propuesta
                if a in notes or b in notes:
                    clashes.append({"type": "interval", "notes": [a, b],
                                    "interval": abs(a - b) % 12})
    return clashes


def resolve_pattern(notes: list[int], scale: str) -> tuple[list[int], list[dict[str, Any]]]:
    """Cuantiza un patrón a la escala; devuelve (resuelto, cambios)."""
    resolved: list[int] = []
    changes: list[dict[str, Any]] = []
    for n in notes:
        q = quantize(int(n), scale)
        resolved.append(q)
        if q != n:
            changes.append({"from": int(n), "to": q})
    return resolved, changes


def shared_pcs(scale_a: str, scale_b: str) -> int:
    return len(pitch_classes(scale_a) & pitch_classes(scale_b))


def scale_neighbors(scale: str) -> list[str]:
    """Escalas 'vecinas' ordenadas por afinidad (clases de altura compartidas):
    relativa, paralelas al mismo root, ±1 quinta en el mismo modo."""
    root_pc, mode = parse_scale(scale)
    candidates: set[str] = set()
    # relativa mayor/menor (y pentatónicas relativas)
    relatives = {
        "minor": (root_pc + 3, "major"), "major": (root_pc + 9, "minor"),
        "minor_pentatonic": (root_pc + 3, "major_pentatonic"),
        "major_pentatonic": (root_pc + 9, "minor_pentatonic"),
    }
    if mode in relatives:
        rpc, rmode = relatives[mode]
        candidates.add(scale_name(rpc % 12, rmode))
    # mismos root, otros modos (paralelas y coloraciones)
    for other in SCALE_INTERVALS:
        if other != mode:
            candidates.add(scale_name(root_pc, other))
    # ±1 quinta, mismo modo
    candidates.add(scale_name((root_pc + 7) % 12, mode))
    candidates.add(scale_name((root_pc + 5) % 12, mode))
    candidates.discard(scale)
    return sorted(candidates, key=lambda c: -shared_pcs(scale, c))


def modulation_step(current: str, target: str) -> str:
    """Paso de modulación gradual hacia target (sin saltos bruscos).

    Si comparten suficientes clases de altura se va directo; si no, se elige el
    vecino de current más cercano a target (modulación pivote).
    """
    if target == current:
        return current
    if shared_pcs(current, target) >= min(len(pitch_classes(target)),
                                          len(pitch_classes(current))) - 2:
        return target
    neighbors = scale_neighbors(current)
    if not neighbors:
        return target
    return max(neighbors, key=lambda n: (shared_pcs(n, target), shared_pcs(n, current)))


def validate_decision(decision: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Sanea una decisión (del LLM o de reglas). None => descartar y usar fallback."""
    if not isinstance(decision, dict):
        return None
    action = decision.get("action")
    value = decision.get("value")
    out = {
        "action": action,
        "value": value,
        "reasoning": str(decision.get("reasoning") or "")[:400],
        "harmonic_resolution": decision.get("harmonic_resolution"),
    }
    try:
        if action == "change_scale":
            parse_scale(str(value))
            out["value"] = str(value)
        elif action == "set_bpm":
            out["value"] = max(config.BPM_MIN, min(config.BPM_MAX, int(value)))
        elif action == "set_fx":
            if not isinstance(value, dict):
                return None
            fx = {k: max(0.0, min(1.0, float(v))) for k, v in value.items()
                  if k in ("reverb", "delay", "distortion")}
            if not fx:
                return None
            out["value"] = fx
        elif action == "harmonic_resolution":
            hr = out["harmonic_resolution"] or (value if isinstance(value, dict) else None)
            if not hr or "resolved_notes" not in hr:
                return None
            hr["resolved_notes"] = [int(n) for n in hr["resolved_notes"]]
            out["harmonic_resolution"] = hr
            out["value"] = None
        elif action == "no_change":
            out["value"] = None
        else:
            return None
    except (ValueError, TypeError, ScaleError):
        return None
    return out


def rule_based_suggestion(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Fallback local del IA Director. Prioridades (CLAUDE.md §7):
    1) resolver choques de la sugerencia de artista pendiente,
    2) atender el voto mayoritario de escala (con cooldown y modulación gradual),
    3) acercar el BPM al promedio votado,
    4) acercar los FX al promedio votado,
    5) variación estética sutil / no_change.
    """
    scale = snapshot.get("scale", config.DEFAULT_SCALE)
    bpm = int(snapshot.get("bpm", config.DEFAULT_BPM))
    votes = snapshot.get("votes") or {}
    pending = snapshot.get("pending_suggestion")
    cooldown_ok = snapshot.get("last_scale_change_age_s", 1e9) >= config.SCALE_CHANGE_COOLDOWN_S

    def decision(action: str, value: Any, reasoning: str,
                 harmonic: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        return {"action": action, "value": value, "reasoning": reasoning,
                "harmonic_resolution": harmonic, "source": "reglas_locales"}

    # 1) choques armónicos del patrón de artista
    if pending and pending.get("notes"):
        notes = [int(n) for n in pending["notes"]]
        clashes = find_clashes(notes, scale, tuple(snapshot.get("current_notes", ())))
        if clashes:
            resolved, changes = resolve_pattern(notes, scale)
            names = ", ".join(NOTE_NAMES[c["from"] % 12] + "→" + NOTE_NAMES[c["to"] % 12]
                              for c in changes) or "voicing ajustado"
            return decision(
                "harmonic_resolution", None,
                f"El patrón de {pending.get('artist_id', 'un artista')} chocaba con "
                f"{scale}; lo ajusté a la escala ({names}) para que sume sin rozar.",
                {"original_notes": notes, "resolved_notes": resolved,
                 "explanation": f"Sustitución por la nota más cercana en {scale}"})

    # 2) escala más votada
    scale_votes: dict[str, int] = (votes.get("scale_votes") or {})
    if scale_votes and cooldown_ok:
        top_scale, top_count = max(scale_votes.items(), key=lambda kv: kv[1])
        if top_scale != scale and top_count >= 2:
            try:
                step = modulation_step(scale, top_scale)
            except ScaleError:
                step = None
            if step and step != scale:
                via = "" if step == top_scale else f" (modulando primero por {step})"
                return decision("change_scale", step,
                                f"La audiencia pide {top_scale}{via}: comparte "
                                f"{shared_pcs(scale, step)} notas con {scale}, "
                                f"así que la transición se sentirá natural.")

    # 3) BPM votado
    bpm_avg = votes.get("bpm_avg")
    if bpm_avg and abs(int(bpm_avg) - bpm) > 6:
        delta = max(-config.BPM_STEP_MAX, min(config.BPM_STEP_MAX, int(bpm_avg) - bpm))
        new_bpm = max(config.BPM_MIN, min(config.BPM_MAX, bpm + delta))
        direction = "subo" if delta > 0 else "bajo"
        return decision("set_bpm", new_bpm,
                        f"La sala pide {'más energía' if delta > 0 else 'calma'}: "
                        f"{direction} el tempo a {new_bpm} BPM, paso a paso.")

    # 4) FX votados
    fx_avg: dict[str, float] = votes.get("fx_avg") or {}
    fx_now: dict[str, float] = snapshot.get("fx") or {}
    for name in ("reverb", "delay", "distortion"):
        if name in fx_avg and abs(fx_avg[name] - fx_now.get(name, 0.0)) > 0.15:
            target = fx_now.get(name, 0.0) + max(
                -config.FX_STEP_MAX, min(config.FX_STEP_MAX,
                                         fx_avg[name] - fx_now.get(name, 0.0)))
            target = round(max(0.0, min(1.0, target)), 2)
            return decision("set_fx", {name: target},
                            f"Ajusto {name} hacia {target:.2f}, como pide la mayoría.")

    # 5) variación estética / mantener
    amplitude = float(snapshot.get("amplitude", 0.0))
    if amplitude > 0.75 and fx_now.get("reverb", 0.0) > 0.3:
        return decision("set_fx", {"reverb": round(max(0.0, fx_now["reverb"] - 0.1), 2)},
                        "La mezcla viene intensa: seco un poco la reverb para dar aire.")
    return decision("no_change", None,
                    f"El groove en {scale} a {bpm} BPM respira bien; dejo que se asiente.")
