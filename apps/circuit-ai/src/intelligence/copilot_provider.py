"""GitHub Copilot CLI provider for local engine testing.

This adapter shells out to the installed Copilot CLI using the machine's local
GitHub/Copilot OAuth state. It is intentionally text-only and denies built-in
MCP/tools by default so engine calls cannot mutate the repo.
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from typing import Any, Dict, Iterable, List, Optional, Tuple


DEFAULT_COPILOT_MODEL = "gpt-4.1"
DEFAULT_COPILOT_TIMEOUT_SECONDS = 90


def _has_any_env(names: Iterable[str]) -> bool:
    return any(bool(os.environ.get(name)) for name in names)


def _node_version_info() -> Dict[str, Any]:
    node_path = shutil.which("node")
    if not node_path:
        return {"available": False, "version": None, "major": None, "supported_for_copilot_cli": False}
    try:
        result = subprocess.run(
            [node_path, "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except Exception:
        return {"available": True, "version": None, "major": None, "supported_for_copilot_cli": False}
    version = (result.stdout or result.stderr or "").strip()
    major = None
    if version.startswith("v"):
        try:
            major = int(version[1:].split(".", 1)[0])
        except ValueError:
            major = None
    return {
        "available": True,
        "version": version or None,
        "major": major,
        "supported_for_copilot_cli": bool(major is not None and major >= 20),
    }


def _runner_prefix() -> List[str]:
    configured = os.environ.get("COPILOT_NODE_RUNNER")
    if configured:
        return shlex.split(configured)
    if _node_version_info().get("supported_for_copilot_cli"):
        return []
    if shutil.which("npx"):
        return ["npx", "-y", "node@20"]
    return []


def _version_command(copilot_path: str) -> List[str]:
    return [*_runner_prefix(), copilot_path, "--version"]


def _prompt_command(copilot_path: str, *, prompt: str, model: str) -> List[str]:
    return [
        *_runner_prefix(),
        copilot_path,
        "--prompt",
        prompt,
        "--model",
        model,
        "--stream",
        "off",
        "--no-custom-instructions",
        "--disable-builtin-mcps",
        "--log-level",
        "error",
    ]


def _gh_authenticated() -> bool:
    gh = shutil.which("gh")
    if not gh:
        return False
    try:
        result = subprocess.run(
            [gh, "auth", "status"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return False
    return result.returncode == 0


def _copilot_cli_runnable(copilot_path: str) -> bool:
    try:
        result = subprocess.run(
            _version_command(copilot_path),
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except Exception:
        return False
    return result.returncode == 0


def copilot_provider_status(model: Optional[str] = None) -> Dict[str, Any]:
    """Return safe readiness metadata without exposing tokens."""

    copilot_path = shutil.which("copilot")
    runner = _runner_prefix()
    command_runnable = bool(copilot_path and _copilot_cli_runnable(copilot_path))
    token_marker = _has_any_env(("COPILOT_GITHUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN")) or any(
        key.startswith("LY_COPILOT_TOKEN_") and bool(value)
        for key, value in os.environ.items()
    )
    gh_authenticated = _gh_authenticated()
    blockers: List[str] = []
    if not copilot_path:
        blockers.append("copilot CLI is not installed")
    if not runner and not _node_version_info().get("supported_for_copilot_cli"):
        blockers.append("Copilot CLI requires Node >=20 or COPILOT_NODE_RUNNER/npx node@20")
    if copilot_path and not command_runnable:
        blockers.append("copilot CLI could not run under the selected Node runner")
    if not (token_marker or gh_authenticated):
        blockers.append("no local GitHub/Copilot auth marker is configured")

    ready = not blockers
    return {
        "status": "ready" if ready else "not_ready",
        "ready_for_live_model": ready,
        "selected": {
            "provider": "copilot" if ready else None,
            "model": model or os.environ.get("COPILOT_MODEL") or DEFAULT_COPILOT_MODEL,
            "command": "copilot" if copilot_path else None,
            "node_runner": " ".join(runner) if runner else "system-node",
        },
        "providers": {
            "copilot_cli": {
                "ready": ready,
                "command_available": bool(copilot_path),
                "command_runnable": command_runnable,
                "gh_authenticated": gh_authenticated,
                "token_marker_configured": token_marker,
                "node": _node_version_info(),
            }
        },
        "blockers": blockers,
        "capabilities": {
            "text_reasoning": ready,
            "structured_json_reasoning": ready,
            "vision_image_input": False,
            "repo_mutation_allowed": False,
            "model_claims_are_advisory": True,
            "secrets_returned": False,
        },
    }


def clean_copilot_output(stdout: str, stderr: str = "") -> str:
    """Strip Copilot CLI usage footer and bullet marker from prompt output."""

    text = "\n".join(part for part in (stdout, stderr) if part).strip()
    kept: List[str] = []
    skip_usage = False
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            if kept and not skip_usage:
                kept.append("")
            continue
        if stripped.startswith("Total usage est:"):
            skip_usage = True
            continue
        if stripped.startswith("Total duration"):
            continue
        if stripped.startswith("Total code changes:"):
            continue
        if stripped.startswith("Usage by model:"):
            skip_usage = True
            continue
        if skip_usage and (stripped.startswith("gpt-") or stripped.startswith("claude-")):
            continue
        if stripped.startswith("Model call failed:"):
            kept.append(stripped)
            continue
        if stripped.startswith("● "):
            kept.append(stripped[2:].strip())
        else:
            kept.append(line)
    return "\n".join(kept).strip()


def call_copilot_prompt(
    prompt: str,
    *,
    model: Optional[str] = None,
    timeout_seconds: Optional[float] = None,
) -> Tuple[str, str]:
    """Call local Copilot CLI and return cleaned text plus model id."""

    selected_model = model or os.environ.get("COPILOT_MODEL") or DEFAULT_COPILOT_MODEL
    copilot_path = shutil.which("copilot")
    if not copilot_path:
        raise RuntimeError("copilot CLI is not installed")
    status = copilot_provider_status(selected_model)
    if not status.get("ready_for_live_model"):
        raise RuntimeError("; ".join(status.get("blockers") or ["copilot provider is not ready"]))

    timeout = float(timeout_seconds or os.environ.get("COPILOT_TIMEOUT_SECONDS") or DEFAULT_COPILOT_TIMEOUT_SECONDS)
    try:
        result = subprocess.run(
            _prompt_command(copilot_path, prompt=prompt, model=selected_model),
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"copilot CLI timed out after {timeout:.0f}s") from exc
    output = clean_copilot_output(result.stdout or "", result.stderr or "")
    if result.returncode != 0:
        raise RuntimeError(output[:500] or f"copilot CLI exited with status {result.returncode}")
    if "requested model is not supported" in output.lower():
        raise RuntimeError(output[:500])
    return output, f"copilot/{selected_model}"
