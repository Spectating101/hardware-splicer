#!/usr/bin/env python3
"""Pin live Qwen board_evidence from golden RC donor photo."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "apps" / "circuit-ai"))

DEFAULT_IMAGE = ROOT / "tests/data/golden/rc_toy_motor_board.jpg"
DEFAULT_EVIDENCE = ROOT / "tests/data/golden/rc_toy_live_board_evidence.json"
DEFAULT_META = ROOT / "tests/data/golden/rc_toy_live_board_evidence.meta.json"


def _load_env() -> None:
    for rel in (".env.local", "apps/circuit-ai/.env.local", "apps/circuit-ai/.env"):
        fp = ROOT / rel
        if not fp.is_file():
            continue
        for line in fp.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Pin live Qwen board_evidence for golden RC photo")
    parser.add_argument("--image", type=Path, default=DEFAULT_IMAGE)
    parser.add_argument("--out", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    _load_env()
    if args.dry_run:
        os.environ.pop("QWEN_API_KEY", None)

    os.environ.setdefault("QWEN_DISABLED", "0")
    os.environ.setdefault("QWEN_OUT_OF_QUOTA", "0")
    os.environ.setdefault("VISION_MONTHLY_USD_LIMIT", "5")
    os.environ.setdefault("VISION_DAILY_USD_LIMIT", "2")
    os.environ.setdefault("VISION_MAX_USD_PER_CALL", "0.25")

    from hardware_splicer.board_vision_salvage import _analyze_board_image_path

    if not args.image.is_file():
        print(f"image not found: {args.image}", file=sys.stderr)
        return 1

    result = _analyze_board_image_path(
        args.image,
        goal="salvage motor driver section for robot drive base",
        live=not args.dry_run,
        device_hint="Playmobil RC toy motor controller PCB",
        symptoms=["motors do not spin", "board silent on battery"],
    )
    mode = str(result.get("mode") or "")
    evidence = result.get("board_evidence") if isinstance(result.get("board_evidence"), dict) else {}
    if not evidence and args.dry_run:
        print(f"dry_run ok mode={mode}")
        return 0
    if not evidence:
        print(json.dumps({k: result.get(k) for k in ("mode", "error", "budget")}, indent=2), file=sys.stderr)
        return 1

    if evidence.get("schema_version") != "board_evidence.v1":
        evidence["schema_version"] = "board_evidence.v1"

    meta = {
        "source_image": str(args.image.relative_to(ROOT)) if args.image.is_relative_to(ROOT) else str(args.image),
        "provider": "qwen",
        "mode": mode,
        "model": result.get("model"),
        "image_sha256": (result.get("preflight") or {}).get("image_sha256"),
        "usage": result.get("usage"),
        "estimated_usd": result.get("estimated_usd"),
        "symptoms": ["motors do not spin", "board silent on battery"],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    DEFAULT_META.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"pinned {args.out}")
    print(f"meta {DEFAULT_META}")
    print(f"mode={mode} salvage_candidates={len(evidence.get('salvage_candidates') or [])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
