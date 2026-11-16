#!/usr/bin/env bash
# HS Microdrone Lab — actual upstream Crazyflie + PyBullet, never mock flight.
# Usage: bash examples/drone_lab/launch_drone_lab.sh serve
#        bash examples/drone_lab/launch_drone_lab.sh demo
set -euo pipefail

MODE="${1:-serve}"
if [[ "$MODE" != "demo" && "$MODE" != "serve" ]]; then
  echo "Usage: $0 [serve|demo]" >&2
  exit 2
fi

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}" )" && pwd)"
WORK="${HS_DRONE_LAB_HOME:-$HOME/.cache/hs-drone-lab}"
PIN="15c426c85ac8e7a5db66d8b100f48858133357f6"
ENGINE="$WORK/gym-pybullet-drones"
VENV="$WORK/.venv311"
UV="${UV:-$(command -v uv || true)}"
if [[ -z "$UV" ]]; then
  echo "Need uv (https://docs.astral.sh/uv/) for isolated Python 3.11 dependencies. No system packages will be modified." >&2
  exit 1
fi
mkdir -p "$WORK"
if [[ ! -d "$ENGINE/.git" ]]; then
  git clone --filter=blob:none --no-checkout https://github.com/learnsyslab/gym-pybullet-drones.git "$ENGINE"
fi
if [[ "$(git -C "$ENGINE" rev-parse HEAD 2>/dev/null || true)" != "$PIN" ]]; then
  git -C "$ENGINE" fetch --depth 1 origin "$PIN"
  git -C "$ENGINE" checkout --detach "$PIN"
fi
if [[ ! -x "$VENV/bin/python" ]]; then
  "$UV" venv --python 3.11 "$VENV"
fi
if ! "$VENV/bin/python" -c 'import numpy, pybullet, gymnasium, scipy, transforms3d, matplotlib, PIL' 2>/dev/null; then
  "$UV" pip install --python "$VENV/bin/python" \
    'pybullet==3.2.7' 'numpy>=1.26,<2.1' 'scipy>=1.12' \
    'gymnasium>=0.29,<2' 'transforms3d>=0.4' 'matplotlib>=3.7' 'pillow>=10'
fi
# Import upstream source directly; no unsupported package fork, no imitation physics.
export PYTHONPATH="$ENGINE${PYTHONPATH:+:$PYTHONPATH}"
if [[ "$MODE" == "serve" ]]; then
  exec "$VENV/bin/python" "$SCRIPT_DIR/flight_lab.py" \
    --mode serve --host 127.0.0.1 --port "${HS_DRONE_LAB_PORT:-8765}"
else
  exec "$VENV/bin/python" "$SCRIPT_DIR/flight_lab.py" \
    --mode demo --out "$WORK/results"
fi
