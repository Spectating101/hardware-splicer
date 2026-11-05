"""An opt-in, source-pinned KiCad ERC worker with Ed25519 evidence receipts.

Separate from the GitHub Actions dispatcher: registering this read-only worker
does NOT authorize a GitHub self-hosted runner or any physical device.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import (
    Encoding, NoEncryption, PrivateFormat, PublicFormat,
)

from .github_signal_worker_registry import allocation_lock

SCHEMA = "hardware_splicer.local_kicad_worker.v1"
CAPABILITY = "kicad_erc_fixed"
SOURCE = "hardware/reference_designs/spi_flash_adapter_v1/spi_flash_adapter_v1.kicad_sch"
NODE_ID = re.compile(r"^hs-node-[0-9a-f]{16}$")
REQUEST_ID = re.compile(r"^hs-local-[0-9a-f]{16}$")
SHA40 = re.compile(r"^[0-9a-f]{40}$")
KEYDIR_PRIVATE = "identity.key"
KEYDIR_PUBLIC = "identity.json"
KICAD_BIN = "/usr/bin/kicad-cli"
HB_MAX_SECONDS = 120


class WorkerError(ValueError):
    pass


def _canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def _public_hex(key: Ed25519PublicKey) -> str:
    return key.public_bytes(Encoding.Raw, PublicFormat.Raw).hex()


def _id(public_hex: str) -> str:
    return "hs-node-" + hashlib.sha256(bytes.fromhex(public_hex)).hexdigest()[:16]


def _private(key_dir: Path) -> Ed25519PrivateKey:
    path = key_dir / KEYDIR_PRIVATE
    if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o077:
        raise WorkerError("private key missing or group/world accessible")
    raw = path.read_bytes()
    if len(raw) != 32:
        raise WorkerError("private key format invalid")
    return Ed25519PrivateKey.from_private_bytes(raw)


def create_identity(key_dir: Path) -> dict[str, Any]:
    if key_dir.is_symlink() or key_dir.exists():
        raise WorkerError("identity directory exists; refusing overwrite")
    key_dir.mkdir(mode=0o700, parents=True)
    key = Ed25519PrivateKey.generate()
    raw = key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    private = key_dir / KEYDIR_PRIVATE
    try:
        fd = os.open(str(private), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as out:
            out.write(raw)
            out.flush()
            os.fsync(out.fileno())
        result = {"schema_version": SCHEMA, "worker_id": _id(_public_hex(key.public_key())),
                  "public_key": _public_hex(key.public_key()),
                  "claimed_capabilities": [CAPABILITY],
                  "physical_authority": False}
        (key_dir / KEYDIR_PUBLIC).write_bytes(_canonical(result) + b"\n")
        return result
    except BaseException:
        raise


def _validate_public(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "schema_version", "worker_id", "public_key",
        "claimed_capabilities", "physical_authority",
    }:
        raise WorkerError("worker public identity schema invalid")
    try:
        pub = bytes.fromhex(value["public_key"])
        if len(pub) != 32:
            raise ValueError("invalid key length")
        Ed25519PublicKey.from_public_bytes(pub)
        expected = _id(value["public_key"])
    except (ValueError, TypeError) as exc:
        raise WorkerError("worker public identity key invalid") from exc
    if (value["schema_version"] != SCHEMA or
        value["worker_id"] != expected or not NODE_ID.fullmatch(expected) or
        value["claimed_capabilities"] != [CAPABILITY] or
        value["physical_authority"] is not False):
        raise WorkerError("worker identity or capabilities invalid")
    return value


def _registry_path(ledger: Path) -> Path:
    if ledger.is_symlink():
        raise WorkerError("worker ledger root symlink forbidden")
    return ledger / "local_worker_nodes.json"


def _read_nodes(ledger: Path) -> dict[str, Any]:
    path = _registry_path(ledger)
    if path.is_symlink():
        raise WorkerError("worker registry symlink forbidden")
    if not path.exists():
        return {"schema_version": SCHEMA, "nodes": []}
    if not path.is_file() or path.stat().st_size > 64_000:
        raise WorkerError("worker registry invalid or oversized")
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise WorkerError("worker registry JSON invalid") from exc
    if (not isinstance(data, dict) or data.get("schema_version") != SCHEMA or
        not isinstance(data.get("nodes"), list) or len(data["nodes"]) > 8):
        raise WorkerError("worker registry schema invalid")
    ids = set()
    for node in data["nodes"]:
        if not isinstance(node, dict) or not isinstance(node.get("identity"), dict):
            raise WorkerError("worker enrollment invalid")
        pub = _validate_public(node["identity"])
        if pub["worker_id"] in ids:
            raise WorkerError("duplicate worker identity")
        ids.add(pub["worker_id"])
        if (node.get("state") not in ("approved", "revoked") or
            type(node.get("last_seq")) is not int or node["last_seq"] < 0 or
            (node.get("last_seen_utc") is not None and
             not isinstance(node.get("last_seen_utc"), str))):
            raise WorkerError("worker enrollment state invalid")
    return data


def _save_nodes(ledger: Path, data: dict[str, Any]) -> None:
    dest = _registry_path(ledger)
    fd, temp = tempfile.mkstemp(prefix=".local-worker-", dir=ledger)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(_canonical(data) + b"\n")
            out.flush()
            os.fsync(out.fileno())
        if dest.is_symlink():
            raise WorkerError("worker registry symlink forbidden")
        os.replace(temp, dest)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def enroll(ledger: Path, identity_file: Path, *, approve: bool = False) -> dict[str, Any]:
    if approve is not True:
        raise WorkerError("enrollment requires explicit operator --approve")
    if identity_file.is_symlink() or identity_file.stat().st_size > 4096:
        raise WorkerError("unsafe public identity file")
    identity = _validate_public(json.loads(identity_file.read_text()))
    with allocation_lock(ledger):
        data = _read_nodes(ledger)
        if len(data["nodes"]) >= 8 or any(
            x["identity"]["worker_id"] == identity["worker_id"] for x in data["nodes"]
        ):
            raise WorkerError("worker already enrolled or capacity reached")
        row = {"identity": identity, "state": "approved", "last_seq": 0,
               "last_seen_utc": None}
        data["nodes"].append(row)
        _save_nodes(ledger, data)
        return row


def revoke(ledger: Path, worker_id: str, *, approve: bool = False) -> dict[str, Any]:
    if approve is not True:
        raise WorkerError("revocation requires explicit --approve")
    if not NODE_ID.fullmatch(worker_id):
        raise WorkerError("invalid worker id")
    with allocation_lock(ledger):
        data = _read_nodes(ledger)
        node = next((x for x in data["nodes"] if x["identity"]["worker_id"] == worker_id), None)
        if node is None:
            raise WorkerError("worker not enrolled")
        node["state"] = "revoked"
        node["last_seen_utc"] = None
        _save_nodes(ledger, data)
        return node


def _lookup(ledger: Path, worker_id: str) -> dict[str, Any]:
    if not NODE_ID.fullmatch(worker_id):
        raise WorkerError("invalid worker id")
    node = next((n for n in _read_nodes(ledger)["nodes"]
                 if n["identity"]["worker_id"] == worker_id), None)
    if node is None:
        raise WorkerError("worker not enrolled")
    return node


def _sign(key: Ed25519PrivateKey, body: dict[str, Any]) -> dict[str, Any]:
    return {"body": body, "signature": key.sign(_canonical(body)).hex()}


def _check_signature(identity: dict[str, Any], message: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(message, dict) or set(message) != {"body", "signature"}:
        raise WorkerError("signed worker message schema invalid")
    body = message["body"]
    if not isinstance(body, dict):
        raise WorkerError("signed worker body invalid")
    try:
        sig = bytes.fromhex(message["signature"])
        if len(sig) != 64:
            raise ValueError("invalid signature length")
        Ed25519PublicKey.from_public_bytes(
            bytes.fromhex(identity["public_key"])
        ).verify(sig, _canonical(body))
    except (InvalidSignature, ValueError, KeyError, TypeError) as exc:
        raise WorkerError("worker signature verification failed") from exc
    if not isinstance(body, dict) or body.get("worker_id") != identity["worker_id"]:
        raise WorkerError("worker signed identity mismatch")
    return body


def heartbeat(ledger: Path, key_dir: Path, *, when: dt.datetime | None = None,
              sequence: int | None = None) -> dict[str, Any]:
    """Sign and ingest a bounded liveness proof. No implicit key registration."""
    key = _private(key_dir)
    worker_id = _id(_public_hex(key.public_key()))
    current = when or dt.datetime.now(dt.timezone.utc)
    current = current.astimezone(dt.timezone.utc)
    node = _lookup(ledger, worker_id)
    next_seq = node["last_seq"] + 1 if sequence is None else sequence
    message = _sign(key, {
        "schema_version": SCHEMA, "kind": "heartbeat", "worker_id": worker_id,
        "sequence": next_seq, "sent_utc": current.isoformat(timespec="seconds"),
        "capability": CAPABILITY, "physical_authority": False,
    })
    # Verify against receiver time, never against the sender's claimed time.
    return accept_heartbeat(ledger, message)


def accept_heartbeat(ledger: Path, message: dict[str, Any],
                     *, now: dt.datetime | None = None) -> dict[str, Any]:
    current = (now or dt.datetime.now(dt.timezone.utc)).astimezone(dt.timezone.utc)
    with allocation_lock(ledger):
        body = message.get("body") if isinstance(message, dict) else None
        worker_id = body.get("worker_id", "") if isinstance(body, dict) else ""
        node = _lookup(ledger, worker_id)
        if node["state"] != "approved":
            raise WorkerError("worker revoked or not approved")
        body = _check_signature(node["identity"], message)
        if (body.get("schema_version") != SCHEMA or body.get("kind") != "heartbeat"
            or body.get("capability") != CAPABILITY or body.get("physical_authority") is not False
            or type(body.get("sequence")) is not int
            or body["sequence"] <= node["last_seq"]):
            raise WorkerError("invalid/replayed worker heartbeat")
        try:
            timestamp = dt.datetime.fromisoformat(body["sent_utc"])
            if timestamp.utcoffset() is None:
                raise ValueError("naive timestamp")
            age = abs((current - timestamp).total_seconds())
        except (KeyError, ValueError, TypeError) as exc:
            raise WorkerError("heartbeat timestamp malformed") from exc
        if age > 90:
            raise WorkerError("heartbeat expired or from future")
        node["last_seq"] = body["sequence"]
        node["last_seen_utc"] = current.isoformat(timespec="seconds")
        data = _read_nodes(ledger)
        for i, row in enumerate(data["nodes"]):
            if row["identity"]["worker_id"] == worker_id:
                data["nodes"][i] = node
        _save_nodes(ledger, data)
        return {"worker_id": worker_id, "state": "approved",
                "last_seq": node["last_seq"], "last_seen_utc": node["last_seen_utc"],
                "heartbeat_signature_verified": True, "physical_authority": False}


def _require_online(ledger: Path, worker_id: str) -> dict[str, Any]:
    node = _lookup(ledger, worker_id)
    if node["state"] != "approved":
        raise WorkerError("worker revoked")
    stamp = node["last_seen_utc"]
    if not stamp:
        raise WorkerError("signed heartbeat is required before execution")
    try:
        seen = dt.datetime.fromisoformat(stamp)
        age = (dt.datetime.now(dt.timezone.utc) - seen).total_seconds()
    except ValueError as exc:
        raise WorkerError("invalid stored heartbeat") from exc
    if age < 0 or age > HB_MAX_SECONDS:
        raise WorkerError("worker heartbeat stale; send a fresh signed heartbeat")
    return node


def _git(workspace: Path, *args: str) -> bytes:
    try:
        p = subprocess.run(["git", "-C", str(workspace), *args], check=True,
                           capture_output=True, timeout=20)
        return p.stdout
    except (OSError, subprocess.SubprocessError) as exc:
        raise WorkerError("cannot resolve approved committed source") from exc


def _source(workspace: Path, source_ref: str | None = None) -> tuple[str, bytes]:
    sha = source_ref or _git(workspace, "rev-parse", "HEAD").decode().strip()
    if not SHA40.fullmatch(sha):
        raise WorkerError("invalid pinned source commit")
    raw = _git(workspace, "show", f"{sha}:{SOURCE}")
    reference = workspace / SOURCE
    if (len(raw) > 12 * 1024 * 1024 or not raw or
        (source_ref is None and
         (reference.is_symlink() or not reference.is_file()
          or reference.read_bytes() != raw))):
        raise WorkerError("local source is modified, unsafe or oversized")
    return sha, raw


def run_erc(ledger: Path, key_dir: Path, workspace: Path, *,
            execute: bool = False, request_id: str | None = None,
            run_fn: Any = subprocess.run) -> dict[str, Any]:
    key = _private(key_dir)
    worker_id = _id(_public_hex(key.public_key()))
    node = _require_online(ledger, worker_id)
    sha, raw = _source(workspace)
    rid = request_id or ("hs-local-" + secrets.token_hex(8))
    if not REQUEST_ID.fullmatch(rid):
        raise WorkerError("invalid fixed ERC request ID")
    planned = {"request_id": rid, "worker_id": worker_id, "task": CAPABILITY,
               "source_commit": sha, "input_sha256": hashlib.sha256(raw).hexdigest(),
               "source_path": SOURCE, "physical_authority": False,
               "state": "prepared"}
    if not execute:
        return planned
    with allocation_lock(ledger):
        _require_online(ledger, worker_id)
        jobs = ledger / "node_jobs"
        if jobs.is_symlink():
            raise WorkerError("worker job storage symlink forbidden")
        jobs.mkdir(mode=0o700, exist_ok=True)
        destination = jobs / rid
        if destination.exists() or destination.is_symlink():
            raise WorkerError("duplicate local job ID")
        destination.mkdir(mode=0o700)
    try:
        with tempfile.TemporaryDirectory(prefix="hs-erc-") as td:
            tmp = Path(td)
            path = tmp / "spi_flash_adapter_v1.kicad_sch"
            path.write_bytes(raw)
            report = tmp / "erc.json"
            if not Path(KICAD_BIN).is_file():
                raise WorkerError("reviewed KiCad CLI binary unavailable")
            vers = run_fn([KICAD_BIN, "version"], capture_output=True, text=True,
                          timeout=20, check=False)
            version = str(vers.stdout).strip()
            if vers.returncode != 0 or not re.fullmatch(r"9\.\d+\.\d+", version):
                raise WorkerError("KiCad major version not approved (requires v9)")
            cmd = [KICAD_BIN, "sch", "erc", "--format", "json", "-o",
                   str(report), str(path)]
            proc = run_fn(cmd, capture_output=True, text=True, timeout=120, check=False)
            if proc.returncode != 0 or not report.is_file() or report.stat().st_size > 2_000_000:
                raise WorkerError("KiCad ERC did not produce bounded diagnostic output")
            payload = json.loads(report.read_bytes())
            if (not isinstance(payload, dict) or
                payload.get("$schema") != "https://schemas.kicad.org/erc.v1.json"
                or not isinstance(payload.get("sheets"), list)):
                raise WorkerError("KiCad ERC report schema invalid")
            findings = []
            for sheet in payload["sheets"]:
                if not isinstance(sheet, dict) or not isinstance(sheet.get("violations"), list):
                    raise WorkerError("KiCad ERC sheet result invalid")
                findings.extend(sheet["violations"])
            if any(not isinstance(f, dict) or f.get("severity") not in
                   ("error", "warning", "exclusion") for f in findings):
                raise WorkerError("KiCad ERC violation result invalid")
            counts = {k: sum(f["severity"] == k for f in findings)
                      for k in ("error", "warning", "exclusion")}
            report_bytes = report.read_bytes()
            receipt = {
                **planned, "schema_version": SCHEMA, "kind": "erc_result",
                "state": "diagnostics_produced_not_design_approved",
                "kicad_version": version,
                "erc_schema": payload["$schema"],
                "report_sha256": hashlib.sha256(report_bytes).hexdigest(),
                "report_bytes": len(report_bytes), "finding_count": len(findings),
                "severity_counts": counts, "design_approved": False,
                "hardware_connected": False, "fabrication_authorized": False,
                "executed_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                "heartbeat_sequence_at_execution": node["last_seq"],
            }
            signed = _sign(key, receipt)
            _check_signature(node["identity"], signed)
            # A revocation occurring while KiCad runs must block output acceptance.
            with allocation_lock(ledger):
                _require_online(ledger, worker_id)
            (destination / "erc.json").write_bytes(report_bytes)
            (destination / "receipt.json").write_bytes(_canonical(signed) + b"\n")
            return {**receipt, "signature_verified": True, "artifact_directory": str(destination)}
    except BaseException:
        shutil.rmtree(destination)
        raise


def verify_erc(ledger: Path, workspace: Path, request_id: str) -> dict[str, Any]:
    if not REQUEST_ID.fullmatch(request_id):
        raise WorkerError("invalid local job ID")
    folder = ledger / "node_jobs" / request_id
    receipt_file = folder / "receipt.json"
    report_file = folder / "erc.json"
    if (folder.is_symlink() or receipt_file.is_symlink() or report_file.is_symlink() or
        not receipt_file.is_file() or not report_file.is_file() or
        receipt_file.stat().st_size > 40_000 or report_file.stat().st_size > 2_000_000):
        raise WorkerError("signed ERC evidence missing or unsafe")
    packet = json.loads(receipt_file.read_bytes())
    signed_body = packet.get("body") if isinstance(packet, dict) else None
    worker_id = signed_body.get("worker_id", "") if isinstance(signed_body, dict) else ""
    node = _lookup(ledger, worker_id)
    body = _check_signature(node["identity"], packet)
    sha, raw = _source(workspace, body.get("source_commit"))
    if (body.get("schema_version") != SCHEMA or body.get("kind") != "erc_result"
        or body.get("request_id") != request_id or body.get("task") != CAPABILITY
        or body.get("state") != "diagnostics_produced_not_design_approved"
        or body.get("source_commit") != sha
        or body.get("source_path") != SOURCE
        or body.get("input_sha256") != hashlib.sha256(raw).hexdigest()
        or body.get("report_sha256") != hashlib.sha256(report_file.read_bytes()).hexdigest()
        or body.get("report_bytes") != report_file.stat().st_size
        or body.get("physical_authority") is not False
        or body.get("hardware_connected") is not False
        or body.get("fabrication_authorized") is not False
        or body.get("design_approved") is not False):
        raise WorkerError("ERC receipt, source pin or report integrity mismatch")
    report = json.loads(report_file.read_bytes())
    findings = [f for sheet in report["sheets"] for f in sheet["violations"]]
    counts = {k: sum(f["severity"] == k for f in findings)
              for k in ("error", "warning", "exclusion")}
    if body.get("finding_count") != len(findings) or body.get("severity_counts") != counts:
        raise WorkerError("ERC signed finding counts mismatch")
    return {"ok": True, "request_id": request_id, "worker_id": worker_id,
            "signature_verified": True, "report_sha256": body["report_sha256"],
            "finding_count": len(findings), "severity_counts": counts,
            "worker_currently_revoked": node["state"] == "revoked",
            "design_approved": False, "physical_authority": False}


def nodes_status(ledger: Path) -> dict[str, Any]:
    """Inspectable worker enrollment, never automatic execution authority."""
    entries = []
    for node in _read_nodes(ledger)["nodes"]:
        last = node["last_seen_utc"]
        fresh = False
        if last is not None:
            try:
                seen = dt.datetime.fromisoformat(last)
                delta = (dt.datetime.now(dt.timezone.utc) - seen).total_seconds()
                fresh = seen.utcoffset() is not None and 0 <= delta <= HB_MAX_SECONDS
            except (ValueError, TypeError):
                fresh = False
        entries.append({
            "worker_id": node["identity"]["worker_id"],
            "capabilities": node["identity"]["claimed_capabilities"],
            "state": node["state"],
            "last_heartbeat_utc": last,
            "heartbeat_fresh": fresh and node["state"] == "approved",
            "last_sequence": node["last_seq"],
            "remote_dispatch_enabled": False,
            "physical_authority": False,
        })
    return {"schema_version": SCHEMA, "nodes": entries,
            "source": "local_operator_approved_only", "remote_dispatch_enabled": False}


def verify_bundle(bundle: Path, workspace: Path) -> dict[str, Any]:
    """Verify an exported public evidence bundle, without a private key/ledger.

    This proves signature ownership of the included public key and integrity
    of the source/report; it does NOT independently vouch for the signer host.
    """
    paths = [bundle / name for name in ("public_identity.json", "receipt.json", "erc.json")]
    if (bundle.is_symlink() or any(
        p.is_symlink() or not p.is_file() or p.stat().st_size > max_bytes
        for p, max_bytes in zip(paths, (4096, 40_000, 2_000_000))
    )):
        raise WorkerError("exported evidence bundle missing or unsafe")
    identity = _validate_public(json.loads(paths[0].read_bytes()))
    packet = json.loads(paths[1].read_bytes())
    body = _check_signature(identity, packet)
    raw = paths[2].read_bytes()
    try:
        native = json.loads(raw)
        found = [row for sheet in native["sheets"] for row in sheet["violations"]]
        counts = {kind: sum(row["severity"] == kind for row in found)
                  for kind in ("error", "warning", "exclusion")}
    except (TypeError, KeyError, ValueError) as exc:
        raise WorkerError("native ERC evidence malformed") from exc
    reference = workspace / SOURCE
    if (reference.is_symlink() or not reference.is_file()
        or reference.stat().st_size > 12 * 1024 * 1024):
        raise WorkerError("reference schematic missing or unsafe")
    input_hash = hashlib.sha256(reference.read_bytes()).hexdigest()
    if (body.get("schema_version") != SCHEMA or body.get("kind") != "erc_result"
        or body.get("task") != CAPABILITY or body.get("source_path") != SOURCE
        or not SHA40.fullmatch(body.get("source_commit", ""))
        or body.get("input_sha256") != input_hash
        or body.get("report_sha256") != hashlib.sha256(raw).hexdigest()
        or body.get("report_bytes") != len(raw)
        or body.get("erc_schema") != "https://schemas.kicad.org/erc.v1.json"
        or native.get("$schema") != body.get("erc_schema")
        or not str(body.get("kicad_version", "")).startswith("9.")
        or body.get("finding_count") != len(found)
        or body.get("severity_counts") != counts
        or body.get("physical_authority") is not False
        or body.get("hardware_connected") is not False
        or body.get("fabrication_authorized") is not False
        or body.get("design_approved") is not False):
        raise WorkerError("exported signed receipt/source/report inconsistent")
    return {
        "ok": True, "worker_id": identity["worker_id"],
        "request_id": body["request_id"],
        "signed_receipt_verified": True,
        "report_sha256": body["report_sha256"],
        "source_commit_claim": body["source_commit"],
        "source_bytes_match_checkout": True,
        "finding_count": len(found), "severity_counts": counts,
        "operator_enrollment_independently_proven": False,
        "device_identity_hardware_attested": False,
        "physical_authority": False,
        "design_approved": False,
    }
