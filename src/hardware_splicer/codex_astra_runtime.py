"""Fail-closed runtime planning for one Codex/Astra Hardware-Splicer case."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .codex_astra_case import build_codex_case_package, frozen_case_instructions
from .codex_astra_preflight import (
    ASTRA_MODEL,
    HS_MCP_SERVER_NAME,
    build_codex_exec_argv,
    build_launch_environment,
    paths_are_disjoint,
)

CODEX_ALLOWANCE_CONFIRMATION = "I_ACCEPT_CODEX_ALLOWANCE_USAGE"
BLOCKED_PROVIDER_ENV = (
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "DASHSCOPE_API_KEY",
    "QWEN_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
)

_MCP_OFFLINE_ENV = {
    "HARDWARE_SPLICER_OFFLINE_LLM": "1",
    "HARDWARE_SPLICER_OFFLINE_VISION": "1",
    "HARDWARE_SPLICER_OFFLINE_SALVAGE": "1",
    "HARDWARE_SPLICER_OFFLINE_COMPOSE": "1",
    "HARDWARE_SPLICER_OFFLINE_PHRASE_EXPAND": "1",
    "HARDWARE_SPLICER_SKIP_VISION_LIVE": "1",
    "HARDWARE_SPLICER_AUTOROUTE": "0",
    "HARDWARE_SPLICER_JLC_ENRICH": "0",
    "HARDWARE_SPLICER_QWEN_BUILD_PICK": "0",
    "HARDWARE_SPLICER_QWEN_MODULE_PICK": "0",
    "HARDWARE_SPLICER_QWEN_COMPOSE": "0",
    "HARDWARE_SPLICER_QWEN_WORKSHOP": "0",
    "HARDWARE_SPLICER_LLM_FIRST": "0",
    "QWEN_DISABLED": "1",
}


@dataclass(frozen=True)
class RuntimeContext:
    manifest_path: Path
    observer_dir: Path
    workspace: Path
    mission_file: Path
    snapshot_file: Path
    instructions_file: Path
    backend_project_root: Path
    hs_repo_root: Path
    experiment_project_id: str
    case_id: str


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object in {path}")
    return value


def _path(value: Any, *, field: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"runtime manifest field {field} must be a non-empty path")
    return Path(value).expanduser().resolve()


def validate_runtime_manifest(manifest_path: str | os.PathLike[str]) -> RuntimeContext:
    manifest_file = Path(manifest_path).expanduser().resolve()
    manifest = _load_json(manifest_file)
    observer = manifest_file.parent
    workspace = _path(manifest.get("model_visible_workspace"), field="model_visible_workspace")
    mission = _path(manifest.get("mission_file"), field="mission_file")
    snapshot = _path(manifest.get("snapshot_file"), field="snapshot_file")
    instructions = _path(
        manifest.get("developer_instructions_file"),
        field="developer_instructions_file",
    )
    backend_root = _path(manifest.get("backend_project_root"), field="backend_project_root")
    repo = _path(manifest.get("hs_repo_root"), field="hs_repo_root")
    project_id = str(manifest.get("experiment_project_id") or "").strip()
    case_id = str(manifest.get("case_id") or "").strip()
    if not project_id or not case_id:
        raise ValueError("runtime manifest requires experiment_project_id and case_id")

    for first, second, label in (
        (workspace, observer, "workspace/observer"),
        (workspace, repo, "workspace/repository"),
        (observer, repo, "observer/repository"),
    ):
        if not paths_are_disjoint(first, second):
            raise ValueError(f"{label} paths must be disjoint")
    if mission.parent != workspace or mission.name != "MISSION.txt":
        raise ValueError("MISSION.txt must be the only canonical model-visible mission path")
    visible_entries = sorted(path.name for path in workspace.iterdir())
    if visible_entries != ["MISSION.txt"]:
        raise ValueError(
            "model-visible workspace must contain exactly MISSION.txt before execution"
        )
    if not backend_root.is_dir() or any(backend_root.iterdir()):
        raise ValueError("backend project root must exist and be empty before execution")
    if backend_root.parent != observer:
        raise ValueError("backend project root must live directly inside observer directory")
    if snapshot.parent != observer or instructions.parent != observer:
        raise ValueError("snapshot and developer instructions must remain observer-only")

    expected = build_codex_case_package(
        case_id=case_id,
        experiment_project_id=project_id,
    )
    expected_visible = expected["model_visible"]
    expected_outer = expected["observer_only"]
    if mission.read_text(encoding="utf-8") != expected_visible["mission_text"]:
        raise ValueError("MISSION.txt no longer matches the frozen case protocol")
    if instructions.read_text(encoding="utf-8") != expected_visible["developer_instructions"]:
        raise ValueError("developer instructions no longer match the frozen case protocol")
    if _load_json(snapshot) != expected_outer["snapshot"]:
        raise ValueError("observer snapshot no longer matches the frozen case")
    for field in ("snapshot_sha256", "input_sha256", "instructions_sha256"):
        if manifest.get(field) != expected_outer[field]:
            raise ValueError(f"runtime manifest {field} no longer matches the frozen case")
    if manifest.get("outer_labels_visible_to_model") is not False:
        raise ValueError("runtime manifest must keep outer labels invisible to the model")

    return RuntimeContext(
        manifest_path=manifest_file,
        observer_dir=observer,
        workspace=workspace,
        mission_file=mission,
        snapshot_file=snapshot,
        instructions_file=instructions,
        backend_project_root=backend_root,
        hs_repo_root=repo,
        experiment_project_id=project_id,
        case_id=case_id,
    )


def blocked_provider_env_names(env: Mapping[str, str]) -> tuple[str, ...]:
    return tuple(name for name in BLOCKED_PROVIDER_ENV if env.get(name))


def sanitized_runtime_environment(
    env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    result = build_launch_environment(os.environ if env is None else env)
    for name in BLOCKED_PROVIDER_ENV:
        result.pop(name, None)
    return result


def _toml_override(key: str, value: str) -> str:
    return key + "=" + json.dumps(value)


def build_single_case_runtime_argv(
    context: RuntimeContext,
    *,
    codex_command: str,
    mcp_command: str,
) -> list[str]:
    placeholder_trace = context.workspace / ".observer-trace-placeholder"
    placeholder_last = context.workspace / ".observer-last-placeholder"
    argv = build_codex_exec_argv(
        workspace=context.workspace,
        hs_repo_root=context.hs_repo_root,
        mcp_command=mcp_command,
        prompt_file=context.mission_file,
        trace_file=placeholder_trace,
        last_message_file=placeholder_last,
        model=ASTRA_MODEL,
        reasoning_effort="low",
        codex_command=codex_command,
    )
    server = f"mcp_servers.{HS_MCP_SERVER_NAME}.env"
    profile = "permissions.hs-astra-cleanroom.filesystem"
    injected = [
        _toml_override("developer_instructions", frozen_case_instructions()),
        _toml_override(
            f'{profile}.{json.dumps(str(context.observer_dir))}',
            "deny",
        ),
        _toml_override(
            f"{server}.HARDWARE_SPLICER_PROJECT_ROOT",
            str(context.backend_project_root),
        ),
    ]
    injected.extend(
        _toml_override(f"{server}.{name}", value)
        for name, value in sorted(_MCP_OFFLINE_ENV.items())
    )
    expanded = [argv[0]]
    for override in injected:
        expanded.extend(["-c", override])
    expanded.extend(argv[1:])

    # JSONL already contains the terminal agent message. Avoid asking Codex itself to
    # write any observer artifact; the outer runner owns all trace/audit persistence.
    last_index = expanded.index("--output-last-message")
    del expanded[last_index : last_index + 2]
    return expanded


def validate_execution_acknowledgement(
    *,
    execute: bool,
    confirmation: str | None,
) -> None:
    if not execute:
        return
    if confirmation != CODEX_ALLOWANCE_CONFIRMATION:
        raise ValueError(
            "live Codex execution requires exact confirmation="
            f"{CODEX_ALLOWANCE_CONFIRMATION!r}"
        )


def runtime_plan(
    context: RuntimeContext,
    *,
    argv: list[str],
    source_env: Mapping[str, str],
) -> dict[str, Any]:
    return {
        "schema_version": "hardware_splicer.codex_astra_runtime_plan.v1",
        "model": ASTRA_MODEL,
        "case_id": context.case_id,
        "experiment_project_id": context.experiment_project_id,
        "workspace": str(context.workspace),
        "observer_dir": str(context.observer_dir),
        "backend_project_root": str(context.backend_project_root),
        "argv": argv,
        "provider_credentials_present_in_parent_env": list(
            blocked_provider_env_names(source_env)
        ),
        "provider_credentials_forwarded_to_runtime": False,
        "internal_hs_provider_access_disabled": True,
        "model_filesystem_denies_observer_directory": True,
        "codex_writes_observer_artifacts": False,
        "single_case_only": True,
        "api_fallback": False,
        "execution_performed": False,
        "physical_authority_granted": False,
    }
