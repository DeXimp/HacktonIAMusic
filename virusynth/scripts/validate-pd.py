"""Valida el grafo de un patch .pd (formato de texto de Pure Data).

Comprueba que cada `#X connect origen _ destino _` referencia índices de objeto
existentes en su canvas (el error clásico al escribir patches a mano). No
sustituye a abrir el patch en Pd, pero caza los fallos estructurales.

Uso:  python scripts/validate-pd.py pd-patches/main.pd
"""
from __future__ import annotations

import sys
from pathlib import Path


def logical_records(text: str) -> list[str]:
    """Une líneas físicas en registros terminados por ';' (no escapado)."""
    records, buf, escaped = [], [], False
    for ch in text:
        if escaped:
            buf.append(ch)
            escaped = False
        elif ch == "\\":
            buf.append(ch)
            escaped = True
        elif ch == ";":
            records.append("".join(buf).strip().replace("\n", " "))
            buf = []
        else:
            buf.append(ch)
    return [r for r in records if r]


def validate(path: Path) -> int:
    records = logical_records(path.read_text(encoding="utf-8", errors="replace"))
    # pila de canvases: cada nivel = {"n": nº objetos, "connects": [(a,b,rec)]}
    stack: list[dict] = []
    errors: list[str] = []
    total_objects = 0

    def close_canvas() -> dict:
        cv = stack.pop()
        for a, b, rec in cv["connects"]:
            if a >= cv["n"] or b >= cv["n"]:
                errors.append(f"connect fuera de rango (objetos={cv['n']}): {rec}")
        return cv

    for rec in records:
        parts = rec.split()
        if not parts:
            continue
        if parts[0] == "#N" and parts[1] == "canvas":
            stack.append({"n": 0, "connects": []})
        elif parts[0] == "#X" and parts[1] == "restore":
            if len(stack) < 2:
                errors.append(f"restore sin subcanvas abierto: {rec}")
                continue
            close_canvas()
            stack[-1]["n"] += 1          # el subpatch es un objeto del padre
            total_objects += 1
        elif parts[0] == "#X" and parts[1] == "connect":
            try:
                a, b = int(parts[2]), int(parts[4])
            except (IndexError, ValueError):
                errors.append(f"connect malformado: {rec}")
                continue
            stack[-1]["connects"].append((a, b, rec))
        elif parts[0] == "#X" and parts[1] == "coords":
            pass
        elif parts[0] == "#X":
            stack[-1]["n"] += 1
            total_objects += 1
        elif parts[0] == "#A":
            pass

    while stack:                          # cierra el canvas raíz
        close_canvas()

    if errors:
        print(f"FAIL {path.name}:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"PASS {path.name}: {total_objects} objetos, grafo consistente")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python scripts/validate-pd.py <patch.pd> [...]")
        raise SystemExit(2)
    raise SystemExit(max(validate(Path(p)) for p in sys.argv[1:]))
