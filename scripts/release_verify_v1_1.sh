#!/usr/bin/env bash
# Release verify for v1.1.0 — run before tagging.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PYTHON="${ROOT}/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON=python3
fi

echo "==> release verify: verify-product-internal"
make verify-product-internal

echo ""
echo "==> release verify: v1.1 interface API tests"
HARDWARE_SPLICER_ALLOW_ARBITRARY_OUT_DIR=1 PYTHONPATH=src "$PYTHON" -m pytest \
  tests/test_build_files_security.py tests/test_oss_integrations_api.py tests/test_build_files_api.py -q

echo ""
echo "==> release verify: version surfaces"
VER=$("$PYTHON" -c "from hardware_splicer import _version; print(_version.__version__)")
if [[ "$VER" != "1.1.0" ]]; then
  echo "FAIL: _version.py is $VER, expected 1.1.0"
  exit 1
fi
echo "    version $VER OK"

echo ""
echo "release verify v1.1.0: PASSED"
echo "Next: sign docs/RELEASE_CHECKLIST_v1.1.md"
echo "      gh release create v1.1.0 --title 'v1.1.0' --notes-file RELEASE_NOTES_v1.1.0.md"
