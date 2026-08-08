#!/usr/bin/env bash
# ViruSynth — arranque todo-en-uno (macOS / Linux)
#   ./scripts/start-all.sh [--no-pd] [--no-ai] [--serial-port /dev/ttyUSB0]
set -euo pipefail
cd "$(dirname "$0")/.."

NO_PD=0; BRIDGE_ARGS=(-m bridge.main); SERIAL=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-pd) NO_PD=1 ;;
    --no-ai) BRIDGE_ARGS+=(--no-ai) ;;
    --serial-port) SERIAL="$2"; shift ;;
  esac
  shift
done
if [[ -n "$SERIAL" ]]; then BRIDGE_ARGS+=(--serial-port "$SERIAL")
else BRIDGE_ARGS+=(--mock-sensors); fi

PY=.venv/bin/python
if [[ ! -x "$PY" ]]; then
  echo "[setup] Creando venv e instalando dependencias..."
  python3 -m venv .venv
  "$PY" -m pip install --quiet -r bridge/requirements.txt
fi

if [[ "$NO_PD" -eq 0 ]]; then
  if command -v pd >/dev/null 2>&1; then
    echo "[pd] Abriendo main.pd"
    pd -open pd-patches/main.pd &
  else
    echo "[pd] Pure Data no encontrado; arrancando el simulador test-osc.py"
    "$PY" scripts/test-osc.py --telemetry &
  fi
fi

echo "[bridge] python ${BRIDGE_ARGS[*]}"
"$PY" "${BRIDGE_ARGS[@]}" &

echo "[web] http://localhost:8080"
"$PY" -m http.server 8080 -d web &

trap 'kill 0' EXIT
echo
echo "Audiencia:  http://<IP-de-esta-máquina>:8080/?role=audience"
echo "Artistas:   http://<IP>:8080/?role=artist   ·   Proyector: /?role=stage"
wait
