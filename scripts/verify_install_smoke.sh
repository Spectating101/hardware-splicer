#!/usr/bin/env bash
# Internal install smoke — verifies slim install prerequisites without full verify-splice.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> verify_install_smoke: prerequisites"
command -v python3 >/dev/null
command -v npm >/dev/null
python3 --version
node --version

if command -v kicad-cli >/dev/null; then
  kicad-cli --version
else
  echo "WARN: kicad-cli not on PATH (required for verify-splice-v1)"
fi

echo "==> verify_install_smoke: slim install"
bash scripts/install_splice_v1.sh

VENV="${HARDWARE_SPLICER_VENV:-$ROOT/.venv}"
export PYTHONPATH="$ROOT/src"
"$VENV/bin/python" -c "from hardware_splicer import _version; print('version', _version.__version__)"
"$VENV/bin/hs-doctor" || true

echo "==> verify_install_smoke: product import"
"$VENV/bin/python" -c "from hardware_splicer.api import create_app; create_app(); print('api ok')"

echo "verify_install_smoke: passed"
