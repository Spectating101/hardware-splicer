from __future__ import annotations

from copy import deepcopy

import pytest

from hardware_splicer.engineering_review_identity import AUTHORITY_CEILING
from hardware_splicer.finding_ledger import (
    ENGINEERING_FINDINGS_KEY,
    MAX_FINDING_TEXT,
    bound_finding_text,
    replace_producer_findings,
    validate_ledger_entry,
    validate_recorded_at,
)
from hardware_splicer.finding_provenance import finding_id


def _entry(
    *,
    category: str = "failed_check",
    text: str = "DRC failed with 2 error(s).",
    object_id: str | None = None,
    source_ref: str | None = "action-1",
    kind: str = "deterministic",
    extra: dict | None = None,
) -> dict:
    row = {
        "category": category,
        "object_id": object_id,
        "text": text,
        "provenance": {
            "kind": kind,
            "basis": "design_quality gate blocker from an executed deterministic compose",
            "source_ref": source_ref,
            "authority_ceiling": AUTHORITY_CEILING,
        },
        "recorded_at": "2026-10-05T06:00:00+00:00",
    }
    if extra:
        row.update(extra)
    return row


def test_replace_producer_findings_replaces_only_that_producer() -> None:
    snapshot = {
        ENGINEERING_FINDINGS_KEY: [
            {
                **_entry(text="Old gate blocker.", source_ref="action-old"),
                "producer": "design_quality_gate",
                "producer_run": "action-old",
                "finding_id": "stale",
            },
            {
                **_entry(
                    category="release_blocker",
                    text="requirement 'req-rail' has no verification",
                    object_id="req-rail",
                    source_ref="unverified_requirement",
                ),
                "producer": "release_assessment",
                "producer_run": "assess_release@rev1",
                "finding_id": "keep-me",
            },
        ],
        "release_authorized": False,
    }
    original = deepcopy(snapshot)
    incoming = [
        _entry(
            text="Electrical safety checks failed on the compiled build graph.",
            source_ref="action-new",
        )
    ]

    updated = replace_producer_findings(
        snapshot, "design_quality_gate", "action-new", incoming
    )

    assert snapshot == original
    incoming[0]["text"] = "mutated after call"
    gate = [
        row
        for row in updated[ENGINEERING_FINDINGS_KEY]
        if row["producer"] == "design_quality_gate"
    ]
    other = [
        row
        for row in updated[ENGINEERING_FINDINGS_KEY]
        if row["producer"] == "release_assessment"
    ]
    assert len(gate) == 1
    assert gate[0]["text"] == "Electrical safety checks failed on the compiled build graph."
    assert gate[0]["producer_run"] == "action-new"
    assert gate[0]["finding_id"] == finding_id(
        "failed_check",
        None,
        "Electrical safety checks failed on the compiled build graph.",
        "action-new",
    )
    assert other == [
        row
        for row in original[ENGINEERING_FINDINGS_KEY]
        if row["producer"] == "release_assessment"
    ]
    assert updated["release_authorized"] is False


def test_replace_producer_findings_empty_list_clears_that_producer() -> None:
    snapshot = {
        ENGINEERING_FINDINGS_KEY: [
            {
                **_entry(),
                "producer": "design_quality_gate",
                "producer_run": "action-old",
            },
            {
                **_entry(
                    category="release_blocker",
                    text="safety requirement is open",
                    source_ref="safety_not_closed",
                ),
                "producer": "release_assessment",
                "producer_run": "assess_release@rev1",
            },
        ]
    }
    original = deepcopy(snapshot)

    updated = replace_producer_findings(snapshot, "design_quality_gate", "action-fixed", [])

    assert snapshot == original
    producers = {row["producer"] for row in updated[ENGINEERING_FINDINGS_KEY]}
    assert producers == {"release_assessment"}


def test_replace_producer_findings_rejects_unallowlisted_producer_even_when_empty() -> None:
    snapshot = {
        ENGINEERING_FINDINGS_KEY: [
            {
                **_entry(),
                "producer": "design_quality_gate",
                "producer_run": "action-old",
            },
            {
                **_entry(
                    category="release_blocker",
                    text="safety requirement is open",
                    source_ref="safety_not_closed",
                ),
                "producer": "release_assessment",
                "producer_run": "assess_release@rev1",
            },
        ]
    }
    original = deepcopy(snapshot)

    with pytest.raises(ValueError, match="allowlist"):
        replace_producer_findings(snapshot, "untrusted_producer", "run-1", [])

    assert snapshot == original
    assert snapshot[ENGINEERING_FINDINGS_KEY] == original[ENGINEERING_FINDINGS_KEY]


def test_replace_producer_findings_replaces_malformed_ledger() -> None:
    incoming = [_entry(text="Catalog build graph did not compile.", source_ref="action-new")]
    other = {
        **_entry(
            category="release_blocker",
            text="requirement remains unverified",
            object_id="req-rail",
            source_ref="unverified_requirement",
        ),
        "producer": "release_assessment",
        "producer_run": "assess_release@rev1",
    }

    for raw in (None, "x", {}):
        updated = replace_producer_findings(
            {ENGINEERING_FINDINGS_KEY: raw},
            "design_quality_gate",
            "action-new",
            incoming,
        )
        rows = updated[ENGINEERING_FINDINGS_KEY]
        assert isinstance(rows, list)
        assert len(rows) == 1
        assert rows[0]["producer"] == "design_quality_gate"
        assert rows[0]["text"] == "Catalog build graph did not compile."

    well_formed = replace_producer_findings(
        {ENGINEERING_FINDINGS_KEY: [other]},
        "design_quality_gate",
        "action-new",
        incoming,
    )
    producers = {row["producer"] for row in well_formed[ENGINEERING_FINDINGS_KEY]}
    assert producers == {"design_quality_gate", "release_assessment"}


def test_replace_producer_findings_ids_match_projection_function() -> None:
    updated = replace_producer_findings(
        {},
        "release_assessment",
        "assess_release@rev3",
        [
            _entry(
                category="release_blocker",
                text="verification 'v-1' is failed",
                object_id="v-1",
                source_ref="verification_not_passed",
            )
        ],
    )
    row = updated[ENGINEERING_FINDINGS_KEY][0]
    assert row["finding_id"] == finding_id(
        "release_blocker",
        "v-1",
        "verification 'v-1' is failed",
        "verification_not_passed",
    )
    assert row["provenance"]["kind"] == "deterministic"
    assert row["provenance"]["authority_ceiling"] == "observed"


@pytest.mark.parametrize(
    "entry, match",
    [
        (_entry(text=""), "non-empty"),
        (_entry(text="x" * 1001), "at most 1000"),
        (_entry(kind="unknown"), "deterministic"),
        (_entry(kind="model_derived"), "deterministic"),
        (_entry(extra={"release_authorized": True}), "authority-ish"),
        (_entry(extra={"authority": "verified"}), "authority-ish"),
    ],
)
def test_replace_producer_findings_rejects_invalid_entries(entry: dict, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        replace_producer_findings({}, "design_quality_gate", "action-1", [entry])


def test_replace_producer_findings_rejects_upgraded_authority_ceiling() -> None:
    entry = _entry()
    entry["provenance"]["authority_ceiling"] = "verified"
    with pytest.raises(ValueError, match="authority_ceiling"):
        replace_producer_findings({}, "design_quality_gate", "action-1", [entry])


def test_replace_producer_findings_rejects_missing_authority_ceiling() -> None:
    entry = _entry()
    del entry["provenance"]["authority_ceiling"]
    with pytest.raises(ValueError, match="authority_ceiling"):
        replace_producer_findings({}, "design_quality_gate", "action-1", [entry])


def test_replace_producer_findings_rejects_unknown_top_level_key() -> None:
    with pytest.raises(ValueError, match="unknown extra keys"):
        replace_producer_findings(
            {},
            "design_quality_gate",
            "action-1",
            [_entry(extra={"extra": "forged"})],
        )


def test_replace_producer_findings_rejects_unknown_provenance_key() -> None:
    entry = _entry()
    entry["provenance"]["note"] = "forged"
    with pytest.raises(ValueError, match="unknown extra provenance keys"):
        replace_producer_findings({}, "design_quality_gate", "action-1", [entry])


def test_validate_recorded_at_accepts_only_utc() -> None:
    assert validate_recorded_at("2026-10-05T06:00:00+00:00") == "2026-10-05T06:00:00+00:00"
    assert validate_recorded_at("2026-10-05T06:00:00Z") == "2026-10-05T06:00:00Z"
    with pytest.raises(ValueError, match="UTC"):
        validate_recorded_at("2026-10-05T14:00:00+08:00")
    with pytest.raises(ValueError, match="UTC"):
        validate_recorded_at("2026-10-05T06:00:00")


def test_bound_finding_text_marks_truncation() -> None:
    exact = "x" * MAX_FINDING_TEXT
    assert bound_finding_text(exact) == (exact, False)
    long = "y" * (MAX_FINDING_TEXT + 25)
    bounded, truncated = bound_finding_text(long)
    assert truncated is True
    assert len(bounded) == MAX_FINDING_TEXT
    assert bounded == ("y" * (MAX_FINDING_TEXT - 1)) + "…"


def test_validate_ledger_entry_rejects_schema_defects() -> None:
    category = "failed_check"
    text = "DRC failed with 2 error(s)."
    source_ref = "action-1"
    valid = {
        "finding_id": finding_id(category, None, text, source_ref),
        "category": category,
        "object_id": None,
        "text": text,
        "producer": "design_quality_gate",
        "producer_run": "action-1",
        "provenance": {
            "kind": "deterministic",
            "basis": "design_quality gate blocker from an executed deterministic compose",
            "source_ref": source_ref,
            "authority_ceiling": AUTHORITY_CEILING,
        },
        "recorded_at": "2026-10-05T06:00:00+00:00",
    }
    assert validate_ledger_entry(valid)["finding_id"] == valid["finding_id"]

    with pytest.raises(ValueError, match="category"):
        validate_ledger_entry({**valid, "category": "traceability_issue"})
    with pytest.raises(ValueError, match="non-empty"):
        validate_ledger_entry({**valid, "text": ""})
    with pytest.raises(ValueError, match="at most 1000"):
        validate_ledger_entry({**valid, "text": "x" * 1001})
    with pytest.raises(ValueError, match="deterministic"):
        validate_ledger_entry(
            {**valid, "provenance": {**valid["provenance"], "kind": "unknown"}}
        )
    with pytest.raises(ValueError, match="allowlist"):
        validate_ledger_entry({**valid, "producer": "invented"})
    with pytest.raises(ValueError, match="producer_run"):
        validate_ledger_entry({**valid, "producer_run": ""})
    with pytest.raises(ValueError, match="recorded_at"):
        validate_ledger_entry({k: v for k, v in valid.items() if k != "recorded_at"})
    with pytest.raises(ValueError, match="UTC"):
        validate_ledger_entry({**valid, "recorded_at": "2026-10-05T14:00:00+08:00"})
    with pytest.raises(ValueError, match="authority_ceiling"):
        validate_ledger_entry(
            {**valid, "provenance": {**valid["provenance"], "authority_ceiling": "verified"}}
        )
    with pytest.raises(ValueError, match="finding_id"):
        validate_ledger_entry({**valid, "finding_id": "finding-forged000000"})
    with pytest.raises(ValueError, match="unknown extra keys"):
        validate_ledger_entry({**valid, "forged": True})
