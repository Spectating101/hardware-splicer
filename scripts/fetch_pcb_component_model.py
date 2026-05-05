#!/usr/bin/env python3
"""Fetch the promoted PCB component YOLO checkpoint."""

from __future__ import annotations

import hashlib
import sys
import urllib.request
from pathlib import Path


MODEL_URL = (
    "https://raw.githubusercontent.com/aryan-programmer/pcb-fault-detection/master/"
    "pcb-components-detection/yolo11n_best_thawed.pt"
)
MODEL_PATH = Path("models/pcb/pcb_components_yolo11n_thawed.pt")
EXPECTED_SHA256 = "be7f320411e9f8bc75d2925e46c6516e1b2387819df1f672bf3b50ec546184f8"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = MODEL_PATH.with_suffix(".pt.tmp")
    print(f"downloading {MODEL_URL}")
    urllib.request.urlretrieve(MODEL_URL, tmp_path)

    actual = sha256(tmp_path)
    if actual != EXPECTED_SHA256:
        tmp_path.unlink(missing_ok=True)
        print(f"checksum mismatch: expected {EXPECTED_SHA256}, got {actual}", file=sys.stderr)
        return 1

    tmp_path.replace(MODEL_PATH)
    print(f"saved {MODEL_PATH} ({MODEL_PATH.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
