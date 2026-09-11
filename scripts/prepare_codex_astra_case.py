#!/usr/bin/env python3
"""Prepare one frozen HS case for Codex without exposing outer evaluator metadata."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import uuid
from pathlib import Path

# Direct execution from scripts/ would otherwise import legacy scripts/hardware_splicer.py.
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

from hardware_splicer.codex_astra_case import build_codex_case_package
from hardware_splicer.codex_astra_preflight import paths_are_disjoint
from hardware_splicer.cleanroom_primary_source_spi_flash_experiment import (
    BLIND_CASE_ID as PRIMARY_SOURCE_BLIND_CASE_ID,
    CASE_ID as PRIMARY_SOURCE_CASE_ID,
    IDENTITY_CONFLICT_CASE_ID as PRIMARY_SOURCE_IDENTITY_CONFLICT_CASE_ID,
    verify_primary_source_directory,
)


def _require_empty_directory(path: Path, *, label: str) -> None:
    if path.exists() and not path.is_dir():
        raise SystemExit(f"{label} must be a directory: {path}")
    path.mkdir(parents=True, exist_ok=True)
    if any(path.iterdir()):
        raise SystemExit(f"{label} must be empty to avoid evidence contamination: {path}")


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Write one model-visible frozen mission to an empty clean-room workspace and "
            "keep evaluator/backend state in a separate observer directory. No model is called."
        )
    )
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--observer-dir", required=True)
    parser.add_argument("--hs-repo-root", required=True)
    parser.add_argument("--experiment-project-id")
    parser.add_argument(
        "--primary-source-dir",
        help="Required local hash-pinned PDF capture for the primary-source case.",
    )
    args = parser.parse_args()

    workspace = Path(args.workspace).expanduser().resolve()
    observer = Path(args.observer_dir).expanduser().resolve()
    repo = Path(args.hs_repo_root).expanduser().resolve()
    if not paths_are_disjoint(workspace, observer):
        raise SystemExit("workspace and observer directory must be disjoint")
    if not paths_are_disjoint(workspace, repo):
        raise SystemExit("model-visible workspace and HS repository must be disjoint")
    if not paths_are_disjoint(observer, repo):
        raise SystemExit("observer directory and HS repository must be disjoint")
    _require_empty_directory(workspace, label="model-visible workspace")
    _require_empty_directory(observer, label="observer directory")

    project_id = args.experiment_project_id or f"hs-astra-{uuid.uuid4().hex[:16]}"
    package = build_codex_case_package(
        case_id=args.case_id,
        experiment_project_id=project_id,
    )
    visible = package["model_visible"]
    outer = package["observer_only"]

    mission_path = workspace / "MISSION.txt"
    mission_path.write_text(visible["mission_text"], encoding="utf-8")

    instructions_path = observer / "DEVELOPER_INSTRUCTIONS.txt"
    instructions_path.write_text(
        visible["developer_instructions"],
        encoding="utf-8",
    )
    snapshot_path = observer / "CASE_SNAPSHOT.json"
    _write_json(snapshot_path, outer["snapshot"])

    primary_capture_manifest = None
    if args.case_id in {
        PRIMARY_SOURCE_CASE_ID,
        PRIMARY_SOURCE_BLIND_CASE_ID,
        PRIMARY_SOURCE_IDENTITY_CONFLICT_CASE_ID,
    }:
        if not args.primary_source_dir:
            raise SystemExit("primary-source case requires --primary-source-dir")
        capture_root = Path(args.primary_source_dir).expanduser().resolve()
        capture = verify_primary_source_directory(capture_root)
        if not capture.get("pass"):
            raise SystemExit("primary-source document capture failed hash verification")
        retained_root = observer / "PRIMARY_SOURCES"
        retained_root.mkdir()
        for row in capture["documents"]:
            shutil.copyfile(capture_root / row["filename"], retained_root / row["filename"])
        primary_capture_manifest = retained_root / "CAPTURE_MANIFEST.json"
        _write_json(primary_capture_manifest, capture)

    backend_store = observer / "BACKEND_STORE"
    backend_store.mkdir()

    manifest = dict(outer)
    manifest.pop("snapshot", None)
    manifest.update(
        {
            "model_visible_workspace": str(workspace),
            "mission_file": str(mission_path),
            "observer_directory": str(observer),
            "snapshot_file": str(snapshot_path),
            "developer_instructions_file": str(instructions_path),
            "backend_project_root": str(backend_store),
            "backend_project_root_initially_empty": True,
            "hs_repo_root": str(repo),
        }
    )
    if primary_capture_manifest is not None:
        manifest.update(
            {
                "primary_source_capture_manifest": str(primary_capture_manifest),
                "primary_source_document_count": 3,
                "primary_source_documents_model_visible": False,
            }
        )
    manifest_path = observer / "CASE_MANIFEST.json"
    _write_json(manifest_path, manifest)

    summary = {
        "schema_version": "hardware_splicer.codex_astra_case_prep.v2",
        "experiment_project_id": project_id,
        "mission_file": str(mission_path),
        "observer_manifest": str(manifest_path),
        "snapshot_file": str(snapshot_path),
        "backend_project_root": str(backend_store),
        "workspace_contains_outer_evaluator_manifest": False,
        "provider_network_io_performed": False,
        "model_inference_performed": False,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
