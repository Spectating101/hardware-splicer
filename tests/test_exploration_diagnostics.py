"""A scenario that cannot clear because CadQuery is unusable must say so, not only "claimable=False"."""

import importlib.util
import json
import stat
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def harness(tmp_path_factory):
    out = tmp_path_factory.mktemp("exploration")
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("HARDWARE_SPLICER_EXPLORATION_OUT", str(out))
        spec = importlib.util.spec_from_file_location("exploration_test_under_test", ROOT / "scripts" / "exploration_test.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


def _python(tmp_path, *, exit_code, stderr=""):
    script = tmp_path / "fake-python"
    script.write_text(f"#!/bin/sh\necho '{stderr}' >&2\nexit {exit_code}\n", encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    return script


def _result(tmp_path, *, compile_ok=True, claimable=False):
    path = tmp_path / "SCENARIO_RESULT.json"
    path.write_text(json.dumps({"compile_ok": compile_ok, "project_authority": {"claimable": claimable}}), encoding="utf-8")
    return path


def _proc(code):
    return subprocess.CompletedProcess(args=[], returncode=code, stdout="", stderr="")


def test_a_failing_scenario_names_the_cadquery_import_error(harness, tmp_path, monkeypatch):
    monkeypatch.setenv("SPLICER3D_PYTHON", str(_python(tmp_path, exit_code=1, stderr="ImportError: libGL.so.1: cannot open shared object file")))
    ok, detail = harness._scenario_passes(Path("closed_pan_tilt_mechatronics_project.json"), _result(tmp_path), _proc(1))
    assert not ok
    assert "compile_ok=True claimable=False exit=1" in detail
    assert "cannot import cadquery: ImportError: libGL.so.1: cannot open shared object file" in detail


def test_a_failing_scenario_adds_nothing_when_cadquery_imports(harness, tmp_path, monkeypatch):
    monkeypatch.setenv("SPLICER3D_PYTHON", str(_python(tmp_path, exit_code=0)))
    ok, detail = harness._scenario_passes(Path("some_scenario.json"), _result(tmp_path), _proc(1))
    assert not ok
    assert detail == "compile_ok=True claimable=False exit=1"


def test_a_passing_scenario_is_not_probed(harness, tmp_path, monkeypatch):
    monkeypatch.setenv("SPLICER3D_PYTHON", str(tmp_path / "does-not-exist"))
    ok, detail = harness._scenario_passes(Path("some_scenario.json"), _result(tmp_path, claimable=True), _proc(0))
    assert ok
    assert detail == "compile_ok=True claimable=True exit=0"
