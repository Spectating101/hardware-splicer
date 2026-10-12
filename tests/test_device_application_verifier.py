"""A partial/crashed host execution must never earn a successful result."""
import importlib.util
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest


def verifier():
    path = Path(__file__).resolve().parents[1] / "scripts/verify_device_application.py"
    spec = importlib.util.spec_from_file_location("device_application_verifier_tests", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("lane", ["host", "vendor"])
@pytest.mark.parametrize("fault", ["exit", "missing", "duplicate", "unknown", "finding", "truthy", "object", "bad_name", "json", "timeout"])
def test_bad_harness_results_fail_closed(tmp_path, monkeypatch, lane, fault):
    module = verifier()
    expected = module.HOST_SCENARIOS if lane == "host" else module.VENDOR_SCENARIOS
    rows = [{"scenario": name, "pass": True} for name in expected]
    exit_code = 0
    if fault == "exit":
        exit_code = 1
    elif fault == "missing":
        rows.pop()
    elif fault == "duplicate":
        rows[-1] = rows[0]
    elif fault == "unknown":
        rows[-1]["scenario"] = "not_expected"
    elif fault == "finding":
        rows[-1]["finding"] = True
    elif fault == "truthy":
        rows[-1]["pass"] = "true"
    elif fault == "object":
        rows[-1] = ["not an object"]
    elif fault == "bad_name":
        rows[-1]["scenario"] = []
    output = ("\n".join(json.dumps(row) for row in rows) + "\n").encode()
    if fault == "json":
        output = b"not json\n"
    monkeypatch.setattr(module, "vendor_libs_available", lambda _: True)
    monkeypatch.setattr(module.shutil, "which", lambda _: "/usr/bin/g++")

    def run(command, **kwargs):
        if command[-1] == "--version":
            return SimpleNamespace(returncode=0, stdout=b"g++ test\n", stderr=b"")
        if "-std=c++17" in command:
            return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")
        assert kwargs["timeout"] == 60
        if fault == "timeout":
            raise subprocess.TimeoutExpired(command, 60, output=output)
        return SimpleNamespace(returncode=exit_code, stdout=output, stderr=b"")

    monkeypatch.setattr(module.subprocess, "run", run)
    report, _ = module._run_host(tmp_path) if lane == "host" else module._run_vendor_host(tmp_path, tmp_path)
    assert report["pass"] is False and report["reason"]
    assert report["physical_correctness"] == "UNPROVEN"
    assert report["firmware_authorized"] is False and report["power_on_authorized"] is False


def test_complete_results_pass_only_with_successful_exit():
    module = verifier()
    for expected in (module.HOST_SCENARIOS, module.VENDOR_SCENARIOS):
        rows = [{"scenario": name, "pass": True} for name in expected]
        assert module._scenario_failure(rows, expected, 0) == ""
        assert module._scenario_failure(rows, expected, -11)


def test_relative_vendor_library_path_is_resolved_before_changing_compile_directory(tmp_path, monkeypatch):
    module = verifier()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(module, "vendor_libs_available", lambda _: True)
    monkeypatch.setattr(module.shutil, "which", lambda _: "/usr/bin/g++")
    rows = [{"scenario": name, "pass": True} for name in module.VENDOR_SCENARIOS]

    def run(command, **kwargs):
        if command[-1] == "--version":
            return SimpleNamespace(returncode=0, stdout=b"g++ test\n", stderr=b"")
        if "-std=c++17" in command:
            for name in module.VENDOR_LIB_DIRS:
                assert str(tmp_path / "libs" / name) in command
            return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")
        return SimpleNamespace(returncode=0, stdout=("\n".join(json.dumps(row) for row in rows)).encode(), stderr=b"")

    monkeypatch.setattr(module.subprocess, "run", run)
    report, _ = module._run_vendor_host(tmp_path / "project", Path("libs"))
    assert report["pass"] is True
