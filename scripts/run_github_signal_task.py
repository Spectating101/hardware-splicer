#!/usr/bin/env python3
"""Choose an approved GitHub-source-native specialist for an engineering task."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

# Prefer the repo source over any installed HS build.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from hardware_splicer.github_signal_task_router import run_task
from hardware_splicer.github_signal_pipeline import SignalEvaluationError


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--feed",required=True,type=Path)
    p.add_argument("--objective",required=True)
    p.add_argument("--checkout-base",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    p.add_argument("--fetch",action="store_true")
    p.add_argument("--sandbox",choices=("bwrap","docker"),default="bwrap",
                   help="Explicit isolation backend; Docker image must be pre-pulled")
    p.add_argument("--schematic",type=Path)
    p.add_argument("--board-repo",type=Path)
    p.add_argument("--board",type=Path)
    p.add_argument("--revision-a")
    p.add_argument("--revision-b")
    args=p.parse_args()
    try:
        verdict=run_task(
            objective=args.objective,
            feed=json.loads(args.feed.read_text()),
            checkout_base=args.checkout_base,
            output_dir=args.out,
            fetch=args.fetch,
            schematic=args.schematic,
            board_repo=args.board_repo,
            board=args.board,
            revision_a=args.revision_a,
            revision_b=args.revision_b,
            sandbox_backend=args.sandbox,
        )
    except (SignalEvaluationError, OSError, ValueError) as exc:
        print(json.dumps({"ok":False,"error":str(exc)},indent=2))
        return 2
    print(json.dumps(verdict,indent=2,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
