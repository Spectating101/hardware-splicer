from hardware_splicer.gcode_dry_run import GcodeDryRunAnalyzer, MachineEnvelope
from hardware_splicer.physical_artifact import PhysicalArtifactRegistry


def test_modal_linear_motion_is_included_in_bounds():
    artifacts = PhysicalArtifactRegistry()
    artifacts.register(
        artifact_id="modal-job",
        kind="machine_job",
        generator="cam",
        content=b"G21\nG90\nG1 X10 Y0 F200\nX120 Y0\n",
    )
    report = GcodeDryRunAnalyzer(
        artifacts=artifacts,
        envelope=MachineEnvelope(0, 100, 0, 100, -5, 20),
    ).analyze("modal-job")
    assert report["motion_lines"] == 2
    assert report["bounds_mm"]["x"] == [0.0, 120.0]
    assert report["envelope_violations"][0]["axis"] == "X"


def test_non_integer_gcode_is_blocked_not_ignored():
    artifacts = PhysicalArtifactRegistry()
    artifacts.register(
        artifact_id="opaque-job",
        kind="machine_job",
        generator="cam",
        content=b"G21\nG90\nG59.1\nX20\n",
    )
    report = GcodeDryRunAnalyzer(
        artifacts=artifacts,
        envelope=MachineEnvelope(0, 100, 0, 100, -5, 20),
    ).analyze("opaque-job")
    assert any(row["type"] == "non_integer_or_unsupported_control_code" for row in report["unsupported_or_opaque"])
    assert report["ready_for_live_execution"] is False
