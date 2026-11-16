#!/usr/bin/env bash
# Native Hardware Splicer prompt -> independent 65/75mm microdrone CAD,
# electronics BOM, robotic topology, and generic upstream reference flight.
# bash examples/drone_lab/produce_with_hs.sh 65
# bash examples/drone_lab/produce_with_hs.sh 75
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SIZE="${1:-65}"
if [[ "$SIZE" != "65" && "$SIZE" != "75" && "$SIZE" != "70" ]]; then
 echo "Choose a 65mm, custom 70mm, or 75mm drone profile." >&2
 exit 2
fi
CACHE="${HS_DRONE_PRODUCT_CACHE:-$HOME/.cache/hardware-splicer/hs-product}"
OUTPUT="${HS_DRONE_PRODUCT_OUTPUT:-$CACHE/output/HS_WHOOP${SIZE}_ORIGINAL}"
UV="${UV:-$(command -v uv || true)}"
PYTHON="${HS_DRONE_PRODUCT_PYTHON:-$CACHE/.venv/bin/python}"
OPENSCAD="${HS_DRONE_OPENSCAD:-$CACHE/tools/OpenSCAD-2021.01-x86_64.AppImage}"
OPENSCAD_PIN="f758528f2cd213f773c7a105fb63bf3b45bf754b0f586fbb7c9cd653ffcd0882"
FLIGHT_PIN="15c426c85ac8e7a5db66d8b100f48858133357f6"
mkdir -p "$CACHE/tools" "$CACHE/sources"
if [[ ! -x "$PYTHON" ]]; then
  [[ -n "$UV" ]] || { echo "uv is needed: https://docs.astral.sh/uv" >&2; exit 2; }
  "$UV" venv --python 3.11 "$CACHE/.venv"
fi
if ! "$PYTHON" -c 'import pydantic,pybullet,numpy,scipy,gymnasium,transforms3d,matplotlib,PIL,trimesh' >/dev/null 2>&1; then
  [[ -n "$UV" ]] || { echo "uv is required to install missing dependencies" >&2; exit 2; }
  "$UV" pip install --python "$PYTHON" --no-progress \
    'pydantic>=2,<3' 'pybullet==3.2.7' 'numpy>=1.26,<2.1' \
    'scipy>=1.12' 'gymnasium>=0.29,<2' 'transforms3d>=0.4' \
    'matplotlib>=3.7' 'pillow>=10' 'trimesh>=4.6'
fi
SIM="$CACHE/sources/gym-pybullet-drones"
if [[ ! -d "$SIM/.git" ]]; then
  mkdir -p "$SIM"
  git -C "$SIM" init -q
  git -C "$SIM" remote add origin https://github.com/learnsyslab/gym-pybullet-drones.git
fi
if [[ "$(git -C "$SIM" rev-parse HEAD 2>/dev/null || true)" != "$FLIGHT_PIN" ]]; then
  git -C "$SIM" fetch -q --depth 1 origin "$FLIGHT_PIN"
  git -C "$SIM" checkout -q --detach FETCH_HEAD
fi
if [[ ! -x "$OPENSCAD" ]]; then
  [[ -z "${HS_DRONE_OPENSCAD:-}" ]] || { echo "OpenSCAD executable absent" >&2; exit 2; }
  curl -fLsS --retry 2 -o "$OPENSCAD" \
    "https://github.com/openscad/openscad/releases/download/openscad-2021.01/OpenSCAD-2021.01-x86_64.AppImage"
  chmod +x "$OPENSCAD"
fi
if [[ "$OPENSCAD" == "$CACHE/tools/OpenSCAD-2021.01-x86_64.AppImage" ]]; then
  echo "$OPENSCAD_PIN  $OPENSCAD" | sha256sum --check --status || {
    echo "OpenSCAD AppImage checksum mismatch" >&2; exit 3;
  }
fi
SCAD="$OPENSCAD"
if [[ "$OPENSCAD" == *.AppImage && "${HS_APPIMAGE_EXTRACT_AND_RUN:-0}" == "1" ]]; then
  SCAD="$CACHE/tools/openscad-no-fuse"
  printf '#!/usr/bin/env bash\nexec "%s" --appimage-extract-and-run "$@"\n' "$OPENSCAD" > "$SCAD"
  chmod +x "$SCAD"
fi
export PYTHONPATH="$ROOT/src:$ROOT/apps/mecha-splicer/src${PYTHONPATH:+:$PYTHONPATH}"
REQUEST="$ROOT/examples/drone_lab/design_requests/hs_native_${SIZE}mm.json"
if [[ "$SIZE" == "70" ]]; then
  REQUEST="$ROOT/examples/drone_lab/design_requests/hs_native_70mm_custom.json"
fi
exec "$PYTHON" -m hardware_splicer.drone_product_delivery \
  --design-request "$REQUEST" \
  --out "$OUTPUT" \
  --flight-source "$SIM" \
  --openscad-bin "$SCAD"
