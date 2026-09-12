from __future__ import annotations

import json
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from hardware_splicer.codex_astra_runtime import CODEX_ALLOWANCE_CONFIRMATION
from hardware_splicer.codex_budgeted_entrypoint import (
    ASTRA_DEFAULT_TIMEOUT_SECONDS,
    ASTRA_LAUNCHER_TEMP_ROOT,
    ASTRA_MAX_TIMEOUT_SECONDS,
    build_delegated_runner_argv,
    clamp_timeout_seconds,
    resource_guard_manifest,
    resolve_canonical_backend,
    validate_launcher,
    write_budgeted_mcp_launcher,
    write_resource_guard_manifest,
)
from hardware_splicer.codex_budgeted_mcp_proxy import (
    ASTRA_MAX_BACKEND_CALLS,
    ASTRA_MAX_MCP_TOOL_CALLS,
    ASTRA_MAX_REQUEST_BYTES,
)


def test_timeout_is_hard_capped_at_five_minutes() -> None:
    assert ASTRA_LAUNCHER_TEMP_ROOT == Path("/tmp")
    assert ASTRA_DEFAULT_TIMEOUT_SECONDS == 300
    assert ASTRA_MAX_TIMEOUT_SECONDS == 300
    assert clamp_timeout_seconds(30) == 30
    assert clamp_timeout_seconds(300) == 300
    with pytest.raises(ValueError, match="may not exceed 300"):
        clamp_timeout_seconds(301)
    with pytest.raises(ValueError, match="at least 30"):
        clamp_timeout_seconds(29)
    with pytest.raises(TypeError):
        clamp_timeout_seconds(True)


def test_budgeted_launcher_is_private_executable_and_wraps_only_proxy(tmp_path: Path) -> None:
    backend = tmp_path / "hs-backend-mcp"
    backend.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    backend.chmod(0o700)
    launcher = write_budgeted_mcp_launcher(
        tmp_path / "launcher",
        backend_command=str(backend),
        python_command=sys.executable,
    )
    assert validate_launcher(launcher) is True
    assert stat.S_IMODE(launcher.stat().st_mode) == 0o700
    text = launcher.read_text(encoding="utf-8")
    assert "-m hardware_splicer.codex_budgeted_mcp_proxy" in text
    assert "--backend-command" in text
    assert str(backend.resolve()) in text
    assert text.startswith("#!/bin/sh\nset -eu\n")


def test_budgeted_launcher_preserves_virtualenv_python_symlink(tmp_path: Path) -> None:
    backend = tmp_path / "hs-backend-mcp"
    backend.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    backend.chmod(0o700)
    real_python = tmp_path / "python-real"
    real_python.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    real_python.chmod(0o700)
    venv_python = tmp_path / "venv-python"
    venv_python.symlink_to(real_python)

    launcher = write_budgeted_mcp_launcher(
        tmp_path / "launcher",
        backend_command=str(backend),
        python_command=str(venv_python),
    )

    text = launcher.read_text(encoding="utf-8")
    assert str(venv_python) in text
    assert str(real_python) not in text


def test_canonical_backend_rejects_an_already_budgeted_launcher(tmp_path: Path) -> None:
    raw_backend = tmp_path / "hs-backend-mcp"
    raw_backend.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    raw_backend.chmod(0o700)
    launcher = write_budgeted_mcp_launcher(
        tmp_path / "governed-mcp",
        backend_command=str(raw_backend),
        python_command=sys.executable,
    )

    with pytest.raises(ValueError, match="raw canonical hs-backend-mcp"):
        resolve_canonical_backend(str(launcher))


def test_delegated_runner_cannot_escape_governed_mcp_or_timeout(tmp_path: Path) -> None:
    runner = tmp_path / "run_codex_astra_case.py"
    manifest = tmp_path / "CASE_MANIFEST.json"
    launcher = tmp_path / "governed-mcp"
    for path in (runner, manifest, launcher):
        path.write_text("", encoding="utf-8")

    argv = build_delegated_runner_argv(
        runner_script=runner,
        manifest=manifest,
        mcp_launcher=launcher,
        timeout_seconds=300,
        codex_command="/fake/codex",
        execute=True,
        confirmation=CODEX_ALLOWANCE_CONFIRMATION,
    )
    assert argv[argv.index("--mcp-command") + 1] == str(launcher.resolve())
    assert argv[argv.index("--timeout-seconds") + 1] == "300"
    assert argv[argv.index("--codex-command") + 1] == "/fake/codex"
    assert "--execute" in argv
    assert argv[argv.index("--confirm-codex-allowance") + 1] == CODEX_ALLOWANCE_CONFIRMATION
    assert "hs-backend-mcp" not in argv

    with pytest.raises(ValueError, match="may not exceed 300"):
        build_delegated_runner_argv(
            runner_script=runner,
            manifest=manifest,
            mcp_launcher=launcher,
            timeout_seconds=301,
        )


def test_resource_guard_manifest_names_bounded_exposure_not_exact_cost(tmp_path: Path) -> None:
    guard = resource_guard_manifest(timeout_seconds=300)
    assert guard["timeout_seconds"] == 300
    assert guard["timeout_hard_max_seconds"] == 300
    assert guard["mcp_tool_calls_hard_max"] == ASTRA_MAX_MCP_TOOL_CALLS == 20
    assert guard["backend_calls_hard_max"] == ASTRA_MAX_BACKEND_CALLS == 12
    assert guard["mcp_request_bytes_hard_max"] == ASTRA_MAX_REQUEST_BYTES == 262_144
    assert guard["api_fallback"] is False
    assert guard["exact_allowance_cost_guaranteed"] is False
    assert "do not guarantee" in guard["claim_boundary"]

    path = write_resource_guard_manifest(tmp_path / "guard.json", timeout_seconds=300)
    assert json.loads(path.read_text(encoding="utf-8")) == guard


def test_budgeted_runner_dry_run_emits_only_resource_plan(tmp_path: Path) -> None:
    observer = tmp_path / "observer"
    observer.mkdir()
    manifest = observer / "CASE_MANIFEST.json"
    manifest.write_text(
        json.dumps({"observer_directory": str(observer)}),
        encoding="utf-8",
    )
    backend = tmp_path / "fake-hs-backend-mcp"
    backend.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    backend.chmod(0o700)

    script = Path(__file__).resolve().parents[1] / "scripts" / "run_budgeted_codex_astra_case.py"
    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--manifest",
            str(manifest),
            "--backend-command",
            str(backend),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr + completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["execution_performed"] is False
    assert payload["resource_guard"]["mcp_tool_calls_hard_max"] == 20
    assert payload["resource_guard"]["backend_calls_hard_max"] == 12
    assert payload["resource_guard"]["timeout_seconds"] == 300
    assert payload["api_fallback"] is False
    delegated = payload["delegated_argv"]
    launcher = delegated[delegated.index("--mcp-command") + 1]
    assert launcher.startswith("/tmp/hs-astra-budgeted-mcp-")
    assert str(backend.resolve()) not in delegated
    assert (observer / "CODEX_ASTRA_RESOURCE_GUARD.json").is_file()


def test_budgeted_runner_rejects_timeout_above_hard_max_before_delegate(tmp_path: Path) -> None:
    observer = tmp_path / "observer"
    observer.mkdir()
    manifest = observer / "CASE_MANIFEST.json"
    manifest.write_text(json.dumps({"observer_directory": str(observer)}), encoding="utf-8")
    backend = tmp_path / "fake-hs-backend-mcp"
    backend.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    backend.chmod(0o700)
    script = Path(__file__).resolve().parents[1] / "scripts" / "run_budgeted_codex_astra_case.py"
    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--manifest",
            str(manifest),
            "--backend-command",
            str(backend),
            "--timeout-seconds",
            "301",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert completed.returncode != 0
    assert "may not exceed 300" in completed.stderr
    assert not (observer / "CODEX_ASTRA_RESOURCE_GUARD.json").exists()
