#!/usr/bin/env bash
# Launch prep for v1.1.0-alpha.1 — verify, build UI, print release commands.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PYTHON="${ROOT}/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON=python3
fi

echo "==> launch prep: verify-product-v1"
make verify-product-v1

echo ""
echo "==> launch prep: optional UI interface smoke (skip if API not running)"
if curl -sf http://127.0.0.1:8787/health >/dev/null 2>&1; then
  PYTHONPATH=src "$PYTHON" scripts/verify_ui_interface_smoke.py
else
  echo "    skipped — start API: make splice-ui-serve"
fi

echo ""
echo "==> launch prep: DONE"
echo ""
echo "Deploy demo:  make splice-ui-serve"
echo "Launch doc:   docs/LAUNCH_v1.1.md"
echo ""
echo "GitHub prerelease (after gh auth login):"
echo "  gh release create v1.1.0-alpha.1 \\"
echo "    --title 'v1.1.0-alpha.1 — Interface Preview' \\"
echo "    --notes-file RELEASE_NOTES_v1.1.0-alpha.1.md \\"
echo "    --prerelease"
