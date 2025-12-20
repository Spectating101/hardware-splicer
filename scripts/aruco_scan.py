#!/usr/bin/env python3
"""
Scan an image for ArUco markers to help bench/robot calibration.
Outputs JSON with marker IDs and pixel coordinates.
Usage:
  python scripts/aruco_scan.py --image path/to/photo.jpg --dict DICT_4X4_50
"""
import argparse
import json
import os
import sys

import cv2

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "src")
for path in (ROOT, SRC):
    if path not in sys.path:
        sys.path.insert(0, path)

from vision.aruco_locator import detect_markers  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True, help="Path to image with ArUco markers")
    ap.add_argument("--dict", default="DICT_4X4_50", help="ArUco dictionary name (e.g., DICT_4X4_50)")
    ap.add_argument("--output", default="aruco_markers.json", help="Where to write marker JSON")
    args = ap.parse_args()

    img = cv2.imread(args.image)
    if img is None:
        raise SystemExit(f"Failed to read image: {args.image}")

    markers = detect_markers(img, dictionary=args.dict)
    data = [
        {"id": m.marker_id, "center": {"x": m.center[0], "y": m.center[1]}, "corners": m.corners}
        for m in markers
    ]
    with open(args.output, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Detected {len(markers)} markers -> {args.output}")


if __name__ == "__main__":
    main()
