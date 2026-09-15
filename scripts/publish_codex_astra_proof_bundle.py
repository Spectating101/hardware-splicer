#!/usr/bin/env python3
"""Publish one sanitized Codex/Astra observer proof bundle."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent
sys.path[:] = [
    str(_REPO_ROOT / "src"),
    *[entry for entry in sys.path if Path(entry or os.curdir).resolve() != _SCRIPT_DIR],
]

from hardware_splicer.codex_astra_proof_bundle import publish_proof_bundle


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--observer-dir", required=True)
    parser.add_argument("--destination", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--repository-commit", required=True)
    args = parser.parse_args()
    result = publish_proof_bundle(
        observer=Path(args.observer_dir),
        destination=Path(args.destination),
        run_id=args.run_id,
        repository_commit=args.repository_commit,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
