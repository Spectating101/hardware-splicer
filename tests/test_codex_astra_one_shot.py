from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest

from hardware_splicer.codex_astra_runtime import (
    LIVE_EXECUTION_CLAIM_FILE,
    RuntimeContext,
    claim_live_execution,
)


def _context(tmp_path: Path) -> RuntimeContext:
    observer = tmp_path / "observer"
    workspace = tmp_path / "workspace"
    repo = tmp_path / "repo"
    backend = observer / "BACKEND_STORE"
    observer.mkdir()
    workspace.mkdir()
    repo.mkdir()
    backend.mkdir()
    mission = workspace / "MISSION.txt"
    snapshot = observer / "CASE_SNAPSHOT.json"
    instructions = observer / "DEVELOPER_INSTRUCTIONS.txt"
    manifest = observer / "CASE_MANIFEST.json"
    for path in (mission, snapshot, instructions, manifest):
        path.write_text("{}", encoding="utf-8")
    return RuntimeContext(
        manifest_path=manifest,
        observer_dir=observer,
        workspace=workspace,
        mission_file=mission,
        snapshot_file=snapshot,
        instructions_file=instructions,
        backend_project_root=backend,
        hs_repo_root=repo,
        experiment_project_id="opaque-project",
        case_id="frozen-case",
    )


def test_live_execution_claim_is_atomic_and_never_reusable(tmp_path: Path) -> None:
    context = _context(tmp_path)
    claim = claim_live_execution(context)
    assert claim == context.observer_dir / LIVE_EXECUTION_CLAIM_FILE
    assert stat.S_IMODE(claim.stat().st_mode) == 0o600
    payload = json.loads(claim.read_text(encoding="utf-8"))
    assert payload["case_id"] == "frozen-case"
    assert payload["experiment_project_id"] == "opaque-project"
    assert payload["single_use"] is True
    assert payload["api_fallback"] is False
    assert payload["physical_authority_granted"] is False

    with pytest.raises(ValueError, match="already has a live execution attempt"):
        claim_live_execution(context)

    assert claim.is_file()


def test_failed_retry_cannot_replace_existing_claim(tmp_path: Path) -> None:
    context = _context(tmp_path)
    claim = claim_live_execution(context)
    original = claim.read_bytes()
    with pytest.raises(ValueError):
        claim_live_execution(context)
    assert claim.read_bytes() == original
