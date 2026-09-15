#!/usr/bin/env python3
"""Download and verify the frozen primary documents for the SPI Astra case."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent
sys.path[:] = [
    str(_REPO_ROOT / "src"),
    *[entry for entry in sys.path if Path(entry or os.curdir).resolve() != _SCRIPT_DIR],
]

from hardware_splicer.cleanroom_primary_source_spi_flash_experiment import (
    primary_source_case_definition,
    verify_primary_source_directory,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--destination", required=True)
    args = parser.parse_args()
    destination = Path(args.destination).expanduser().resolve()
    if destination.exists() and any(destination.iterdir()):
        raise SystemExit("primary-source destination must be empty")
    destination.mkdir(parents=True, exist_ok=True)

    for document in primary_source_case_definition()["documents"]:
        request = urllib.request.Request(
            document["download_url"],
            headers={"User-Agent": "Hardware-Splicer-evidence-capture/1"},
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            content = response.read(16 * 1024 * 1024 + 1)
        if len(content) > 16 * 1024 * 1024:
            raise SystemExit(f"document exceeds capture ceiling: {document['source_id']}")
        (destination / document["filename"]).write_bytes(content)

    result = verify_primary_source_directory(destination)
    (destination / "CAPTURE_MANIFEST.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if result["pass"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
