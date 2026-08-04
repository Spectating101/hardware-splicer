from __future__ import annotations

from hardware_splicer.machine_project import AuthorityState, MachineProject
from hardware_splicer.machine_project_seed import machine_project_from_intake
from hardware_splicer.manufacturing_projection import project_manufacturing_identities


def _intake() -> dict:
    return {
        "project_name": "projection-rover",
        "goal": "Build a traceable inspection rover.",
        "available_parts": [{"name": "controller", "type": "controller"}],
        "connectors": [
            {"connector_id": "j1", "mates_with": "p1", "pin_count": 2},
            {"connector_id": "p1", "mates_with": "j1", "pin_count": 2},
        ],
        "harnesses": [
            {
                "harness_id": "motor-harness",
                "endpoints": ["j1", "p1"],
                "conductors": [{"from_pin": "1", "to_pin": "1", "net": "motor+"}],
            }
        ],
        "physical_instances": [
            {"instance_id": "motor-left-001", "part_id": "wheel-motor", "serial": "L001"}
        ],
        "fasteners": [{"fastener_id": "m3x10", "size": "M3x10", "quantity": 4}],
        "cad_models": [
            {
                "cad_id": "motor-bracket-step",
                "format": "step",
                "path": "cad/motor-bracket.step",
                "revision": "r4",
                "content_hash": "sha256:cad",
            }
        ],
        "mounts": [{"mount_id": "motor-bracket", "cad_id": "motor-bracket-step"}],
        "fabrication_artifacts": [
            {
                "artifact_id": "pcb-gerbers",
                "kind": "gerber_archive",
                "path": "release/pcb.zip",
                "revision": "r4",
                "content_hash": "sha256:pcb",
            }
        ],
    }


def test_projection_creates_canonical_components_interfaces_and_artifacts() -> None:
    intake = _intake()
    project = machine_project_from_intake(intake)
    projected = project_manufacturing_identities(
        project,
        plan={"normalized_intake": intake, "machine_project": project.model_dump(mode="json")},
        intake=intake,
    )

    component_ids = {row.component_id for row in projected.components}
    interface_ids = {row.interface_id for row in projected.interfaces}
    artifact_ids = {row.artifact_id for row in projected.artifacts}

    assert {"mfg-connector-j1", "mfg-connector-p1", "mfg-harness-motor-harness"}.issubset(component_ids)
    assert "mfg-instance-motor-left-001" in component_ids
    assert "mfg-fastener-m3x10" in component_ids
    assert "mfg-mount-motor-bracket" in component_ids
    assert "mfg-harness-interface-motor-harness" in interface_ids
    assert "mfg-cad-motor-bracket-step" in artifact_ids
    assert "mfg-release-pcb-gerbers" in artifact_ids
    assert not [row for row in projected.traceability_issues() if row.code == "invalid_ref"]
    assert projected.metadata["manufacturing_authority_unchanged"] is True


def test_projection_does_not_promote_manufacturing_authority() -> None:
    intake = _intake()
    project = machine_project_from_intake(intake)
    projected = project_manufacturing_identities(
        project,
        plan={"normalized_intake": intake, "machine_project": project.model_dump(mode="json")},
        intake=intake,
    )

    projection = projected.discipline_payloads["manufacturing_projection"]
    assert projection["manufacturing_authorized"] is False
    assert projection["authority"] == AuthorityState.PROPOSED.value
    assert all(
        row.authority in {AuthorityState.PROPOSED, AuthorityState.DECLARED, AuthorityState.OBSERVED}
        for row in projected.components
        if row.component_id.startswith("mfg-")
    )


def test_projection_is_idempotent_for_stable_manufacturing_ids() -> None:
    intake = _intake()
    project = machine_project_from_intake(intake)
    first = project_manufacturing_identities(
        project,
        plan={"normalized_intake": intake, "machine_project": project.model_dump(mode="json")},
        intake=intake,
    )
    second = project_manufacturing_identities(
        first,
        plan={"normalized_intake": intake, "machine_project": first.model_dump(mode="json")},
        intake=intake,
    )

    assert len({row.component_id for row in second.components}) == len(second.components)
    assert len({row.interface_id for row in second.interfaces}) == len(second.interfaces)
    assert len({row.artifact_id for row in second.artifacts}) == len(second.artifacts)
    MachineProject.model_validate(second.model_dump(mode="json"))
