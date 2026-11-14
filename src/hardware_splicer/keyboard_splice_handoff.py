"""Canonical HS MachineProject handoff for subtractive PCB reuse.

All model-generated content remains proposed/declared. A geometry or copper
island result can NEVER be used alone to grant physical authority.
"""
from __future__ import annotations

from typing import Any, Mapping

from .machine_project_seed import machine_project_from_intake
from .machine_project import (
    AuthorityState, EvidenceRef, ReleaseState, Requirement,
    Interface, InterfaceContract, InterfaceEndpoint, Subsystem, Domain,
    RequirementKind, VerificationMethod, VerificationStatus, VerificationType,
)


def build_keyboard_splice_handoff(cut: Mapping[str, Any], topology: Mapping[str, Any]) -> dict:
    if cut.get("source_file_sha256") != topology.get("source_sha256"):
        raise ValueError("PCB reference and copper island source revisions differ")
    if cut.get("release") != "BLOCKED_REFERENCE_ONLY":
        raise ValueError("unsupported cut analysis authority state")
    if topology.get("qualified_for_build") is not False:
        raise ValueError("modeled copper cannot qualify for construction")
    if topology.get("release") != "BLOCKED_REFERENCE_TOPOLOGY_ONLY":
        raise ValueError("unrecognized postcut topology authority")
    seam = (cut.get("best_scanned_straight_seam") or {}).get("x_mm")
    if seam != topology.get("cut_x_mm"):
        raise ValueError("cut path and electrical connectivity use different seam coordinates")
    project=machine_project_from_intake({
        "project_name":"keyboard-pcb-reuse-virtual-cut",
        "goal":"Reuse a documented, legally owned rigid-PCB keyboard as a physically verified split keyboard",
        "available_parts":[{"name":"reference PCB","source":"external","role":"electrical","domain":"electrical"}],
        "constraints":{"retained_controller":True,"cut_type":"physical_subtractive_work"},
    })
    safety=Requirement(
        requirement_id="req-prove-physical-postcut-electrical-safety",
        statement="Verify physical PCB identity, copper continuity, USB/ESD and every intended key before energizing",
        kind=RequirementKind.SAFETY,
        allocated_to=["system"],
        verification_method_ids=["verification-postcut-bench"],
    )
    project.requirements.append(safety)
    project.subsystems.extend([
        Subsystem(subsystem_id="donor-left-pcb", name="Remaining donor PCB left half",
                  parent_subsystem_id="system", domain=Domain.ELECTRICAL),
        Subsystem(subsystem_id="donor-right-pcb", name="Remaining donor PCB right half",
                  parent_subsystem_id="system", domain=Domain.ELECTRICAL),
    ])
    project.interfaces.append(Interface(
        interface_id="interface-cut-restoration-harness",
        name="Original copper topology restored across physical split",
        kind="electrical_interposer",
        endpoints=[
            InterfaceEndpoint(object_id="donor-left-pcb",port="unknown_actual_testpads"),
            InterfaceEndpoint(object_id="donor-right-pcb",port="unknown_actual_testpads"),
        ],
        contracts=[InterfaceContract(
            contract_type="postcut_original_net_continuity",
            values={"model_candidate_graph_edges":topology["candidate_graph_edges"]},
            unresolved_fields=[
                "original_board_revision","exact_copper_islands","solderable_pads",
                "harness_pinout","return_current_path","cable_strain_relief"
            ],
            authority=AuthorityState.PROPOSED,
        )],
        authority=AuthorityState.PROPOSED,
    ))
    project.verifications.append(VerificationMethod(
        verification_id="verification-postcut-bench",
        name="Donor PCB registration, safe mechanical cut, solder inspection, and powered key scan",
        method_type=VerificationType.TEST,
        status=VerificationStatus.BLOCKED,
        requirement_ids=[safety.requirement_id],
        target_ids=["system"],
        procedure="Requires an actual matched donor, solderable connectors and independent physical measurements",
    ))
    project.evidence.append(EvidenceRef(
        evidence_id="evidence-source-bound-virtual-cut",
        kind="reference_copper_geometry_model",
        basis="KiCad reference board and conservative modeled material removal",
        ref=cut["source_file_sha256"],
        supports=["system"],
        authority=AuthorityState.DECLARED,
        simulated=True,
        metadata={"topology_sha256":topology["payload_sha256"]},
    ))
    project.discipline_payloads["keyboard_splice"]={
        "reference_source_sha256":cut["source_file_sha256"],
        "model_sha256":topology["payload_sha256"],
        "cut_x_mm":seam,
        "physical_donor_verified":False,"fabrication_authorized":False,
    }
    gate=project.assess_release(ReleaseState.BUILD_READY)
    if gate.allowed:
        raise ValueError("unexpected build authorization from modeled copper evidence")
    return {
        "project":project.model_dump(mode="json"),
        "release_assessment":gate.model_dump(mode="json"),
        "physical_authority_granted":False,
        "canonical_summary":{
            "requested":gate.requested_state.value,
            "achieved":gate.achieved_state.value,
            "allowed":gate.allowed,
            "blocker_codes":[issue.code for issue in gate.blockers],
        },
    }
