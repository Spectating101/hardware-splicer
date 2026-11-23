#!/usr/bin/env python3
"""Native KiCad SPI checkpoint proof: fresh run or verified resume."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hardware_splicer.spi_checkpoint import (
    CheckpointError, STAGES, _read, run,
)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("run", "resume", "status"))
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--repo-root", type=Path, default=ROOT)
    p.add_argument("--interrupt-after", choices=STAGES,
                   help="Test-only: persist completed stage, then exit interpreter 77")
    args = p.parse_args()
    if args.action == "status":
        try:
            point = _read(args.out / "checkpoint.json")
            print(json.dumps({
                "schema": point.get("schema"),
                "completed": point.get("completed"),
                "state": point.get("state"),
                "physical_authority": point.get("physical_authority"),
                "source_head": point.get("source_head"),
            }, indent=2))
            return 0
        except (CheckpointError, OSError) as exc:
            print(json.dumps({"status": "unavailable", "error": str(exc)}), file=sys.stderr)
            return 2
    if args.action == "resume" and args.interrupt_after is not None:
        p.error("--interrupt-after is permitted only on fresh test runs")
    try:
        result = run(repo_root=args.repo_root, out=args.out,
                     resume=args.action == "resume",
                     interrupt_after=args.interrupt_after)
        print(json.dumps(result, sort_keys=True, indent=2))
        return 0
    except (CheckpointError, ValueError, OSError, KeyError, TypeError,
            TimeoutError) as exc:
        print(json.dumps({
            "status": "blocked",
            "error_type": type(exc).__name__,
            "error": str(exc)[:300],
            "physical_authority": False,
        }), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
