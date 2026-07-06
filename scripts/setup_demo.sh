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
if [[ -f "$ROOT/requirements-apps-test.txt" ]]; then
  "$PIP" install -r "$ROOT/requirements-apps-test.txt"
fi

echo "==> Build compiler frontend deps (TypeScript for compile_build_graph.cjs)"
if command -v npm >/dev/null 2>&1; then
  (cd apps/circuit-ai/circuit-ai-frontend && npm install --silent)
  (cd apps/hardware-splicer-demo && npm install --silent)
  if command -v make >/dev/null 2>&1; then
    make -C "$ROOT" export-engine-pcb-data export-catalog-recipes
  else
    (cd "$ROOT" && node scripts/export_engine_pcb_data.cjs && node scripts/export_catalog_recipes.cjs)
  fi
else
  echo "WARN: npm not found — build compiler and dashboard will not work"
fi

echo "==> 3D-Splicer runtime (required for intake/compile demos with use_3d_splicer)"
SPLICER3D_VENV="$ROOT/apps/3d-splicer/.venv"
if [[ -x "$SPLICER3D_VENV/bin/python" && ! -x "$SPLICER3D_VENV/bin/pip" ]]; then
  echo "WARN: repairing broken 3d-splicer venv (python without pip)"
  rm -rf "$SPLICER3D_VENV"
fi
if [[ ! -x "$SPLICER3D_VENV/bin/python" ]]; then
  python3 -m venv "$SPLICER3D_VENV"
fi
"$SPLICER3D_VENV/bin/python" -m ensurepip --upgrade >/dev/null 2>&1 || true
"$SPLICER3D_VENV/bin/pip" install -q -U pip
# Fast path: API tests without CadQuery (optional full stack below).
"$SPLICER3D_VENV/bin/pip" install -q \
  pytest pytest-asyncio pytest-cov httpx fastapi uvicorn pydantic \
  numpy shapely jinja2 trimesh python-multipart redis
if [[ "${HARDWARE_SPLICER_SKIP_CADQUERY:-}" != "1" && -f "$ROOT/apps/3d-splicer/requirements.txt" ]]; then
  if ! "$SPLICER3D_VENV/bin/pip" install -q -r "$ROOT/apps/3d-splicer/requirements.txt"; then
    echo "WARN: CadQuery install failed — STL rendering unavailable; run: make setup-cadquery"
  fi
fi

echo "==> Doctor check"
"$PYTHON" scripts/hardware_splicer.py doctor

echo "==> Done. Activate: source $VENV/bin/activate"
echo "    Scratch output: \$HARDWARE_SPLICER_TMP_ROOT or $ROOT/.cache/hardware-splicer"
echo "    Next: make verify  OR  see docs/DEMO_10_MIN.md"
