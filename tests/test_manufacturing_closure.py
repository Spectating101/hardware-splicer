from __future__ import annotations

from hardware_splicer.manufacturing_closure import build_manufacturing_closure


def _closed_plan() -> dict:
    return {
        "machine_project": {"project_id": "inspection-rover", "metadata": {}, "discipline_payloads": {}},
        "candidate_revision": "rev-8",
        "normalized_intake": {
            "electrical_pins": [
                {"component_id": "mcu", "pin": "gpio12", "net": "left_motor_pwm"},
                {"component_id": "mcu", "pin": "gpio13", "net": "right_motor_pwm"},
            ],
            "firmware_pin_map": [
                {"component_id": "mcu", "physical_pin": "gpio12", "net": "left_motor_pwm"},
                {"component_id": "mcu", "physical_pin": "gpio13", "net": "right_motor_pwm"},
            ],
            "connectors": [
                {"connector_id": "j1", "mates_with": "p1"},
                {"connector_id": "p1", "mates_with": "j1"},
            ],
            "harnesses": [
                {
                    "harness_id": "motor-harness",
                    "endpoints": ["j1", "p1"],
                    "conductors": [
                        {"from_pin": "1", "to_pin": "1", "net": "left_motor_pwm"},
                        {"from_pin": "2", "to_pin": "2", "net": "return"},
                    ],
                }
            ],
            "bom": [
                {"part_id": "wheel-motor", "quantity": 2},
                {"part_id": "m3x10", "quantity": 8},
            ],
            "physical_instances": [
                {"part_id": "wheel-motor", "quantity": 2},
                {"part_id": "m3x10", "quantity": 8},
            ],
            "fasteners": [{"fastener_id": "m3x10", "size": "M3x10"}],
            "assembly_steps": [
                {"step_id": "mount-motors", "instruction": "Install both motors using eight M3x10 fasteners."}
            ],
            "mounts": [{"mount_id": "motor-bracket", "cad_id": "motor-bracket-step"}],
            "cad_models": [{"cad_id": "motor-bracket-step", "format": "step"}],
            "fabrication_artifacts": [
                {"artifact_id": "pcb-gerbers", "revision": "rev-8", "content_hash": "sha256:pcb"},
                {"artifact_id": "motor-bracket-step", "revision": "rev-8", "content_hash": "sha256:step"},
                {"artifact_id": "firmware-bin", "revision": "rev-8", "content_hash": "sha256:fw"},
            ],
        },
    }


def test_manufacturing_closure_can_close_consistent_candidate() -> None:
    report = build_manufacturing_closure(_closed_plan())

    assert report.project_id == "inspection-rover"
    assert report.candidate_revision == "rev-8"
    assert report.status == "closed"
    assert report.blocking_checks == []
    assert report.metadata["manufacturing_authorized"] is False
    assert report.metadata["release_authorized"] is False
    assert any(row.check_id == "fabrication-revision-coherence" and row.status.value == "pass" for row in report.checks)


def test_pin_mismatch_is_a_blocking_cross_domain_failure() -> None:
    plan = _closed_plan()
    plan["normalized_intake"]["firmware_pin_map"][0]["net"] = "right_motor_pwm"

    report = build_manufacturing_closure(plan)

    mismatch = next(row for row in report.checks if row.check_id == "pin-mcu-gpio12")
    assert mismatch.status.value == "fail"
    assert mismatch.blocking is True
    assert report.status == "blocked"
    assert any(row["check_id"] == mismatch.check_id for row in report.required_evidence)


def test_harness_bom_mount_and_revision_gaps_remain_explicit() -> None:
    plan = _closed_plan()
    body = plan["normalized_intake"]
    body["connectors"] = [{"connector_id": "j1", "mates_with": "missing-p1"}]
    body["harnesses"][0]["conductors"] = []
    body["bom"][0]["quantity"] = 1
    body["mounts"][0]["cad_id"] = "missing-step"
    body["fabrication_artifacts"][1]["revision"] = "rev-7"

    report = build_manufacturing_closure(plan)
    failing_ids = {row.check_id for row in report.blocking_checks}

    assert "connector-mate-j1" in failing_ids
    assert "harness-endpoints-motor-harness" in failing_ids
    assert "harness-conductors-motor-harness" in failing_ids
    assert "bom-quantity-wheel-motor" in failing_ids
    assert "mount-cad-motor-bracket" in failing_ids
    assert "fabrication-revision-coherence" in failing_ids


def test_missing_manufacturing_inputs_do_not_become_false_passes() -> None:
    report = build_manufacturing_closure(
        {"machine_project": {"project_id": "requirements-only", "metadata": {}, "discipline_payloads": {}}}
    )

    assert report.status == "blocked"
    assert report.blocking_checks
    unknown = {row.check_id for row in report.checks if row.status.value == "unknown"}
    assert {
        "electrical-pin-map-present",
        "firmware-pin-map-present",
        "bom-present",
        "fabrication-artifacts-present",
    }.issubset(unknown)
