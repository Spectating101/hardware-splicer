#!/usr/bin/env bash
# Create GitHub Release v1.0.2 with sample zip (requires: gh auth login)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
gh release create v1.0.2 \
  --repo Spectating101/hardware-splicer \
  --title "Splice Agent v1.0.2 — Internal maturity" \
  --notes-file RELEASE_NOTES_v1.0.2.md \
  releases/sample-splice-sprint-robot-repair-cafe.zip
echo "Release: https://github.com/Spectating101/hardware-splicer/releases/tag/v1.0.2"
