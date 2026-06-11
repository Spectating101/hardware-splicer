#!/usr/bin/env bash
# Run full Hardware-Splicer verification on a cluster node with large scratch.
# Usage (on cluster):
#   export HARDWARE_SPLICER_TMP_ROOT=/scratch/$USER/hardware-splicer
#   bash scripts/cluster_verify.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

export HARDWARE_SPLICER_TMP_ROOT="${HARDWARE_SPLICER_TMP_ROOT:-$ROOT/.cache/hardware-splicer}"
export HARDWARE_SPLICER_SKIP_VISION_LIVE="${HARDWARE_SPLICER_SKIP_VISION_LIVE:-1}"

echo "==> scratch: $HARDWARE_SPLICER_TMP_ROOT"
mkdir -p "$HARDWARE_SPLICER_TMP_ROOT"

if [[ ! -x .venv/bin/python ]]; then
  bash scripts/setup_demo.sh
fi
# shellcheck disable=SC1091
source .venv/bin/activate

bash scripts/cleanup_test_artifacts.sh
make verify
make explore
make test-apps

if [[ "${HARDWARE_SPLICER_RUN_VISION_LIVE:-}" == "1" ]]; then
  echo "==> optional live vision probe"
  pytest tests/test_vision_live_optional.py -q
fi

if [[ "${HARDWARE_SPLICER_CLUSTER_FULL_APPS:-}" == "1" ]]; then
  echo "==> full circuit-ai suite (slow)"
  make test-apps-full
fi

echo "cluster_verify: all requested checks passed"
