"""Zero-inference preflight and launch planning for Codex/Astra HS experiments."""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

MIN_CODEX_VERSION = (0, 153, 0)
ASTRA_MODEL = "gpt-6-astra"
HS_MCP_SERVER_NAME = "hardware-splicer-backend"
HS_MCP_TOOLS = (
    "hs_backend_status",
    "hs_backend_list_operations",
    "hs_backend_describe_operation",
    "hs_backend_call",
)
FORBIDDEN_API_ENV = ("OPENAI_API_KEY",)
CHATGPT_STATUS_MARKER = "Logged in using ChatGPT"
API_STATUS_MARKERS = ("Logged in using API key", "API key")


@dataclass(frozen=True)
class CommandResult:
    argv: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class PreflightReport:
    codex_path: str | None
    codex_version: str | None
    codex_version_ok: bool
    auth_mode: str
    chatgpt_auth_ok: bool
    astra_bundled_catalog_ok: bool
    api_key_env_present: tuple[str, ...]
    workspace: str
    hs_repo_root: str
    workspace_isolated: bool
    mcp_command: str | None
    mcp_command_found: bool
    inference_performed: bool = False
    provider_network_probe_performed: bool = False

    @property
    def pass_(self) -> bool:
        return (
            self.codex_path is not None
            and self.codex_version_ok
            and self.chatgpt_auth_ok
            and self.astra_bundled_catalog_ok
            and not self.api_key_env_present
            and self.workspace_isolated
            and self.mcp_command_found
            and not self.inference_performed
            and not self.provider_network_probe_performed
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "schema": "hardware_splicer.codex_astra_preflight.v2",
            "pass": self.pass_,
            "codex_path": self.codex_path,
            "codex_version": self.codex_version,
            "minimum_codex_version": ".".join(map(str, MIN_CODEX_VERSION)),
            "codex_version_ok": self.codex_version_ok,
            "auth_mode": self.auth_mode,
            "chatgpt_auth_ok": self.chatgpt_auth_ok,
            "astra_bundled_catalog_ok": self.astra_bundled_catalog_ok,
            "bundled_catalog_refresh_performed": False,
            "api_key_env_present": list(self.api_key_env_present),
            "workspace": self.workspace,
            "hs_repo_root": self.hs_repo_root,
            "workspace_isolated": self.workspace_isolated,
            "mcp_command": self.mcp_command,
            "mcp_command_found": self.mcp_command_found,
            "inference_performed": self.inference_performed,
            "provider_network_probe_performed": self.provider_network_probe_performed,
            "claim_boundary": (
                "Passing preflight proves only local client/auth/bundled-model/isolation/MCP "
                "prerequisites. Bundled catalog presence does not prove account rollout or "
                "model entitlement. It does not prove Astra competence, engineering "
                "correctness, physical correctness, or physical authority."
            ),
        }


def _run(argv: Sequence[str], *, env: Mapping[str, str] | None = None) -> CommandResult:
    completed = subprocess.run(
        list(argv),
        capture_output=True,
        text=True,
        env=None if env is None else dict(env),
        check=False,
        timeout=20,
    )
    return CommandResult(
        argv=tuple(argv),
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def parse_codex_version(text: str) -> tuple[int, int, int] | None:
    match = re.search(r"(?<!\d)(\d+)\.(\d+)\.(\d+)(?!\d)", text)
    if not match:
        return None
    return tuple(int(value) for value in match.groups())


def version_is_supported(text: str) -> bool:
    parsed = parse_codex_version(text)
    return parsed is not None and parsed >= MIN_CODEX_VERSION


def classify_login_status(stdout: str, stderr: str = "") -> str:
    text = "\n".join((stdout, stderr))
    if CHATGPT_STATUS_MARKER in text:
        return "chatgpt"
    if any(marker in text for marker in API_STATUS_MARKERS):
        return "api_key"
    if "not logged in" in text.lower() or "not authenticated" in text.lower():
        return "not_authenticated"
    return "unknown"


def bundled_catalog_has_model(text: str, model: str = ASTRA_MODEL) -> bool:
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return False

    def walk(node: Any) -> bool:
        if isinstance(node, Mapping):
            if node.get("slug") == model or node.get("id") == model or node.get("model") == model:
                return True
            return any(walk(child) for child in node.values())
        if isinstance(node, Sequence) and not isinstance(node, (str, bytes, bytearray)):
            return any(walk(child) for child in node)
        return False

    return walk(value)


def _resolved(path: str | os.PathLike[str]) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def paths_are_disjoint(
    workspace: str | os.PathLike[str],
    hs_repo_root: str | os.PathLike[str],
) -> bool:
    work = _resolved(workspace)
    repo = _resolved(hs_repo_root)
    if work == repo:
        return False
    try:
        work.relative_to(repo)
        return False
    except ValueError:
        pass
    try:
        repo.relative_to(work)
        return False
    except ValueError:
        return True


def present_api_key_env(env: Mapping[str, str]) -> tuple[str, ...]:
    return tuple(name for name in FORBIDDEN_API_ENV if env.get(name))


def resolve_executable(command: str, env: Mapping[str, str] | None = None) -> str | None:
    candidate = Path(command).expanduser()
    if candidate.is_absolute() or candidate.parent != Path("."):
        return str(candidate.resolve(strict=False)) if candidate.exists() else None
    path_value = None if env is None else env.get("PATH")
    return shutil.which(command, path=path_value)


def shell_quote_argv(argv: Sequence[str]) -> str:
    return " ".join(shlex.quote(value) for value in argv)


def _toml_string(value: str) -> str:
    return json.dumps(value)


def _override(key: str, value: object) -> str:
    if isinstance(value, bool):
        encoded = "true" if value else "false"
    elif isinstance(value, (int, float)):
        encoded = str(value)
    elif isinstance(value, str):
        encoded = _toml_string(value)
    elif isinstance(value, Mapping):
        encoded_items: list[str] = []
        for item_key, item_value in value.items():
            if not isinstance(item_value, str):
                raise TypeError(
                    f"unsupported override map value for {key}: "
                    f"{type(item_value).__name__}"
                )
            encoded_items.append(
                f"{_toml_string(str(item_key))}={_toml_string(item_value)}"
            )
        encoded = "{" + ",".join(encoded_items) + "}"
    elif isinstance(value, Sequence):
        encoded = "[" + ",".join(_toml_string(str(item)) for item in value) + "]"
    else:
        raise TypeError(f"unsupported override value for {key}: {type(value).__name__}")
    return f"{key}={encoded}"


def build_cleanroom_overrides(
    *,
    workspace: str | os.PathLike[str],
    hs_repo_root: str | os.PathLike[str],
    mcp_command: str,
    mcp_args: Sequence[str] = (),
    model: str = ASTRA_MODEL,
    reasoning_effort: str = "low",
    extra_read_paths: Sequence[str | os.PathLike[str]] = (),
    extra_denied_paths: Sequence[str | os.PathLike[str]] = (),
) -> list[str]:
    work = str(_resolved(workspace))
    repo = str(_resolved(hs_repo_root))
    if not paths_are_disjoint(work, repo):
        raise ValueError("clean-room workspace must not contain or be contained by the HS repository")
    resolved_mcp = resolve_executable(mcp_command) or str(_resolved(mcp_command))
    profile = "hs-astra-cleanroom"
    server = f"mcp_servers.{HS_MCP_SERVER_NAME}"
    filesystem_rules = {
        ":minimal": "read",
        work: "write",
        **{str(_resolved(path)): "read" for path in extra_read_paths},
        repo: "deny",
        **{str(_resolved(path)): "deny" for path in extra_denied_paths},
    }
    overrides = [
        _override("forced_login_method", "chatgpt"),
        _override("model", model),
        _override("model_reasoning_effort", reasoning_effort),
        _override("approval_policy", "never"),
        _override("web_search", "disabled"),
        _override("suppress_unstable_features_warning", True),
        _override("features.plugins", False),
        _override("features.skip_host_skill_discovery", True),
        _override("default_permissions", profile),
        _override(f"permissions.{profile}.filesystem", filesystem_rules),
        _override(f"permissions.{profile}.network.enabled", False),
        _override(f"{server}.command", resolved_mcp),
        _override(f"{server}.args", list(mcp_args)),
        _override(f"{server}.required", True),
        _override(f"{server}.supports_parallel_tool_calls", False),
        _override(f"{server}.default_tools_approval_mode", "approve"),
        _override(f"{server}.enabled_tools", list(HS_MCP_TOOLS)),
        _override(f"{server}.startup_timeout_sec", 30),
        _override(f"{server}.tool_timeout_sec", 60),
    ]
    for tool in HS_MCP_TOOLS:
        limit = 8_000 if tool == "hs_backend_call" else 4_000
        overrides.append(_override(f"{server}.tools.{tool}.approval_mode", "approve"))
        overrides.append(_override(f"{server}.tools.{tool}.output_token_limit", limit))
    return overrides


def build_codex_exec_argv(
    *,
    workspace: str | os.PathLike[str],
    hs_repo_root: str | os.PathLike[str],
    mcp_command: str,
    prompt_file: str | os.PathLike[str],
    trace_file: str | os.PathLike[str],
    last_message_file: str | os.PathLike[str],
    mcp_args: Sequence[str] = (),
    model: str = ASTRA_MODEL,
    reasoning_effort: str = "low",
    codex_command: str = "codex",
    extra_read_paths: Sequence[str | os.PathLike[str]] = (),
    extra_denied_paths: Sequence[str | os.PathLike[str]] = (),
) -> list[str]:
    work = str(_resolved(workspace))
    prompt = _resolved(prompt_file)
    trace = _resolved(trace_file)
    last = _resolved(last_message_file)
    if prompt.parent != _resolved(workspace):
        raise ValueError("prompt_file must live directly inside the clean-room workspace")
    if trace.parent != _resolved(workspace):
        raise ValueError("trace_file must live directly inside the clean-room workspace")
    if last.parent != _resolved(workspace):
        raise ValueError("last_message_file must live directly inside the clean-room workspace")
    overrides = build_cleanroom_overrides(
        workspace=work,
        hs_repo_root=hs_repo_root,
        mcp_command=mcp_command,
        mcp_args=mcp_args,
        model=model,
        reasoning_effort=reasoning_effort,
        extra_read_paths=extra_read_paths,
        extra_denied_paths=extra_denied_paths,
    )
    argv = [codex_command]
    for item in overrides:
        argv.extend(["-c", item])
    argv.extend(
        [
            "exec",
            "--ignore-user-config",
            "--ignore-rules",
            "--skip-git-repo-check",
            "--ephemeral",
            "--json",
            "-m",
            model,
            "-C",
            work,
            "--output-last-message",
            str(last),
            "-",
        ]
    )
    return argv


def build_launch_environment(env: Mapping[str, str] | None = None) -> dict[str, str]:
    result = dict(os.environ if env is None else env)
    for name in FORBIDDEN_API_ENV:
        result.pop(name, None)
    return result


def run_zero_inference_preflight(
    *,
    workspace: str | os.PathLike[str],
    hs_repo_root: str | os.PathLike[str],
    codex_command: str = "codex",
    mcp_command: str = "hs-backend-mcp",
    env: Mapping[str, str] | None = None,
) -> PreflightReport:
    source_env = dict(os.environ if env is None else env)
    codex_path = resolve_executable(codex_command, source_env)
    mcp_path = resolve_executable(mcp_command, source_env)
    isolated = paths_are_disjoint(workspace, hs_repo_root)
    forbidden = present_api_key_env(source_env)

    version_text = None
    version_ok = False
    auth_mode = "unavailable"
    chatgpt_ok = False
    astra_bundled_ok = False
    if codex_path:
        clean_env = build_launch_environment(source_env)
        version_result = _run([codex_path, "--version"], env=clean_env)
        version_text = (version_result.stdout or version_result.stderr).strip() or None
        version_ok = version_result.returncode == 0 and version_is_supported(version_text or "")
        login_result = _run(
            [codex_path, "login", "status"],
            env=clean_env,
        )
        auth_mode = classify_login_status(login_result.stdout, login_result.stderr)
        chatgpt_ok = login_result.returncode == 0 and auth_mode == "chatgpt"
        catalog_result = _run(
            [codex_path, "debug", "models", "--bundled"],
            env=clean_env,
        )
        astra_bundled_ok = (
            catalog_result.returncode == 0
            and bundled_catalog_has_model(catalog_result.stdout, ASTRA_MODEL)
        )

    return PreflightReport(
        codex_path=codex_path,
        codex_version=version_text,
        codex_version_ok=version_ok,
        auth_mode=auth_mode,
        chatgpt_auth_ok=chatgpt_ok,
        astra_bundled_catalog_ok=astra_bundled_ok,
        api_key_env_present=forbidden,
        workspace=str(_resolved(workspace)),
        hs_repo_root=str(_resolved(hs_repo_root)),
        workspace_isolated=isolated,
        mcp_command=mcp_path,
        mcp_command_found=mcp_path is not None,
    )
