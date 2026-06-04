#!/usr/bin/env bash
set -euo pipefail

# Installs Python runtime deps and prints optional system deps for richer rendering.
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt

echo ""
echo "Runtime setup complete."
echo "Optional system dependencies for full local capabilities:"
echo "  - openscad (for SCAD->STL without docker)"
echo "  - kicad-cli (for real PCB export/check workflows on Circuit-AI side)"
