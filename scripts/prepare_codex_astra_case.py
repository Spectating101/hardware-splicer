#!/usr/bin/env python3
"""Prepare one frozen HS case for Codex without exposing outer evaluator metadata."""

from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path

from hardware_splicer.codex_astra_case import build_codex_case_package
from hardware_splicer.codex_astra_preflight import paths_are_disjoint


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
            "keep evaluator metadata in a separate observer directory. No model is called."
        )
    )
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--observer-dir", required=True)
    parser.add_argument("--experiment-project-id")
    args = parser.parse_args()

    workspace = Path(args.workspace).expanduser().resolve()
    observer = Path(args.observer_dir).expanduser().resolve()
    if not paths_are_disjoint(workspace, observer):
        raise SystemExit("workspace and observer directory must be disjoint")
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
    manifest = dict(outer)
    manifest.pop("snapshot", None)
    manifest.update(
        {
            "model_visible_workspace": str(workspace),
            "mission_file": str(mission_path),
            "observer_directory": str(observer),
            "snapshot_file": str(snapshot_path),
            "developer_instructions_file": str(instructions_path),
        }
    )
    manifest_path = observer / "CASE_MANIFEST.json"
    _write_json(manifest_path, manifest)

    summary = {
        "schema_version": "hardware_splicer.codex_astra_case_prep.v1",
        "experiment_project_id": project_id,
        "mission_file": str(mission_path),
        "observer_manifest": str(manifest_path),
        "snapshot_file": str(snapshot_path),
        "workspace_contains_outer_evaluator_manifest": False,
        "provider_network_io_performed": False,
        "model_inference_performed": False,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
