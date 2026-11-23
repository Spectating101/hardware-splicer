#!/usr/bin/env bash
# Internal install smoke — verifies slim install prerequisites without full verify-splice.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> verify_install_smoke: prerequisites"
command -v python3 >/dev/null
python3 --version

if command -v kicad-cli >/dev/null; then
  kicad-cli --version
else
  echo "WARN: kicad-cli not on PATH (required for verify-splice-v1)"
fi

echo "==> verify_install_smoke: slim install"
bash scripts/install_splice_v1.sh

VENV="${HARDWARE_SPLICER_VENV:-$ROOT/.venv}"
"$VENV/bin/python" -m pip check

state="$(mktemp -d)"
trap 'rm -rf -- "$state"' EXIT
export HARDWARE_SPLICER_STATE_DIR="$state"
export HARDWARE_SPLICER_PROJECT_ROOT="$state/projects"
export HARDWARE_SPLICER_OUTPUT_ROOT="$state/builds"
export HARDWARE_SPLICER_TMP_ROOT="$state/scratch"
export HARDWARE_SPLICER_JOB_WORKERS=0 HARDWARE_SPLICER_JLC_ENRICH=0 HARDWARE_SPLICER_AUTOROUTE=0
echo "==> verify_install_smoke: deployed API, registered sources and board compile"
"$VENV/bin/python" - <<'PY'
from os import environ
from pathlib import Path

from fastapi.testclient import TestClient
from hardware_splicer import compile_catalog_build
from hardware_splicer.product_api import app

with TestClient(app) as client:
    health = client.get("/health")
    health.raise_for_status()
    assert health.json()["ok"], health.text
    digital = client.get("/v1/digital/cases")
    digital.raise_for_status()
    cases = digital.json()["cases"]
    assert cases and all(case["source_inputs_available"] for case in cases), cases

board = compile_catalog_build("automatic_plant_watering", Path(environ["HARDWARE_SPLICER_OUTPUT_ROOT"]), export_gerber=False)
assert board.design_quality["build_graph_compiled"], board.design_quality
assert board.kicad_pcb_file and Path(board.kicad_pcb_file).is_file()
print(f"{len(cases)} registered cases, PCB generated")
PY

echo "verify_install_smoke: passed"
