#!/usr/bin/env bash
# Build an isolated source copy, then test it without touching existing servers.
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
FRONTEND="$ROOT/apps/circuit-ai/circuit-ai-frontend"
MODE=${1:-mock}
if [[ $# -gt 0 ]]; then shift; fi
if [[ "$MODE" != mock && "$MODE" != real ]]; then
  echo "Usage: bash scripts/verify_device_frontend.sh [mock|real] [spec patterns...]" >&2
  exit 2
fi

PLAYWRIGHT_ROOT=${HS_PLAYWRIGHT_ROOT:-/tmp/hs-playwright}
APP_PORT=${HS_FRONTEND_TEST_PORT:-3102}
BACKEND_PORT=${HS_BACKEND_TEST_PORT:-8102}
if [[ ! -x "$ROOT/.venv/bin/python" || ! -d "$FRONTEND/node_modules" || ! -f "$PLAYWRIGHT_ROOT/node_modules/@playwright/test/cli.js" ]]; then
  echo "Requires the repo Python environment, frontend dependencies and pinned Playwright under HS_PLAYWRIGHT_ROOT." >&2
  exit 2
fi

"$ROOT/.venv/bin/python" -c 'import socket, sys
ports = [int(value) for value in sys.argv[1:]]
if len(set(ports)) != 2 or any(port < 1024 or port > 65535 for port in ports):
    raise SystemExit("Choose two distinct unprivileged test ports.")
for port in ports:
    with socket.socket() as sock:
        # Permit TIME_WAIT from a previous test server, not an active listener.
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", port))' "$APP_PORT" "$BACKEND_PORT"

mkdir -p "$ROOT/.cache/hardware-splicer"
RUN_DIR=$(mktemp -d "$ROOT/.cache/hardware-splicer/frontend-verify-XXXXXX")
echo "Test artifacts: $RUN_DIR"
mkdir -p "$RUN_DIR/frontend"
# Do not copy credentials, the live build, or dependency caches into the snapshot.
rsync -a --exclude=node_modules --exclude=.next --exclude='.env*' --exclude='*.tsbuildinfo' "$FRONTEND/" "$RUN_DIR/frontend/"
ln -s "$FRONTEND/node_modules" "$RUN_DIR/frontend/node_modules"

backend_pid=''
frontend_pid=''
cleanup() {
  # Only processes started by this script; never kill an owner by its port.
  if [[ -n "$frontend_pid" ]]; then kill "$frontend_pid" 2>/dev/null || true; wait "$frontend_pid" 2>/dev/null || true; fi
  if [[ -n "$backend_pid" ]]; then kill "$backend_pid" 2>/dev/null || true; wait "$backend_pid" 2>/dev/null || true; fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

(cd "$RUN_DIR/frontend" && NEXT_TELEMETRY_DISABLED=1 npm run build) > "$RUN_DIR/build.log" 2>&1 || {
  tail -n 40 "$RUN_DIR/build.log"
  exit 1
}

export PYTHONPATH="$ROOT/src"
export HARDWARE_SPLICER_PROJECT_ROOT="$RUN_DIR/projects"
export HARDWARE_SPLICER_OUTPUT_ROOT="$RUN_DIR/outputs"
export HARDWARE_SPLICER_TMP_ROOT="$RUN_DIR/scratch"
export HARDWARE_SPLICER_OFFLINE_LLM=1
export HS_DEVICE_RUNTIME_ENABLED=1
if [[ "$MODE" == real ]]; then
  # A person's operator token for this run only: the registry holds its hash, the spec gets the plain value.
  export HS_E2E_OPERATOR_TOKEN="e2e-$(head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n')"
  HARDWARE_SPLICER_OPERATOR_TOKENS=$("$ROOT/.venv/bin/python" -c 'import json, os
from hardware_splicer.operator_identity import hash_operator_token
print(json.dumps({hash_operator_token(os.environ["HS_E2E_OPERATOR_TOKEN"]): {"id": "e2e-owner", "kind": "human"}}))')
  export HARDWARE_SPLICER_OPERATOR_TOKENS
fi
export HS_BACKEND_URL="http://127.0.0.1:$BACKEND_PORT"
if [[ "$MODE" == real ]]; then
  "$ROOT/.venv/bin/python" -m uvicorn hardware_splicer.product_api:create_product_app --factory --host 127.0.0.1 --port "$BACKEND_PORT" > "$RUN_DIR/backend.log" 2>&1 &
else
  "$ROOT/.venv/bin/python" -m uvicorn mock_canonical_project_studio_backend:app --app-dir "$ROOT/scripts" --host 127.0.0.1 --port "$BACKEND_PORT" > "$RUN_DIR/backend.log" 2>&1 &
fi
backend_pid=$!

wait_for() {
  local url=$1 pid=$2
  for ((attempt=0; attempt<60; attempt++)); do
    if ! kill -0 "$pid" 2>/dev/null; then echo "Test service exited; inspect $RUN_DIR." >&2; return 1; fi
    if curl -fsS -o /dev/null "$url" 2>/dev/null; then return 0; fi
    sleep 1
  done
  echo "Timed out waiting for $url; inspect $RUN_DIR." >&2
  return 1
}
wait_for "http://127.0.0.1:$BACKEND_PORT/v1/devices/examples" "$backend_pid"

(cd "$RUN_DIR/frontend" && exec env NEXT_TELEMETRY_DISABLED=1 HARDWARE_SPLICER_API_URL="http://127.0.0.1:$BACKEND_PORT" node node_modules/next/dist/bin/next start -H 127.0.0.1 -p "$APP_PORT") > "$RUN_DIR/frontend.log" 2>&1 &
frontend_pid=$!
wait_for "http://127.0.0.1:$APP_PORT/engineering/device" "$frontend_pid"

export NODE_PATH="$PLAYWRIGHT_ROOT/node_modules"
export OUTSIDER_APP_URL="http://127.0.0.1:$APP_PORT"
export HS_FRONTEND_VERIFY_DIR="$RUN_DIR"
if [[ $# -eq 0 ]]; then set -- device-assembly device-case device-engineering device-firmware device-draft device-application device-observations device-modeled-run donor-device-handoff missions; fi
node "$PLAYWRIGHT_ROOT/node_modules/@playwright/test/cli.js" test -c "$FRONTEND/playwright.device.config.cjs" "$@"
