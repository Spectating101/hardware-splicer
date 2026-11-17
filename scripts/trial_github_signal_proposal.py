#!/usr/bin/env python3
"""Explicit offline trial of a proposed adapter; grants no tool approval."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from hardware_splicer.github_signal_proposals import PROPOSED_ADAPTERS, trial_proposed_adapter


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter", required=True, choices=PROPOSED_ADAPTERS)
    parser.add_argument("--checkout", required=True, type=Path)
    parser.add_argument("--board", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = trial_proposed_adapter(args.adapter, args.checkout, args.board, args.out)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(json.dumps({"ok": False, "error": str(exc), "approval_effect": "none"}), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
