#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

VENV="${HARDWARE_SPLICER_VENV:-$ROOT/.venv}"
PYTHON="$VENV/bin/python"
PIP="$VENV/bin/pip"

echo "==> Python venv at $VENV"
if [[ ! -x "$PYTHON" ]]; then
  python3 -m venv "$VENV"
fi
"$PIP" install --upgrade pip
"$PIP" install -r requirements.txt

echo "==> Build compiler frontend deps (TypeScript for compile_build_graph.cjs)"
if command -v npm >/dev/null 2>&1; then
  (cd apps/circuit-ai/circuit-ai-frontend && npm install --silent)
  (cd apps/hardware-splicer-demo && npm install --silent)
else
  echo "WARN: npm not found — build compiler and dashboard will not work"
fi

echo "==> Doctor check"
"$PYTHON" scripts/hardware_splicer.py doctor

echo "==> Done. Activate: source $VENV/bin/activate"
echo "    Next: make verify  OR  see docs/DEMO_10_MIN.md"
