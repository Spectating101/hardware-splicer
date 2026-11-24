"""No-physical-authority Optiplex ERC worker signing and enrollment tests."""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

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


def test_public_optiplex_native_evidence_bundle_and_tamper_detection(tmp_path):
    from hardware_splicer.local_kicad_worker import verify_bundle
    import shutil
    bundle = (Path(__file__).resolve().parents[1] /
              "evidence/github_signals/optiplex_signed_erc_20261105")
    result = verify_bundle(bundle, Path(__file__).resolve().parents[1])
    assert result["ok"] is True
    assert result["signed_receipt_verified"] is True
    assert result["finding_count"] == 40
    assert result["severity_counts"]["warning"] == 40
    assert result["operator_enrollment_independently_proven"] is False
    copy = tmp_path / "bundle"
    shutil.copytree(bundle, copy)
    (copy / "erc.json").write_text("{}")
    with pytest.raises(worker.WorkerError, match="malformed|inconsistent"):
        verify_bundle(copy, Path(__file__).resolve().parents[1])


@pytest.mark.parametrize("violations", [[{"severity": "bogus"}], {}])
def test_exported_bundle_rejects_invalid_native_erc_findings(prepared, tmp_path, violations):
    import hashlib

    key, _, identity = prepared
    root = Path(__file__).resolve().parents[1]
    original = root / "evidence/github_signals/optiplex_signed_erc_20261105"
    body = json.loads((original / "receipt.json").read_text())["body"]
    raw = json.dumps({"$schema": "https://schemas.kicad.org/erc.v1.json",
                      "sheets": [{"violations": violations}]}).encode()
    body.update(worker_id=identity["worker_id"], report_sha256=hashlib.sha256(raw).hexdigest(),
                report_bytes=len(raw), finding_count=len(violations),
                severity_counts={"error": 0, "warning": 0, "exclusion": 0})
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "public_identity.json").write_text(json.dumps(identity))
    (bundle / "receipt.json").write_text(json.dumps(worker._sign(worker._private(key), body)))
    (bundle / "erc.json").write_bytes(raw)
    with pytest.raises(worker.WorkerError, match="malformed"):
        worker.verify_bundle(bundle, root)


ERC_SCHEMA = "https://schemas.kicad.org/erc.v1.json"
FAKE_SOURCE = b"fixed schematic bytes"


def _forge_job(ledger, key, identity, rid, report, monkeypatch, **overrides):
    """Write a correctly signed ERC job directory, optionally with bad fields.

    The worker holds the key, so a compromised or buggy worker can sign any
    body; the verifier must still reject what it cannot trust.
    """
    import hashlib

    monkeypatch.setattr(worker, "_source",
                        lambda workspace, source_ref=None: ("a" * 40, FAKE_SOURCE))
    raw = report if isinstance(report, bytes) else json.dumps(report).encode()
    try:
        parsed = json.loads(raw)
        found = [f for s in parsed["sheets"] for f in s["violations"]]
    except Exception:
        found = []
    counts = {k: sum(isinstance(f, dict) and f.get("severity") == k for f in found)
              for k in ("error", "warning", "exclusion")}
    body = {
        "schema_version": worker.SCHEMA, "kind": "erc_result", "request_id": rid,
        "worker_id": identity["worker_id"], "task": worker.CAPABILITY,
        "source_commit": "a" * 40, "source_path": worker.SOURCE,
        "input_sha256": hashlib.sha256(FAKE_SOURCE).hexdigest(),
        "state": "diagnostics_produced_not_design_approved",
        "erc_schema": ERC_SCHEMA, "kicad_version": "9.0.2",
        "report_sha256": hashlib.sha256(raw).hexdigest(), "report_bytes": len(raw),
        "finding_count": len(found), "severity_counts": counts,
        "design_approved": False, "hardware_connected": False,
        "fabrication_authorized": False, "physical_authority": False,
        "executed_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "heartbeat_sequence_at_execution": 1,
    }
    body.update(overrides)
    folder = ledger / "node_jobs" / rid
    folder.mkdir(parents=True)
    (folder / "erc.json").write_bytes(raw)
    (folder / "receipt.json").write_text(json.dumps(worker._sign(worker._private(key), body)))
    return body


RID = "hs-local-2222222222222222"
GOOD_REPORT = {"$schema": ERC_SCHEMA, "sheets": [{"violations": [{"severity": "warning"}]}]}


def test_verify_erc_accepts_well_formed_forged_job_baseline(prepared, tmp_path, monkeypatch):
    key, ledger, identity = prepared
    worker.heartbeat(ledger, key)
    _forge_job(ledger, key, identity, RID, GOOD_REPORT, monkeypatch)
    assert worker.verify_erc(ledger, tmp_path, RID)["finding_count"] == 1


@pytest.mark.parametrize("report", [
    {"$schema": ERC_SCHEMA, "sheets": [{"violations": [{"severity": "bogus"}]}]},
    {"$schema": ERC_SCHEMA, "sheets": [{"violations": {}}]},
    {"$schema": ERC_SCHEMA, "sheets": "nope"},
    {"$schema": ERC_SCHEMA, "sheets": [{}]},
    {"$schema": ERC_SCHEMA, "sheets": [{"violations": [{}]}]},
    {"$schema": ERC_SCHEMA, "sheets": [{"violations": ["x"]}]},
    {"$schema": ERC_SCHEMA, "sheets": [7]},
    {"$schema": "https://example.invalid/not-erc.json", "sheets": []},
    {"sheets": []},
    [],
], ids=str)
def test_verify_erc_rejects_malformed_signed_report(prepared, tmp_path, monkeypatch, report):
    key, ledger, identity = prepared
    worker.heartbeat(ledger, key)
    _forge_job(ledger, key, identity, RID, report, monkeypatch)
    with pytest.raises(worker.WorkerError):
        worker.verify_erc(ledger, tmp_path, RID)


def test_verify_erc_rejects_non_json_signed_report(prepared, tmp_path, monkeypatch):
    key, ledger, identity = prepared
    worker.heartbeat(ledger, key)
    _forge_job(ledger, key, identity, RID, b"\xff not json", monkeypatch)
    with pytest.raises(worker.WorkerError):
        worker.verify_erc(ledger, tmp_path, RID)


def test_verify_erc_rejects_report_schema_not_matching_receipt(prepared, tmp_path, monkeypatch):
    key, ledger, identity = prepared
    worker.heartbeat(ledger, key)
    _forge_job(ledger, key, identity, RID, GOOD_REPORT, monkeypatch, erc_schema="other")
    with pytest.raises(worker.WorkerError):
        worker.verify_erc(ledger, tmp_path, RID)


BAD_RECEIPT_FIELDS = [
    {"finding_count": True},
    {"finding_count": 1.0},
    {"severity_counts": {"error": False, "warning": 1, "exclusion": False}},
    {"severity_counts": {"error": 0.0, "warning": 1.0, "exclusion": 0.0}},
    {"severity_counts": {"error": 0, "warning": 1, "exclusion": 0, "extra": 0}},
    {"report_bytes": "x"},
    {"kicad_version": "9.fake"},
    {"kicad_version": 9.0},
    {"kicad_version": "10.0.1"},
    {"kicad_version": "9.0"},
    {"state": "design_approved"},
    {"state": None},
    {"source_commit": 123},
    {"source_commit": None},
    {"request_id": 5},
    {"request_id": "../../evil"},
    {"input_sha256": 7},
    {"report_sha256": ["x"]},
    {"heartbeat_sequence_at_execution": True},
    {"heartbeat_sequence_at_execution": "1"},
    {"design_approved": 0},
    {"physical_authority": 0},
]


@pytest.mark.parametrize("override", BAD_RECEIPT_FIELDS, ids=str)
def test_verify_erc_rejects_loosely_typed_receipt_fields(prepared, tmp_path, monkeypatch, override):
    key, ledger, identity = prepared
    worker.heartbeat(ledger, key)
    _forge_job(ledger, key, identity, RID, GOOD_REPORT, monkeypatch, **override)
    with pytest.raises(worker.WorkerError):
        worker.verify_erc(ledger, tmp_path, RID)


def test_non_string_worker_id_is_a_worker_error_not_a_type_error(prepared, tmp_path):
    key, ledger, identity = prepared
    folder = ledger / "node_jobs" / RID
    folder.mkdir(parents=True)
    (folder / "erc.json").write_text("{}")
    (folder / "receipt.json").write_text(json.dumps(
        {"body": {"worker_id": 123}, "signature": "00" * 64}))
    with pytest.raises(worker.WorkerError):
        worker.verify_erc(ledger, tmp_path, RID)
    with pytest.raises(worker.WorkerError):
        worker.accept_heartbeat(ledger, {"body": {"worker_id": ["x"]}, "signature": "00"})


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_BUNDLE = ROOT / "evidence/github_signals/optiplex_signed_erc_20261105"


def _forge_bundle(tmp_path, key, identity, report=None, **overrides):
    """Signed exported bundle for the real committed source, with optional bad fields."""
    import hashlib

    body = dict(json.loads((PUBLIC_BUNDLE / "receipt.json").read_text())["body"])
    report = report if report is not None else {
        "$schema": ERC_SCHEMA, "sheets": [{"violations": [{"severity": "warning"}]}]}
    raw = report if isinstance(report, bytes) else json.dumps(report).encode()
    body.update(worker_id=identity["worker_id"], report_sha256=hashlib.sha256(raw).hexdigest(),
                report_bytes=len(raw), finding_count=1,
                severity_counts={"error": 0, "warning": 1, "exclusion": 0},
                executed_utc=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"))
    body.update(overrides)
    bundle = tmp_path / "forged-bundle"
    bundle.mkdir()
    (bundle / "public_identity.json").write_text(json.dumps(identity))
    (bundle / "receipt.json").write_text(json.dumps(worker._sign(worker._private(key), body)))
    (bundle / "erc.json").write_bytes(raw)
    return bundle


def _verify_bundle(bundle, identity, workspace=ROOT, **kwargs):
    return worker.verify_bundle(bundle, workspace, **kwargs)


def test_forged_bundle_baseline_is_accepted(prepared, tmp_path):
    key, _, identity = prepared
    bundle = _forge_bundle(tmp_path, key, identity)
    assert _verify_bundle(bundle, identity)["finding_count"] == 1


@pytest.mark.parametrize("override", BAD_RECEIPT_FIELDS + [
    {"request_id": None}, {"state": "diagnostics_produced_not_design_approved_x"},
], ids=str)
def test_verify_bundle_rejects_loosely_typed_receipt_fields(prepared, tmp_path, override):
    key, _, identity = prepared
    bundle = _forge_bundle(tmp_path, key, identity, **override)
    with pytest.raises(worker.WorkerError):
        _verify_bundle(bundle, identity)


def test_verify_bundle_rejects_missing_request_id_and_state(prepared, tmp_path):
    import hashlib

    key, _, identity = prepared
    bundle = _forge_bundle(tmp_path, key, identity)
    body = json.loads((bundle / "receipt.json").read_text())["body"]
    for field in ("request_id", "state"):
        trimmed = {k: v for k, v in body.items() if k != field}
        (bundle / "receipt.json").write_text(json.dumps(worker._sign(worker._private(key), trimmed)))
        with pytest.raises(worker.WorkerError):
            _verify_bundle(bundle, identity)


def test_verify_bundle_non_string_signed_worker_id_is_worker_error(prepared, tmp_path):
    key, _, identity = prepared
    bundle = _forge_bundle(tmp_path, key, identity, worker_id=123)
    with pytest.raises(worker.WorkerError):
        _verify_bundle(bundle, identity)


def test_non_json_receipt_or_identity_is_a_worker_error(prepared, tmp_path):
    key, _, identity = prepared
    for name in ("receipt.json", "public_identity.json"):
        (tmp_path / name).mkdir()
        bundle = _forge_bundle(tmp_path / name, key, identity)
        (bundle / name).write_bytes(b"\xff{not json")
        with pytest.raises(worker.WorkerError):
            _verify_bundle(bundle, identity)


def _tiny_repo(tmp_path):
    import hashlib

    repo = tmp_path / "repo"
    source = repo / worker.SOURCE
    source.parent.mkdir(parents=True)
    source.write_bytes(b"committed schematic")
    for cmd in (["init", "-q"], ["add", "-A"],
                ["-c", "user.name=t", "-c", "user.email=t@example.invalid",
                 "commit", "-q", "-m", "x"]):
        subprocess.run(["git", "-C", str(repo), *cmd], check=True)
    commit = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], check=True,
                            capture_output=True, text=True).stdout.strip()
    return repo, commit, hashlib.sha256(b"committed schematic").hexdigest()


def test_verify_bundle_hashes_source_at_commit_not_working_tree(prepared, tmp_path):
    key, _, identity = prepared
    repo, commit, digest = _tiny_repo(tmp_path)
    bundle = _forge_bundle(tmp_path, key, identity, source_commit=commit, input_sha256=digest)
    # Local edits to the checked-out schematic must not break historical evidence.
    (repo / worker.SOURCE).write_bytes(b"locally edited schematic")
    result = _verify_bundle(bundle, identity, workspace=repo)
    assert result["source_bytes_match_commit"] is True
    assert "source_bytes_match_checkout" not in result


def test_verify_bundle_rejects_nonexistent_source_commit(prepared, tmp_path):
    key, _, identity = prepared
    # The working tree matches the signed digest, but the commit never existed.
    bundle = _forge_bundle(tmp_path, key, identity, source_commit="0" * 40)
    with pytest.raises(worker.WorkerError):
        _verify_bundle(bundle, identity)


def test_verify_bundle_rejects_commit_whose_source_differs_from_signed_digest(prepared, tmp_path):
    key, _, identity = prepared
    repo, commit, digest = _tiny_repo(tmp_path)
    bundle = _forge_bundle(tmp_path, key, identity, source_commit=commit, input_sha256="0" * 64)
    with pytest.raises(worker.WorkerError):
        _verify_bundle(bundle, identity, workspace=repo)
