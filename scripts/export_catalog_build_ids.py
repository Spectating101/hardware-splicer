#!/usr/bin/env python3
"""Export canonical catalog build IDs for frontend (gate 1.5 — no plan-to-graph import)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hardware_splicer.catalog import CATALOG_BUILD_IDS  # noqa: E402

OUT = (
    ROOT
    / "apps"
    / "circuit-ai"
    / "circuit-ai-frontend"
    / "lib"
    / "hardware-splicer"
    / "catalog-build-ids.json"
)


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "hardware_splicer.catalog_build_ids.v1",
        "build_ids": list(CATALOG_BUILD_IDS),
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
