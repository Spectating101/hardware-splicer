from __future__ import annotations

from hardware_splicer.manufacturing_closure import build_manufacturing_closure


def test_raw_and_normalized_inputs_do_not_duplicate_closure_checks() -> None:
    intake = {
        "electrical_pins": [{"component_id": "mcu", "pin": "gpio1", "net": "motor_pwm"}],
        "firmware_pin_map": [{"component_id": "mcu", "physical_pin": "gpio1", "net": "motor_pwm"}],
        "connectors": [
            {"connector_id": "j1", "mates_with": "p1"},
            {"connector_id": "p1", "mates_with": "j1"},
        ],
        "harnesses": [
            {
                "harness_id": "h1",
                "endpoints": ["j1", "p1"],
                "conductors": [{"from_pin": "1", "to_pin": "1", "net": "motor_pwm"}],
            }
        ],
        "bom": [{"part_id": "motor", "quantity": 1}],
        "physical_instances": [{"part_id": "motor", "quantity": 1}],
        "fasteners": [{"fastener_id": "m3", "size": "M3"}],
        "assembly_steps": [{"instruction": "Install the M3 fastener."}],
        "mounts": [{"mount_id": "motor", "cad_id": "motor-step"}],
        "cad_models": [{"cad_id": "motor-step"}],
        "fabrication_artifacts": [
            {"artifact_id": "release", "revision": "r1", "content_hash": "sha256:release"}
        ],
    }
    plan = {
        "machine_project": {"project_id": "dedup", "metadata": {}, "discipline_payloads": {}},
        "candidate_revision": "r1",
        "normalized_intake": dict(intake),
    }

    report = build_manufacturing_closure(plan, intake=intake)
    check_ids = [row.check_id for row in report.checks]

    assert len(check_ids) == len(set(check_ids))
    quantity = next(row for row in report.checks if row.check_id == "bom-quantity-motor")
    assert quantity.metadata == {"bom_quantity": 1, "instance_quantity": 1}
    assert report.status == "closed"
