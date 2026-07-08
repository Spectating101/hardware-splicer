#!/usr/bin/env bash
# Track B — alpha.5 agent quickstart on alien WSL (FGEDHGV pattern).
# Run on controller: scp tarball + this script to Windows user dir, then:
#   ssh desktop-fgedhgv "wsl --distribution Ubuntu-24.04 -- bash /mnt/c/Users/user/hs_fgedhgv_track_b.sh"
#
# Or inside WSL after placing hs-alpha5.tar.gz at /mnt/c/Users/user/:
#   bash scripts/agent_quickstart_verify.sh /mnt/c/Users/user/hs-alpha5.tar.gz
set -euo pipefail

ARCHIVE="${1:-/mnt/c/Users/user/hs-alpha5.tar.gz}"
ROOT="${HS_TRACK_ROOT:-/root/hardware-splicer-alpha5}"
LOG="${HS_TRACK_LOG:-/root/hs-alpha5-quickstart.log}"
START_TS=$(date +%s)

exec > >(tee -a "$LOG") 2>&1

echo "==> Track B agent quickstart @ $(date -Is)"
echo "==> hostname: $(hostname)"
echo "==> archive: $ARCHIVE"
echo "==> root: $ROOT"

rm -rf "$ROOT"
mkdir -p "$ROOT"
tar -xzf "$ARCHIVE" -C "$ROOT"
cd "$ROOT"

export HARDWARE_SPLICER_OFFLINE_COMPOSE="${HARDWARE_SPLICER_OFFLINE_COMPOSE:-1}"
export HARDWARE_SPLICER_AUTOROUTE=0
export HARDWARE_SPLICER_ALLOW_ARBITRARY_OUT_DIR=1

echo "==> install"
bash scripts/install_splice_v1.sh

# shellcheck disable=SC1091
source .venv/bin/activate

echo "==> doctor"
hs-doctor --json | python3 -c "import json,sys; d=json.load(sys.stdin); print('doctor_ok', d.get('ok'))"

echo "==> start API"
PYTHONPATH=src python3 scripts/hardware_splicer.py serve --host 127.0.0.1 --port 8787 &
API_PID=$!
trap 'kill "$API_PID" 2>/dev/null || true' EXIT

for _ in $(seq 1 60); do
  curl -sf http://127.0.0.1:8787/health >/dev/null 2>&1 && break
  sleep 1
done

echo "==> curl 1: modules catalog"
curl -s http://127.0.0.1:8787/v1/modules/catalog | python3 -c "
import json,sys
b=json.load(sys.stdin)
print('catalog_count', b.get('count'))
assert b.get('ok') and b.get('count',0) >= 20
"

echo "==> curl 2: canvas agent loop"
curl -s -X POST http://127.0.0.1:8787/v1/compose/agent-loop \
  -H 'Content-Type: application/json' \
  -d '{
    "phrase": "Alien machine canvas agent quickstart",
    "canvas_nodes": [
      {"id": "m1", "moduleId": "esp32-devkit"},
      {"id": "m2", "moduleId": "dht22"}
    ],
    "allow_llm_first": false,
    "max_manual_retries": 2,
    "finalize_package": true,
    "project_name": "alien_track_b_canvas"
  }' | python3 -c "
import json,sys
r=json.load(sys.stdin)
al=r.get('agent_loop') or {}
print('resolved', al.get('resolved'))
print('drc_errors', al.get('final_kicad_drc_errors'))
print('copper', al.get('copper_tier'))
print('package', bool(r.get('project_package')))
print('out_dir', r.get('out_dir'))
assert al.get('resolved') is True
assert al.get('final_kicad_drc_errors') == 0
assert r.get('project_package')
"

END_TS=$(date +%s)
echo "==> PASS wall_seconds=$((END_TS - START_TS))"
kill "$API_PID" 2>/dev/null || true
