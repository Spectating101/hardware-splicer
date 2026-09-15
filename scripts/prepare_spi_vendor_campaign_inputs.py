#!/usr/bin/env python3
"""Prepare the three exact vendor-model inputs for the frozen SPI campaign.

The Winbond models are imported from foreground files acquired through the vendor session. The
TI TXU0304 model is fetched from the public official endpoint unless ``--txu-zip`` is supplied.
Raw vendor bytes are processed in memory and are never copied into ``--out-dir``; only manifests,
capability audits, preflight metadata, and campaign projections are persisted.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))

from hardware_splicer.spi_model_capability_gate import apply_spi_model_capability_gate
from hardware_splicer.spi_vendor_model_capability_audit import audit_txu0304_ibis_capabilities
from hardware_splicer.spi_vendor_verilog_preflight import preflight_winbond_verilog_model
from hardware_splicer.spi_virtual_model_campaign import build_spi_virtual_model_campaign
from hardware_splicer.spi_winbond_ibis_capability import audit_winbond_ibis_capabilities
from hardware_splicer.spi_winbond_verilog_capability import audit_winbond_verilog_capabilities
from hardware_splicer.vendor_model_capture import (
    capture_vendor_model_file,
    capture_vendor_model_url,
)

_TXU_ID = "txu0304-ibis-scem787"
_WINBOND_IBIS_ID = "w25q128jwsiq-ibis-da03-aag072"
_WINBOND_VERILOG_ID = "w25q128jw-q-verilog-da02-aag072"
_TXU_URL = "https://www.ti.com/lit/zip/SCEM787"
_TXU_SHA256 = "sha256:1b7b33ae0ce9452eb69ed6ccea4d05f558fef83023d7bc6637b8e9342eb4b4d0"
_WINBOND_IBIS_URL = (
    "https://www.winbond.com/hq/support/documentation/downloadV2022.jsp?"
    "__locale=en&xmlPath=/support/resources/.content/item/DA03-AAG072.html&level=3"
)
_WINBOND_VERILOG_URL = (
    "https://www.winbond.com/hq/support/documentation/downloadV2022.jsp?"
    "__locale=en&xmlPath=/support/resources/.content/item/DA02-AAG072.html&level=2"
)


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--winbond-ibis", required=True, type=Path)
    parser.add_argument("--winbond-verilog", required=True, type=Path)
    parser.add_argument(
        "--txu-zip",
        type=Path,
        help="optional foreground SCEM787.ZIP; otherwise fetch the pinned official TI URL",
    )
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--preflight-timeout-s", type=int, default=30)
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)

    if args.txu_zip:
        txu_payload, txu_manifest = capture_vendor_model_file(
            path=args.txu_zip,
            model_id=_TXU_ID,
            source_url=_TXU_URL,
            expected_hosts=["www.ti.com"],
            expected_model_kind="IBIS",
            filename="SCEM787.ZIP",
            expected_sha256=_TXU_SHA256,
        )
    else:
        txu_payload, txu_manifest = capture_vendor_model_url(
            model_id=_TXU_ID,
            url=_TXU_URL,
            expected_hosts=["www.ti.com"],
            filename="SCEM787.ZIP",
            expected_model_kind="IBIS",
            expected_sha256=_TXU_SHA256,
        )

    winbond_ibis_payload, winbond_ibis_manifest = capture_vendor_model_file(
        path=args.winbond_ibis,
        model_id=_WINBOND_IBIS_ID,
        source_url=_WINBOND_IBIS_URL,
        expected_hosts=["www.winbond.com"],
        expected_model_kind="IBIS",
        filename=args.winbond_ibis.name,
    )
    winbond_verilog_payload, winbond_verilog_manifest = capture_vendor_model_file(
        path=args.winbond_verilog,
        model_id=_WINBOND_VERILOG_ID,
        source_url=_WINBOND_VERILOG_URL,
        expected_hosts=["www.winbond.com"],
        expected_model_kind="Verilog",
        filename=args.winbond_verilog.name,
    )

    txu_audit = audit_txu0304_ibis_capabilities(txu_payload, txu_manifest)
    winbond_ibis_audit = audit_winbond_ibis_capabilities(
        winbond_ibis_payload,
        winbond_ibis_manifest,
    )
    winbond_verilog_audit = audit_winbond_verilog_capabilities(
        winbond_verilog_payload,
        winbond_verilog_manifest,
    )
    winbond_verilog_preflight = preflight_winbond_verilog_model(
        winbond_verilog_payload,
        winbond_verilog_manifest,
        timeout_s=args.preflight_timeout_s,
    )

    manifests = [txu_manifest, winbond_ibis_manifest, winbond_verilog_manifest]
    campaign = build_spi_virtual_model_campaign(manifests)
    gated = apply_spi_model_capability_gate(
        campaign,
        [txu_audit, winbond_ibis_audit, winbond_verilog_preflight],
    )

    _write(args.out_dir / "txu0304.capture.json", txu_manifest)
    _write(args.out_dir / "txu0304.capability.json", txu_audit)
    _write(args.out_dir / "winbond-w25q128jwsiq-ibis.capture.json", winbond_ibis_manifest)
    _write(args.out_dir / "winbond-w25q128jwsiq-ibis.capability.json", winbond_ibis_audit)
    _write(args.out_dir / "winbond-w25q128jw-q-verilog.capture.json", winbond_verilog_manifest)
    _write(args.out_dir / "winbond-w25q128jw-q-verilog.static-capability.json", winbond_verilog_audit)
    _write(args.out_dir / "winbond-w25q128jw-q-verilog.preflight.json", winbond_verilog_preflight)
    _write(args.out_dir / "SPI_VENDOR_INPUT_CAMPAIGN.json", campaign)
    _write(args.out_dir / "SPI_VENDOR_CAPABILITY_GATED_CAMPAIGN.json", gated)

    summary = {
        "schema_version": "hardware_splicer.spi_vendor_campaign_input_preparation.v1",
        "input_campaign_status": campaign.get("status"),
        "capability_gated_status": gated.get("status"),
        "input_ready_execution_ids": campaign.get("ready_execution_ids", []),
        "capability_ready_execution_ids": gated.get("ready_execution_ids", []),
        "blocked_execution_ids": gated.get("blocked_execution_ids", []),
        "capture_sha256": {
            _TXU_ID: txu_manifest.get("sha256"),
            _WINBOND_IBIS_ID: winbond_ibis_manifest.get("sha256"),
            _WINBOND_VERILOG_ID: winbond_verilog_manifest.get("sha256"),
        },
        "verilog_preflight_status": winbond_verilog_preflight.get("status"),
        "raw_vendor_bytes_copied_to_output": False,
        "model_execution_result_count": 0,
        "modeled_evidence_only": True,
        "measured_evidence_present": False,
        "physical_correctness": "UNPROVEN",
        "physical_authority_granted": False,
        "authority_effect": "none",
        "required_next_step": (
            "Build and bind exact execution harnesses only for capability-ready cases; no "
            "manufacturer-model result exists until those harnesses execute and pass audit."
        ),
    }
    _write(args.out_dir / "PREPARATION_SUMMARY.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if gated.get("any_execution_ready") else 2


if __name__ == "__main__":
    raise SystemExit(main())
