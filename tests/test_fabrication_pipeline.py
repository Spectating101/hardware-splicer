from __future__ import annotations

import hashlib

import pytest

from hardware_splicer.fabrication_operator import FabricationGrantStore, FabricationValidationError
from hardware_splicer.fabrication_pipeline import FabricationPipeline
from hardware_splicer.printer_operator import FabricationPrinter, OctoPrintBackend
from hardware_splicer.slicer_operator import SlicedArtifact, SlicerOperator, SlicerProfile
from hardware_splicer.slicer_registry import SlicerProfileRegistry

HUMAN = {"kind": "human", "id": "project-owner"}
PROJECT = "fielddeck"
MISSION = "mission-fabrication-001"
GEOMETRY = b"solid fielddeck\nendsolid fielddeck\n"
PROFILE_BYTES = b"[print:HS]\nlayer_height = 0.2\n"
GCODE = b"; fake sliced output\nG28\nG1 X10 Y10\n"


class FakeSlicer:
    name = "fake_slicer"
    version = "1.0.0"

    def slice(self, *, source_filename, geometry, profile):
        return GCODE, {"estimated_time_seconds": 90}


class FakeTransport:
    def __init__(self):
        self.calls = []

    def upload(self, path, *, filename, data, fields):
        self.calls.append(("upload", path, filename, data, dict(fields)))
        return {"files": {"local": {"path": filename}}}

    def request(self, method, path, *, json_body=None):
        self.calls.append(("request", method, path, json_body))
        return {}


def _profile(printer_id="printer-lab"):
    return SlicerProfile(
        profile_id=f"{printer_id}-pla",
        printer_id=printer_id,
        filename="profile.ini",
        content=PROFILE_BYTES,
        material="PLA",
    )


def _pipeline(tmp_path, printer_id="printer-lab"):
    grants = FabricationGrantStore(tmp_path / "grants")
    transport = FakeTransport()
    printer = FabricationPrinter(
        printer_id=printer_id,
        backend=OctoPrintBackend(),
        transport=transport,
        grants=grants,
    )
    return FabricationPipeline(printer), grants, transport


def _slice(profile=None):
    return SlicerOperator(FakeSlicer()).slice_geometry(
        source_filename="fielddeck-case.stl",
        geometry=GEOMETRY,
        profile=profile or _profile(),
    )


def test_profile_registry_exposes_hash_not_bytes_and_enforces_printer_binding():
    registry = SlicerProfileRegistry([_profile(), _profile("printer-two")])
    public = registry.list_public(printer_id="printer-lab")
    assert len(public) == 1
    assert public[0]["profile_id"] == "printer-lab-pla"
    assert public[0]["profile_sha256"] == hashlib.sha256(PROFILE_BYTES).hexdigest()
    assert "content" not in public[0]
    assert registry.get("printer-lab-pla", printer_id="printer-lab").content == PROFILE_BYTES
    with pytest.raises(FabricationValidationError, match="different printer"):
        registry.get("printer-two-pla", printer_id="printer-lab")


def test_pipeline_stages_only_exact_gcode_from_matching_slicer_receipt(tmp_path):
    pipeline, _grants, transport = _pipeline(tmp_path)
    artifact = _slice()
    staged = pipeline.stage_sliced(artifact)

    assert staged.prepared.artifact_sha256 == hashlib.sha256(GCODE).hexdigest()
    assert staged.slicer_receipt.output_gcode_sha256 == staged.prepared.artifact_sha256
    assert len(staged.slicer_receipt_sha256) == 64
    assert transport.calls == [
        (
            "upload",
            "/api/files/local",
            "fielddeck-case.gcode",
            GCODE,
            {"select": "true", "print": "false"},
        )
    ]


def test_pipeline_rejects_tampered_gcode_before_printer_upload(tmp_path):
    pipeline, _grants, transport = _pipeline(tmp_path)
    artifact = _slice()
    tampered = SlicedArtifact(receipt=artifact.receipt, gcode=artifact.gcode + b"M112\n")
    with pytest.raises(FabricationValidationError, match="do not match"):
        pipeline.stage_sliced(tampered)
    assert transport.calls == []


def test_pipeline_rejects_receipt_for_other_printer(tmp_path):
    pipeline, _grants, transport = _pipeline(tmp_path, printer_id="printer-lab")
    artifact = _slice(_profile("printer-two"))
    with pytest.raises(FabricationValidationError, match="different printer"):
        pipeline.stage_sliced(artifact)
    assert transport.calls == []


def test_pipeline_start_still_requires_exact_one_shot_human_grant(tmp_path):
    pipeline, grants, transport = _pipeline(tmp_path)
    staged = pipeline.stage_sliced(_slice())
    grant = grants.issue(
        project_id=PROJECT,
        mission_id=MISSION,
        operator_id="printer-lab",
        action="start",
        artifact_sha256=staged.prepared.artifact_sha256,
        author=HUMAN,
    )
    run = pipeline.start(
        staged,
        project_id=PROJECT,
        mission_id=MISSION,
        grant_id=grant["grant_id"],
    )
    assert run.artifact_sha256 == staged.slicer_receipt.output_gcode_sha256
    assert transport.calls[-1] == ("request", "POST", "/api/job", {"command": "start"})
