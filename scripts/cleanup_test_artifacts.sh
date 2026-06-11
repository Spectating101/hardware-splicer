#!/usr/bin/env bash
# Free scratch space from repeated verify/explore runs (safe: only Hardware-Splicer prefixes).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

clean_dir() {
  local dir="$1"
  [[ -d "$dir" ]] || return 0
  for prefix in \
    hardware_splicer_exploration \
    hardware_splicer_functional_audit \
    hardware_splicer_backend_benchmark \
    hardware_splicer_tier_scores \
    hardware_splicer_demo \
    hardware_splicer_e2e_ \
    exploration \
    functional_audit \
    backend_benchmark \
    hs_clone \
    hs_robust \
    hs_final; do
    find "$dir" -maxdepth 1 -name "${prefix}*" -exec rm -rf {} + 2>/dev/null || true
  done
}

clean_dir "/tmp"
clean_dir "${HARDWARE_SPLICER_TMP_ROOT:-$ROOT/.cache/hardware-splicer}"
echo "cleaned Hardware-Splicer artifacts under /tmp and project scratch cache"
