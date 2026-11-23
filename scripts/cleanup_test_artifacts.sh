#!/usr/bin/env bash
# Remove completed verification outputs from this project's configured scratch root.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
scratch="${HARDWARE_SPLICER_TMP_ROOT:-$ROOT/.cache/hardware-splicer}"
[[ -d "$scratch" ]] || exit 0
scratch="$(cd -P -- "$scratch" && pwd)"

# The runtime also accepts externally supplied scratch paths. Protect shared
# temporary roots, including aliases, before looking at any children.
for protected in / "$ROOT" "$HOME" /tmp /var/tmp /dev/shm "${TMPDIR:-/tmp}" "${TEMP:-/tmp}" "${TMP:-/tmp}"; do
  if [[ -d "$protected" && "$scratch" -ef "$protected" ]]; then
    echo "Choose a dedicated Hardware Splicer scratch directory: $scratch" >&2
    exit 1
  fi
done

clean_report() {
  local dir="$scratch/$1" report="$scratch/$1/$2"
  [[ -d "$dir" && ! -L "$dir" && -f "$report" && ! -L "$report" ]] || return 0
  if python3 - "$report" "$3" <<'PY'
import json
import sys
from pathlib import Path

try:
    report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
except (ValueError, FileNotFoundError):
    sys.exit(1)
sys.exit(0 if isinstance(report, dict) and report.get("schema_version") == sys.argv[2] else 1)
PY
  then
    rm -r -- "$dir"
    echo "Removed $dir"
  fi
}

clean_report exploration EXPLORATION_REPORT.json hardware_splicer.exploration_test.v1
clean_report functional_audit FUNCTIONAL_DELIVERY_AUDIT.json hardware_splicer.functional_delivery_audit.v1
clean_report backend_benchmark BENCHMARK_REPORT.json hardware_splicer.backend_design_benchmark.v1
clean_report tier_scores INTAKE_TIER_SCORES.json hardware_splicer.intake_tier_scores.v1
