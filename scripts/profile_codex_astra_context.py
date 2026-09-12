#!/usr/bin/env python3
"""Profile durable Astra trace context material without model inference."""

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

from hardware_splicer.codex_astra_context_profile import profile_codex_astra_trace


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", required=True)
    parser.add_argument("--static-artifact", action="append", default=[])
    parser.add_argument("--target-input-tokens", type=int, default=200_000)
    args = parser.parse_args()
    report = profile_codex_astra_trace(
        args.trace,
        static_artifact_paths=args.static_artifact,
        target_input_tokens=args.target_input_tokens,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
