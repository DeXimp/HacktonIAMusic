"""Simulador de Pure Data (stdlib puro) — verificación sin audio.

Escucha OSC en :9000 (lo que Pd recibiría) y lo imprime; con --telemetry
emite /pd/state/amplitude hacia :8000 como haría el patch real.

Uso:  python scripts/test-osc.py [--telemetry]
"""
from __future__ import annotations

import argparse
import math
import socket
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bridge import osc_mini  # noqa: E402

PD_RECV = ("127.0.0.1", 9000)   # donde escucharía Pd
BRIDGE_RECV = ("127.0.0.1", 8000)  # donde escucha el bridge


def telemetry_loop() -> None:
    out = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    t0 = time.time()
    while True:
        amp = 0.4 + 0.3 * abs(math.sin((time.time() - t0) * 1.7))
        out.sendto(osc_mini.encode("/pd/state/amplitude", float(round(amp, 3))),
                   BRIDGE_RECV)
        time.sleep(0.1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--telemetry", action="store_true",
                    help="emitir /pd/state/amplitude hacia :8000")
    args = ap.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(PD_RECV)
    print(f"[test-osc] Simulador de Pd escuchando en udp://{PD_RECV[0]}:{PD_RECV[1]}"
          + (" (+telemetría)" if args.telemetry else ""))
    if args.telemetry:
        threading.Thread(target=telemetry_loop, daemon=True).start()
    try:
        while True:
            data, _ = sock.recvfrom(4096)
            stamp = time.strftime("%H:%M:%S")
            for address, oscargs in osc_mini.decode(data):
                print(f"{stamp}  {address}  {oscargs}")
    except KeyboardInterrupt:
        print("\n[test-osc] adiós")


if __name__ == "__main__":
    main()
