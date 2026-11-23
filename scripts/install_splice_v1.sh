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
extras=()
if [[ "${INSTALL_MCP:-1}" == "1" ]]; then
  extras+=(mcp)
fi
if [[ "${INSTALL_DEV:-0}" == "1" ]]; then
  extras+=(dev)
fi
if [[ "${INSTALL_CAD:-0}" == "1" ]]; then
  extras+=(cad)
fi
package="$ROOT"
if (( ${#extras[@]} )); then
  package="$ROOT[$(IFS=,; echo "${extras[*]}")]"
fi
"$PIP" install -r "$ROOT/requirements-splice-v1.txt" -e "$package"

# The Python board compiler reads the checked-in recipes and footprints.
if [[ "${INSTALL_CATALOG_TOOLS:-0}" == "1" ]]; then
  echo "==> Install the legacy frontend catalog tools and regenerate engine data"
  npm --prefix "$ROOT/apps/circuit-ai/circuit-ai-frontend" ci
  node scripts/export_engine_pcb_data.cjs
  node scripts/export_catalog_recipes.cjs
fi

echo "==> Doctor"
export PYTHONPATH="$ROOT/src"
"$PYTHON" scripts/hardware_splicer.py doctor || true

echo ""
echo "Done. Activate: source $VENV/bin/activate"
echo "  hs-doctor | hs-serve --port 8787 | hs-mcp"
echo "  make verify-splice-v1   # developers: INSTALL_DEV=1 before running tests"
echo "  3D CAD (STEP/STL, hinge and print studies, full test suite): rerun with INSTALL_CAD=1"
echo "  Frontend catalog maintenance: rerun with INSTALL_CATALOG_TOOLS=1 (Node and npm required)"
echo "  Gerber export and KiCad checks require kicad-cli 9+; see docs/SETUP.md"
