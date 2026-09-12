from __future__ import annotations

from copy import deepcopy

import hardware_splicer.codex_astra_raw_document_adjudication as raw_adjudication
from hardware_splicer.cleanroom_primary_source_spi_flash_experiment import (
    primary_source_case_definition,
    primary_source_spi_flash_raw_document_snapshot,
)
from hardware_splicer.document_evidence import (
    DOCUMENT_EXTRACTION_IMPLEMENTATION,
    ExtractedDocument,
    text_sha256,
)


def _passing_fixture(monkeypatch):
    snapshot = deepcopy(primary_source_spi_flash_raw_document_snapshot())
    rules = raw_adjudication._expected_claims()
    documents: dict[str, ExtractedDocument] = {}
    claims_by_source: dict[str, list[dict]] = {}

    for source in snapshot["engineeringSources"]:
        source_id = source["source_id"]
        matching = {
            claim_id: rule
            for claim_id, rule in rules.items()
            if rule["source_id"] == source_id
        }
        if not matching:
            continue
        page_count = int(source["metadata"]["raw_document_page_count"])
        pages = [""] * page_count
        pending: list[tuple[str, dict, int, str]] = []
        for claim_id, rule in matching.items():
            page_number = min(rule["pdf_page_numbers"])
            support = " | ".join(group[0] for group in rule["semantic_groups"])
            pages[page_number - 1] += support + "\n"
            pending.append((claim_id, rule, page_number, support))
        document = ExtractedDocument(
            project_id="raw-doc-test",
            source_id=source_id,
            content_hash=source["content_hash"],
            document_revision=source["revision"],
            pages=tuple(pages),
            library_version="test",
        )
        documents[source_id] = document
        claims_by_source[source_id] = [
            {
                "claim_id": claim_id,
                "source_id": source_id,
                "subject_id": "test-subject",
                "predicate": "test-predicate",
                "value": support,
                "authority": "proposed",
                "evidence_locator": {
                    "page": page_number,
                    "source_content_hash": document.content_hash,
                    "page_text_sha256": text_sha256(document.pages[page_number - 1]),
                    "supporting_text_sha256": text_sha256(support),
                    "extraction_implementation": DOCUMENT_EXTRACTION_IMPLEMENTATION,
                },
                "metadata": {
                    "claim_origin": "model_proposed_from_hash_bound_document_text",
                    "supporting_text": support,
                    "independent_review_state": "unreviewed",
                    "automatic_authorization": False,
                },
            }
            for claim_id, _rule, page_number, support in pending
        ]

    monkeypatch.setattr(
        raw_adjudication,
        "extract_registered_pdf",
        lambda _project_id, source, project_root: documents[source["source_id"]],
    )
    for source in snapshot["engineeringSources"]:
        if source["source_id"] in claims_by_source:
            source["claims"] = claims_by_source[source["source_id"]]

    refs = [
        {"source_id": rule["source_id"], "claim_id": claim_id}
        for claim_id, rule in rules.items()
    ]
    snapshot["preFabricationPlan"] = {
        "assessment": {
            "blockers": primary_source_case_definition()["adjudication"][
                "required_unresolved_facts"
            ],
            "independent_signoff": False,
            "physical_correctness": "UNPROVEN",
        },
        "architecture_candidates": [
            {
                "candidate_id": "direct-3v3",
                "status": "rejected_by_absolute_maximum",
                "source_refs": refs,
            },
            {
                "candidate_id": "txu0304",
                "status": "preferred_family_candidate",
                "proposed_logical_mapping": [
                    {"host": "SCLK", "dut": "CLK", "direction": "host_to_dut"},
                    {"host": "CS#", "dut": "/CS", "direction": "host_to_dut"},
                    {
                        "host": "MOSI_IO0",
                        "dut": "DI_IO0",
                        "direction": "host_to_dut",
                    },
                    {
                        "host": "MISO_IO1",
                        "dut": "DO_IO1",
                        "direction": "dut_to_host",
                    },
                ],
            },
            {
                "candidate_id": "single-sn74axc4t245",
                "status": "rejected",
                "description": "Shared direction controls cannot implement 3+1.",
            },
        ],
        "fabrication_ready": False,
        "power_on_ready": False,
        "physical_authority_granted": False,
        "physical_correctness": "UNPROVEN",
    }
    return snapshot


def test_raw_document_adjudication_accepts_only_fully_anchored_flow(
    monkeypatch,
) -> None:
    snapshot = _passing_fixture(monkeypatch)

    report = raw_adjudication.adjudicate_raw_document_snapshot(
        snapshot,
        project_id="raw-doc-test",
        project_root="/unused",
    )

    assert report["status"] == "pass"
    assert report["metrics"]["fully_anchored_claim_count"] == 11
    assert report["metrics"]["used_target_claim_count"] == 11
    assert report["metrics"]["reference_issue_count"] == 0


def test_raw_document_adjudication_rejects_wrong_page_and_authority(
    monkeypatch,
) -> None:
    snapshot = _passing_fixture(monkeypatch)
    claim = next(
        row
        for source in snapshot["engineeringSources"]
        for row in source.get("claims") or []
        if row["claim_id"] == "dut-operating-supply"
    )
    claim["authority"] = "declared"
    claim["evidence_locator"]["page"] = 1

    report = raw_adjudication.adjudicate_raw_document_snapshot(
        snapshot,
        project_id="raw-doc-test",
        project_root="/unused",
    )

    assert report["status"] == "fail"
    issues = {
        (row["claim_id"], row["check"]) for row in report["claim_issues"]
    }
    assert ("dut-operating-supply", "authority_proposed") in issues
    assert ("dut-operating-supply", "expected_pdf_page") in issues
