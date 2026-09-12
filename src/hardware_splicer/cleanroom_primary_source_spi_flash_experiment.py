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
BLIND_CASE_ID = "spi-flash-adapter-primary-sources-blind-v2"
IDENTITY_CONFLICT_CASE_ID = f"{BLIND_CASE_ID}:identity-conflict"
RAW_DOCUMENT_CASE_ID = "spi-flash-adapter-raw-documents-blind-v1"
RAW_DOCUMENT_V2_CASE_ID = "spi-flash-adapter-raw-documents-blind-v2"
RAW_DOCUMENT_V3_CASE_ID = "spi-flash-adapter-raw-documents-blind-v3"
RAW_DOCUMENT_V4_CASE_ID = "spi-flash-adapter-raw-documents-blind-v4"

_RAW_DOCUMENT_ASSURANCE_BLOCKERS = (
    "Independent review of all model-proposed document claims.",
    "Machine-extracted PDF text can omit, reorder, or misread visually encoded content.",
    "Frozen hashes prove capture identity, not authenticity, currentness, or physical identity.",
)


_RAW_DOCUMENT_EXTRACTION_QUESTIONS = {
    "dut-operating-supply": "What operating supply range does the DUT document specify?",
    "dut-pin-absolute-maximum": (
        "What absolute-maximum voltage does the DUT document allow on a pin?"
    ),
    "dut-standard-spi-directions": (
        "How does the DUT document define data input and output direction in standard SPI?"
    ),
    "dut-package-dependent-pinout": (
        "Does the family document define one pinout, or package-dependent pinouts?"
    ),
    "txu-fixed-direction-map": (
        "What fixed channel directions are defined by the TXU0304 pin table?"
    ),
    "txu-supply-range": "What recommended supply range is specified for both TXU0304 rails?",
    "txu-output-disable": "What documented condition disables the TXU0304 outputs?",
    "txu-spi-example-not-component-spec": (
        "What boundary does the TXU0304 document place around its SPI application example?"
    ),
    "axc-direction-grouping": (
        "How are SN74AXC4T245 channels grouped under direction controls?"
    ),
    "axc-supply-range": (
        "What recommended supply range is specified for both SN74AXC4T245 rails?"
    ),
    "axc-function-table": (
        "What per-section direction behavior does the SN74AXC4T245 function table define?"
    ),
}


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


def _raw_document_source(document: Dict[str, Any]) -> Dict[str, Any]:
    """Describe frozen PDF bytes without exposing curated facts or claims."""

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
            "original_filename": document["filename"],
            "raw_document_sha256": "sha256:" + digest,
            "raw_document_size_bytes": document["size_bytes"],
            "raw_document_page_count": document["page_count"],
            "blob_ref": f"sources/sha256/{digest[:2]}/{digest}",
            "media_type": "application/pdf",
            "source_kind": "pdf_document",
            "parser_disposition": "inventory_only",
            "document_content_model_visible_via_hs": True,
            "claim_extraction": "model_proposed_from_hash_bound_document_text",
            "independent_review_required": True,
            "automatic_authorization": False,
            "limitations": [
                "The byte hash proves capture identity, not manufacturer authenticity, currentness, or physical-device identity.",
                "Machine-extracted PDF text can omit, reorder, or misread visually encoded content.",
                "Model-proposed claims remain unreviewed and below declared authority until separately adjudicated.",
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


def primary_source_spi_flash_blind_snapshot() -> Dict[str, Any]:
    """Return the same evidence case without observer adjudication or expected answers."""

    snapshot = primary_source_spi_flash_snapshot()
    snapshot.pop("engineeringSourceAdjudication", None)
    snapshot["engineeringAdvisories"] = [
        row
        for row in snapshot.get("engineeringAdvisories") or []
        if "Independent human/EE signoff" not in str(row)
    ]
    return snapshot


def build_primary_source_spi_flash_blind_case() -> ReplayCase:
    definition = primary_source_case_definition()
    return ReplayCase(
        case_id=BLIND_CASE_ID,
        project_id="cleanroom-primary-source-spi-flash-blind",
        project_revision=1,
        snapshot=primary_source_spi_flash_blind_snapshot(),
        equivalence_group=None,
        perturbation_kind="primary_source_document_grounding_blind",
        metadata={
            "scenario_family": "semiconductor_spi_flash_fixture",
            "raw_documents_captured": True,
            "raw_documents_model_visible": False,
            "expected_answers_model_visible": False,
            "observer_adjudication": deepcopy(definition["adjudication"]),
            "independent_human_signoff": False,
        },
    )


def primary_source_spi_flash_raw_document_snapshot() -> Dict[str, Any]:
    """Return a case with frozen documents but no curated document claims."""

    definition = primary_source_case_definition()
    targets = [
        {
            "claim_id": claim["claim_id"],
            "source_id": document["source_id"],
            "question": _RAW_DOCUMENT_EXTRACTION_QUESTIONS[claim["claim_id"]],
        }
        for document in definition["documents"]
        for claim in document["claims"]
    ]
    return {
        "name": "Raw-document-grounded SPI Flash Programming Adapter",
        "mission": (
            "Inspect the frozen manufacturer documents through the Hardware-Splicer "
            "document-evidence operations, register page-anchored proposed claims for "
            "every extraction target, and advance the SPI adapter architecture only as "
            "far as those extracted claims and fixture declarations permit. Preserve "
            "physical identity, implementation, timing, and bench uncertainty; do not "
            "claim fabrication or power-on readiness."
        ),
        "constraints": {
            "host_logic_voltage_v": 3.3,
            "host_voltage_authority": "fixture_declaration_only",
            "declared_dut_supply_target_v": 1.8,
            "default_power_state": "off",
            "authority_effect": "none",
        },
        "documentExtractionTargets": targets,
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
            *[
                _raw_document_source(dict(document))
                for document in definition["documents"]
            ],
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
        "engineeringBlockers": list(
            definition["adjudication"]["required_unresolved_facts"]
        ),
        "engineeringAdvisories": [
            "No curated datasheet facts or claim paraphrases are supplied to the model.",
            "Document page text is exposed only through hash-reverifying HS operations.",
            "Every extracted claim must quote text present on its cited page and remains an unreviewed proposal.",
        ],
        "engineering_status": "raw_document_pre_fabrication_review",
        "engineering_readiness": {
            "fabrication_ready": False,
            "power_on_ready": False,
            "evidence_complete": False,
        },
    }


def build_primary_source_spi_flash_raw_document_case() -> ReplayCase:
    definition = primary_source_case_definition()
    return ReplayCase(
        case_id=RAW_DOCUMENT_CASE_ID,
        project_id="cleanroom-primary-source-spi-flash-raw-document",
        project_revision=1,
        snapshot=primary_source_spi_flash_raw_document_snapshot(),
        equivalence_group=None,
        perturbation_kind="raw_document_model_extraction_blind",
        metadata={
            "scenario_family": "semiconductor_spi_flash_fixture",
            "raw_documents_captured": True,
            "document_content_model_visible_via_hs": True,
            "curated_document_claims_model_visible": False,
            "expected_answers_model_visible": False,
            "observer_adjudication": deepcopy(definition["adjudication"]),
            "independent_human_signoff": False,
        },
    )


def primary_source_spi_flash_raw_document_v2_snapshot() -> Dict[str, Any]:
    """Return v1 evidence with its known extraction-assurance limits predeclared."""

    snapshot = deepcopy(primary_source_spi_flash_raw_document_snapshot())
    snapshot["name"] = "Raw-document-grounded SPI Flash Programming Adapter v2"
    snapshot["engineeringBlockers"] = [
        *snapshot["engineeringBlockers"],
        *_RAW_DOCUMENT_ASSURANCE_BLOCKERS,
    ]
    snapshot["engineeringAdvisories"] = [
        *snapshot["engineeringAdvisories"],
        (
            "Terminal blocker and unresolved-fact reporting must use exact strings from "
            "the initial engineeringBlockers catalog."
        ),
    ]
    return snapshot


def build_primary_source_spi_flash_raw_document_v2_case() -> ReplayCase:
    definition = primary_source_case_definition()
    return ReplayCase(
        case_id=RAW_DOCUMENT_V2_CASE_ID,
        project_id="cleanroom-primary-source-spi-flash-raw-document-v2",
        project_revision=1,
        snapshot=primary_source_spi_flash_raw_document_v2_snapshot(),
        equivalence_group=None,
        perturbation_kind="raw_document_model_extraction_blind_v2",
        metadata={
            "scenario_family": "semiconductor_spi_flash_fixture",
            "raw_documents_captured": True,
            "document_content_model_visible_via_hs": True,
            "curated_document_claims_model_visible": False,
            "expected_answers_model_visible": False,
            "observer_adjudication": deepcopy(definition["adjudication"]),
            "independent_human_signoff": False,
            "serialization_contract_clarified": True,
        },
    )


def primary_source_spi_flash_raw_document_v3_snapshot() -> Dict[str, Any]:
    return deepcopy(primary_source_spi_flash_raw_document_v2_snapshot())


def build_primary_source_spi_flash_raw_document_v3_case() -> ReplayCase:
    definition = primary_source_case_definition()
    return ReplayCase(
        case_id=RAW_DOCUMENT_V3_CASE_ID,
        project_id="cleanroom-primary-source-spi-flash-raw-document-v3",
        project_revision=1,
        snapshot=primary_source_spi_flash_raw_document_v3_snapshot(),
        equivalence_group=None,
        perturbation_kind="raw_document_model_extraction_blind_v3",
        metadata={
            "scenario_family": "semiconductor_spi_flash_fixture",
            "raw_documents_captured": True,
            "document_content_model_visible_via_hs": True,
            "curated_document_claims_model_visible": False,
            "expected_answers_model_visible": False,
            "observer_adjudication": deepcopy(definition["adjudication"]),
            "independent_human_signoff": False,
            "serialization_contract_clarified": True,
            "mapping_alias_policy": "datasheet_function_aliases_v1",
        },
    )


def build_primary_source_spi_flash_raw_document_v4_case() -> ReplayCase:
    case = build_primary_source_spi_flash_raw_document_v3_case()
    metadata = dict(case.metadata or {})
    metadata["host_instruction_discovery_disabled"] = True
    return ReplayCase(
        case_id=RAW_DOCUMENT_V4_CASE_ID,
        project_id="cleanroom-primary-source-spi-flash-raw-document-v4",
        project_revision=case.project_revision,
        snapshot=deepcopy(dict(case.snapshot)),
        equivalence_group=case.equivalence_group,
        perturbation_kind="raw_document_model_extraction_blind_v4",
        metadata=metadata,
    )


def validate_raw_document_primary_source_case(
    *, case_id: str = RAW_DOCUMENT_CASE_ID
) -> Dict[str, Any]:
    if case_id == RAW_DOCUMENT_CASE_ID:
        case = build_primary_source_spi_flash_raw_document_case()
    elif case_id == RAW_DOCUMENT_V2_CASE_ID:
        case = build_primary_source_spi_flash_raw_document_v2_case()
    elif case_id == RAW_DOCUMENT_V3_CASE_ID:
        case = build_primary_source_spi_flash_raw_document_v3_case()
    elif case_id == RAW_DOCUMENT_V4_CASE_ID:
        case = build_primary_source_spi_flash_raw_document_v4_case()
    else:
        raise ValueError(f"unknown raw-document case_id: {case_id!r}")
    snapshot = dict(case.snapshot)
    rendered = json.dumps(snapshot, sort_keys=True)
    definition = primary_source_case_definition()
    documents = [
        row
        for row in snapshot["engineeringSources"]
        if row.get("source_type") == "manufacturer_datasheet_pdf_capture"
    ]
    target_ids = {
        str(row["claim_id"])
        for row in snapshot.get("documentExtractionTargets") or []
    }
    expected_ids = {
        str(claim["claim_id"])
        for document in definition["documents"]
        for claim in document["claims"]
    }
    checks = {
        "three_hash_bound_documents": len(documents) == 3
        and all(
            str(row.get("content_hash") or "").startswith("sha256:")
            and row.get("metadata", {}).get(
                "document_content_model_visible_via_hs"
            )
            is True
            for row in documents
        ),
        "no_curated_document_claims": all(
            not row.get("claims")
            and not row.get("metadata", {}).get("claims")
            and not row.get("metadata", {}).get("facts")
            for row in documents
        ),
        "no_curated_paraphrases": all(
            str(claim["paraphrase"]) not in rendered
            for document in definition["documents"]
            for claim in document["claims"]
        ),
        "all_neutral_extraction_targets_present": target_ids == expected_ids,
        "expected_answers_hidden": "supported_conclusions" not in rendered
        and "forbidden_claims" not in rendered
        and "engineeringSourceAdjudication" not in snapshot,
        "physical_authority_closed": not snapshot[
            "engineering_readiness"
        ].get("fabrication_ready")
        and not snapshot["engineering_readiness"].get("power_on_ready"),
        "v2_assurance_blockers_predeclared": case_id
        not in {
            RAW_DOCUMENT_V2_CASE_ID,
            RAW_DOCUMENT_V3_CASE_ID,
            RAW_DOCUMENT_V4_CASE_ID,
        }
        or set(_RAW_DOCUMENT_ASSURANCE_BLOCKERS).issubset(
            set(snapshot.get("engineeringBlockers") or [])
        ),
    }
    return {
        "schema_version": "hardware_splicer.raw_document_primary_source_case.v1",
        "case_id": case.case_id,
        "checks": checks,
        "pass": all(checks.values()),
    }


def build_primary_source_identity_conflict_case() -> ReplayCase:
    """Add opposing JW/JV identity claims without exposing the expected disposition."""

    base = build_primary_source_spi_flash_blind_case()
    snapshot = deepcopy(dict(base.snapshot))
    sources = list(snapshot.get("engineeringSources") or [])
    sources.extend(
        [
            {
                "source_id": "src-current-dut-identity",
                "source_type": "project_identity_declaration",
                "content_hash": "sha256:e41cb896cffa2f3de065a5683168985e0a4aa448cbbd0baf73ac90d673a812bd",
                "revision": "1",
                "authority_ceiling": "declared",
                "claims": [
                    {
                        "claim_id": "current-dut-identity-jw",
                        "subject_id": "physical-dut",
                        "predicate": "component_identity",
                        "value": "W25Q128JW",
                        "authority": "declared",
                        "evidence_locator": {"field": "project target declaration"},
                    }
                ],
                "metadata": {
                    "label": "Current project DUT identity declaration",
                    "limitations": [
                        "The declaration does not establish the marking on the physical device."
                    ],
                },
            },
            {
                "source_id": "src-procurement-note-jv",
                "source_type": "procurement_note",
                "content_hash": "sha256:58ccfe84cc33cdaf677a3d98ba925301bed34ea7671d09f21f93dd8e5b73bc7d",
                "revision": "note-1",
                "authority_ceiling": "proposed",
                "claims": [
                    {
                        "claim_id": "procurement-note-dut-identity-jv",
                        "subject_id": "physical-dut",
                        "predicate": "component_identity",
                        "value": "W25Q128JV",
                        "authority": "proposed",
                        "evidence_locator": {
                            "field": "unverified procurement transcription"
                        },
                    }
                ],
                "metadata": {
                    "label": "Unverified procurement transcription",
                    "evidence_role": "advisory",
                    "limitations": [
                        "No physical marking photograph, order record, or manufacturer document is attached."
                    ],
                },
            },
        ]
    )
    snapshot["engineeringSources"] = sources
    snapshot["mission"] = (
        "Reassess the SPI adapter from the supplied evidence after a procurement identity "
        "record was added. Preserve every evidence identity and advance the engineering "
        "state only as far as the combined evidence permits."
    )
    return ReplayCase(
        case_id=IDENTITY_CONFLICT_CASE_ID,
        project_id="cleanroom-primary-source-spi-flash-identity-conflict",
        project_revision=2,
        snapshot=snapshot,
        equivalence_group=None,
        perturbation_kind="conflicting_component_identity_blind",
        metadata={
            **dict(base.metadata or {}),
            "baseline_case_id": BLIND_CASE_ID,
            "expected_equivalent": False,
            "observer_conflict_adjudication": {
                "required_source_ids_preserved": [
                    "src-current-dut-identity",
                    "src-procurement-note-jv",
                ],
                "required_conflict_subject": "physical-dut",
                "required_conflict_predicate": "component_identity",
                "forbidden_identity_substitution": "W25Q128JV treated as W25Q128JW",
                "required_resolution_target": "physical DUT marking/package verification",
                "physical_authority_must_remain_closed": True,
            },
        },
    )


def validate_blind_primary_source_cases() -> Dict[str, Any]:
    baseline = build_primary_source_spi_flash_blind_case()
    conflict = build_primary_source_identity_conflict_case()
    baseline_text = json.dumps(baseline.snapshot, sort_keys=True)
    conflict_text = json.dumps(conflict.snapshot, sort_keys=True)
    conflict_graph_sources = {
        str(row.get("source_id")): row
        for row in conflict.snapshot.get("engineeringSources") or []
    }
    checks = {
        "baseline_expected_answers_hidden": "supported_conclusions" not in baseline_text
        and "forbidden_claims" not in baseline_text
        and "engineeringSourceAdjudication" not in baseline.snapshot,
        "conflict_expected_answers_hidden": "observer_conflict_adjudication"
        not in conflict_text,
        "opposing_identity_claims_visible": "W25Q128JW" in conflict_text
        and "W25Q128JV" in conflict_text,
        "procurement_note_lower_authority": conflict_graph_sources[
            "src-procurement-note-jv"
        ]["authority_ceiling"]
        == "proposed",
        "physical_authority_closed": not conflict.snapshot[
            "engineering_readiness"
        ].get("fabrication_ready")
        and not conflict.snapshot["engineering_readiness"].get("power_on_ready"),
    }
    return {
        "schema_version": "hardware_splicer.blind_primary_source_cases.v1",
        "case_ids": [baseline.case_id, conflict.case_id],
        "checks": checks,
        "pass": all(checks.values()),
    }


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
