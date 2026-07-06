#!/usr/bin/env bash
# Splice Agent v1.0 slim install — see docs/PACKAGING_AND_DEPLOYMENT.md
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

VENV="${HARDWARE_SPLICER_VENV:-$ROOT/.venv}"
PYTHON="$VENV/bin/python"
PIP="$VENV/bin/pip"

echo "==> Splice v1 slim install at $ROOT"
echo "==> Python venv: $VENV"
if [[ ! -x "$PYTHON" ]]; then
  python3 -m venv "$VENV"
fi
"$PIP" install --upgrade pip wheel
"$PIP" install -r "$ROOT/requirements-splice-v1.txt"
"$PIP" install -e "$ROOT"
if [[ "${INSTALL_MCP:-1}" == "1" ]]; then
  "$PIP" install -e "$ROOT[mcp]"
fi
if [[ "${INSTALL_DEV:-0}" == "1" ]]; then
  "$PIP" install -e "$ROOT[dev]"
fi

echo "==> KiCad build compiler (Node) — required for compile"
if command -v npm >/dev/null 2>&1; then
  (cd "$ROOT/apps/circuit-ai/circuit-ai-frontend" && npm install --silent)
  if command -v make >/dev/null 2>&1; then
    make -C "$ROOT" export-engine-pcb-data export-catalog-recipes
  else
    (cd "$ROOT" && node scripts/export_engine_pcb_data.cjs && node scripts/export_catalog_recipes.cjs)
  fi
else
  echo "WARN: npm not found — KiCad graph compile will fail until Node 18+ is installed"
fi

echo "==> Doctor"
export PYTHONPATH="$ROOT/src"
"$PYTHON" scripts/hardware_splicer.py doctor || true

echo ""
echo "Done. Activate: source $VENV/bin/activate"
echo "  hs-doctor | hs-serve --port 8787 | hs-mcp"
echo "  make verify-splice-v1   # developers: INSTALL_DEV=1 before running tests"
echo "Prerequisites: kicad-cli 9+, Node 18+ — see docs/SETUP.md"
