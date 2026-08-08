"""Smoke test de Fase 1 — verificación automatizada SIN Pd y SIN hardware.

Hace de Pd (escucha UDP :9000), arranca el bridge en modo mock y comprueba que
llegan triggers de nota y parámetros continuos. Exit code 0 = PASS.

Uso:  python scripts/smoke_test.py
"""
from __future__ import annotations

import socket
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from bridge import osc_mini  # noqa: E402

CAPTURE_S = 9.0
EXPECTED = {
    "/pd/trigger/note": 6,     # secuenciador (corcheas) + FSR mock
    "/pd/set/cutoff": 1,       # accel X -> filtro
    "/pd/set/volume": 1,       # potenciómetro
}


def main() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(0.25)
    try:
        sock.bind(("127.0.0.1", 9000))
    except OSError:
        print("FAIL: el puerto 9000 está ocupado (¿Pd o test-osc abiertos?)")
        return 2

    print("[smoke] Arrancando bridge --mock-sensors --no-portal --no-ai ...")
    proc = subprocess.Popen(
        [sys.executable, "-m", "bridge.main", "--mock-sensors",
         "--no-portal", "--no-ai", "--log-level", "WARNING"],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    counts: Counter[str] = Counter()
    deadline = time.time() + CAPTURE_S
    try:
        while time.time() < deadline:
            if proc.poll() is not None:
                print("FAIL: el bridge terminó antes de tiempo. Salida:")
                print(proc.stdout.read() if proc.stdout else "")
                return 1
            try:
                data, _ = sock.recvfrom(4096)
            except socket.timeout:
                continue
            for address, _args in osc_mini.decode(data):
                counts[address] += 1
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        sock.close()

    print(f"[smoke] Mensajes OSC capturados en {CAPTURE_S:.0f}s:")
    for address, n in sorted(counts.items()):
        print(f"    {address:<24} x{n}")

    failures = [f"{addr} (esperado>={need}, visto={counts.get(addr, 0)})"
                for addr, need in EXPECTED.items() if counts.get(addr, 0) < need]
    if failures:
        print("FAIL: " + "; ".join(failures))
        return 1
    print("PASS: Fase 1 verificada (mock -> bridge -> OSC hacia Pd)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
