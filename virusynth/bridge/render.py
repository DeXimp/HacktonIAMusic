"""El renderizador: junta estilo, armonia, motivo y arreglo en un compas.

render_bar() no tiene azar ni I/O: la misma secuencia de contextos produce
siempre la misma partitura. Eso es lo que hace posibles el test dorado y
scripts/render-jam.py, y es la razon de que este modulo no viva dentro de
sequencer.py: el reloj asincrono es otra responsabilidad.

No es una funcion pura, y conviene saber exactamente en que: _render_chords
AVANZA ctx.prev_voicing a proposito, porque la conduccion de voces necesita
saber donde quedo el acorde anterior. Consecuencia medida: el voicing de un
compas depende de QUE compas se renderizo antes. Con la progresion
(i, VI, VII, i), el VI da (60, 65, 69) desde un contexto fresco o despues del i,
pero (57, 60, 65) si antes se renderizo el VII.

Repetir el MISMO compas seguido si es idempotente -- voice_lead no mueve nada
cuando el acorde no cambio --, asi que la impureza no se nota en un reintento.
Lo que hay que respetar es el orden: la misma secuencia de compases desde un
contexto fresco da siempre la misma partitura, y eso es lo que necesitan el test
dorado y render-jam.py. Ver test_render.TestContratoDeEstado.

Un compas son 16 semicorcheas. Las duraciones se expresan en pasos, no en
milisegundos: la conversion depende del BPM y la hace quien reproduce.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import harmony, motif as M, music_engine
from .arrangement import SectionPlan
from .style import DRUM_PATTERNS, StyleDeck

STEPS_PER_BAR = 16
DRUM_IDS = {"kick": 0, "snare": 1, "hat": 2}

VELOCITY_ACCENT = 104
VELOCITY_NORMAL = 74
VELOCITY_SOFT = 56
DRUM_VELOCITY = {"kick": 112, "snare": 96, "hat": 58}


@dataclass(frozen=True)
class VoiceEvent:
    voice: str
    step: int
    notes: tuple[int, ...]
    velocity: int
    dur_steps: int


@dataclass(frozen=True)
class Bar:
    index: int
    bpm: int
    ms: int
    swing: float
    section: str
    events: tuple[VoiceEvent, ...]


@dataclass
class RenderContext:
    scale: str
    root: int
    bpm: int
    deck: StyleDeck
    section: SectionPlan
    bar_in_section: int
    progression: tuple[str, ...]
    motif: M.Motif
    is_last_bar: bool = False
    prev_voicing: list[int] = field(default_factory=list)
    # Patron de un artista remoto, ya cuantizado a la escala por
    # music_engine.resolve_pattern. Si viene, reemplaza al leitmotiv en la voz
    # lead: el artista toca la melodia y el motor le pone el acompanamiento.
    artist_pattern: list[int] | None = None


def step_ms(bpm: int) -> float:
    """Duracion de una semicorchea en milisegundos."""
    return 60000.0 / max(1, bpm) / 4.0


def bar_ms(bpm: int) -> int:
    return round(step_ms(bpm) * STEPS_PER_BAR)


def _scale_size(scale: str) -> int:
    return max(1, len(music_engine.pitch_classes(scale)))


def _lowest_with_pc(pc: int, lo: int, hi: int) -> int:
    """La nota mas grave >= lo que tenga la clase de altura `pc`.

    `lo + pc` NO sirve: solo cae en la clase de altura correcta si `lo` es un Do.
    El bajo de determinacion arranca en 33, que es un La, asi que `lo + 9` para
    un La daba 42 = Fa#, un tritono de distancia. Hay que medir el intervalo
    desde `lo`, no desde Do.
    """
    note = lo + ((pc - lo) % 12)
    return M.fold_to_range(note, lo, hi)


def _render_bass(ctx: RenderContext, roman: str) -> list[VoiceEvent]:
    # El registro sale del propio rango de la voz: la nota mas grave que la voz
    # admite con esa clase de altura es justo donde tiene que estar un bajo.
    # Sin numeros magicos.
    patch = ctx.deck.voices["bass"]
    pcs = harmony.chord_pitch_classes(ctx.scale, roman)
    root_note = _lowest_with_pc(pcs[0], patch.range_lo, patch.range_hi)
    fifth = _lowest_with_pc(pcs[min(2, len(pcs) - 1)],
                            patch.range_lo, patch.range_hi)

    if ctx.section.tempo_mode == "half" or ctx.section.density < 0.4:
        steps = (0, 8)
    elif ctx.section.density < 0.7:
        steps = (0, 4, 8, 12)
    else:
        steps = (0, 3, 6, 8, 11, 14)

    events = []
    for i, step in enumerate(steps):
        note = root_note if i % 3 != 2 else fifth
        events.append(VoiceEvent("bass", step, (note,),
                                 VELOCITY_ACCENT if step == 0 else VELOCITY_NORMAL,
                                 2))
    return events


def _render_chords(ctx: RenderContext, roman: str) -> list[VoiceEvent]:
    patch = ctx.deck.voices["chords"]
    voicing = harmony.voice_lead(ctx.prev_voicing, ctx.scale, roman,
                                 patch.range_lo, patch.range_hi)
    ctx.prev_voicing = list(voicing)

    if ctx.section.density < 0.4:
        steps = (0,)
    elif ctx.section.density < 0.7:
        steps = (2, 10)
    else:
        steps = (2, 6, 10, 14)

    return [VoiceEvent("chords", step, tuple(voicing), VELOCITY_SOFT, 2)
            for step in steps]


def _render_pad(ctx: RenderContext, roman: str) -> list[VoiceEvent]:
    patch = ctx.deck.voices["pad"]
    voicing = harmony.voice_lead([], ctx.scale, roman,
                                 patch.range_lo, patch.range_hi)
    return [VoiceEvent("pad", 0, tuple(voicing), VELOCITY_SOFT, STEPS_PER_BAR)]


def _render_artist_pattern(ctx: RenderContext) -> list[VoiceEvent]:
    """El patron de un artista remoto, en la voz lead.

    Llega como una LISTA DE NOTAS sin ritmo: la UI de artista (web/js/
    artist-ui.js) va encolando los toques del artista, no dibuja una rejilla con
    silencios. Asi que el ritmo lo pone el motor -- una nota por corchea, que es
    lo que hacia el secuenciador viejo -- y el artista pone las alturas.

    Las notas vienen ya cuantizadas a la escala (music_engine.resolve_pattern),
    pero NO acotadas al registro: hay que plegarlas al rango de la voz o se
    saldrian del patch.
    """
    patch = ctx.deck.voices["lead"]
    pattern = [int(n) for n in (ctx.artist_pattern or ())]
    if not pattern:
        return []

    events = []
    for i, step in enumerate(range(0, STEPS_PER_BAR, 2)):
        note = M.fold_to_range(pattern[i % len(pattern)],
                               patch.range_lo, patch.range_hi)
        acento = i % len(pattern) == 0      # el patron vuelve a empezar
        events.append(VoiceEvent(
            "lead", step, (note,),
            VELOCITY_ACCENT if acento else VELOCITY_NORMAL, 2))
    return events


def _render_lead(ctx: RenderContext, roman: str) -> list[VoiceEvent]:
    """El motivo, rearmonizado al acorde del compas. Esto es el leitmotiv.

    Si hay un patron de artista, manda el artista: ver _render_artist_pattern.
    """
    if ctx.artist_pattern:
        return _render_artist_pattern(ctx)

    patch = ctx.deck.voices["lead"]
    degrees = harmony.chord_degrees(ctx.scale, roman)
    shaped = M.reharmonize(ctx.motif, degrees, _scale_size(ctx.scale))
    if ctx.section.density >= 0.9:
        shaped = M.ornament(shaped, 1)
    elif ctx.section.tempo_mode == "half":
        shaped = M.augment(shaped, 2)

    root = ctx.root + 12 * ctx.section.octave
    events = []
    for offset, note, dur, accent in M.realize(shaped, ctx.scale, root,
                                               patch.range_lo, patch.range_hi):
        if offset >= STEPS_PER_BAR:
            break
        events.append(VoiceEvent(
            "lead", offset, (note,),
            VELOCITY_ACCENT if accent else VELOCITY_NORMAL,
            min(dur, STEPS_PER_BAR - offset)))
    return events


def _render_drums(ctx: RenderContext) -> list[VoiceEvent]:
    pattern_id = ("fill" if (ctx.is_last_bar and ctx.section.fill_on_last_bar)
                  else ctx.deck.drum_patterns.get(ctx.section.name, "basico"))
    kit = DRUM_PATTERNS.get(pattern_id, DRUM_PATTERNS["basico"])

    events = []
    for name, row in kit.items():
        drum_id = DRUM_IDS.get(name)
        if drum_id is None:
            continue
        for step, char in enumerate(row[:STEPS_PER_BAR]):
            if char == "x":
                events.append(VoiceEvent("drums", step, (drum_id,),
                                         DRUM_VELOCITY.get(name, 90), 1))
    return events


def render_bar(ctx: RenderContext, bar_index: int) -> Bar:
    """Compone un compas completo. Determinista, y avanza ctx.prev_voicing."""
    roman = harmony.chord_at(ctx.progression, ctx.bar_in_section)
    events: list[VoiceEvent] = []

    if "bass" in ctx.section.voices:
        events += _render_bass(ctx, roman)
    if "chords" in ctx.section.voices:
        events += _render_chords(ctx, roman)
    if "pad" in ctx.section.voices:
        events += _render_pad(ctx, roman)
    if "lead" in ctx.section.voices:
        events += _render_lead(ctx, roman)
    events += _render_drums(ctx)

    events.sort(key=lambda e: (e.step, e.voice))
    return Bar(index=bar_index, bpm=ctx.bpm, ms=bar_ms(ctx.bpm),
               swing=ctx.deck.swing, section=ctx.section.name,
               events=tuple(events))
