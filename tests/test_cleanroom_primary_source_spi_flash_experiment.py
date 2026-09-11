from __future__ import annotations

from hardware_splicer.cleanroom_primary_source_spi_flash_experiment import (
    CASE_ID,
    build_primary_source_spi_flash_case,
    primary_source_case_definition,
    validate_primary_source_spi_flash_case,
)
from hardware_splicer.codex_astra_case import select_exact_case


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
