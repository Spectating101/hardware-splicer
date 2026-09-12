#!/usr/bin/env python3
"""Adjudicate one blinded raw-document Astra observer."""

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
    *[
        entry
        for entry in sys.path
        if Path(entry or os.curdir).resolve() != _SCRIPT_DIR
    ],
]

from hardware_splicer.codex_astra_raw_document_adjudication import (  # noqa: E402
    DATASHEET_FUNCTION_ALIAS_POLICY,
    EXACT_MAPPING_POLICY,
    adjudicate_raw_document_snapshot,
)
from hardware_splicer.cleanroom_primary_source_spi_flash_experiment import (  # noqa: E402
    RAW_DOCUMENT_V3_CASE_ID,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--observer-dir", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    observer = Path(args.observer_dir).expanduser().resolve()
    manifest = json.loads(
        (observer / "CASE_MANIFEST.json").read_text(encoding="utf-8")
    )
    project_id = str(manifest["experiment_project_id"])
    backend_root = observer / "BACKEND_STORE"
    project_root = backend_root / project_id
    project = json.loads((project_root / "project.json").read_text(encoding="utf-8"))
    revision = int(project["latest_revision"])
    envelope = json.loads(
        (project_root / "revisions" / f"{revision:08d}.json").read_text(
            encoding="utf-8"
        )
    )
    report = adjudicate_raw_document_snapshot(
        envelope["snapshot"],
        project_id=project_id,
        project_root=backend_root,
        mapping_alias_policy=(
            DATASHEET_FUNCTION_ALIAS_POLICY
            if manifest.get("case_id") == RAW_DOCUMENT_V3_CASE_ID
            else EXACT_MAPPING_POLICY
        ),
    )
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
