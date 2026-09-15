#!/usr/bin/env python3
"""Print the zero-inference vendor-model campaign plan/readiness result."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))

from hardware_splicer.spi_virtual_model_campaign import build_spi_virtual_model_campaign


def _load_capture_manifests(paths: list[Path]) -> list[dict]:
    rows: list[dict] = []
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise SystemExit(f"capture manifest must be a JSON object: {path}")
        rows.append(payload)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--capture-manifest",
        action="append",
        default=[],
        type=Path,
        help="captured vendor-model manifest JSON; may be repeated",
    )
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    result = build_spi_virtual_model_campaign(_load_capture_manifests(args.capture_manifest))
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["status"] in {"model_capture_required", "ready_for_model_execution"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
