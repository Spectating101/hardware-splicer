from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("hs_pc_bench_collect_t", ROOT / "bench_collect.py")
bc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bc)


def ok(stdout="", rc=0):
    return {"status": "ok", "rc": rc, "stdout": stdout, "stderr": "", "seconds": 0.0, "cmd": []}


# --- claim 1: a transient smartctl failure must not be read as "self-test finished"
def test_unparseable_smart_output_means_unknown_not_finished():
    assert bc.selftest_running("") is None
    assert bc.selftest_running("not json") is None
    assert bc.selftest_running(json.dumps({"ata_smart_data": {"self_test": {"status": {"value": 0}}}})) is False
    assert bc.selftest_running(json.dumps({"ata_smart_data": {"self_test": {"status": {"value": 0xF5}}}})) is True
    assert bc.selftest_running(json.dumps({"nvme_self_test_log": {"current_self_test_operation": {"value": 1}}})) is True


def test_selftest_polling_keeps_waiting_through_a_transient_failure(monkeypatch, tmp_path):
    answers = iter(["", "garbage", json.dumps({"ata_smart_data": {"self_test": {"status": {"value": 0xF1}}}}),
                    json.dumps({"ata_smart_data": {"self_test": {"status": {"value": 0}}}}),
                    json.dumps({"smart_status": {"passed": True}, "ata_smart_attributes": {"table": []}})])
    calls = []

    def fake_run(cmd, timeout=60):
        calls.append(cmd)
        if "-t" in cmd:
            return ok("Sending command: Start short self-test.\nSelf-test has begun\n")
        return ok(next(answers))
    monkeypatch.setattr(bc, "run", fake_run)
    monkeypatch.setattr(bc, "tool", lambda n: "/x/" + n)
    monkeypatch.setattr(bc, "disks", lambda: ["/dev/sda"])
    monkeypatch.setattr(bc.time, "sleep", lambda s: None)
    b = bc.Bundle(tmp_path, redact=False)
    bc.step_storage(b, selftest=True)
    polls = [c for c in calls if "-t" not in c]
    assert len(polls) >= 4, "stopped polling after a failed read instead of waiting for the test to finish"
    st = json.loads((tmp_path / "selftest_sda.json").read_text())
    assert st["began"] is True


# --- claim 2: ping target and raw output must not survive --redact-serials
def test_redaction_covers_ping_target_output_and_argv(monkeypatch, tmp_path):
    monkeypatch.setattr(bc, "tool", lambda n: "/x/" + n)
    monkeypatch.setattr(bc, "run", lambda cmd, timeout=60: ok("PING 192.168.1.1 (192.168.1.1) 56 bytes\n5 packets transmitted"))
    b = bc.Bundle(tmp_path, redact=True)
    bc.step_network(b, "192.168.1.1")
    blob = "".join(p.read_text() for p in tmp_path.iterdir())
    assert "192.168.1.1" not in blob
    assert "192.168.1.1" not in " ".join(bc.safe_argv(["--out", "x", "--ping-target", "192.168.1.1", "--redact-serials"]))


# --- claim 3: a failing blockdev must be recorded, not crash (may not crash today; hardened either way)
def test_verify_wipe_records_a_failed_size_read_instead_of_crashing(monkeypatch, tmp_path):
    def fake_run(cmd, timeout=60):
        if "blockdev" in cmd[0]:
            return {"status": "ok", "rc": 1, "stdout": "blockdev: cannot open /dev/sdz", "stderr": "", "seconds": 0, "cmd": cmd}
        return ok('{"signatures": []}')
    monkeypatch.setattr(bc, "run", fake_run)
    monkeypatch.setattr(bc, "tool", lambda n: "/x/" + n)
    b = bc.Bundle(tmp_path, redact=False)
    bc.verify_wipe(b, "/dev/sdz")
    rec = json.loads((tmp_path / "wipe_sdz.json").read_text())
    assert rec["size_bytes"] == 0 and rec["sampled_blocks"] == 0
    assert rec["signature_tool"] != "ok" or rec["hs_status"] == "size_unavailable"


# --- claim 4: never mix a new capture with a previous run's files
def test_collector_refuses_a_non_empty_output_directory(tmp_path):
    (tmp_path / "stale_thermal.json").write_text("{}")
    with pytest.raises(SystemExit) as e:
        bc.main(["--out", str(tmp_path), "--role", "control_host"])
    assert e.value.code not in (0, None)


# --- claim 5: the manifest must say which tool versions produced the measurements
def test_manifest_records_tool_versions_not_just_availability(tmp_path):
    out = tmp_path / "b"
    assert bc.main(["--out", str(out), "--role", "control_host", "--redact-serials"]) == 0
    man = json.loads((out / "manifest.json").read_text())
    assert isinstance(man.get("tool_versions"), dict) and man["tool_versions"]
    assert any(v for v in man["tool_versions"].values()), "at least one tool reports a version here"
    assert "python" in man["tool_versions"]
