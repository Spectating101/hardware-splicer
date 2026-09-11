"""Document-grounded SPI-flash case with hash-identified primary sources."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from importlib.resources import files
from pathlib import Path
from typing import Any, Dict

from .cleanroom_replay import ReplayCase


SCHEMA_VERSION = "hardware_splicer.cleanroom_primary_source_spi_flash_experiment.v1"
CASE_ID = "spi-flash-adapter-primary-sources-v1"


def primary_source_case_definition() -> Dict[str, Any]:
    resource = files("hardware_splicer.data").joinpath("astra_primary_source_spi.json")
    value = json.loads(resource.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("primary-source SPI case definition must be a JSON object")
    return value


def verify_primary_source_directory(directory: str | Path) -> Dict[str, Any]:
    """Verify a local capture against the preregistered document bytes."""

    root = Path(directory).expanduser().resolve()
    definition = primary_source_case_definition()
    rows: list[dict[str, Any]] = []
    for document in definition["documents"]:
        path = root / str(document["filename"])
        content = path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        checks = {
            "is_pdf": content.startswith(b"%PDF-"),
            "sha256_matches": digest == document["sha256"],
            "size_matches": len(content) == document["size_bytes"],
        }
        rows.append(
            {
                "source_id": document["source_id"],
                "filename": document["filename"],
                "sha256": "sha256:" + digest,
                "size_bytes": len(content),
                "expected_page_count": document["page_count"],
                "checks": checks,
                "pass": all(checks.values()),
            }
        )
    return {
        "schema_version": "hardware_splicer.primary_source_capture_verification.v1",
        "captured_on": definition["captured_on"],
        "document_count": len(rows),
        "documents": rows,
        "pass": bool(rows) and all(row["pass"] for row in rows),
        "raw_documents_model_visible": False,
        "authority_effect": "none",
    }


def _document_source(document: Dict[str, Any]) -> Dict[str, Any]:
    digest = str(document["sha256"])
    return {
        "source_id": document["source_id"],
        "source_type": "manufacturer_datasheet_pdf_capture",
        "content_hash": "sha256:" + digest,
        "revision": document["document_revision"],
        "authority_ceiling": "declared",
        "metadata": {
            "label": document["title"],
            "vendor": document["vendor"],
            "source_locator": document["download_url"],
            "locator_stability": document["download_url_stability"],
            "captured_on": primary_source_case_definition()["captured_on"],
            "document_code": document["document_code"],
            "document_revision": document["document_revision"],
            "document_date": document["document_date"],
            "raw_document_sha256": "sha256:" + digest,
            "raw_document_size_bytes": document["size_bytes"],
            "raw_document_page_count": document["page_count"],
            "raw_bytes_model_visible": False,
            "claim_extraction": "predeclared_page_addressed_paraphrase",
            "facts": deepcopy(document["facts"]),
            "claims": deepcopy(document["claims"]),
            "limitations": [
                "The byte hash proves capture identity, not manufacturer authenticity, currentness, or physical-device identity.",
                "The model sees page-addressed adjudicated paraphrases, not raw PDF bytes.",
            ],
        },
    }


def primary_source_spi_flash_snapshot() -> Dict[str, Any]:
    definition = primary_source_case_definition()
    document_sources = [_document_source(dict(row)) for row in definition["documents"]]
    return {
        "name": "Primary-source-grounded SPI Flash Programming Adapter",
        "mission": (
            "Use the page-addressed claims from the hash-identified manufacturer documents "
            "to advance the SPI adapter architecture as far as the evidence permits. Preserve "
            "physical identity, implementation, timing, and bench uncertainty; do not claim "
            "fabrication or power-on readiness."
        ),
        "constraints": {
            "host_logic_voltage_v": 3.3,
            "host_voltage_authority": "fixture_declaration_only",
            "declared_dut_supply_target_v": 1.8,
            "default_power_state": "off",
            "authority_effect": "none",
        },
        "engineeringSources": [
            {
                "source_id": "src-controller",
                "source_type": "fixture_interface_declaration",
                "content_hash": "sha256:3v3-spi-controller-declaration-v2",
                "revision": "2",
                "authority_ceiling": "declared",
                "metadata": {
                    "label": "Unresolved 3.3 V SPI programmer declaration",
                    "facts": {
                        "host_logic_voltage_v": 3.3,
                        "host_output_signals": ["SCLK", "CS#", "MOSI_IO0"],
                        "host_input_signals": ["MISO_IO1"],
                        "exact_programmer_identity_resolved": False,
                        "maximum_spi_clock_verified": False,
                    },
                    "limitations": [
                        "No programmer datasheet or measurement capture is attached."
                    ],
                },
            },
            *document_sources,
            {
                "source_id": "src-fixture",
                "source_type": "fixture_readiness_declaration",
                "content_hash": "sha256:spi-adapter-fixture-readiness-v2",
                "revision": "2",
                "authority_ceiling": "declared",
                "metadata": {
                    "label": "Adapter bring-up boundary",
                    "facts": {
                        "default_power_state": "off",
                        "physical_dut_marking_captured": False,
                        "exact_dut_package_verified": False,
                        "dut_supply_implementation_verified": False,
                        "physical_bench_evidence_present": False,
                    },
                },
            },
        ],
        "engineeringSourceAdjudication": deepcopy(definition["adjudication"]),
        "engineeringBlockers": list(definition["adjudication"]["required_unresolved_facts"]),
        "engineeringAdvisories": [
            "Raw manufacturer PDF bytes were captured and hash-identified outside the model-visible snapshot.",
            "Page-addressed paraphrases remain declared document evidence, not physical evidence.",
            "Independent human/EE signoff of the preregistered adjudication remains pending.",
        ],
        "engineering_status": "primary_source_pre_fabrication_review",
        "engineering_readiness": {
            "fabrication_ready": False,
            "power_on_ready": False,
            "evidence_complete": False,
        },
    }


def build_primary_source_spi_flash_case() -> ReplayCase:
    return ReplayCase(
        case_id=CASE_ID,
        project_id="cleanroom-primary-source-spi-flash",
        project_revision=1,
        snapshot=primary_source_spi_flash_snapshot(),
        equivalence_group=None,
        perturbation_kind="primary_source_document_grounding",
        metadata={
            "scenario_family": "semiconductor_spi_flash_fixture",
            "raw_documents_captured": True,
            "raw_documents_model_visible": False,
            "independent_human_signoff": False,
        },
    )


def validate_primary_source_spi_flash_case() -> Dict[str, Any]:
    case = build_primary_source_spi_flash_case()
    snapshot = dict(case.snapshot)
    documents = [
        row
        for row in snapshot["engineeringSources"]
        if row.get("source_type") == "manufacturer_datasheet_pdf_capture"
    ]
    claims = [claim for row in documents for claim in row["metadata"].get("claims", [])]
    checks = {
        "three_primary_documents": len(documents) == 3,
        "all_documents_sha256_identified": all(
            str(row.get("content_hash", "")).startswith("sha256:")
            and len(str(row.get("content_hash"))) == 71
            for row in documents
        ),
        "all_claims_page_addressed": bool(claims)
        and all("page" in claim or "pages" in claim for claim in claims),
        "raw_bytes_not_claimed_model_visible": all(
            row["metadata"].get("raw_bytes_model_visible") is False for row in documents
        ),
        "independent_signoff_pending": snapshot["engineeringSourceAdjudication"].get(
            "independent_signoff"
        )
        is False,
        "physical_authority_closed": not snapshot["engineering_readiness"].get(
            "fabrication_ready"
        )
        and not snapshot["engineering_readiness"].get("power_on_ready"),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "case_id": case.case_id,
        "checks": checks,
        "pass": all(checks.values()),
    }
