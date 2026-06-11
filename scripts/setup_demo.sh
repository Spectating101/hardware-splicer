#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> Installing Python dependencies"
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt

echo "==> Doctor check"
python3 scripts/hardware_splicer.py doctor

echo "==> Dashboard dependencies (optional)"
if command -v npm >/dev/null 2>&1; then
  (cd apps/hardware-splicer-demo && npm install)
else
  echo "npm not found — skip dashboard install"
fi

echo "==> Done. Next: make verify  OR  see docs/DEMO_10_MIN.md"
