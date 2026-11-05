"""No-physical-authority Optiplex ERC worker signing and enrollment tests."""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys

import pytest

from hardware_splicer import local_kicad_worker as worker


@pytest.fixture
def prepared(tmp_path):
    key = tmp_path / "identity"
    ledger = tmp_path / "ledger"
    identity = worker.create_identity(key)
    worker.enroll(ledger, key / "identity.json", approve=True)
    return key, ledger, identity


def test_identity_key_is_private_and_not_automatically_enrolled(tmp_path):
    key = tmp_path / "new-identity"
    i = worker.create_identity(key)
    assert i["worker_id"].startswith("hs-node-")
    assert (key / "identity.key").stat().st_mode & 0o077 == 0
    assert "private" not in (key / "identity.json").read_text()
    with pytest.raises(worker.WorkerError, match="overwrite"):
        worker.create_identity(key)
    with pytest.raises(worker.WorkerError, match="approve"):
        worker.enroll(tmp_path / "ledger", key / "identity.json")


def test_signed_heartbeat_replay_tamper_and_revocation(prepared):
    key, ledger, i = prepared
    assert worker.heartbeat(ledger, key)["last_seq"] == 1
    assert worker.heartbeat(ledger, key)["last_seq"] == 2
    with pytest.raises(worker.WorkerError, match="replayed"):
        worker.heartbeat(ledger, key, sequence=2)
    raw = worker._private(key)
    packet = worker._sign(raw, {
        "schema_version": worker.SCHEMA, "kind": "heartbeat",
        "worker_id": i["worker_id"], "sequence": 3,
        "sent_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "capability": worker.CAPABILITY, "physical_authority": False,
    })
    tampered = json.loads(json.dumps(packet))
    tampered["body"]["physical_authority"] = True
    with pytest.raises(worker.WorkerError, match="signature"):
        worker.accept_heartbeat(ledger, tampered)
    with pytest.raises(worker.WorkerError, match="approve"):
        worker.revoke(ledger, i["worker_id"])
    worker.revoke(ledger, i["worker_id"], approve=True)
    with pytest.raises(worker.WorkerError, match="revoked"):
        worker.accept_heartbeat(ledger, packet)
    with pytest.raises(worker.WorkerError, match="revoked"):
        worker.heartbeat(ledger, key)


def test_expired_and_future_heartbeat_refused(prepared):
    key, ledger, i = prepared
    old = dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=300)
    with pytest.raises(worker.WorkerError, match="expired"):
        worker.heartbeat(ledger, key, when=old)
    # Signed claims from the future must not bypass the admission gate.
    now = dt.datetime.now(dt.timezone.utc)
    future = worker._sign(worker._private(key), {
        "schema_version": worker.SCHEMA, "kind": "heartbeat",
        "worker_id": i["worker_id"], "sequence": 1,
        "sent_utc": (now + dt.timedelta(seconds=300)).isoformat(timespec="seconds"),
        "capability": worker.CAPABILITY, "physical_authority": False,
    })
    with pytest.raises(worker.WorkerError, match="expired"):
        worker.accept_heartbeat(ledger, future, now=now)


def test_unenrolled_key_and_untrusted_identity_cannot_execute(tmp_path):
    key = tmp_path / "identity"
    worker.create_identity(key)
    with pytest.raises(worker.WorkerError, match="not enrolled"):
        worker.heartbeat(tmp_path / "ledger", key)


def test_erc_produces_signed_real_schema_report_and_verifies(prepared, tmp_path, monkeypatch):
    key, ledger, i = prepared
    worker.heartbeat(ledger, key)
    monkeypatch.setattr(worker, "_source", lambda workspace, source_ref=None: ("a" * 40, b"fixed schematic bytes"))
    monkeypatch.setattr(worker, "KICAD_BIN", sys.executable)
    payload = {"$schema": "https://schemas.kicad.org/erc.v1.json",
               "sheets": [{"violations": [{"severity": "warning", "type": "lib_symbol_issues"},
                                          {"severity": "error", "type": "pin_conflict"}]}]}
    args_seen = []
    def runner(args, **kw):
        args_seen.append(args)
        if args[1:] == ["version"]:
            return subprocess.CompletedProcess(args, 0, stdout="9.0.2\n", stderr="")
        assert args[1:5] == ["sch", "erc", "--format", "json"]
        open(args[6], "w").write(json.dumps(payload))
        return subprocess.CompletedProcess(args, 0, stdout="Found 2 violations", stderr="")
    rid = "hs-local-1111111111111111"
    plan = worker.run_erc(ledger, key, tmp_path, execute=False, request_id=rid,
                          run_fn=runner)
    assert plan["state"] == "prepared"
    assert len(args_seen) == 0
    result = worker.run_erc(ledger, key, tmp_path, execute=True, request_id=rid,
                            run_fn=runner)
    assert result["finding_count"] == 2
    assert result["severity_counts"] == {"error": 1, "warning": 1, "exclusion": 0}
    assert result["design_approved"] is False
    verified = worker.verify_erc(ledger, tmp_path, rid)
    assert verified["signature_verified"] is True
    assert verified["finding_count"] == 2
    with pytest.raises(worker.WorkerError, match="duplicate"):
        worker.run_erc(ledger, key, tmp_path, execute=True, request_id=rid,
                       run_fn=runner)
    folder = ledger / "node_jobs" / rid
    (folder / "erc.json").write_text("{}")
    with pytest.raises(worker.WorkerError, match="integrity"):
        worker.verify_erc(ledger, tmp_path, rid)


def test_no_signed_heartbeat_no_local_execution(prepared, tmp_path, monkeypatch):
    key, ledger, _ = prepared
    monkeypatch.setattr(worker, "_source", lambda workspace, source_ref=None: ("a" * 40, b"fixed schematic bytes"))
    with pytest.raises(worker.WorkerError, match="heartbeat"):
        worker.run_erc(ledger, key, tmp_path, execute=True)


def test_legacy_remote_dispatch_stays_separate():
    from hardware_splicer.github_signal_remote_dispatch import TASKS
    assert worker.CAPABILITY not in TASKS
    assert worker.KICAD_BIN == "/usr/bin/kicad-cli"
