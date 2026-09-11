"""Fail-closed stdio MCP governor for the one-shot Codex/Astra experiment.

This proxy does not implement Hardware-Splicer operations. It relays JSON-RPC traffic to
the canonical ``hs-backend-mcp`` child process while enforcing a deliberately small call
budget before any tool request reaches that child. The limit is about resource exposure,
not engineering authority.
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import signal
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, TextIO

ASTRA_MAX_MCP_TOOL_CALLS = 20
ASTRA_MAX_BACKEND_CALLS = 8
ASTRA_MAX_REQUEST_BYTES = 262_144

_ALLOWED_TOOLS = {
    "hs_backend_status",
    "hs_backend_list_operations",
    "hs_backend_describe_operation",
    "hs_backend_call",
}
_BUDGET_ERROR_CODE = -32098
_POLICY_ERROR_CODE = -32097


@dataclass
class ToolBudget:
    max_tool_calls: int = ASTRA_MAX_MCP_TOOL_CALLS
    max_backend_calls: int = ASTRA_MAX_BACKEND_CALLS
    tool_calls: int = 0
    backend_calls: int = 0

    def admit(self, name: str) -> tuple[bool, str | None]:
        if name not in _ALLOWED_TOOLS:
            return False, f"tool {name!r} is outside the Hardware-Splicer clean-room allowlist"
        next_total = self.tool_calls + 1
        next_backend = self.backend_calls + (1 if name == "hs_backend_call" else 0)
        if next_total > self.max_tool_calls:
            return False, (
                f"MCP tool-call budget exhausted: requested call {next_total}, "
                f"hard limit is {self.max_tool_calls}"
            )
        if next_backend > self.max_backend_calls:
            return False, (
                f"hs_backend_call budget exhausted: requested backend call {next_backend}, "
                f"hard limit is {self.max_backend_calls}"
            )
        self.tool_calls = next_total
        self.backend_calls = next_backend
        return True, None

    def snapshot(self) -> dict[str, int]:
        return {
            "tool_calls_used": self.tool_calls,
            "tool_calls_limit": self.max_tool_calls,
            "backend_calls_used": self.backend_calls,
            "backend_calls_limit": self.max_backend_calls,
        }


def classify_client_line(raw: str, budget: ToolBudget) -> tuple[str, dict[str, Any] | None]:
    """Return ``forward`` or ``deny`` plus a safe JSON-RPC denial when applicable."""

    encoded_size = len(raw.encode("utf-8"))
    if encoded_size > ASTRA_MAX_REQUEST_BYTES:
        return "deny", _error_response(
            request_id=None,
            code=_POLICY_ERROR_CODE,
            message=(
                f"MCP client message exceeds hard request-size limit: "
                f"{encoded_size} > {ASTRA_MAX_REQUEST_BYTES} bytes"
            ),
            budget=budget,
        )
    try:
        message = json.loads(raw)
    except json.JSONDecodeError:
        return "deny", _error_response(
            request_id=None,
            code=_POLICY_ERROR_CODE,
            message="MCP client message is not valid JSON",
            budget=budget,
        )
    if not isinstance(message, Mapping):
        return "deny", _error_response(
            request_id=None,
            code=_POLICY_ERROR_CODE,
            message="MCP client message must be a JSON object",
            budget=budget,
        )
    if message.get("method") != "tools/call":
        return "forward", None

    request_id = message.get("id")
    params = message.get("params")
    if not isinstance(params, Mapping):
        return "deny", _error_response(
            request_id=request_id,
            code=_POLICY_ERROR_CODE,
            message="MCP tools/call params must be an object",
            budget=budget,
        )
    name = params.get("name")
    if not isinstance(name, str) or not name:
        return "deny", _error_response(
            request_id=request_id,
            code=_POLICY_ERROR_CODE,
            message="MCP tools/call requires a non-empty tool name",
            budget=budget,
        )
    admitted, reason = budget.admit(name)
    if admitted:
        return "forward", None
    code = _POLICY_ERROR_CODE if name not in _ALLOWED_TOOLS else _BUDGET_ERROR_CODE
    return "deny", _error_response(
        request_id=request_id,
        code=code,
        message=reason or "MCP tool call denied",
        budget=budget,
    )


def _error_response(
    *,
    request_id: Any,
    code: int,
    message: str,
    budget: ToolBudget,
) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {
            "code": code,
            "message": message,
            "data": {
                "schema_version": "hardware_splicer.codex_mcp_budget_refusal.v1",
                **budget.snapshot(),
                "api_fallback": False,
                "physical_authority_granted": False,
            },
        },
    }


def _reader(stream: TextIO, events: queue.Queue[tuple[str, str | None]], kind: str) -> None:
    try:
        for line in stream:
            events.put((kind, line))
    finally:
        events.put((kind + "_eof", None))


def _terminate(child: subprocess.Popen[str]) -> None:
    if child.poll() is not None:
        return
    child.terminate()
    try:
        child.wait(timeout=2)
    except subprocess.TimeoutExpired:
        child.kill()
        child.wait(timeout=2)


def run_proxy(
    *,
    backend_command: str,
    backend_args: list[str],
    budget: ToolBudget,
) -> int:
    child = subprocess.Popen(
        [backend_command, *backend_args],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        env=dict(os.environ),
    )
    assert child.stdin is not None
    assert child.stdout is not None
    assert child.stderr is not None

    events: queue.Queue[tuple[str, str | None]] = queue.Queue()
    stdin_thread = threading.Thread(
        target=_reader,
        args=(sys.stdin, events, "client"),
        daemon=True,
    )
    stdout_thread = threading.Thread(
        target=_reader,
        args=(child.stdout, events, "backend"),
        daemon=True,
    )
    stderr_thread = threading.Thread(
        target=_reader,
        args=(child.stderr, events, "backend_stderr"),
        daemon=True,
    )
    stdin_thread.start()
    stdout_thread.start()
    stderr_thread.start()

    shutting_down = False

    def stop(_signum: int, _frame: object) -> None:
        nonlocal shutting_down
        shutting_down = True
        _terminate(child)

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(sig, stop)
        except (ValueError, OSError):
            pass

    backend_stdout_eof = False
    while not shutting_down:
        if child.poll() is not None and backend_stdout_eof:
            return int(child.returncode or 0)
        try:
            kind, line = events.get(timeout=0.2)
        except queue.Empty:
            continue

        if kind == "backend":
            assert line is not None
            sys.stdout.write(line)
            sys.stdout.flush()
            continue
        if kind == "backend_stderr":
            assert line is not None
            sys.stderr.write(line)
            sys.stderr.flush()
            continue
        if kind == "backend_eof":
            backend_stdout_eof = True
            continue
        if kind == "backend_stderr_eof":
            continue
        if kind == "client_eof":
            try:
                child.stdin.close()
            except OSError:
                pass
            try:
                return child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                _terminate(child)
                return 88
        if kind != "client" or line is None:
            continue

        action, denial = classify_client_line(line, budget)
        if action == "deny":
            sys.stdout.write(json.dumps(denial, separators=(",", ":")) + "\n")
            sys.stdout.flush()
            # Disconnect immediately after a hard policy/budget breach. The MCP server is
            # marked required by the Codex experiment, so continued reasoning cannot turn a
            # denied over-budget session into a passing run.
            _terminate(child)
            return 87
        try:
            child.stdin.write(line)
            child.stdin.flush()
        except (BrokenPipeError, OSError):
            _terminate(child)
            return 86

    _terminate(child)
    return 128


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Relay canonical HS MCP stdio with a hard one-case tool-call budget."
    )
    parser.add_argument("--backend-command", default="hs-backend-mcp")
    parser.add_argument("backend_arg", nargs="*")
    args = parser.parse_args()
    backend = Path(args.backend_command).expanduser()
    command = str(backend.resolve()) if backend.is_absolute() else args.backend_command
    return run_proxy(
        backend_command=command,
        backend_args=list(args.backend_arg),
        budget=ToolBudget(),
    )


if __name__ == "__main__":
    raise SystemExit(main())
