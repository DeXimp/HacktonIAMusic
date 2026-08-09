"""
ViruSynth — detiene todos los procesos lanzados por scripts\\start-all.ps1
    python scripts\\stop-all.py
    python scripts\\stop-all.py --dry-run
    python scripts\\stop-all.py --yes

Busca y mata:
  - Pure Data (pd.exe)
  - Bridge (python -m bridge.main)
  - Simulador OSC (scripts\\test-osc.py), si se usó en lugar de Pd
  - Servidor web (python -m http.server <puerto>, el que haya elegido start-all.ps1)
"""

import argparse
import json
import subprocess
import sys


def get_processes():
    """Devuelve una lista de dicts {pid, name, cmd} usando PowerShell/CIM."""
    ps_cmd = (
        "Get-CimInstance Win32_Process | "
        "Select-Object ProcessId,Name,CommandLine | ConvertTo-Json -Compress"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
        )
    except (
        subprocess.CalledProcessError,
        FileNotFoundError,
        subprocess.TimeoutExpired,
    ) as e:
        print(
            f"[error] No se pudo listar procesos via PowerShell: {e}", file=sys.stderr
        )
        return []

    raw = result.stdout.strip()
    if not raw:
        return []

    data = json.loads(raw)
    if isinstance(
        data, dict
    ):  # PowerShell devuelve un objeto suelto si solo hay 1 resultado
        data = [data]

    return [
        {
            "pid": p.get("ProcessId"),
            "name": p.get("Name") or "",
            "cmd": p.get("CommandLine") or "",
        }
        for p in data
        if p.get("ProcessId") is not None
    ]


# (etiqueta, función que decide si un proceso hace match)
MATCHERS = [
    ("Pure Data (pd.exe)", lambda p: p["name"].lower() == "pd.exe"),
    (
        "Bridge (bridge.main)",
        lambda p: "python" in p["name"].lower() and "bridge.main" in p["cmd"],
    ),
    (
        "Simulador OSC (test-osc.py)",
        lambda p: "python" in p["name"].lower() and "test-osc.py" in p["cmd"],
    ),
    (
        "Servidor web (http.server)",
        # start-all.ps1 elige el primer puerto libre a partir de 8080 (puede
        # no ser 8080 si algo mas en la maquina ya lo esta usando), asi que
        # no se puede matchear por numero de puerto -- se matchea por la
        # carpeta que sirve en su lugar.
        lambda p: (
            "python" in p["name"].lower()
            and "http.server" in p["cmd"]
            and "web" in p["cmd"]
        ),
    ),
]


def find_targets(procs):
    targets = []
    for label, match in MATCHERS:
        for p in procs:
            if match(p):
                targets.append((label, p))
    return targets


def kill_pid(pid):
    subprocess.run(
        ["taskkill", "/F", "/PID", str(pid)],
        capture_output=True,
        text=True,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Detiene los procesos de ViruSynth (Pd, bridge, web)."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Solo mostrar qué se detendría, sin matar nada",
    )
    parser.add_argument(
        "-y", "--yes", action="store_true", help="No pedir confirmación"
    )
    args = parser.parse_args()

    if sys.platform != "win32":
        print(
            "[warn] Este script está pensado para Windows (usa taskkill/PowerShell).",
            file=sys.stderr,
        )

    procs = get_processes()
    if not procs:
        print("[info] No se pudo obtener la lista de procesos, o está vacía.")
        return

    targets = find_targets(procs)
    if not targets:
        print("[info] No se encontraron procesos de ViruSynth en ejecución.")
        return

    print("Procesos encontrados:")
    for label, p in targets:
        preview = p["cmd"][:100] + ("..." if len(p["cmd"]) > 100 else "")
        print(f"  [PID {p['pid']}] {label}  ->  {preview}")

    if args.dry_run:
        print("\n(--dry-run) No se detuvo nada.")
        return

    if not args.yes:
        resp = input("\n¿Detener estos procesos? [s/N] ").strip().lower()
        if resp not in ("s", "si", "sí", "y", "yes"):
            print("Cancelado.")
            return

    seen_pids = set()
    for label, p in targets:
        pid = p["pid"]
        if pid in seen_pids:
            continue
        seen_pids.add(pid)
        print(f"[stop] Matando PID {pid} ({label})...")
        kill_pid(pid)

    print("[done] Procesos detenidos.")


if __name__ == "__main__":
    main()
