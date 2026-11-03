#!/usr/bin/env bash
# Actual HS-native drone product output: mechanics, topology, sourced airframe,
# BOM, OpenSCAD printable STL, and real upstream PyBullet flight animation.
# One command: bash examples/drone_lab/produce_with_hs.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CACHE="${HS_DRONE_PRODUCT_CACHE:-$HOME/.cache/hardware-splicer/hs-whoop65}"
OUTPUT="${HS_DRONE_PRODUCT_OUTPUT:-$CACHE/output/HS_WHOOP65_PRODUCT}"
UV="${UV:-$(command -v uv || true)}"
PYTHON="${HS_DRONE_PRODUCT_PYTHON:-$CACHE/.venv/bin/python}"
OPENSCAD="${HS_DRONE_OPENSCAD:-$CACHE/tools/OpenSCAD-2021.01-x86_64.AppImage}"
OPENSCAD_PIN="f758528f2cd213f773c7a105fb63bf3b45bf754b0f586fbb7c9cd653ffcd0882"
AIRFRAME_PIN="13cf8c2909de18afe5ddc95b091026e6f11f8e8a"
FLIGHT_PIN="15c426c85ac8e7a5db66d8b100f48858133357f6"
mkdir -p "$CACHE" "$CACHE/tools" "$CACHE/sources"
if [[ ! -x "$PYTHON" ]]; then
  if [[ -z "$UV" ]]; then
    echo "uv is required for an isolated Python 3.11 environment: https://docs.astral.sh/uv" >&2
    exit 2
  fi
  "$UV" venv --python 3.11 "$CACHE/.venv"
fi
if ! "$PYTHON" -c 'import pydantic, pybullet, numpy, scipy, gymnasium, transforms3d, matplotlib, PIL' >/dev/null 2>&1; then
  if [[ -z "$UV" ]]; then
    echo "uv is required to install missing simulator/CAD Python dependencies" >&2
    exit 2
  fi
  "$UV" pip install --python "$PYTHON" --no-progress \
    'pydantic>=2,<3' 'pybullet==3.2.7' 'numpy>=1.26,<2.1' \
    'scipy>=1.12' 'gymnasium>=0.29,<2' 'transforms3d>=0.4' \
    'matplotlib>=3.7' 'pillow>=10'
fi

checkout_source() {
  local name="$1" url="$2" pin="$3"
  local dir="$CACHE/sources/$name"
  if [[ ! -d "$dir/.git" ]]; then
    mkdir -p "$dir"
    git -C "$dir" init -q
    git -C "$dir" remote add origin "$url"
  fi
  local head
  head="$(git -C "$dir" rev-parse HEAD 2>/dev/null || true)"
  if [[ "$head" != "$pin" ]]; then
    git -C "$dir" fetch -q --depth 1 origin "$pin"
    git -C "$dir" checkout -q --detach FETCH_HEAD
  fi
}
checkout_source "3d-parametric-whoop" \
  "https://github.com/vsergeev/3d-parametric-whoop.git" "$AIRFRAME_PIN"
checkout_source "gym-pybullet-drones" \
  "https://github.com/learnsyslab/gym-pybullet-drones.git" "$FLIGHT_PIN"

if [[ ! -x "$OPENSCAD" ]]; then
  if [[ -n "${HS_DRONE_OPENSCAD:-}" ]]; then
    echo "Requested HS_DRONE_OPENSCAD executable does not exist: $OPENSCAD" >&2
    exit 2
  fi
  curl -fLsS --retry 2 \
    -o "$OPENSCAD" \
    "https://github.com/openscad/openscad/releases/download/openscad-2021.01/OpenSCAD-2021.01-x86_64.AppImage"
  chmod +x "$OPENSCAD"
fi
# The bundled binary is pinned; reject modified downloads.
if [[ "$OPENSCAD" == "$CACHE/tools/OpenSCAD-2021.01-x86_64.AppImage" ]]; then
  echo "$OPENSCAD_PIN  $OPENSCAD" | sha256sum --check --status || {
    echo "Refusing to run an OpenSCAD binary with an unexpected checksum." >&2
    exit 3
  }
fi

# On GitHub runners without FUSE, the AppImage extraction fallback is needed.
SCAD_BIN="$OPENSCAD"
if [[ "$OPENSCAD" == *.AppImage && "${HS_APPIMAGE_EXTRACT_AND_RUN:-0}" == "1" ]]; then
  SCAD_BIN="$CACHE/tools/openscad-headless"
  cat > "$SCAD_BIN" <<EOF
#!/usr/bin/env bash
exec "$OPENSCAD" --appimage-extract-and-run "\$@"
EOF
  chmod +x "$SCAD_BIN"
fi

export PYTHONPATH="$ROOT/src:$ROOT/apps/mecha-splicer/src${PYTHONPATH:+:$PYTHONPATH}"
exec "$PYTHON" -m hardware_splicer.drone_product_delivery \
  --build "$ROOT/examples/drone_lab/hs_whoop65_build.json" \
  --out "$OUTPUT" \
  --airframe-source "$CACHE/sources/3d-parametric-whoop" \
  --flight-source "$CACHE/sources/gym-pybullet-drones" \
  --openscad-bin "$SCAD_BIN"
