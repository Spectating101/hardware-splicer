"""Canonical resource-bounded entrypoint helpers for one live Codex/Astra case."""

from __future__ import annotations

import json
import os
import shlex
import shutil
import stat
import sys
from pathlib import Path
from typing import Mapping

from .codex_budgeted_mcp_proxy import (
    ASTRA_MAX_BACKEND_CALLS,
    ASTRA_MAX_MCP_TOOL_CALLS,
    ASTRA_MAX_REQUEST_BYTES,
)

ASTRA_DEFAULT_TIMEOUT_SECONDS = 300
ASTRA_MAX_TIMEOUT_SECONDS = 300
ASTRA_LAUNCHER_TEMP_ROOT = Path("/tmp")
_BUDGET_PROXY_MARKERS = (
    "hardware_splicer.codex_budgeted_mcp_proxy",
    "hs-astra-budgeted-mcp",
)


def clamp_timeout_seconds(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("timeout must be an integer number of seconds")
    if value < 30:
        raise ValueError("timeout must be at least 30 seconds")
    if value > ASTRA_MAX_TIMEOUT_SECONDS:
        raise ValueError(
            f"Astra one-case timeout may not exceed {ASTRA_MAX_TIMEOUT_SECONDS} seconds"
        )
    return value


def resolve_canonical_backend(command: str = "hs-backend-mcp", env: Mapping[str, str] | None = None) -> str:
    source_env = dict(os.environ if env is None else env)
    candidate = Path(command).expanduser()
    if candidate.is_absolute() or candidate.parent != Path("."):
        resolved = candidate.resolve(strict=False)
        if not resolved.is_file():
            raise FileNotFoundError(f"canonical HS MCP backend not found: {resolved}")
        _reject_nested_budget_proxy(resolved)
        return str(resolved)
    found = shutil.which(command, path=source_env.get("PATH"))
    if not found:
        raise FileNotFoundError(f"canonical HS MCP backend not found on PATH: {command}")
    resolved = Path(found).resolve()
    _reject_nested_budget_proxy(resolved)
    return str(resolved)


def _reject_nested_budget_proxy(command: Path) -> None:
    """Reject a governor passed where the raw canonical backend is required.

    The stdio relay is deliberately single-layer. Nesting two instances can leave both
    relays waiting on each other's line-reader lifecycle and prevent MCP initialize from
    completing. Generated launchers are small text files, so inspect only a bounded prefix;
    opaque binaries remain eligible canonical backend commands.
    """

    try:
        if command.stat().st_size > 65_536:
            return
        prefix = command.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return
    if any(marker in prefix for marker in _BUDGET_PROXY_MARKERS):
        raise ValueError(
            "--backend-command must be the raw canonical hs-backend-mcp executable, "
            "not an existing Astra budget proxy/launcher"
        )


def write_budgeted_mcp_launcher(
    path: str | os.PathLike[str],
    *,
    backend_command: str,
    python_command: str | None = None,
) -> Path:
    """Write an executable shim that can only start the budgeted MCP proxy."""

    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    # Preserve a virtualenv's interpreter path. Resolving the `python` symlink to the
    # system interpreter silently drops the environment that contains this package, and
    # Codex intentionally does not forward PYTHONPATH to MCP children by default.
    python = str(Path(python_command or sys.executable).expanduser().absolute())
    backend = str(Path(backend_command).expanduser().resolve())
    body = (
        "#!/bin/sh\n"
        "set -eu\n"
        "exec "
        + shlex.quote(python)
        + " -m hardware_splicer.codex_budgeted_mcp_proxy --backend-command "
        + shlex.quote(backend)
        + ' "$@"\n'
    )
    target.write_text(body, encoding="utf-8")
    target.chmod(0o700)
    return target


def validate_launcher(path: str | os.PathLike[str]) -> bool:
    candidate = Path(path).expanduser().resolve()
    if not candidate.is_file():
        return False
    mode = stat.S_IMODE(candidate.stat().st_mode)
    return mode == 0o700 and os.access(candidate, os.X_OK)


def build_delegated_runner_argv(
    *,
    runner_script: str | os.PathLike[str],
    manifest: str | os.PathLike[str],
    mcp_launcher: str | os.PathLike[str],
    timeout_seconds: int = ASTRA_DEFAULT_TIMEOUT_SECONDS,
    codex_command: str = "codex",
    execute: bool = False,
    confirmation: str | None = None,
) -> list[str]:
    timeout = clamp_timeout_seconds(timeout_seconds)
    argv = [
        sys.executable,
        str(Path(runner_script).expanduser().resolve()),
        "--manifest",
        str(Path(manifest).expanduser().resolve()),
        "--codex-command",
        codex_command,
        "--mcp-command",
        str(Path(mcp_launcher).expanduser().resolve()),
        "--timeout-seconds",
        str(timeout),
    ]
    if execute:
        argv.append("--execute")
        if confirmation is not None:
            argv.extend(["--confirm-codex-allowance", confirmation])
    return argv


def resource_guard_manifest(*, timeout_seconds: int) -> dict[str, object]:
    return {
        "schema_version": "hardware_splicer.codex_astra_resource_guard.v3",
        "timeout_seconds": clamp_timeout_seconds(timeout_seconds),
        "timeout_hard_max_seconds": ASTRA_MAX_TIMEOUT_SECONDS,
        "mcp_tool_calls_hard_max": ASTRA_MAX_MCP_TOOL_CALLS,
        "backend_calls_hard_max": ASTRA_MAX_BACKEND_CALLS,
        "mcp_request_bytes_hard_max": ASTRA_MAX_REQUEST_BYTES,
        "api_fallback": False,
        "exact_allowance_cost_guaranteed": False,
        "claim_boundary": (
            "These limits bound wall-clock and MCP-loop exposure for one prepared case. "
            "They do not guarantee an exact Codex allowance or token cost because model "
            "reasoning and provider accounting remain external."
        ),
    }


def write_resource_guard_manifest(path: str | os.PathLike[str], *, timeout_seconds: int) -> Path:
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(resource_guard_manifest(timeout_seconds=timeout_seconds), indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    return target
