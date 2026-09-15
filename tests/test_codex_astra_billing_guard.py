from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from hardware_splicer.codex_astra_runtime import (
    BLOCKED_PROVIDER_ENV,
    sanitized_runtime_environment,
)


def _fake_codex(path: Path) -> None:
    path.write_text(
        '''#!/usr/bin/env python3
import json
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
raise SystemExit(77)
''',
        encoding="utf-8",
    )
    path.chmod(0o755)


def test_codex_api_key_is_a_blocked_runtime_credential() -> None:
    assert "CODEX_API_KEY" in BLOCKED_PROVIDER_ENV
    clean = sanitized_runtime_environment(
        {
            "PATH": "/bin",
            "CODEX_API_KEY": "must-never-reach-codex-exec",
            "OPENAI_API_KEY": "also-blocked",
            "SAFE": "kept",
        }
    )
    assert "CODEX_API_KEY" not in clean
    assert "OPENAI_API_KEY" not in clean
    assert clean["SAFE"] == "kept"


def test_emitted_manual_launch_unsets_codex_api_key(tmp_path: Path) -> None:
    workspace = tmp_path / "cleanroom"
    repo = tmp_path / "hardware-splicer"
    workspace.mkdir()
    repo.mkdir()
    mission = workspace / "MISSION.txt"
    mission.write_text("model-visible mission only", encoding="utf-8")
    fake_codex = tmp_path / "codex"
    fake_mcp = tmp_path / "hs-backend-mcp"
    _fake_codex(fake_codex)
    fake_mcp.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake_mcp.chmod(0o755)

    env = dict(os.environ)
    env["CODEX_API_KEY"] = "dangerous-parent-key"
    script = Path(__file__).resolve().parents[1] / "scripts" / "preflight_codex_astra.py"
    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--workspace",
            str(workspace),
            "--hs-repo-root",
            str(repo),
            "--codex-command",
            str(fake_codex),
            "--mcp-command",
            str(fake_mcp),
            "--mission-file",
            str(mission),
            "--emit-launch-plan",
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr + completed.stdout
    payload = json.loads(completed.stdout)
    assert "CODEX_API_KEY" in payload["parent_provider_credentials_present"]
    assert "CODEX_API_KEY" in payload["launch_plan"]["environment_unsets"]
    assert "-u CODEX_API_KEY" in payload["launch_plan"]["shell_display"]
    assert "dangerous-parent-key" not in completed.stdout
    assert payload["live_execution_performed"] is False
    assert payload["codex_allowance_consumed_by_this_script"] is False
