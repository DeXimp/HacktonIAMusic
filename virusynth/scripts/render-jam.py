"""Renderiza N compases del motor a un Standard MIDI File.

Sirve para afinar el estilo de oido sin levantar Pd, el bridge ni el navegador.

Uso:
  .venv\\Scripts\\python scripts/render-jam.py --bars 16 --out jam.mid
  .venv\\Scripts\\python scripts/render-jam.py --style arcade --scale C_major
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bridge import midi, style          # noqa: E402
from bridge.sequencer import Sequencer  # noqa: E402
from bridge.state import GlobalState    # noqa: E402


class _SilentPd:
    """El renderizado offline no manda nada a Pd."""

    def trigger_note(self, note: int, velocity: int) -> None:
        pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="render-jam", description="Renderiza la jam a un archivo MIDI")
    parser.add_argument("--bars", type=int, default=16, help="compases (default 16)")
    parser.add_argument("--style", default=style.DEFAULT_STYLE_ID,
                        choices=sorted(style.STYLES), help="estilo del preset")
    parser.add_argument("--scale", default="", help="escala (default: la del estilo)")
    parser.add_argument("--bpm", type=int, default=0, help="BPM (default: el del estilo)")
    parser.add_argument("--out", default="jam.mid", help="archivo de salida")
    args = parser.parse_args(argv)

    deck = style.get_style(args.style)
    state = GlobalState()
    state.jam.scale = args.scale or deck.scales[0]
    state.jam.bpm = args.bpm or deck.default_bpm

    sequencer = Sequencer(state, _SilentPd(), style_id=args.style)
    bars = [sequencer.next_bar() for _ in range(max(1, args.bars))]

    out = Path(args.out)
    out.write_bytes(midi.bars_to_midi(bars))
    total = sum(len(b.events) for b in bars)
    secciones = []
    for bar in bars:
        if not secciones or secciones[-1] != bar.section:
            secciones.append(bar.section)
    print(f"{out}: {len(bars)} compases, {total} eventos, "
          f"estilo {deck.name}, escala {state.jam.scale}, {state.jam.bpm} BPM")
    print("secciones: " + " -> ".join(secciones))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
