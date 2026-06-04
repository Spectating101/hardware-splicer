import json
import subprocess

from src.intelligence import copilot_provider
from src.intelligence.copilot_provider import clean_copilot_output, copilot_provider_status


def test_clean_copilot_output_strips_usage_footer():
    cleaned = clean_copilot_output(
        "● COPILOT_OK\n\nTotal usage est: 0 Premium requests\nUsage by model:\n    gpt-4.1  1 input\n"
    )

    assert cleaned == "COPILOT_OK"


def test_copilot_status_reports_oauth_readiness_without_tokens(monkeypatch):
    monkeypatch.setenv("LY_COPILOT_TOKEN_1", "secret-token")
    monkeypatch.setattr(copilot_provider.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(
        copilot_provider,
        "_node_version_info",
        lambda: {
            "available": True,
            "version": "v18.20.8",
            "major": 18,
            "supported_for_copilot_cli": False,
        },
    )
    monkeypatch.setattr(copilot_provider, "_copilot_cli_runnable", lambda _path: True)
    monkeypatch.setattr(copilot_provider, "_gh_authenticated", lambda: True)

    status = copilot_provider_status("gpt-4.1")
    serialized = json.dumps(status)

    assert status["status"] == "ready"
    assert status["selected"]["node_runner"] == "npx -y node@20"
    assert status["providers"]["copilot_cli"]["gh_authenticated"] is True
    assert status["providers"]["copilot_cli"]["token_marker_configured"] is True
    assert "secret-token" not in serialized


def test_call_copilot_prompt_uses_non_mutating_cli_flags(monkeypatch):
    calls = {}
    monkeypatch.setenv("LY_COPILOT_TOKEN_1", "secret-token")
    monkeypatch.setattr(copilot_provider.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(copilot_provider, "_copilot_cli_runnable", lambda _path: True)
    monkeypatch.setattr(copilot_provider, "_gh_authenticated", lambda: True)

    def fake_run(cmd, **kwargs):
        if "--prompt" in cmd:
            calls["cmd"] = cmd
            return subprocess.CompletedProcess(cmd, 0, stdout="● {\"ok\": true}\nTotal usage est: 0\n", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="0.0.363", stderr="")

    monkeypatch.setattr(copilot_provider.subprocess, "run", fake_run)

    text, model = copilot_provider.call_copilot_prompt("Return JSON", model="gpt-4.1", timeout_seconds=1)

    assert text == '{"ok": true}'
    assert model == "copilot/gpt-4.1"
    assert "--disable-builtin-mcps" in calls["cmd"]
    assert "--no-custom-instructions" in calls["cmd"]
    assert "--allow-all-tools" not in calls["cmd"]
