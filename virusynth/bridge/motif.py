"""El leitmotiv de ViruSynth: un motivo y sus transformaciones.

Lo que hace que Undertale suene a Undertale no es el timbre: es que una misma
celula melodica vuelve transformada en contextos distintos. Este modulo es esa
maquina.

Los pasos guardan GRADOS RELATIVOS de la escala, no notas MIDI, para que el
motivo sobreviva a las modulaciones y a los cambios de escala que vota la
audiencia. La conversion a notas concretas ocurre solo en realize().

Todas las transformaciones son puras y deterministas: devuelven un Motif nuevo
y nunca usan azar, porque de eso depende que el test dorado sea estable.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Sequence

from . import music_engine


@dataclass(frozen=True)
class MotifStep:
    degree: int          # desplazamiento en grados de escala respecto a la tonica
    dur: int             # duracion en semicorcheas
    accent: bool = False


@dataclass(frozen=True)
class Motif:
    steps: tuple[MotifStep, ...] = ()
    name: str = ""

    @property
    def length(self) -> int:
        return sum(s.dur for s in self.steps)


def transpose(m: Motif, n: int) -> Motif:
    return replace(m, steps=tuple(replace(s, degree=s.degree + n) for s in m.steps))


def invert(m: Motif, axis: int = 0) -> Motif:
    return replace(m, steps=tuple(replace(s, degree=2 * axis - s.degree)
                                  for s in m.steps))


def retrograde(m: Motif) -> Motif:
    return replace(m, steps=tuple(reversed(m.steps)))


def scale_time(m: Motif, factor: float) -> Motif:
    """Multiplica las duraciones. Nunca deja un paso por debajo de 1."""
    return replace(m, steps=tuple(replace(s, dur=max(1, round(s.dur * factor)))
                                  for s in m.steps))


def augment(m: Motif, f: int = 2) -> Motif:
    """Estira las duraciones por `f`. Un factor no positivo no hace nada."""
    if f <= 0:
        return m
    return scale_time(m, float(f))


def diminish(m: Motif, f: int = 2) -> Motif:
    """Encoge las duraciones por `f`. Un factor no positivo no hace nada.

    La guarda no es decorativa: la Fase 2 expone estas transformaciones a la
    IA via transform_motif, donde `f` puede venir de una decision del modelo
    o de un voto sin validar. Un 0 aqui reventaba con ZeroDivisionError.
    """
    if f <= 0:
        return m
    return scale_time(m, 1.0 / float(f))


def octave(m: Motif, n: int, degrees_per_octave: int) -> Motif:
    return transpose(m, n * degrees_per_octave)


def _nearest_chord_tone(degree: int, chord_degrees: Sequence[int],
                        scale_size: int) -> int:
    """El tono de acorde mas cercano a `degree`, en la octava que sea.

    Por cada grado del acorde solo hay dos candidatos capaces de ganar: los
    dos que enmarcan a `degree`. Se derivan con division entera, asi que la
    respuesta es exacta para grados arbitrariamente lejanos. Una ventana fija
    de N octavas deja de ser correcta en cuanto el motivo la desborda, y
    octave(m, 4, 7) la desborda con lo mas normal del mundo.

    Empate: gana el mas grave, como antes.
    """
    candidates = []
    for c in chord_degrees:
        k = (degree - c) // scale_size
        candidates.append(c + scale_size * k)
        candidates.append(c + scale_size * (k + 1))
    return min(candidates, key=lambda cand: (abs(cand - degree), cand))


def reharmonize(m: Motif, chord_degrees: Sequence[int], scale_size: int) -> Motif:
    """Ancla los pasos ACENTUADOS al tono de acorde mas cercano.

    Los pasos sin acento se dejan tal cual: son las notas de paso que dan
    movimiento. Si el acorde no aporta ningun grado, el motivo vuelve intacto.
    """
    if not chord_degrees or scale_size <= 0:
        return m
    new_steps = []
    for step in m.steps:
        if step.accent:
            best = _nearest_chord_tone(step.degree, chord_degrees, scale_size)
            new_steps.append(replace(step, degree=best))
        else:
            new_steps.append(step)
    return replace(m, steps=tuple(new_steps))


def ornament(m: Motif, level: int = 1) -> Motif:
    """Inserta notas de paso entre grados distantes, conservando la duracion.

    Un paso se parte en dos mitades solo si dura >= 2 semicorcheas y el salto
    hasta el paso siguiente es de 2 grados o mas. Determinista por diseno.
    """
    result = m
    for _ in range(max(0, level)):
        new_steps: list[MotifStep] = []
        steps = result.steps
        for i, step in enumerate(steps):
            nxt = steps[i + 1] if i + 1 < len(steps) else None
            gap = abs(nxt.degree - step.degree) if nxt is not None else 0
            if nxt is not None and gap >= 2 and step.dur >= 2:
                first = step.dur // 2
                new_steps.append(replace(step, dur=first))
                middle = step.degree + (1 if nxt.degree > step.degree else -1)
                new_steps.append(MotifStep(degree=middle,
                                           dur=step.dur - first, accent=False))
            else:
                new_steps.append(step)
        result = replace(result, steps=tuple(new_steps))
    return result


def fold_to_range(note: int, lo: int, hi: int) -> int:
    """Pliega por octavas hasta entrar en [lo, hi]. Nunca descarta la nota."""
    if lo > hi:
        return note
    guard = 0
    while note < lo and guard < 16:
        note += 12
        guard += 1
    while note > hi and guard < 32:
        note -= 12
        guard += 1
    return max(lo, min(hi, note))


def realize(m: Motif, scale: str, root: int,
            lo: int, hi: int) -> list[tuple[int, int, int, bool]]:
    """Grados -> notas MIDI concretas. Devuelve (offset, nota, dur, accent)."""
    if not m.steps:
        return []
    notes = music_engine.scale_notes(scale, 0, 127)
    if not notes:
        return []
    base = min(range(len(notes)), key=lambda i: (abs(notes[i] - root), i))

    events: list[tuple[int, int, int, bool]] = []
    offset = 0
    for step in m.steps:
        idx = max(0, min(len(notes) - 1, base + step.degree))
        events.append((offset, fold_to_range(notes[idx], lo, hi),
                       step.dur, step.accent))
        offset += step.dur
    return events
