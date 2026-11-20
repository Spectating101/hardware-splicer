"""The task script's exit status must reflect the verdict, not only exceptions."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_github_signal_task.py"


def _load():
    spec = importlib.util.spec_from_file_location("run_github_signal_task", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("verdict, code", [({"ok": True}, 0), ({"ok": False, "reason": "tool_blocked"}, 3), ({}, 3)])
def test_exit_status_follows_the_verdict(tmp_path, monkeypatch, capsys, verdict, code):
    module = _load()
    feed = tmp_path / "feed.json"
    feed.write_text("{}")
    monkeypatch.setattr(module, "run_task", lambda **kwargs: verdict)
    monkeypatch.setattr(sys, "argv", ["run_github_signal_task.py", "--feed", str(feed), "--objective", "x",
                                      "--checkout-base", str(tmp_path), "--out", str(tmp_path / "out")])
    assert module.main() == code
    assert json.loads(capsys.readouterr().out) == verdict
