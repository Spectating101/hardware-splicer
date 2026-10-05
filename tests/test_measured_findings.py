from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from hardware_splicer.finding_ledger import MAX_FINDING_TEXT
from hardware_splicer.finding_provenance import finding_id, project_findings
from hardware_splicer.physical_evidence import (
    PhysicalEvidenceKind,
    PhysicalEvidenceRecord,
)
from hardware_splicer.physical_evidence_ledger import (
    PhysicalEvidenceEnvelope,
    build_physical_evidence_envelope,
    physical_evidence_envelope_hash,
)
from hardware_splicer.project_findings_api import create_project_findings_router
from hardware_splicer.project_physical_validation import validate_packet_evidence
from hardware_splicer.project_store import ProjectStore
from test_physical_evidence_ledger import _record as ledger_fixture_record

# Captured from the ledger fixture envelope before finding_links existed.
_GOLDEN_LEDGER_ENVELOPE_HASH = (
    "sha256:c66647f33d2310464c423787f3f89c44adc79ba9ed8bc206f143569badf06b5a"
)
# Computed on the unmodified base commit for a legacy record with a None
# measured value (exclude_none hashing would drop it and change this digest).
_GOLDEN_LEGACY_ENVELOPE_HASH = (
    "sha256:db222b6a2f3242383f6e34289545f730b38de05fddbdefb3bbdab0dd06b5eaaf"
)
_PHYSICAL_BASIS = (
    "non-simulated measurement record states that it establishes this finding"
)
_MALFORMED_BASIS = "malformed or non-qualifying measurement record ignored"
_ESTABLISH_TEXT = "Rail current exceeded the declared limit."


def _establish_id(
    evidence_id: str,
    text: str = _ESTABLISH_TEXT,
    object_id: str | None = "rail",
) -> str:
    return finding_id("measured_finding", object_id, text, evidence_id)


def _link(
    *,
    evidence_id: str,
    relation: str,
    text: str | None = _ESTABLISH_TEXT,
    object_id: str | None = "rail",
    finding_id_value: str | None = None,
) -> dict:
    row: dict = {
        "finding_id": finding_id_value
        or (
            _establish_id(evidence_id, text or "", object_id)
            if relation == "establishes" and text
            else "finding-unmatched0000"
        ),
        "relation": relation,
    }
    if text is not None:
        row["text"] = text
    if object_id is not None:
        row["object_id"] = object_id
    return row


def _record_kwargs(
    *,
    evidence_id: str = "rail-test",
    passed: bool = False,
    authority: str = "measured",
    simulated: bool | None = False,
    finding_links: list[dict] | None = None,
    extra_metadata: dict | None = None,
) -> dict:
    metadata: dict = {}
    if simulated is not None:
        metadata["simulated"] = simulated
    if extra_metadata:
        metadata.update(extra_metadata)
    body: dict = {
        "evidence_id": evidence_id,
        "project_id": "physical-rover",
        "candidate_revision": "r2",
        "kind": PhysicalEvidenceKind.ELECTRICAL,
        "target_ids": ["physical-rover"],
        "procedure_id": "procedure-current-limited-power",
        "passed": passed,
        "captured_at": "2026-08-04T02:30:00+00:00",
        "operator": "bench-operator",
        "authority": authority,
        "metadata": metadata,
    }
    if finding_links is not None:
        body["finding_links"] = finding_links
    return body


def _record(**kwargs) -> PhysicalEvidenceRecord:
    return PhysicalEvidenceRecord(**_record_kwargs(**kwargs))


def _envelope_record_dump(record: PhysicalEvidenceRecord | dict) -> dict:
    if isinstance(record, PhysicalEvidenceRecord):
        return record.model_dump(mode="json")
    return dict(record)


def _physical_snapshot(
    records: list[PhysicalEvidenceRecord | dict],
    extra: dict | None = None,
) -> dict:
    envelopes = []
    for index, record in enumerate(records, start=1):
        dumped = _envelope_record_dump(record)
        envelopes.append(
            {
                "envelope_id": f"envelope-{dumped.get('evidence_id', index)}",
                "record": dumped,
            }
        )
    snapshot = {
        "physicalValidation": {
            "audited_physical_evidence": {"envelopes": envelopes}
        }
    }
    if extra:
        snapshot.update(extra)
    return snapshot


def test_establishes_link_accepted_on_failed_non_simulated_measured_record() -> None:
    record = _record(
        finding_links=[_link(evidence_id="rail-test", relation="establishes")],
    )
    assert record.finding_links is not None
    assert len(record.finding_links) == 1
    assert record.finding_links[0].relation == "establishes"


@pytest.mark.parametrize("authority", ["measured", "verified", "authorized"])
def test_establishes_accepts_measured_verified_authorized(authority: str) -> None:
    _record(
        authority=authority,
        finding_links=[_link(evidence_id="rail-test", relation="establishes")],
    )


def test_clears_link_accepted_on_passing_record() -> None:
    record = _record(
        passed=True,
        finding_links=[
            _link(
                evidence_id="rail-test",
                relation="clears",
                text=None,
                finding_id_value="finding-existing00000",
            )
        ],
    )
    assert record.finding_links[0].relation == "clears"
    assert record.finding_links[0].text is None


def test_absent_finding_links_default_none() -> None:
    record = _record()
    assert record.finding_links is None


def test_rejects_unknown_relation() -> None:
    with pytest.raises(ValueError, match="relation"):
        _record(
            finding_links=[
                {
                    "finding_id": _establish_id("rail-test"),
                    "relation": "mentions",
                    "text": _ESTABLISH_TEXT,
                    "object_id": "rail",
                }
            ]
        )


def test_rejects_establishes_on_passing_record() -> None:
    with pytest.raises(ValueError, match="passing measurement cannot establish"):
        _record(
            passed=True,
            finding_links=[_link(evidence_id="rail-test", relation="establishes")],
        )


def test_rejects_establishes_when_simulated_true() -> None:
    with pytest.raises(ValueError, match="simulated"):
        _record(
            simulated=True,
            finding_links=[_link(evidence_id="rail-test", relation="establishes")],
        )


def test_rejects_establishes_when_simulated_flag_missing() -> None:
    with pytest.raises(ValueError, match="simulated"):
        _record(
            simulated=None,
            finding_links=[_link(evidence_id="rail-test", relation="establishes")],
        )


def test_rejects_establishes_without_text() -> None:
    with pytest.raises(ValueError, match="text"):
        _record(
            finding_links=[
                {
                    "finding_id": "finding-notused000000",
                    "relation": "establishes",
                    "object_id": "rail",
                }
            ]
        )


def test_rejects_establishes_text_over_limit() -> None:
    with pytest.raises(ValueError, match="1000"):
        _record(
            finding_links=[
                _link(
                    evidence_id="rail-test",
                    relation="establishes",
                    text="x" * (MAX_FINDING_TEXT + 1),
                )
            ]
        )


def test_rejects_clears_on_failed_record() -> None:
    with pytest.raises(ValueError, match="passing"):
        _record(
            passed=False,
            finding_links=[
                _link(
                    evidence_id="rail-test",
                    relation="clears",
                    text=None,
                    finding_id_value="finding-existing00000",
                )
            ],
        )


def test_rejects_more_than_twenty_links() -> None:
    links = [
        _link(
            evidence_id="rail-test",
            relation="establishes",
            text=f"Defect {index}.",
            object_id="rail",
        )
        for index in range(21)
    ]
    with pytest.raises(ValueError, match="20"):
        _record(finding_links=links)


def test_rejects_low_authority_even_with_establishes_link() -> None:
    with pytest.raises(ValueError, match="physical evidence authority"):
        _record(
            authority="observed",
            finding_links=[_link(evidence_id="rail-test", relation="establishes")],
        )


def test_old_record_envelope_hash_unchanged_when_finding_links_absent() -> None:
    record = ledger_fixture_record()
    dumped = record.model_dump(mode="json")
    assert "finding_links" not in dumped
    envelope = build_physical_evidence_envelope(
        envelope_id="envelope-thermal-run",
        record=record,
        raw_files=[
            {
                "ref": "lab://thermal/run-1.csv",
                "content_hash": f"sha256:{'a' * 64}",
                "media_type": "text/csv",
                "size_bytes": 2048,
            }
        ],
        created_at="2026-08-04T02:05:00+00:00",
        created_by="operator",
    )
    assert envelope.envelope_hash == _GOLDEN_LEDGER_ENVELOPE_HASH


def test_legacy_record_envelope_hash_matches_unmodified_base() -> None:
    rec = PhysicalEvidenceRecord(
        evidence_id="ev-1",
        project_id="p",
        candidate_revision="6",
        kind="inspection",
        target_ids=["t"],
        procedure_id="proc",
        passed=True,
        captured_at="2026-10-01T00:00:00Z",
        operator="op",
        measured_values={"temperature_c": None, "vout": 1.8},
        metadata={"simulated": False},
    )
    dumped = rec.model_dump(mode="json")
    assert "finding_links" not in dumped
    assert (
        physical_evidence_envelope_hash(
            envelope_id="e1",
            record=rec,
            raw_files=[],
            created_at="2026-10-01T00:00:00Z",
            created_by="x",
        )
        == _GOLDEN_LEGACY_ENVELOPE_HASH
    )
    linked = PhysicalEvidenceRecord(
        evidence_id="ev-1",
        project_id="p",
        candidate_revision="6",
        kind="inspection",
        target_ids=["t"],
        procedure_id="proc",
        passed=True,
        captured_at="2026-10-01T00:00:00Z",
        operator="op",
        measured_values={"temperature_c": None, "vout": 1.8},
        metadata={"simulated": False},
        finding_links=[
            {
                "finding_id": "finding-legacy000001",
                "relation": "clears",
            }
        ],
    )
    assert "finding_links" in linked.model_dump(mode="json")
    assert (
        physical_evidence_envelope_hash(
            envelope_id="e1",
            record=linked,
            raw_files=[],
            created_at="2026-10-01T00:00:00Z",
            created_by="x",
        )
        != _GOLDEN_LEGACY_ENVELOPE_HASH
    )


def test_two_records_establishing_same_text_keep_one_and_annotate_rest() -> None:
    later = _record(
        evidence_id="ev-b",
        finding_links=[_link(evidence_id="ev-b", relation="establishes")],
    )
    earlier = _record(
        evidence_id="ev-a",
        finding_links=[_link(evidence_id="ev-a", relation="establishes")],
        authority="verified",
    )
    findings = project_findings(_physical_snapshot([later, earlier]), 1)
    measured = [row for row in findings if row["category"] == "measured_finding"]
    assert len(measured) == 1
    row = measured[0]
    assert row["provenance"]["source_ref"] == "ev-a"
    assert row["finding_id"] == _establish_id("ev-a")
    assert row["physical_evidence"] == [
        {
            "evidence_id": "ev-b",
            "relation": "establishes",
            "passed": False,
            "authority": "measured",
        }
    ]


def test_packet_ingest_accepts_valid_establishes_links() -> None:
    record = PhysicalEvidenceRecord(
        evidence_id="dut-fail",
        project_id="adapter",
        candidate_revision="adapter@deadbeef",
        kind=PhysicalEvidenceKind.INSPECTION,
        target_ids=["identify-dut"],
        procedure_id="hs.spi.identify-dut.v1",
        passed=False,
        captured_at="2026-09-13T02:00:00+00:00",
        operator="bench-operator",
        raw_refs=["lab://dut-fail.jpg"],
        artifact_hashes={"canonical-project-snapshot": "sha256:" + "a" * 64},
        metadata={
            "simulated": False,
            "public_web": False,
            "capture_origin": "physical_test_article",
            "direct_operator_observation": True,
        },
        finding_links=[
            _link(
                evidence_id="dut-fail",
                relation="establishes",
                text="Observed marking does not match the declared DUT.",
                object_id="identify-dut",
            )
        ],
    )
    envelope = build_physical_evidence_envelope(
        envelope_id="envelope-dut-fail",
        record=record,
        raw_files=[
            {
                "ref": "lab://dut-fail.jpg",
                "content_hash": "sha256:" + "c" * 64,
                "media_type": "image/jpeg",
            }
        ],
        created_at="2026-09-13T02:05:00+00:00",
        created_by="bench-operator",
    )
    packet = {
        "project_id": "adapter",
        "candidate_revision": "adapter@deadbeef",
        "artifact_hashes": {"canonical-project-snapshot": "sha256:" + "a" * 64},
        "gates": [
            {
                "gate_id": "identify-dut",
                "kind": PhysicalEvidenceKind.INSPECTION.value,
                "procedure_id": "hs.spi.identify-dut.v1",
                "required_measured_fields": [],
                "required_raw_media": ["image/*"],
                "prerequisite_gate_ids": [],
                "requires_authorized_operation": None,
            }
        ],
    }
    validate_packet_evidence(packet, [envelope])


def test_packet_ingest_rejects_malformed_links() -> None:
    body = _record_kwargs(
        evidence_id="dut-fail",
        finding_links=[
            {
                "finding_id": "finding-bad",
                "relation": "establishes",
                "text": _ESTABLISH_TEXT,
                "object_id": "rail",
            }
        ],
    )
    body["kind"] = PhysicalEvidenceKind.INSPECTION
    body["target_ids"] = ["identify-dut"]
    body["procedure_id"] = "hs.spi.identify-dut.v1"
    body["raw_refs"] = ["lab://dut-fail.jpg"]
    body["artifact_hashes"] = {"canonical-project-snapshot": "sha256:" + "a" * 64}
    body["metadata"] = {
        "simulated": False,
        "public_web": False,
        "capture_origin": "physical_test_article",
        "direct_operator_observation": True,
    }
    with pytest.raises((ValueError, ValidationError)):
        PhysicalEvidenceEnvelope.model_validate(
            {
                "envelope_id": "envelope-dut-fail",
                "record": body,
                "raw_files": [
                    {
                        "ref": "lab://dut-fail.jpg",
                        "content_hash": "sha256:" + "c" * 64,
                    }
                ],
                "created_at": "2026-09-13T02:05:00+00:00",
                "created_by": "bench-operator",
                "envelope_hash": "sha256:" + "d" * 64,
            }
        )


def test_projection_emits_physical_finding_for_qualifying_failed_record() -> None:
    record = _record(
        finding_links=[_link(evidence_id="rail-test", relation="establishes")],
    )
    findings = project_findings(_physical_snapshot([record]), 1)
    measured = [row for row in findings if row["category"] == "measured_finding"]
    assert len(measured) == 1
    row = measured[0]
    assert row["object_id"] == "rail"
    assert row["text"] == _ESTABLISH_TEXT
    assert row["finding_id"] == _establish_id("rail-test")
    assert row["provenance"] == {
        "kind": "physical",
        "basis": _PHYSICAL_BASIS,
        "source_ref": "rail-test",
        "authority_ceiling": "observed",
    }


@pytest.mark.parametrize(
    "overrides",
    [
        {"simulated": True},
        {"simulated": None},
        {"passed": True},
        {"authority": "observed"},
    ],
)
def test_projection_never_emits_physical_for_non_qualifying_record(
    overrides: dict,
) -> None:
    kwargs = {
        "passed": False,
        "simulated": False,
        "authority": "measured",
        "finding_links": [_link(evidence_id="rail-test", relation="establishes")],
    }
    kwargs.update(overrides)
    if kwargs.get("passed") is True:
        kwargs["finding_links"] = [
            _link(
                evidence_id="rail-test",
                relation="clears",
                text=None,
                finding_id_value=_establish_id("rail-test"),
            )
        ]
    raw = _record_kwargs(**kwargs)
    findings = project_findings(_physical_snapshot([raw]), 1)
    assert "physical" not in {row["provenance"]["kind"] for row in findings}
    assert all(row["category"] != "measured_finding" for row in findings)


def test_clears_annotates_but_does_not_remove_or_relabel() -> None:
    blocker_text = "No measured startup-current evidence exists."
    blocker_id = finding_id("object_blocker", "rail", blocker_text, None)
    record = _record(
        passed=True,
        finding_links=[
            _link(
                evidence_id="rail-test",
                relation="clears",
                text=None,
                finding_id_value=blocker_id,
            )
        ],
    )
    snapshot = _physical_snapshot(
        [record],
        extra={
            "engineeringSystemGraph": {
                "nodes": [{"object_id": "rail", "blockers": [blocker_text]}]
            }
        },
    )
    findings = project_findings(snapshot, 1)
    blockers = [row for row in findings if row["category"] == "object_blocker"]
    assert len(blockers) == 1
    row = blockers[0]
    assert row["finding_id"] == blocker_id
    assert row["provenance"]["kind"] == "unknown"
    assert row["physical_evidence"] == [
        {
            "evidence_id": "rail-test",
            "relation": "clears",
            "passed": True,
            "authority": "measured",
        }
    ]


def test_unmatched_clears_surfaced_on_api_payload(tmp_path: Path) -> None:
    record = _record(
        passed=True,
        finding_links=[
            _link(
                evidence_id="rail-test",
                relation="clears",
                text=None,
                finding_id_value="finding-doesnotexist01",
            )
        ],
    )
    snapshot = _physical_snapshot([record])
    store = ProjectStore(tmp_path)
    store.save("robot", snapshot, expected_revision=0)
    app = FastAPI()
    app.include_router(create_project_findings_router(store))
    api = TestClient(app)

    response = api.get("/v1/projects/robot/findings")
    assert response.status_code == 200
    body = response.json()
    assert body["unmatched_links"] == [
        {"evidence_id": "rail-test", "finding_id": "finding-doesnotexist01"}
    ]
    assert all(row["category"] != "measured_finding" for row in body["findings"])


def test_malformed_record_is_surfaced_not_dropped() -> None:
    snapshot = {
        "physicalValidation": {
            "audited_physical_evidence": {
                "envelopes": [{"envelope_id": "broken", "record": {"passed": False}}]
            }
        }
    }
    findings = project_findings(snapshot, 1)
    malformed = [
        row
        for row in findings
        if row["category"] == "traceability_issue"
        and row["provenance"]["source_ref"] == "physicalValidation"
    ]
    assert len(malformed) == 1
    assert malformed[0]["provenance"]["kind"] == "unknown"
    assert malformed[0]["provenance"]["basis"] == _MALFORMED_BASIS
    assert malformed[0]["provenance"]["authority_ceiling"] == "observed"


def test_measured_finding_does_not_change_authority_or_snapshot_bytes() -> None:
    record = _record(
        finding_links=[_link(evidence_id="rail-test", relation="establishes")],
    )
    snapshot = _physical_snapshot(
        [record],
        extra={
            "release_authorized": False,
            "physical_authority_granted": False,
            "fabrication_ready": False,
            "requested_release_state": "concept",
        },
    )
    original = deepcopy(snapshot)
    findings = project_findings(snapshot, 1)
    assert snapshot == original
    assert snapshot["release_authorized"] is False
    assert snapshot["physical_authority_granted"] is False
    assert snapshot["fabrication_ready"] is False
    assert any(row["category"] == "measured_finding" for row in findings)
    for row in findings:
        assert row["provenance"]["authority_ceiling"] == "observed"


def test_findings_api_with_measured_finding_is_read_only(tmp_path: Path) -> None:
    record = _record(
        finding_links=[_link(evidence_id="rail-test", relation="establishes")],
    )
    store = ProjectStore(tmp_path)
    store.save("robot", _physical_snapshot([record]), expected_revision=0)
    before = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in sorted(tmp_path.rglob("*"))
        if path.is_file()
    }
    app = FastAPI()
    app.include_router(create_project_findings_router(store))
    api = TestClient(app)
    response = api.get("/v1/projects/robot/findings")
    assert response.status_code == 200
    assert any(
        row["category"] == "measured_finding" for row in response.json()["findings"]
    )
    after = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in sorted(tmp_path.rglob("*"))
        if path.is_file()
    }
    assert after == before


def test_measured_finding_ids_are_stable() -> None:
    record = _record(
        finding_links=[_link(evidence_id="rail-test", relation="establishes")],
    )
    snapshot = _physical_snapshot([record])
    first = project_findings(snapshot, 1)
    second = project_findings(deepcopy(snapshot), 2)
    measured = [row for row in first if row["category"] == "measured_finding"]
    assert measured[0]["finding_id"] == _establish_id("rail-test")
    assert measured[0]["finding_id"] == [
        row["finding_id"] for row in second if row["category"] == "measured_finding"
    ][0]


def test_measured_finding_sorts_before_traceability_issue() -> None:
    record = _record(
        finding_links=[_link(evidence_id="rail-test", relation="establishes")],
    )
    snapshot = _physical_snapshot(
        [record],
        extra={"engineeringFindings": "not-a-list"},
    )
    categories = [row["category"] for row in project_findings(snapshot, 1)]
    assert "measured_finding" in categories
    assert "traceability_issue" in categories
    assert categories.index("measured_finding") < categories.index("traceability_issue")


def test_simulated_record_with_links_is_surfaced_not_physical() -> None:
    raw = _record_kwargs(
        simulated=True,
        finding_links=[_link(evidence_id="rail-test", relation="establishes")],
    )
    findings = project_findings(_physical_snapshot([raw]), 1)
    assert all(row["provenance"]["kind"] != "physical" for row in findings)
    malformed = [
        row
        for row in findings
        if row["provenance"]["source_ref"] == "physicalValidation"
    ]
    assert len(malformed) == 1
    assert malformed[0]["provenance"]["basis"] == _MALFORMED_BASIS
