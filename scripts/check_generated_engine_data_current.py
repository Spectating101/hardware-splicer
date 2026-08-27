#!/usr/bin/env python3
"""Fail when generated engine JSON differs semantically from the committed files.

Generated-data freshness is an engineering-truth check, not a whitespace check.  The
exporters are free to use a canonical presentation style, but a reformat-only change must
not make Robot Reference E2E red.  Conversely, any value/list/object drift remains a hard
failure.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


DEFAULT_PATHS = (
    "src/hardware_splicer/data/engine_pcb_data.json",
    "src/hardware_splicer/data/catalog_recipes.json",
)


def _load_json_text(text: str, *, label: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{label} is not valid JSON: {exc}") from exc


def _head_text(path: str) -> str:
    proc = subprocess.run(
        ["git", "show", f"HEAD:{path}"],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip() or "git show failed"
        raise RuntimeError(f"cannot read committed {path}: {detail}")
    return proc.stdout


def _first_difference(expected: Any, actual: Any, path: str = "$") -> str:
    if type(expected) is not type(actual):
        return f"{path}: type {type(expected).__name__} != {type(actual).__name__}"
    if isinstance(expected, dict):
        expected_keys = set(expected)
        actual_keys = set(actual)
        missing = sorted(expected_keys - actual_keys)
        added = sorted(actual_keys - expected_keys)
        if missing:
            return f"{path}: missing keys {missing}"
        if added:
            return f"{path}: added keys {added}"
        for key in expected:
            if expected[key] != actual[key]:
                return _first_difference(expected[key], actual[key], f"{path}.{key}")
        return f"{path}: objects differ"
    if isinstance(expected, list):
        if len(expected) != len(actual):
            return f"{path}: list length {len(expected)} != {len(actual)}"
        for index, (left, right) in enumerate(zip(expected, actual)):
            if left != right:
                return _first_difference(left, right, f"{path}[{index}]")
        return f"{path}: lists differ"
    return f"{path}: {expected!r} != {actual!r}"


def check_path(path: str) -> tuple[bool, str]:
    working_path = Path(path)
    if not working_path.is_file():
        return False, f"generated file missing: {path}"
    committed = _load_json_text(_head_text(path), label=f"HEAD:{path}")
    generated = _load_json_text(working_path.read_text(encoding="utf-8"), label=path)
    if committed == generated:
        return True, f"semantic-current: {path}"
    return False, f"semantic-drift: {path}: {_first_difference(committed, generated)}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="*", default=list(DEFAULT_PATHS))
    args = parser.parse_args()

    failed = False
    for path in args.paths:
        try:
            ok, message = check_path(path)
        except RuntimeError as exc:
            ok, message = False, str(exc)
        print(message)
        failed = failed or not ok
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
