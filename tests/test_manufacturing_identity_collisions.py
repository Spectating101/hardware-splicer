from __future__ import annotations

from hardware_splicer.manufacturing_closure import build_manufacturing_closure


def _minimum_release() -> dict:
    return {
        "machine_project": {"project_id": "identity-collision", "metadata": {}, "discipline_payloads": {}},
        "candidate_revision": "r2",
        "normalized_intake": {
            "electrical_pins": [
                {"component_id": "mcu", "pin": "gpio1", "net": "motor_pwm"},
                {"component_id": "mcu", "pin": "gpio1", "net": "status_led"},
            ],
            "firmware_pin_map": [
                {"component_id": "mcu", "physical_pin": "gpio1", "net": "motor_pwm"}
            ],
            "connectors": [
                {"connector_id": "j1", "mates_with": "p1", "pin_count": 2},
                {"connector_id": "j1", "mates_with": "p2", "pin_count": 4},
                {"connector_id": "p1", "mates_with": "j1", "pin_count": 2},
                {"connector_id": "p2", "mates_with": "j1", "pin_count": 4},
            ],
            "harnesses": [
                {
                    "harness_id": "h1",
                    "endpoints": ["j1", "p1"],
                    "conductors": [{"from_pin": "1", "to_pin": "1"}],
                }
            ],
            "bom": [{"part_id": "mcu", "quantity": 1}],
            "physical_instances": [{"instance_id": "mcu-1", "part_id": "mcu", "quantity": 1}],
            "fasteners": [{"fastener_id": "m3", "size": "M3"}],
            "assembly_steps": [{"instruction": "Install the M3 fastener."}],
            "mounts": [{"mount_id": "board", "cad_id": "board-step"}],
            "cad_models": [{"cad_id": "board-step"}],
            "fabrication_artifacts": [
                {"artifact_id": "board", "revision": "r1", "content_hash": "sha256:old"},
                {"artifact_id": "board", "revision": "r2", "content_hash": "sha256:new"},
            ],
        },
    }


def test_conflicting_pin_connector_and_artifact_identities_block_closure() -> None:
    report = build_manufacturing_closure(_minimum_release())
    collisions = {row.check_id: row for row in report.checks if row.category == "identity_collision"}

    assert "identity-collision-electrical_pin-mcu-gpio1" in collisions
    assert "identity-collision-connector-j1" in collisions
    assert "identity-collision-fabrication_artifact-board" in collisions
    assert all(row.blocking for row in collisions.values())
    assert report.metadata["identity_collision_count"] == 3
    assert report.status == "blocked"
    assert {
        "identity-collision-electrical_pin-mcu-gpio1",
        "identity-collision-connector-j1",
        "identity-collision-fabrication_artifact-board",
    }.issubset({row["check_id"] for row in report.required_evidence})


def test_exact_duplicate_rows_are_deduplicated_not_reported_as_collisions() -> None:
    plan = _minimum_release()
    body = plan["normalized_intake"]
    body["electrical_pins"] = [
        {"component_id": "mcu", "pin": "gpio1", "net": "motor_pwm"},
        {"component_id": "mcu", "pin": "gpio1", "net": "motor_pwm"},
    ]
    body["connectors"] = [
        {"connector_id": "j1", "mates_with": "p1", "pin_count": 2},
        {"connector_id": "j1", "mates_with": "p1", "pin_count": 2},
        {"connector_id": "p1", "mates_with": "j1", "pin_count": 2},
    ]
    body["fabrication_artifacts"] = [
        {"artifact_id": "board", "revision": "r2", "content_hash": "sha256:new"},
        {"artifact_id": "board", "revision": "r2", "content_hash": "sha256:new"},
    ]

    report = build_manufacturing_closure(plan)

    assert not [row for row in report.checks if row.category == "identity_collision"]
    assert report.metadata.get("identity_collision_count", 0) == 0
