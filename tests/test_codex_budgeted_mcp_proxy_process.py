from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _fake_backend(path: Path) -> Path:
    path.write_text(
        r'''#!/usr/bin/env python3
import json
import sys
for line in sys.stdin:
    request = json.loads(line)
    response = {
        "jsonrpc": "2.0",
        "id": request.get("id"),
        "result": {
            "forwarded_method": request.get("method"),
            "forwarded_tool": (request.get("params") or {}).get("name"),
        },
    }
    print(json.dumps(response, separators=(",", ":")), flush=True)
''',
        encoding="utf-8",
    )
    path.chmod(0o700)
    return path


def _start_proxy(tmp_path: Path) -> subprocess.Popen[str]:
    backend = _fake_backend(tmp_path / "fake-backend")
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "hardware_splicer.codex_budgeted_mcp_proxy",
            "--backend-command",
            str(backend),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )


def _call(process: subprocess.Popen[str], request_id: int, name: str) -> dict:
    assert process.stdin is not None
    assert process.stdout is not None
    request = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {"name": name, "arguments": {}},
    }
    process.stdin.write(json.dumps(request) + "\n")
    process.stdin.flush()
    line = process.stdout.readline()
    assert line, "proxy closed stdout before producing a response"
    return json.loads(line)


def _cleanup(process: subprocess.Popen[str]) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)


def test_process_relays_twenty_tool_calls_then_hard_disconnects(tmp_path: Path) -> None:
    process = _start_proxy(tmp_path)
    try:
        for request_id in range(1, 21):
            response = _call(process, request_id, "hs_backend_status")
            assert response["id"] == request_id
            assert response["result"]["forwarded_tool"] == "hs_backend_status"
        denial = _call(process, 21, "hs_backend_status")
        assert denial["id"] == 21
        assert denial["error"]["code"] == -32098
        assert denial["error"]["data"]["tool_calls_used"] == 20
        assert denial["error"]["data"]["tool_calls_limit"] == 20
        assert denial["error"]["data"]["api_fallback"] is False
        assert process.wait(timeout=3) == 87
    finally:
        _cleanup(process)


def test_process_relays_eight_backend_calls_then_hard_disconnects(tmp_path: Path) -> None:
    process = _start_proxy(tmp_path)
    try:
        for request_id in range(1, 9):
            response = _call(process, request_id, "hs_backend_call")
            assert response["result"]["forwarded_tool"] == "hs_backend_call"
        denial = _call(process, 9, "hs_backend_call")
        assert denial["error"]["code"] == -32098
        assert denial["error"]["data"]["backend_calls_used"] == 8
        assert denial["error"]["data"]["backend_calls_limit"] == 8
        assert process.wait(timeout=3) == 87
    finally:
        _cleanup(process)


def test_process_unknown_tool_is_policy_disconnect(tmp_path: Path) -> None:
    process = _start_proxy(tmp_path)
    try:
        denial = _call(process, 1, "read_repo_source")
        assert denial["error"]["code"] == -32097
        assert denial["error"]["data"]["tool_calls_used"] == 0
        assert process.wait(timeout=3) == 87
    finally:
        _cleanup(process)
