"""Escritura de Standard MIDI Files con stdlib pura.

Para que existe: permite ESCUCHAR lo que compone el motor sin levantar Pd, el
bridge ni el navegador. Es la herramienta con la que se afina el estilo, y la
base del futuro "descarga el tema que compusimos entre todos".

Formato 1 (varias pistas sincronizadas), una pista por voz. La bateria va al
canal 10 del protocolo (indice 9), que es el canal percusivo de General MIDI.

El swing se aplica aca tambien, no solo en el secuenciador: si el archivo
saliera recto, afinar el estilo de oido sobre el MIDI seria afinar otra cosa que
la que suena en vivo. swing_fraction() es la misma formula que
sequencer.swing_offset_ms, expresada como fraccion de paso, y hay un test que
compara las dos para que no se separen.
"""
from __future__ import annotations

import struct
from typing import Sequence

from .render import Bar, STEPS_PER_BAR

CHANNELS = {"lead": 0, "bass": 1, "chords": 2, "pad": 3, "drums": 9}
GM_DRUMS = {0: 36, 1: 38, 2: 42}      # bombo, caja, hat cerrado
DEFAULT_TPQ = 480


def varint(value: int) -> bytes:
    """Delta-time de MIDI: 7 bits por byte, el bit alto marca continuacion."""
    value = max(0, int(value))
    out = bytearray([value & 0x7F])
    value >>= 7
    while value:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    return bytes(reversed(out))


def swing_fraction(step: int, swing: float) -> float:
    """Cuanto se corre un paso, como fraccion de la duracion de un paso.

    Misma formula que sequencer.swing_offset_ms (que devuelve milisegundos):
    solo los pasos impares se retrasan, y nunca alcanzan al paso siguiente.
    """
    if step % 2 == 0 or swing <= 0.0:
        return 0.0
    return min(0.66, max(0.0, swing)) / 3.0


def _track(events: list[tuple[int, bytes]]) -> bytes:
    """events: (tick_absoluto, payload). Devuelve un chunk MTrk completo."""
    events.sort(key=lambda e: e[0])
    body = bytearray()
    last = 0
    for tick, payload in events:
        body += varint(tick - last) + payload
        last = tick
    body += varint(0) + b"\xff\x2f\x00"          # end of track
    return b"MTrk" + struct.pack(">I", len(body)) + bytes(body)


def bars_to_midi(bars: Sequence[Bar], ticks_per_quarter: int = DEFAULT_TPQ) -> bytes:
    """Convierte compases renderizados en un archivo MIDI formato 1."""
    ticks_per_step = ticks_per_quarter // 4
    per_voice: dict[str, list[tuple[int, bytes]]] = {}
    tempo_events: list[tuple[int, bytes]] = []

    last_bpm = None
    for bar_number, bar in enumerate(bars):
        bar_tick = bar_number * STEPS_PER_BAR * ticks_per_step
        if bar.bpm != last_bpm:
            us_per_quarter = int(60_000_000 / max(1, bar.bpm))
            tempo_events.append((bar_tick, b"\xff\x51\x03"
                                 + us_per_quarter.to_bytes(3, "big")))
            last_bpm = bar.bpm
        for event in bar.events:
            channel = CHANNELS.get(event.voice, 0)
            # El corrimiento del swing se aplica al encendido Y al apagado, para
            # que la nota se mueva entera en vez de acortarse.
            offset = round(swing_fraction(event.step, bar.swing)
                           * ticks_per_step)
            start = bar_tick + event.step * ticks_per_step + offset
            end = start + max(1, event.dur_steps) * ticks_per_step
            track = per_voice.setdefault(event.voice, [])
            for raw in event.notes:
                note = GM_DRUMS.get(int(raw), 36) if event.voice == "drums" else int(raw)
                note = max(0, min(127, note))
                velocity = max(1, min(127, int(event.velocity)))
                track.append((start, bytes([0x90 | channel, note, velocity])))
                track.append((end, bytes([0x80 | channel, note, 0])))

    tracks = [_track(tempo_events)]
    for voice in ("lead", "bass", "chords", "pad", "drums"):
        if voice in per_voice:
            tracks.append(_track(per_voice[voice]))

    header = b"MThd" + struct.pack(">IHHH", 6, 1, len(tracks), ticks_per_quarter)
    return header + b"".join(tracks)
