"""Genuine native ERC acceptance on hosts that already have approved KiCad v9.

Only ephemeral pytest keys/registry are used. No service is installed.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from hardware_splicer.local_kicad_worker import (
    KICAD_BIN, create_identity, enroll, heartbeat, run_erc, verify_erc,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(not Path(KICAD_BIN).is_file(),
                    reason="native KiCad not installed on this CI host")
def test_native_signed_erc_from_committed_hs_schematic(tmp_path):
    private = tmp_path / "identity"
    ledger = tmp_path / "ledger"
    created = create_identity(private)
    enroll(ledger, private / "identity.json", approve=True)
    confirmed = heartbeat(ledger, private)
    assert confirmed["heartbeat_signature_verified"] is True
    job = run_erc(ledger, private, ROOT, execute=True)
    verified = verify_erc(ledger, ROOT, job["request_id"])
    assert job["worker_id"] == created["worker_id"]
    assert job["kicad_version"].startswith("9.")
    assert job["signature_verified"] is True
    assert verified["signature_verified"] is True
    assert verified["finding_count"] == job["finding_count"]
    assert verified["report_sha256"] == job["report_sha256"]
    assert verified["design_approved"] is False
    assert verified["physical_authority"] is False
    print(
        "HS_NATIVE_SIGNED_ERC",
        "kicad=" + job["kicad_version"],
        "findings=" + str(job["finding_count"]),
        "sha256=" + job["report_sha256"],
        "worker=" + job["worker_id"],
        "request=" + job["request_id"],
    )
