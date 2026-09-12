from __future__ import annotations

import json

from hardware_splicer.cleanroom_primary_source_spi_flash_experiment import (
    BLIND_CASE_ID,
    CASE_ID,
    IDENTITY_CONFLICT_CASE_ID,
    RAW_DOCUMENT_CASE_ID,
    RAW_DOCUMENT_V2_CASE_ID,
    RAW_DOCUMENT_V3_CASE_ID,
    build_primary_source_identity_conflict_case,
    build_primary_source_spi_flash_case,
    build_primary_source_spi_flash_blind_case,
    build_primary_source_spi_flash_raw_document_case,
    build_primary_source_spi_flash_raw_document_v2_case,
    build_primary_source_spi_flash_raw_document_v3_case,
    primary_source_case_definition,
    validate_blind_primary_source_cases,
    validate_primary_source_spi_flash_case,
    validate_raw_document_primary_source_case,
)
from hardware_splicer.codex_astra_case import build_codex_case_package, select_exact_case


def test_primary_source_case_is_page_addressed_but_not_overclaimed() -> None:
    case = build_primary_source_spi_flash_case()
    snapshot = dict(case.snapshot)
    documents = [
        row
        for row in snapshot["engineeringSources"]
        if row["source_type"] == "manufacturer_datasheet_pdf_capture"
    ]

    assert len(documents) == 3
    assert all(row["metadata"]["raw_bytes_model_visible"] is False for row in documents)
    assert all(
        claim.get("page") or claim.get("pages")
        for row in documents
        for claim in row["metadata"]["claims"]
    )
    assert snapshot["engineeringSourceAdjudication"]["independent_signoff"] is False
    assert snapshot["engineering_readiness"]["fabrication_ready"] is False
    assert snapshot["engineering_readiness"]["power_on_ready"] is False


def test_primary_source_case_is_selectable_for_codex_packaging() -> None:
    assert validate_primary_source_spi_flash_case()["pass"] is True
    assert select_exact_case(CASE_ID).case_id == CASE_ID
    assert all(
        len(document["sha256"]) == 64
        and document["download_url"].startswith("https://")
        for document in primary_source_case_definition()["documents"]
    )


def test_blinded_cases_hide_expected_answers_and_expose_only_conflicting_evidence() -> None:
    baseline = build_primary_source_spi_flash_blind_case()
    conflict = build_primary_source_identity_conflict_case()
    baseline_text = json.dumps(baseline.snapshot, sort_keys=True)
    conflict_text = json.dumps(conflict.snapshot, sort_keys=True)

    assert baseline.case_id == BLIND_CASE_ID
    assert conflict.case_id == IDENTITY_CONFLICT_CASE_ID
    assert "engineeringSourceAdjudication" not in baseline.snapshot
    assert "supported_conclusions" not in baseline_text
    assert "observer_adjudication" not in baseline_text
    assert "observer_conflict_adjudication" not in conflict_text
    assert "W25Q128JW" in conflict_text
    assert "W25Q128JV" in conflict_text
    assert validate_blind_primary_source_cases()["pass"] is True


def test_conflict_case_is_detected_by_assurance_projection() -> None:
    from hardware_splicer.engineering_assurance import build_engineering_assurance

    case = build_primary_source_identity_conflict_case()
    assurance = build_engineering_assurance(case.snapshot)

    conflict = next(
        row
        for row in assurance["conflicts"]
        if row["subject_id"] == "physical-dut"
        and row["predicate"] == "component_identity"
    )
    assert conflict["blocking"] is True
    assert set(conflict["claim_ids"]) == {
        "current-dut-identity-jw",
        "procurement-note-dut-identity-jv",
    }


def test_blinded_cases_are_selectable_without_leaking_observer_rubric() -> None:
    for case_id in (BLIND_CASE_ID, IDENTITY_CONFLICT_CASE_ID):
        selected = select_exact_case(case_id)
        assert selected.case_id == case_id
        assert "observer_adjudication" not in json.dumps(selected.snapshot)


def test_blinded_model_input_excludes_observer_metadata() -> None:
    package = build_codex_case_package(
        case_id=IDENTITY_CONFLICT_CASE_ID,
        experiment_project_id="blind-conflict-test",
    )
    mission = package["model_visible"]["mission_text"]
    observer = package["observer_only"]

    assert "observer_conflict_adjudication" not in mission
    assert "supported_conclusions" not in mission
    assert "forbidden_claims" not in mission
    assert "observer_conflict_adjudication" in observer["case_metadata"]
    assert observer["outer_labels_visible_to_model"] is False


def test_raw_document_case_exposes_questions_and_hashes_not_curated_answers() -> None:
    case = build_primary_source_spi_flash_raw_document_case()
    snapshot_text = json.dumps(case.snapshot, sort_keys=True)
    definition = primary_source_case_definition()

    assert case.case_id == RAW_DOCUMENT_CASE_ID
    assert len(case.snapshot["documentExtractionTargets"]) == 11
    assert all(
        not source.get("claims") and not source.get("metadata", {}).get("claims")
        for source in case.snapshot["engineeringSources"]
        if source.get("source_type") == "manufacturer_datasheet_pdf_capture"
    )
    assert all(
        claim["paraphrase"] not in snapshot_text
        for document in definition["documents"]
        for claim in document["claims"]
    )
    assert validate_raw_document_primary_source_case()["pass"] is True
    assert select_exact_case(RAW_DOCUMENT_CASE_ID).case_id == RAW_DOCUMENT_CASE_ID


def test_raw_document_model_input_hides_expected_values_and_rubric() -> None:
    package = build_codex_case_package(
        case_id=RAW_DOCUMENT_CASE_ID,
        experiment_project_id="raw-document-test",
    )
    mission = package["model_visible"]["mission_text"]
    observer = package["observer_only"]

    assert "supported_conclusions" not in mission
    assert "forbidden_claims" not in mission
    assert "predeclared_page_addressed_paraphrase" not in mission
    assert "observer_adjudication" not in mission
    assert "observer_adjudication" in observer["case_metadata"]
    assert observer["outer_labels_visible_to_model"] is False


def test_raw_document_v2_clarifies_serialization_without_exposing_answers() -> None:
    case = build_primary_source_spi_flash_raw_document_v2_case()
    package = build_codex_case_package(
        case_id=RAW_DOCUMENT_V2_CASE_ID,
        experiment_project_id="raw-document-v2-test",
    )
    mission = package["model_visible"]["mission_text"]
    instructions = package["model_visible"]["developer_instructions"]
    definition = primary_source_case_definition()

    assert case.case_id == RAW_DOCUMENT_V2_CASE_ID
    assert validate_raw_document_primary_source_case(
        case_id=RAW_DOCUMENT_V2_CASE_ID
    )["pass"] is True
    assert select_exact_case(RAW_DOCUMENT_V2_CASE_ID).case_id == RAW_DOCUMENT_V2_CASE_ID
    assert "only bare project signal names" in instructions
    assert "use rejected" in instructions
    assert "exact strings copied from the initial engineeringBlockers" in instructions
    assert "supported_conclusions" not in mission
    assert "forbidden_claims" not in mission
    assert all(
        claim["paraphrase"] not in mission
        for document in definition["documents"]
        for claim in document["claims"]
    )
    assert {
        "Independent review of all model-proposed document claims.",
        "Machine-extracted PDF text can omit, reorder, or misread visually encoded content.",
        "Frozen hashes prove capture identity, not authenticity, currentness, or physical identity.",
    }.issubset(set(case.snapshot["engineeringBlockers"]))


def test_raw_document_v3_changes_only_observer_alias_policy() -> None:
    v2 = build_primary_source_spi_flash_raw_document_v2_case()
    v3 = build_primary_source_spi_flash_raw_document_v3_case()

    assert v3.case_id == RAW_DOCUMENT_V3_CASE_ID
    assert v3.snapshot == v2.snapshot
    assert v3.metadata["mapping_alias_policy"] == "datasheet_function_aliases_v1"
    v2_visible = build_codex_case_package(
        case_id=RAW_DOCUMENT_V2_CASE_ID,
        experiment_project_id="same-visible-project",
    )["model_visible"]
    v3_visible = build_codex_case_package(
        case_id=RAW_DOCUMENT_V3_CASE_ID,
        experiment_project_id="same-visible-project",
    )["model_visible"]
    assert v3_visible == v2_visible
    assert validate_raw_document_primary_source_case(
        case_id=RAW_DOCUMENT_V3_CASE_ID
    )["pass"] is True
    assert select_exact_case(RAW_DOCUMENT_V3_CASE_ID).case_id == RAW_DOCUMENT_V3_CASE_ID
