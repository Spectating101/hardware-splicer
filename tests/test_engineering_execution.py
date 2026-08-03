from __future__ import annotations

from pathlib import Path

import pytest

from hardware_splicer.engineering_execution import (
    ExecutionOperation,
    ExecutionPolicyError,
    ExecutionRequest,
    ExecutionStatus,
    execution_manifest,
    preview_engineering_execution,
    run_engineering_execution,
)


def test_preview_is_non_executing_and_discloses_physical_prohibitions(tmp_path: Path) -> None:
    target = tmp_path / "artifact.bin"
    target.write_bytes(b"hardware-splicer")
    request = ExecutionRequest(
        execution_id="hash-preview",
        operation=ExecutionOperation.ARTIFACT_HASH,
        workspace=".",
        target="artifact.bin",
        execute=False,
    )

    result = preview_engineering_execution(request, root=tmp_path)

    assert result.status == ExecutionStatus.PLANNED
    assert result.argv == []
    assert result.metadata["shell"] is False
    assert result.metadata["network_authorized"] is False
    assert result.metadata["network_isolation_enforced"] is False
    assert result.metadata["flash_authorized"] is False
    assert result.metadata["power_on_authorized"] is False
    assert result.metadata["motion_authorized"] is False


def test_workspace_escape_is_rejected(tmp_path: Path) -> None:
    request = ExecutionRequest(
        execution_id="escape",
        operation=ExecutionOperation.ARTIFACT_HASH,
        workspace=".",
        target="../outside.bin",
    )

    with pytest.raises(ExecutionPolicyError, match="outside execution root"):
        preview_engineering_execution(request, root=tmp_path)


def test_pytest_target_escape_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "tests").mkdir()
    request = ExecutionRequest(
        execution_id="pytest-escape",
        operation=ExecutionOperation.PYTEST,
        workspace=".",
        options={"targets": ["../outside-tests"]},
    )

    with pytest.raises(ExecutionPolicyError, match="outside execution root"):
        preview_engineering_execution(request, root=tmp_path)


def test_pytest_options_are_rejected(tmp_path: Path) -> None:
    (tmp_path / "tests").mkdir()
    request = ExecutionRequest(
        execution_id="pytest-option",
        operation=ExecutionOperation.PYTEST,
        workspace=".",
        options={"targets": ["--collect-only"]},
    )

    with pytest.raises(ExecutionPolicyError, match="cannot be an option"):
        preview_engineering_execution(request, root=tmp_path)


def test_execution_remains_blocked_when_host_policy_is_disabled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "artifact.bin"
    target.write_bytes(b"blocked")
    monkeypatch.delenv("HARDWARE_SPLICER_EXECUTION_ENABLED", raising=False)
    request = ExecutionRequest(
        execution_id="disabled",
        operation=ExecutionOperation.ARTIFACT_HASH,
        workspace=".",
        target="artifact.bin",
        execute=True,
    )

    result = run_engineering_execution(request, root=tmp_path)

    assert result.status == ExecutionStatus.BLOCKED
    assert "execution is disabled by host policy" in result.blockers
    assert result.output_hashes == {}


def test_internal_artifact_hash_can_run_when_explicitly_enabled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "artifact.bin"
    target.write_bytes(b"bounded execution")
    monkeypatch.setenv("HARDWARE_SPLICER_EXECUTION_ENABLED", "1")
    request = ExecutionRequest(
        execution_id="hash-run",
        operation=ExecutionOperation.ARTIFACT_HASH,
        workspace=".",
        target="artifact.bin",
        execute=True,
    )

    result = run_engineering_execution(request, root=tmp_path)
    manifest = execution_manifest(result)

    assert result.status == ExecutionStatus.PASSED
    assert result.output_hashes["artifact.bin"].startswith("sha256:")
    assert manifest["manifest_hash"].startswith("sha256:")
    assert result.metadata["device_access_authorized"] is False


def test_pytest_operation_generates_contained_argv_internally(tmp_path: Path) -> None:
    tests = tmp_path / "tests"
    tests.mkdir()
    request = ExecutionRequest(
        execution_id="pytest-preview",
        operation=ExecutionOperation.PYTEST,
        workspace=".",
        options={"targets": ["tests"]},
        execute=False,
    )

    result = preview_engineering_execution(request, root=tmp_path)

    assert result.status == ExecutionStatus.PLANNED
    assert result.argv[1:4] == ["-m", "pytest", "-q"]
    assert result.argv[-1] == str(tests.resolve())
    assert all(";" not in token for token in result.argv)
