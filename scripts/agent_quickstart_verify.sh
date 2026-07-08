#!/usr/bin/env bash
# Agent quickstart verify — catalog, sync agent-loop, async job; optional Qwen.
#
# Alien (FGEDHGV):
#   bash scripts/deploy_alien_quickstart.sh v1.1.0-alpha.11
#
# Local:
#   bash scripts/agent_quickstart_verify.sh
#   HS_QUICKSTART_FRESH=0 bash scripts/agent_quickstart_verify.sh  # reuse ROOT
set -euo pipefail

ARCHIVE="${1:-}"
ROOT="${HS_TRACK_ROOT:-/root/hardware-splicer-alpha5}"
LOG="${HS_TRACK_LOG:-/root/hs-alpha5-quickstart.log}"
PORT="${HS_QUICKSTART_PORT:-8787}"
START_TS=$(date +%s)

exec > >(tee -a "$LOG") 2>&1

echo "==> agent quickstart verify @ $(date -Is)"
echo "==> hostname: $(hostname)"
echo "==> root: $ROOT"

if [[ -n "$ARCHIVE" ]]; then
  echo "==> extract $ARCHIVE"
  rm -rf "$ROOT"
  mkdir -p "$ROOT"
  tar -xzf "$ARCHIVE" -C "$ROOT"
elif [[ "${HS_QUICKSTART_FRESH:-1}" == "1" ]] || [[ ! -d "$ROOT/.venv" ]]; then
  echo "ERROR: set ARCHIVE path or HS_QUICKSTART_FRESH=0 with existing ROOT"
  exit 1
fi

cd "$ROOT"

export HARDWARE_SPLICER_OFFLINE_COMPOSE="${HARDWARE_SPLICER_OFFLINE_COMPOSE:-1}"
export HARDWARE_SPLICER_OFFLINE_SALVAGE="${HARDWARE_SPLICER_OFFLINE_SALVAGE:-1}"
export HARDWARE_SPLICER_SALVAGE_RESOLVE="${HARDWARE_SPLICER_SALVAGE_RESOLVE:-heuristic}"
export HARDWARE_SPLICER_DRC_FIX_LOOP="${HARDWARE_SPLICER_DRC_FIX_LOOP:-1}"
export HARDWARE_SPLICER_AUTOROUTE=0
export HARDWARE_SPLICER_ALLOW_ARBITRARY_OUT_DIR=1

if [[ ! -x .venv/bin/python ]]; then
  echo "==> install"
  bash scripts/install_splice_v1.sh
fi

# shellcheck disable=SC1091
source .venv/bin/activate

if [[ -f "$ROOT/.env.local" ]] && [[ "${HS_QUICKSTART_QWEN:-0}" == "1" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ROOT/.env.local"
  set +a
  export HARDWARE_SPLICER_OFFLINE_COMPOSE=0
  export HARDWARE_SPLICER_QWEN_COMPOSE=1
fi

echo "==> doctor"
hs-doctor --json | python3 -c "import json,sys; d=json.load(sys.stdin); print('doctor_ok', d.get('ok'))"

echo "==> start API :$PORT"
PYTHONPATH=src python3 scripts/hardware_splicer.py serve --host 127.0.0.1 --port "$PORT" &
API_PID=$!
trap 'kill "$API_PID" 2>/dev/null || true' EXIT

for _ in $(seq 1 60); do
  curl -sf "http://127.0.0.1:$PORT/health" >/dev/null 2>&1 && break
  sleep 1
done

BASE="http://127.0.0.1:$PORT"

echo "==> step 1: modules catalog"
curl -s "$BASE/v1/modules/catalog" | python3 -c "
import json,sys
b=json.load(sys.stdin)
print('catalog_count', b.get('count'))
assert b.get('ok') and b.get('count',0) >= 50
"

echo "==> step 2: sync canvas agent-loop"
curl -s -X POST "$BASE/v1/compose/agent-loop" \
  -H 'Content-Type: application/json' \
  -d '{
    "phrase": "Agent quickstart canvas verify",
    "canvas_nodes": [
      {"id": "m1", "moduleId": "esp32-devkit"},
      {"id": "m2", "moduleId": "dht22"}
    ],
    "allow_llm_first": false,
    "max_manual_retries": 2,
    "finalize_package": true,
    "project_name": "quickstart_canvas"
  }' | python3 -c "
import json,sys
r=json.load(sys.stdin)
al=r.get('agent_loop') or {}
print('sync_resolved', al.get('resolved'), 'drc', al.get('final_kicad_drc_errors'))
assert al.get('resolved') and al.get('final_kicad_drc_errors') == 0
assert r.get('project_package')
"

echo "==> step 3: async compose-agent-loop job"
JOB=$(curl -s -X POST "$BASE/v1/jobs/compose-agent-loop" \
  -H 'Content-Type: application/json' \
  -d '{
    "phrase": "Agent quickstart async job",
    "canvas_nodes": [
      {"id": "m1", "moduleId": "esp32-devkit"},
      {"id": "m2", "moduleId": "dht22"}
    ],
    "allow_llm_first": false,
    "max_manual_retries": 1,
    "finalize_package": true,
    "project_name": "quickstart_async"
  }')
JOB_ID=$(echo "$JOB" | python3 -c "import json,sys; print(json.load(sys.stdin)['job_id'])")
for _ in $(seq 1 120); do
  STATUS=$(curl -s "$BASE/v1/jobs/$JOB_ID" | python3 -c "import json,sys; print(json.load(sys.stdin).get('status'))")
  [[ "$STATUS" == "succeeded" || "$STATUS" == "failed" ]] && break
  sleep 1
done
curl -s "$BASE/v1/jobs/$JOB_ID/result" | python3 -c "
import json,sys
p=json.load(sys.stdin)
assert p.get('ok'), p
body=p.get('result') or {}
al=body.get('agent_loop') or {}
print('async_resolved', al.get('resolved'), 'drc', al.get('final_kicad_drc_errors'))
assert al.get('resolved') and al.get('final_kicad_drc_errors') == 0
assert body.get('project_package')
"

echo "==> step 4: salvage donor_context agent-loop"
SALVAGE_PAYLOAD=$(PYTHONPATH=src python3 scripts/salvage_agent_loop_payload.py)
curl -s -X POST "$BASE/v1/compose/agent-loop" \
  -H 'Content-Type: application/json' \
  -d "$SALVAGE_PAYLOAD" | python3 -c "
import json,sys
r=json.load(sys.stdin)
al=r.get('agent_loop') or {}
print('salvage_mode', r.get('mode'), 'build_id', r.get('build_id'))
print('salvage_resolved', al.get('resolved'), 'drc', al.get('final_kicad_drc_errors'))
assert r.get('mode') == 'salvage_catalog', r.get('mode')
assert r.get('build_id') == 'robot_drive_base', r.get('build_id')
assert r.get('salvage_package')
assert al.get('resolved') and al.get('final_kicad_drc_errors') == 0
assert r.get('project_package')
"

echo "==> step 5: compose+bench loop (salvage, simulated)"
BENCH_PAYLOAD=$(PYTHONPATH=src python3 scripts/salvage_agent_loop_payload.py | python3 -c "import json,sys; p=json.load(sys.stdin); p['simulate_bench']=True; print(json.dumps(p))")
curl -s -X POST "$BASE/v1/compose/bench-loop" \
  -H 'Content-Type: application/json' \
  -d "$BENCH_PAYLOAD" | python3 -c "
import json,sys
r=json.load(sys.stdin)
bl=r.get('bench_loop') or {}
al=r.get('agent_loop') or {}
print('bench_loop_passed', bl.get('passed'), 'power_on', (r.get('bench_session') or {}).get('power_on_authorized'))
assert al.get('final_kicad_drc_errors') == 0
assert bl.get('submitted_capture') is True
assert (r.get('bench_session') or {}).get('power_on_authorized') is True
assert bl.get('passed') is True
assert r.get('project_package')
"

if [[ "${HS_QUICKSTART_QWEN:-0}" == "1" ]]; then
  echo "==> step 6: Qwen phrase agent-loop"
  curl -s -X POST "$BASE/v1/compose/agent-loop" \
    -H 'Content-Type: application/json' \
    -d '{
      "phrase": "ESP32 soil moisture logger with OLED",
      "allow_llm_first": true,
      "max_manual_retries": 1,
      "finalize_package": true,
      "project_name": "quickstart_qwen"
    }' | python3 -c "
import json,sys
r=json.load(sys.stdin)
al=r.get('agent_loop') or {}
print('qwen_resolved', al.get('resolved'), 'tokens', (r.get('qwen_usage') or {}).get('total_tokens'))
assert al.get('resolved') and al.get('final_kicad_drc_errors') == 0
assert r.get('project_package')
"
fi

END_TS=$(date +%s)
echo "==> PASS wall_seconds=$((END_TS - START_TS))"
kill "$API_PID" 2>/dev/null || true
