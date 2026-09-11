from __future__ import annotations

import json
from pathlib import Path

from hardware_splicer.codex_astra_proof_bundle import publish_proof_bundle


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_publish_proof_bundle_redacts_paths_and_accounts_for_original_hashes(
    tmp_path: Path,
) -> None:
    observer = tmp_path / "observer"
    workspace = tmp_path / "workspace"
    repo = tmp_path / "repo"
    observer.mkdir()
    manifest = {
        "case_id": "case-1",
        "experiment_project_id": "project-1",
        "observer_directory": str(observer),
        "backend_project_root": str(observer / "BACKEND_STORE"),
        "developer_instructions_file": str(observer / "DEVELOPER_INSTRUCTIONS.txt"),
        "snapshot_file": str(observer / "CASE_SNAPSHOT.json"),
        "model_visible_workspace": str(workspace),
        "hs_repo_root": str(repo),
    }
    _write_json(observer / "CASE_MANIFEST.json", manifest)
    for name in (
        "CASE_SNAPSHOT.json",
        "CODEX_ASTRA_FINAL_REPORT_SCHEMA.json",
        "CODEX_ASTRA_RESOURCE_GUARD.json",
        "LIVE_EXECUTION_ATTEMPT.json",
    ):
        _write_json(observer / name, {"path": str(observer / "secret")})
    _write_json(
        observer / "CODEX_ASTRA_AUDIT.json",
        {
            "codex_hard_truth_contract_pass": True,
            "codex_mission_progress_contract_pass": True,
            "codex_progress_provenance_contract_pass": True,
            "codex_final_report_contract_pass": True,
            "physical_correctness": "UNPROVEN",
            "physical_authority_granted": False,
            "live_unseen_competence": "UNADJUDICATED",
        },
    )
    _write_json(observer / "CODEX_ASTRA_RUN_RESULT.json", {"result": "passed"})
    _write_json(observer / "CODEX_ASTRA_RUNTIME_PLAN.json", {"repo": str(repo)})
    (observer / "CODEX_ASTRA_TRACE.jsonl").write_text(
        json.dumps({"token": "gho_" + "not-a-real-token", "path": str(workspace)}) + "\n",
        encoding="utf-8",
    )
    (observer / "DEVELOPER_INSTRUCTIONS.txt").write_text(
        f"read {repo}", encoding="utf-8"
    )
    package = observer / "BACKEND_STORE" / "project-1" / "engineering_packages" / "pkg"
    _write_json(package / "MANIFEST.json", {"observer": str(observer)})

    destination = tmp_path / "published"
    result = publish_proof_bundle(
        observer=observer,
        destination=destination,
        run_id="run-1",
        repository_commit="abc123",
    )

    published = "\n".join(
        path.read_text(encoding="utf-8")
        for path in destination.rglob("*")
        if path.is_file()
    )
    assert str(observer) not in published
    assert str(workspace) not in published
    assert str(repo) not in published
    assert "gho_" + "not-a-real-token" not in published
    assert "$OBSERVER_DIR" in published
    assert result["nonclaims"]["physical_correctness"] == "UNPROVEN"
    assert any(row["sanitized"] for row in result["artifacts"])
    assert "- result: `passed`" in (destination / "README.md").read_text()


def test_failed_bundle_readme_does_not_claim_success(tmp_path: Path) -> None:
    observer = tmp_path / "observer"
    observer.mkdir()
    _write_json(observer / "CASE_MANIFEST.json", {"case_id": "case-failed"})
    for name in (
        "CASE_SNAPSHOT.json",
        "CODEX_ASTRA_FINAL_REPORT_SCHEMA.json",
        "CODEX_ASTRA_RESOURCE_GUARD.json",
        "CODEX_ASTRA_RUNTIME_PLAN.json",
        "LIVE_EXECUTION_ATTEMPT.json",
    ):
        _write_json(observer / name, {})
    (observer / "CODEX_ASTRA_TRACE.jsonl").write_text("", encoding="utf-8")
    (observer / "DEVELOPER_INSTRUCTIONS.txt").write_text("test", encoding="utf-8")
    _write_json(
        observer / "CODEX_ASTRA_AUDIT.json",
        {
            "codex_hard_truth_contract_pass": True,
            "codex_mission_progress_contract_pass": True,
            "codex_progress_provenance_contract_pass": False,
            "codex_final_report_contract_pass": True,
            "physical_correctness": "UNPROVEN",
            "physical_authority_granted": False,
            "live_unseen_competence": "UNADJUDICATED",
        },
    )
    _write_json(observer / "CODEX_ASTRA_RUN_RESULT.json", {"result": "failed"})
    _write_json(
        observer
        / "BACKEND_STORE"
        / "project-failed"
        / "engineering_packages"
        / "pkg"
        / "MANIFEST.json",
        {},
    )

    destination = tmp_path / "published"
    publish_proof_bundle(
        observer=observer,
        destination=destination,
        run_id="run-failed",
        repository_commit="abc123",
    )

    readme = (destination / "README.md").read_text()
    assert "- result: `failed`" in readme
    assert "did not satisfy every acceptance contract" in readme
    assert "The run demonstrated" not in readme
