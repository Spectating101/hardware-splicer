#!/usr/bin/env bash
# KiCad MCP dev profile — open KiCad on a compile output, then recheck HS truth.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

usage() {
  cat <<'EOF'
KiCad MCP dev profile (v1.1 interface preview)

Usage:
  scripts/kicad_mcp_dev_profile.sh <build_dir> open
  scripts/kicad_mcp_dev_profile.sh <build_dir> recheck [--no-package] [--no-views]
  scripts/kicad_mcp_dev_profile.sh <build_dir> session

Commands:
  open     Launch KiCad on the primary .kicad_pcb in build_compilation/
  recheck  Re-run DRC/ERC, refresh DESIGN_QUALITY, optional package + PDF/SVG
  session  Print end-to-end workflow (hs-serve, KiCad, MCP, recheck)

Environment:
  HARDWARE_SPLICER_ALLOW_ARBITRARY_OUT_DIR=1  — when build_dir is outside API output root
  PYTHONPATH=src                              — set automatically for recheck

See docs/KICAD_MCP_DEV_PROFILE.md
EOF
}

BUILD_DIR="${1:-}"
CMD="${2:-}"

if [[ -z "$BUILD_DIR" || -z "$CMD" ]]; then
  usage
  exit 1
fi

BUILD_DIR="$(cd "$BUILD_DIR" && pwd)"

find_pcb() {
  PYTHONPATH=src python3 - <<'PY' "$BUILD_DIR"
import sys
from hardware_splicer.build_files import find_primary_pcb
pcb = find_primary_pcb(sys.argv[1])
if not pcb:
    raise SystemExit("no .kicad_pcb under build_compilation/")
print(pcb)
PY
}

case "$CMD" in
  open)
    PCB="$(find_pcb)"
    echo "Opening KiCad: $PCB"
    if command -v kicad >/dev/null 2>&1; then
      exec kicad "$PCB"
    elif command -v pcbnew >/dev/null 2>&1; then
      exec pcbnew "$PCB"
    else
      echo "KiCad not found on PATH (expected kicad or pcbnew)" >&2
      exit 1
    fi
    ;;
  recheck)
    shift 2
    export PYTHONPATH=src
    exec python3 scripts/recheck_build_after_kicad.py "$BUILD_DIR" "$@"
    ;;
  session)
    PCB="$(find_pcb)"
    cat <<EOF

KiCad sidecar session
─────────────────────
Build dir:  $BUILD_DIR
PCB:        $PCB

1) API (optional, for splice-ui Design tab):
   hs-serve --host 127.0.0.1 --port 8787
   make splice-ui-dev

2) Open KiCad for human edits:
   scripts/kicad_mcp_dev_profile.sh "$BUILD_DIR" open

3) Optional MCP: configure a KiCad MCP server in Cursor/Claude with cwd:
   $BUILD_DIR/build_compilation

4) After save in KiCad, refresh Hardware-Splicer truth:
   scripts/kicad_mcp_dev_profile.sh "$BUILD_DIR" recheck

   Or HTTP: POST /v1/build-files/recheck {"build_dir":"$BUILD_DIR"}

5) Review in splice-ui Design tab (KiCanvas + compile truth + fab manifest).

EOF
    ;;
  *)
    usage
    exit 1
    ;;
esac
