#!/usr/bin/env python3
"""Adjudicate the final canonical snapshot from one primary-source Astra observer."""

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

from hardware_splicer.codex_astra_primary_source_adjudication import (
    adjudicate_primary_source_snapshot,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--observer-dir", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    observer = Path(args.observer_dir).expanduser().resolve()
    manifest = json.loads((observer / "CASE_MANIFEST.json").read_text(encoding="utf-8"))
    project_id = str(manifest["experiment_project_id"])
    project_root = observer / "BACKEND_STORE" / project_id
    project = json.loads((project_root / "project.json").read_text(encoding="utf-8"))
    revision = int(project["latest_revision"])
    envelope = json.loads(
        (project_root / "revisions" / f"{revision:08d}.json").read_text(encoding="utf-8")
    )
    report = adjudicate_primary_source_snapshot(envelope["snapshot"])
    report["project_id"] = project_id
    report["final_project_revision"] = revision
    destination = Path(args.out).expanduser().resolve()
    destination.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if report["status"] == "pass" else 4


if __name__ == "__main__":
    raise SystemExit(main())
