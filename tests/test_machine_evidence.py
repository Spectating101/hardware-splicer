from __future__ import annotations

import pytest

from hardware_splicer.machine_evidence import EvidencePromotionError, record_evidence_and_promote
from hardware_splicer.machine_project import (
    AuthorityState,
    Component,
    Domain,
    Interface,
    InterfaceContract,
    InterfaceEndpoint,
    MachineProject,
    Requirement,
    RequirementKind,
    Subsystem,
)


def project() -> MachineProject:
    return MachineProject(
        project_id="robot",
        name="Inspection robot",
        purpose="Inspect a building",
        requirements=[
            Requirement(
                requirement_id="req-runtime",
                statement="The robot shall operate for 90 minutes.",
                kind=RequirementKind.PERFORMANCE,
                allocated_to=["battery"],
            )
        ],
        subsystems=[
            Subsystem(
                subsystem_id="power",
                name="Power",
                domain=Domain.ELECTRICAL,
                component_ids=["battery"],
                interface_ids=["power-link"],
            ),
            Subsystem(
                subsystem_id="drive",
                name="Drive",
                domain=Domain.MECHANICAL,
                component_ids=["motor"],
                interface_ids=["power-link"],
            ),
        ],
        components=[
            Component(
                component_id="battery",
                name="Battery",
                domain=Domain.ELECTRICAL,
                subsystem_id="power",
                requirement_ids=["req-runtime"],
                authority=AuthorityState.DECLARED,
            ),
            Component(
                component_id="motor",
                name="Motor",
                domain=Domain.MECHANICAL,
                subsystem_id="drive",
                authority=AuthorityState.DECLARED,
            ),
        ],
        interfaces=[
            Interface(
                interface_id="power-link",
                name="Battery to motor",
                kind="power",
                endpoints=[
                    InterfaceEndpoint(object_id="battery", port="output"),
                    InterfaceEndpoint(object_id="motor", port="power"),
                ],
                contracts=[
                    InterfaceContract(
                        contract_type="electrical",
                        values={"nominal_voltage_v": 12},
                        unresolved_fields=[],
                        authority=AuthorityState.DECLARED,
                    )
                ],
                authority=AuthorityState.DECLARED,
            )
        ],
    )


def test_physical_measurement_promotes_supported_component() -> None:
    candidate = record_evidence_and_promote(
        project(),
        evidence={
            "evidence_id": "evidence-battery-voltage",
            "kind": "multimeter_capture",
            "basis": "instrument",
            "supports": ["battery"],
            "authority": "measured",
            "simulated": False,
        },
        promotions=[
            {"collection": "components", "object_id": "battery", "authority": "measured"}
        ],
    )

    battery = next(row for row in candidate.components if row.component_id == "battery")
    assert battery.authority == AuthorityState.MEASURED
    assert candidate.evidence[0].authority == AuthorityState.MEASURED


def test_passing_verification_promotes_interface_and_links_traceability() -> None:
    candidate = record_evidence_and_promote(
        project(),
        evidence={
            "evidence_id": "evidence-power-load",
            "kind": "bench_test",
            "basis": "instrument",
            "supports": ["power-link"],
            "authority": "measured",
            "simulated": False,
        },
        verification={
            "verification_id": "verify-power-load",
            "name": "Power load test",
            "method_type": "test",
            "status": "passed",
            "target_ids": ["power-link"],
            "evidence_ids": ["evidence-power-load"],
            "authority": "verified",
        },
        promotions=[
            {"collection": "interfaces", "object_id": "power-link", "authority": "verified"}
        ],
    )

    interface = candidate.interfaces[0]
    assert interface.authority == AuthorityState.VERIFIED
    assert interface.verification_method_ids == ["verify-power-load"]
    assert candidate.verifications[0].status.value == "passed"


def test_simulation_can_verify_analytical_requirement_but_not_physical_target() -> None:
    requirement_candidate = record_evidence_and_promote(
        project(),
        evidence={
            "evidence_id": "evidence-runtime-sim",
            "kind": "digital_twin",
            "basis": "simulation",
            "supports": ["req-runtime"],
            "authority": "verified",
            "simulated": True,
        },
        verification={
            "verification_id": "verify-runtime-analysis",
            "name": "Runtime energy analysis",
            "method_type": "analysis",
            "status": "passed",
            "requirement_ids": ["req-runtime"],
            "evidence_ids": ["evidence-runtime-sim"],
            "authority": "verified",
        },
        promotions=[
            {"collection": "requirements", "object_id": "req-runtime", "authority": "verified"}
        ],
    )
    assert requirement_candidate.requirements[0].authority == AuthorityState.VERIFIED
    assert requirement_candidate.requirements[0].verification_method_ids == [
        "verify-runtime-analysis"
    ]

    with pytest.raises(EvidencePromotionError, match="simulated evidence cannot promote physical"):
        record_evidence_and_promote(
            project(),
            evidence={
                "evidence_id": "evidence-motor-sim",
                "kind": "digital_twin",
                "basis": "simulation",
                "supports": ["motor"],
                "authority": "verified",
                "simulated": True,
            },
            verification={
                "verification_id": "verify-motor-sim",
                "name": "Motor simulation",
                "method_type": "analysis",
                "status": "passed",
                "target_ids": ["motor"],
                "evidence_ids": ["evidence-motor-sim"],
            },
            promotions=[
                {"collection": "components", "object_id": "motor", "authority": "verified"}
            ],
        )


def test_authorization_requires_authorized_physical_evidence_and_passing_verification() -> None:
    with pytest.raises(EvidencePromotionError, match="authorized promotion requires"):
        record_evidence_and_promote(
            project(),
            evidence={
                "evidence_id": "evidence-power-authorize",
                "kind": "bench_test",
                "basis": "instrument",
                "supports": ["power-link"],
                "authority": "measured",
                "simulated": False,
            },
            verification={
                "verification_id": "verify-power-authorize",
                "name": "Power authorization",
                "method_type": "test",
                "status": "passed",
                "target_ids": ["power-link"],
                "evidence_ids": ["evidence-power-authorize"],
            },
            promotions=[
                {
                    "collection": "interfaces",
                    "object_id": "power-link",
                    "authority": "authorized",
                }
            ],
        )


def test_evidence_must_support_target_and_cannot_regress_authority() -> None:
    with pytest.raises(EvidencePromotionError, match="does not declare support"):
        record_evidence_and_promote(
            project(),
            evidence={
                "evidence_id": "evidence-unrelated",
                "kind": "observation",
                "basis": "inspection",
                "supports": ["motor"],
                "authority": "observed",
            },
            promotions=[
                {"collection": "components", "object_id": "battery", "authority": "observed"}
            ],
        )

    measured = record_evidence_and_promote(
        project(),
        evidence={
            "evidence_id": "evidence-battery",
            "kind": "measurement",
            "basis": "instrument",
            "supports": ["battery"],
            "authority": "measured",
        },
        promotions=[
            {"collection": "components", "object_id": "battery", "authority": "measured"}
        ],
    )
    with pytest.raises(EvidencePromotionError, match="cannot regress"):
        record_evidence_and_promote(
            measured,
            evidence={
                "evidence_id": "evidence-observation",
                "kind": "observation",
                "basis": "inspection",
                "supports": ["battery"],
                "authority": "observed",
            },
            promotions=[
                {"collection": "components", "object_id": "battery", "authority": "observed"}
            ],
        )
