from __future__ import annotations

import pytest

from hardware_splicer.fabrication_operator import FabricationValidationError
from hardware_splicer.machine_project import AuthorityState
from hardware_splicer.physical_evidence import PhysicalEvidenceKind
from hardware_splicer.physical_feedback import promote_observation_to_evidence
from hardware_splicer.physical_observation_store import PhysicalObservationStore


def _store_with_frame(tmp_path):
    store = PhysicalObservationStore(tmp_path / "observations")
    record = store.put(
        kind="image",
        source_id="bench-camera-a",
        media_type="image/png",
        data=b"retained-image-bytes",
        metadata={"width": 10, "height": 10},
    )
    return store, record


def test_raw_observation_requires_explicit_pass_fail_and_criteria_before_evidence(tmp_path):
    store, raw = _store_with_frame(tmp_path)
    evidence = promote_observation_to_evidence(
        store,
        raw.observation_id,
        evidence_id="ev-camera-fit-1",
        project_id="project-a",
        candidate_revision="rev-2",
        kind=PhysicalEvidenceKind.INSPECTION,
        target_ids=["enclosure-v2"],
        procedure_id="visual-fit-check-v1",
        passed=True,
        operator="human-reviewer",
        acceptance_criteria={"connector_visible": True, "gross_warping": False},
    )
    assert evidence.authority == AuthorityState.MEASURED
    assert evidence.passed is True
    assert evidence.metadata["simulated"] is False
    assert evidence.metadata["source_class"] == "machine_observation"
    assert evidence.metadata["observation_id"] == raw.observation_id
    assert evidence.metadata["observation_sha256"] == raw.sha256
    assert evidence.raw_refs == [
        f"physical-observation:{raw.observation_id}:sha256:{raw.sha256}"
    ]


def test_instrument_backed_promotion_requires_calibration_reference(tmp_path):
    store = PhysicalObservationStore(tmp_path / "observations")
    raw = store.put(
        kind="instrument_trace",
        source_id="dmm-1",
        media_type="application/json",
        data=b'{"volts":3.31}',
    )
    with pytest.raises(FabricationValidationError, match="calibration"):
        promote_observation_to_evidence(
            store,
            raw.observation_id,
            evidence_id="ev-rail",
            project_id="project-a",
            candidate_revision="rev-3",
            kind="electrical_measurement",
            target_ids=["3v3-rail"],
            procedure_id="rail-voltage-v1",
            passed=True,
            operator="hardware-splicer",
            acceptance_criteria={"min_v": 3.2, "max_v": 3.4},
            measured_values={"volts": 3.31},
            instrument_ids=["dmm-1"],
        )

    evidence = promote_observation_to_evidence(
        store,
        raw.observation_id,
        evidence_id="ev-rail",
        project_id="project-a",
        candidate_revision="rev-3",
        kind="electrical_measurement",
        target_ids=["3v3-rail"],
        procedure_id="rail-voltage-v1",
        passed=True,
        operator="hardware-splicer",
        acceptance_criteria={"min_v": 3.2, "max_v": 3.4},
        measured_values={"volts": 3.31},
        instrument_ids=["dmm-1"],
        calibration_ids=["cal-dmm-2026"],
    )
    assert evidence.instrument_ids == ["dmm-1"]
    assert evidence.calibration_ids == ["cal-dmm-2026"]


def test_promotion_cannot_overwrite_retained_provenance(tmp_path):
    store, raw = _store_with_frame(tmp_path)
    for metadata in (
        {"simulated": True},
        {"source_class": "hs_verified"},
        {"observation_sha256": "0" * 64},
    ):
        with pytest.raises(FabricationValidationError, match="reserved"):
            promote_observation_to_evidence(
                store,
                raw.observation_id,
                evidence_id="ev-1",
                project_id="project-a",
                candidate_revision="rev-1",
                kind="inspection",
                target_ids=["case"],
                procedure_id="inspection-v1",
                passed=False,
                operator="reviewer",
                acceptance_criteria={"fit": True},
                metadata=metadata,
            )


def test_tampered_raw_observation_cannot_be_promoted(tmp_path):
    store, raw = _store_with_frame(tmp_path)
    payload = tmp_path / "observations" / raw.observation_id / "payload.bin"
    payload.write_bytes(b"changed")
    with pytest.raises(FabricationValidationError, match="no longer matches"):
        promote_observation_to_evidence(
            store,
            raw.observation_id,
            evidence_id="ev-1",
            project_id="project-a",
            candidate_revision="rev-1",
            kind="inspection",
            target_ids=["case"],
            procedure_id="inspection-v1",
            passed=False,
            operator="reviewer",
            acceptance_criteria={"fit": True},
        )
