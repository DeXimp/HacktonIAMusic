"""Prueba Pd EN SOLITARIO (sin bridge): envía OSC musical directo a :9000.

Útil para validar el patch main.pd con audio: arpegio en La menor pentatónica,
barrido de cutoff y FX suaves. stdlib puro.

Uso:  python scripts/mock-sensors.py
"""
from __future__ import annotations

import math
import random
import socket
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bridge import osc_mini  # noqa: E402

PD = ("127.0.0.1", 9000)
AM_PENT = [45, 48, 50, 52, 55, 57, 60, 62, 64, 67, 69]


def main() -> None:
    out = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def send(addr, *args):
        out.sendto(osc_mini.encode(addr, *args), PD)

    print(f"[mock-sensors] Tocando hacia udp://{PD[0]}:{PD[1]} (Ctrl+C para salir)")
    send("/pd/set/volume", 0.8)
    send("/pd/set/fx/reverb", 0.35)
    send("/pd/set/fx/delay", 0.25)
    send("/pd/set/fx/distortion", 0.05)
    t0, step = time.time(), 0
    try:
        while True:
            t = time.time() - t0
            note = AM_PENT[(step * 3) % len(AM_PENT)]
            velocity = 85 if step % 4 == 0 else random.randint(50, 70)
            send("/pd/trigger/note", note, velocity)
            cutoff = 300.0 * (4000.0 / 300.0) ** ((math.sin(t * 0.25) + 1) / 2)
            send("/pd/set/cutoff", float(round(cutoff, 1)))
            step += 1
            time.sleep(60.0 / 112 / 2)   # corcheas a 112 BPM
    except KeyboardInterrupt:
        print("\n[mock-sensors] adiós")


if __name__ == "__main__":
    main()
