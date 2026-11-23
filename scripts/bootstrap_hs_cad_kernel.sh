#!/usr/bin/env bash
set -euo pipefail
# Managed, reproducible, software-only OpenCascade/CadQuery geometry environment.
# It is installed outside the app runtime to avoid Python 3.13 OCP wheel conflicts.
VENV="${HOME}/.local/share/hardware-splicer/cad-venv"
command -v uv >/dev/null || { echo 'uv required for CAD bootstrap' >&2; exit 1; }
uv venv --python 3.12 "$VENV"
uv pip install --python "$VENV/bin/python" 'cadquery==2.8.0'
"$VENV/bin/python" -c 'import cadquery; print("HS CAD kernel ready", cadquery.__version__)'
printf 'HS CAD executable: %s\n' "$VENV/bin/python"
