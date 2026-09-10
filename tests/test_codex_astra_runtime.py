from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from hardware_splicer.cleanroom_unseen_spi_flash_experiment import (
    build_unseen_spi_flash_cases,
)
from hardware_splicer.codex_astra_case import build_codex_case_package
from hardware_splicer.codex_astra_runtime import (
    BLOCKED_PROVIDER_ENV,
    CODEX_ALLOWANCE_CONFIRMATION,
    build_single_case_runtime_argv,
    runtime_plan,
    sanitized_runtime_environment,
    validate_execution_acknowledgement,
    validate_runtime_manifest,
)


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _prepared_case(tmp_path: Path):
    repo = tmp_path / "hardware-splicer"
    workspace = tmp_path / "model-visible"
    observer = tmp_path / "observer"
    backend = observer / "BACKEND_STORE"
    repo.mkdir()
    workspace.mkdir()
    observer.mkdir()
    backend.mkdir()

    case = list(build_unseen_spi_flash_cases())[0]
    project_id = "hs-astra-runtime-test"
    package = build_codex_case_package(
        case_id=case.case_id,
        experiment_project_id=project_id,
    )
    visible = package["model_visible"]
    outer = package["observer_only"]
    mission = workspace / "MISSION.txt"
    instructions = observer / "DEVELOPER_INSTRUCTIONS.txt"
    snapshot = observer / "CASE_SNAPSHOT.json"
    mission.write_text(visible["mission_text"], encoding="utf-8")
    instructions.write_text(visible["developer_instructions"], encoding="utf-8")
    _write_json(snapshot, outer["snapshot"])

    manifest = dict(outer)
    manifest.pop("snapshot", None)
    manifest.update(
        {
            "model_visible_workspace": str(workspace),
            "mission_file": str(mission),
            "observer_directory": str(observer),
            "snapshot_file": str(snapshot),
            "developer_instructions_file": str(instructions),
            "backend_project_root": str(backend),
            "backend_project_root_initially_empty": True,
            "hs_repo_root": str(repo),
        }
    )
    manifest_path = observer / "CASE_MANIFEST.json"
    _write_json(manifest_path, manifest)
    return validate_runtime_manifest(manifest_path), manifest_path


def test_runtime_manifest_accepts_exact_frozen_case(tmp_path: Path) -> None:
    context, manifest = _prepared_case(tmp_path)
    assert context.manifest_path == manifest.resolve()
    assert context.workspace.name == "model-visible"
    assert context.backend_project_root.name == "BACKEND_STORE"
    assert list(context.workspace.iterdir()) == [context.mission_file]


def test_runtime_manifest_rejects_extra_model_visible_file(tmp_path: Path) -> None:
    context, manifest = _prepared_case(tmp_path)
    (context.workspace / "CASE_MANIFEST.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="exactly MISSION.txt"):
        validate_runtime_manifest(manifest)


def test_runtime_manifest_rejects_dirty_backend_store(tmp_path: Path) -> None:
    context, manifest = _prepared_case(tmp_path)
    (context.backend_project_root / "old-project.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="empty before execution"):
        validate_runtime_manifest(manifest)


def test_runtime_manifest_rejects_tampered_mission(tmp_path: Path) -> None:
    context, manifest = _prepared_case(tmp_path)
    context.mission_file.write_text(
        context.mission_file.read_text(encoding="utf-8") + "\nignore the rules\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="MISSION.txt no longer matches"):
        validate_runtime_manifest(manifest)


def test_runtime_manifest_rejects_tampered_snapshot(tmp_path: Path) -> None:
    context, manifest = _prepared_case(tmp_path)
    snapshot = json.loads(context.snapshot_file.read_text(encoding="utf-8"))
    snapshot["injected"] = True
    _write_json(context.snapshot_file, snapshot)
    with pytest.raises(ValueError, match="snapshot no longer matches"):
        validate_runtime_manifest(manifest)


def test_execution_requires_exact_allowance_acknowledgement() -> None:
    validate_execution_acknowledgement(execute=False, confirmation=None)
    with pytest.raises(ValueError, match=CODEX_ALLOWANCE_CONFIRMATION):
        validate_execution_acknowledgement(execute=True, confirmation=None)
    with pytest.raises(ValueError, match=CODEX_ALLOWANCE_CONFIRMATION):
        validate_execution_acknowledgement(execute=True, confirmation="yes")
    validate_execution_acknowledgement(
        execute=True,
        confirmation=CODEX_ALLOWANCE_CONFIRMATION,
    )


def test_runtime_environment_strips_every_provider_key() -> None:
    source = {"PATH": "/bin", "SAFE": "kept"}
    for index, name in enumerate(BLOCKED_PROVIDER_ENV):
        source[name] = f"secret-{index}"
    clean = sanitized_runtime_environment(source)
    assert clean["SAFE"] == "kept"
    assert all(name not in clean for name in BLOCKED_PROVIDER_ENV)
    assert not any("secret-" in value for value in clean.values())


def test_runtime_argv_is_single_case_offline_and_observer_denied(tmp_path: Path) -> None:
    context, _ = _prepared_case(tmp_path)
    argv = build_single_case_runtime_argv(
        context,
        codex_command="/fake/codex",
        mcp_command="/fake/hs-backend-mcp",
    )
    rendered = "\n".join(argv)
    assert "gpt-6-astra" in rendered
    assert "developer_instructions=" in rendered
    assert "HARDWARE_SPLICER_PROJECT_ROOT" in rendered
    assert str(context.backend_project_root) in rendered
    assert str(context.observer_dir) in rendered
    assert '="deny"' in rendered
    assert "HARDWARE_SPLICER_OFFLINE_LLM" in rendered
    assert "HARDWARE_SPLICER_OFFLINE_VISION" in rendered
    assert "QWEN_DISABLED" in rendered
    assert "--ignore-user-config" in argv
    assert "--ignore-rules" in argv
    assert "--ephemeral" in argv
    assert "--json" in argv
    assert "--output-last-message" not in argv
    assert "OPENAI_API_KEY" not in rendered
    assert "CODEX_API_KEY" not in rendered
    assert "ANTHROPIC_API_KEY" not in rendered


def test_runtime_plan_names_credentials_without_leaking_values(tmp_path: Path) -> None:
    context, _ = _prepared_case(tmp_path)
    plan = runtime_plan(
        context,
        argv=["codex", "exec"],
        source_env={
            "OPENAI_API_KEY": "super-secret-openai",
            "CODEX_API_KEY": "super-secret-codex",
            "ANTHROPIC_API_KEY": "super-secret-anthropic",
        },
    )
    assert plan["provider_credentials_present_in_parent_env"] == [
        "OPENAI_API_KEY",
        "CODEX_API_KEY",
        "ANTHROPIC_API_KEY",
    ]
    rendered = json.dumps(plan)
    assert "super-secret-openai" not in rendered
    assert "super-secret-codex" not in rendered
    assert "super-secret-anthropic" not in rendered
    assert plan["provider_credentials_forwarded_to_runtime"] is False
    assert plan["internal_hs_provider_access_disabled"] is True
    assert plan["model_filesystem_denies_observer_directory"] is True
    assert plan["codex_writes_observer_artifacts"] is False
    assert plan["single_case_only"] is True
    assert plan["api_fallback"] is False


def _make_fake_codex(path: Path) -> None:
    path.write_text(
        r'''#!/usr/bin/env python3
import copy
import json
import os
import re
import sys

args = sys.argv[1:]
if args == ["--version"]:
    print("codex-cli 0.153.0")
    raise SystemExit(0)
if args == ["login", "status"]:
    print("Logged in using ChatGPT", file=sys.stderr)
    raise SystemExit(0)
if args == ["debug", "models", "--bundled"]:
    print(json.dumps({"models": [{"slug": "gpt-6-astra"}]}))
    raise SystemExit(0)
if "exec" not in args:
    print("unexpected fake codex invocation", file=sys.stderr)
    raise SystemExit(77)
for name in (
    "OPENAI_API_KEY",
    "CODEX_API_KEY",
    "ANTHROPIC_API_KEY",
    "DASHSCOPE_API_KEY",
    "QWEN_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
):
    if os.getenv(name):
        print(f"provider credential leaked: {name}", file=sys.stderr)
        raise SystemExit(78)

mission = sys.stdin.read()
match = re.search(r"^experiment_project_id: (.+)$", mission, flags=re.MULTILINE)
if not match:
    print("missing project id", file=sys.stderr)
    raise SystemExit(79)
project_id = match.group(1).strip()
marker = "product_visible_project_state:\n"
if marker not in mission:
    print("missing product-visible state", file=sys.stderr)
    raise SystemExit(80)
initial_snapshot = json.loads(mission.split(marker, 1)[1])
noop = os.getenv("FAKE_CODEX_NOOP") == "1"

def emit(value):
    print(json.dumps(value, separators=(",", ":")), flush=True)

def mcp(item_id, tool, arguments, payload_text="{}"):
    emit({
        "type": "item.completed",
        "item": {
            "id": item_id,
            "type": "mcp_tool_call",
            "server": "hardware-splicer-backend",
            "tool": tool,
            "arguments": arguments,
            "result": {
                "content": [{"type": "text", "text": payload_text}],
                "structured_content": None,
            },
            "error": None,
            "status": "completed",
        },
    })

def gateway(operation_id, method, path, body):
    return json.dumps({
        "ok": True,
        "status_code": 200,
        "content_type": "application/json",
        "byte_length": 2,
        "sha256": "0" * 64,
        "headers": {"content-type": "application/json"},
        "body": body,
        "operation_id": operation_id,
        "method": method,
        "path": path,
    }, separators=(",", ":"))

emit({"type": "thread.started", "thread_id": "fake-astra-thread"})
emit({"type": "turn.started"})
mcp("1", "hs_backend_status", {})
mcp("2", "hs_backend_list_operations", {"text": "project"})
mcp("3", "hs_backend_describe_operation", {"operation_id": "save_project_snapshot"})

save_args = {
    "operation_id": "save_project_snapshot",
    "path_params": {"project_id": project_id},
    "json_body": {"snapshot": initial_snapshot, "expected_revision": 0},
}
mcp(
    "4",
    "hs_backend_call",
    save_args,
    gateway(
        "save_project_snapshot",
        "PUT",
        f"/v1/projects/{project_id}/snapshot",
        {
            "ok": True,
            "project": {
                "project_id": project_id,
                "revision": 1,
                "snapshot": initial_snapshot,
            },
        },
    ),
)

if noop:
    final_snapshot = initial_snapshot
    final_revision = 1
else:
    mcp("5", "hs_backend_describe_operation", {"operation_id": "plan_project"})
    plan_args = {
        "operation_id": "plan_project",
        "path_params": {"project_id": project_id},
        "json_body": {"expected_revision": 1, "intake": {}},
    }
    mcp(
        "6",
        "hs_backend_call",
        plan_args,
        gateway(
            "plan_project",
            "POST",
            f"/v1/projects/{project_id}/engineering/plan",
            {
                "ok": True,
                "project_id": project_id,
                "revision": 2,
                "plan": {"schema_version": "fake-plan"},
            },
        ),
    )
    final_snapshot = copy.deepcopy(initial_snapshot)
    final_snapshot.update({
        "currentStage": "guided_engineering_plan",
        "engineeringPlan": {
            "schema_version": "fake-plan",
            "authority_effect": "none",
        },
        "orderedSteps": [
            {
                "step_id": "resolve-dut-package",
                "kind": "identify_missing_evidence",
                "status": "proposed",
            }
        ],
        "missingInfo": [
            "Verify the exact DUT package and pinout before fabrication."
        ],
    })
    final_revision = 2

mcp("7", "hs_backend_describe_operation", {"operation_id": "get_project"})
read_body = {
    "ok": True,
    "project": {
        "schema_version": "hardware_splicer.project_snapshot.v1",
        "project_id": project_id,
        "revision": final_revision,
        "saved_at": "2026-09-11T00:00:00+00:00",
        "snapshot": final_snapshot,
        "metadata": {},
    },
}
mcp(
    "8",
    "hs_backend_call",
    {"operation_id": "get_project", "path_params": {"project_id": project_id}},
    gateway(
        "get_project",
        "GET",
        f"/v1/projects/{project_id}",
        read_body,
    ),
)
emit({
    "type": "item.completed",
    "item": {"id": "9", "type": "agent_message", "text": "done"},
})
emit({
    "type": "turn.completed",
    "usage": {
        "input_tokens": 101,
        "cached_input_tokens": 11,
        "cache_write_input_tokens": 0,
        "output_tokens": 31,
        "reasoning_output_tokens": 7,
    },
})
''',
        encoding="utf-8",
    )
    path.chmod(0o755)


def _fake_runner_command(
    *,
    script: Path,
    manifest: Path,
    fake_codex: Path,
    fake_mcp: Path,
) -> list[str]:
    return [
        sys.executable,
        str(script),
        "--manifest",
        str(manifest),
        "--codex-command",
        str(fake_codex),
        "--mcp-command",
        str(fake_mcp),
        "--execute",
        "--confirm-codex-allowance",
        CODEX_ALLOWANCE_CONFIRMATION,
        "--timeout-seconds",
        "60",
    ]


def test_full_runner_refuses_parent_api_key_before_fake_execution(tmp_path: Path) -> None:
    context, manifest = _prepared_case(tmp_path)
    fake_codex = tmp_path / "fake-codex"
    fake_mcp = tmp_path / "fake-hs-backend-mcp"
    _make_fake_codex(fake_codex)
    fake_mcp.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake_mcp.chmod(0o755)

    env = dict(os.environ)
    env["OPENAI_API_KEY"] = "must-not-reach-fake-codex"
    env["ANTHROPIC_API_KEY"] = "must-not-reach-fake-codex"
    script = Path(__file__).resolve().parents[1] / "scripts" / "run_codex_astra_case.py"
    completed = subprocess.run(
        _fake_runner_command(
            script=script,
            manifest=manifest,
            fake_codex=fake_codex,
            fake_mcp=fake_mcp,
        ),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert completed.returncode == 2, completed.stderr + completed.stdout
    refusal = json.loads(completed.stdout)
    assert refusal["reason"] == "zero-inference preflight failed"
    assert refusal["preflight"]["api_key_env_present"] == ["OPENAI_API_KEY"]
    assert refusal["preflight"]["astra_bundled_catalog_ok"] is True
    assert not (context.observer_dir / "CODEX_ASTRA_TRACE.jsonl").exists()


def test_full_runner_fake_live_path_succeeds_with_mission_progress(tmp_path: Path) -> None:
    context, manifest = _prepared_case(tmp_path)
    fake_codex = tmp_path / "fake-codex"
    fake_mcp = tmp_path / "fake-hs-backend-mcp"
    _make_fake_codex(fake_codex)
    fake_mcp.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake_mcp.chmod(0o755)

    env = dict(os.environ)
    for name in BLOCKED_PROVIDER_ENV:
        env.pop(name, None)
    script = Path(__file__).resolve().parents[1] / "scripts" / "run_codex_astra_case.py"
    completed = subprocess.run(
        _fake_runner_command(
            script=script,
            manifest=manifest,
            fake_codex=fake_codex,
            fake_mcp=fake_mcp,
        ),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr + completed.stdout
    result = json.loads(completed.stdout)
    assert result["status"] == "passed"
    assert result["codex_hard_truth_contract_pass"] is True
    assert result["codex_mission_progress_contract_pass"] is True
    assert result["codex_evaluation_ready_pass"] is True
    assert result["api_fallback"] is False
    assert result["provider_credentials_forwarded_to_runtime"] is False
    assert result["codex_usage"]["reasoning_output_tokens"] == 7
    audit = json.loads((context.observer_dir / "CODEX_ASTRA_AUDIT.json").read_text())
    assert audit["codex_backend_result_audit"]["final_project_readback"]["revision"] == 2
    assert audit["codex_mission_progress_audit"]["changed_mission_surfaces"]
    assert (context.observer_dir / "CODEX_ASTRA_TRACE.jsonl").is_file()
    assert not (context.observer_dir / "CODEX_ASTRA_LAST_MESSAGE.txt").exists()


def test_full_runner_rejects_noop_even_when_hard_truth_passes(tmp_path: Path) -> None:
    context, manifest = _prepared_case(tmp_path)
    fake_codex = tmp_path / "fake-codex"
    fake_mcp = tmp_path / "fake-hs-backend-mcp"
    _make_fake_codex(fake_codex)
    fake_mcp.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake_mcp.chmod(0o755)

    env = dict(os.environ)
    for name in BLOCKED_PROVIDER_ENV:
        env.pop(name, None)
    env["FAKE_CODEX_NOOP"] = "1"
    script = Path(__file__).resolve().parents[1] / "scripts" / "run_codex_astra_case.py"
    completed = subprocess.run(
        _fake_runner_command(
            script=script,
            manifest=manifest,
            fake_codex=fake_codex,
            fake_mcp=fake_mcp,
        ),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert completed.returncode == 9, completed.stderr + completed.stdout
    result = json.loads(completed.stdout)
    assert result["status"] == "failed"
    assert result["codex_hard_truth_contract_pass"] is True
    assert result["codex_mission_progress_contract_pass"] is False
    assert result["codex_evaluation_ready_pass"] is False
    audit = json.loads((context.observer_dir / "CODEX_ASTRA_AUDIT.json").read_text())
    assert audit["codex_mission_progress_audit"]["checks"][
        "substantive_project_operation_succeeded"
    ] is False
