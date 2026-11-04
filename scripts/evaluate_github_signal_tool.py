#!/usr/bin/env python3
"""Import GitHub-signal records and try an approved HS specialist adapter.

One deterministic command can fetch exact source revision, verify its license,
execute a fixed read-only tool in a network-isolated bwrap process,
and expose the resulting artifact to the existing HS capability report.

This does not implement a live GitHub Signals subscription/API. Accepted feed
JSON can be exported by GitHub search, a scout, or a future Signal connector.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

# Avoid same-directory scripts/hardware_splicer.py shadowing HS package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from hardware_splicer.github_signal_pipeline import (
    SignalEvaluationError, evaluate_signals,
)

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--feed", type=Path, required=True)
    p.add_argument("--schematic", type=Path, required=True,
                   help="Existing HS engineering input, never modified")
    p.add_argument("--checkout", type=Path, required=True,
                   help="Checkout for exact source-pinned external tool")
    p.add_argument("--out", type=Path, required=True,
                   help="Project-scoped capability artifacts")
    p.add_argument("--fetch", action="store_true",
                   help="Clone only pre-approved GitHub repo into empty checkout")
    p.add_argument("--sandbox", choices=("bwrap", "docker"), default="bwrap",
                   help="Explicit isolated runner. Docker requires pre-pulled image.")
    args = p.parse_args()
    try:
        verdict = evaluate_signals(
            json.loads(args.feed.read_text(encoding="utf-8")),
            checkout=args.checkout, schematic=args.schematic,
            output_dir=args.out, fetch=args.fetch,
            sandbox_backend=args.sandbox,
        )
    except (OSError, ValueError, SignalEvaluationError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, indent=2))
        return 2
    print(json.dumps(verdict, indent=2, sort_keys=True))
    return 0 if verdict["ok"] else 3

if __name__ == "__main__":
    raise SystemExit(main())
