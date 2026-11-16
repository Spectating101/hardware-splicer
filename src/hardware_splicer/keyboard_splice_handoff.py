"""Canonical HS MachineProject handoff for subtractive PCB reuse.

All model-generated content remains proposed/declared. A geometry or copper
island result can NEVER be used alone to grant physical authority.
"""
from __future__ import annotations

from typing import Any, Mapping
import hashlib
import json

from .keyboard_splice_zone_drc import verify_legacy_refilled_copy_receipt
from .machine_project_seed import machine_project_from_intake
from .machine_project import (
    AuthorityState, EvidenceRef, ReleaseState, Requirement,
    Interface, InterfaceContract, InterfaceEndpoint, Subsystem, Domain,
    RequirementKind, VerificationMethod, VerificationStatus, VerificationType,
    MachineProject,
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
    optimized=cut.get("stepped_path_summary")
    if optimized:
        if (optimized.get("physical_cut_authorized") is not False or
            optimized.get("release")!="PROPOSED_CUT_ONLY_NOT_VERIFIED"):
            raise ValueError("stepped path tried to grant cutting authority")
        if topology.get("cut_path_sha256")!=optimized.get("payload_sha256"):
            raise ValueError("copper model does not use the declared stepped cut")
        if topology.get("cut_path_kind")!="stepped_polyline":
            raise ValueError("copper model did not assess a stepped polyline")
    elif topology.get("cut_path_sha256") is not None:
        raise ValueError("unrecorded stepped cut in canonical project")
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
        "stepped_path_sha256":optimized["payload_sha256"] if optimized else None,
        "model_required_copper_connected":topology.get(
            "model_replay_achieved_required_restoration", False),
        "model_unresolved_required_groups":topology.get(
            "model_replay_remaining_required_components",
            topology.get("model_replay_remaining_split_components")),
        "inert_copper_fragments_to_isolate":topology.get("planned_inert_track_remnants", 0),
        "source_preexisting_terminal_net_gaps":topology.get(
            "preexisting_unconnected_terminal_net_count",0),
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


def extend_keyboard_splice_handoff(
    existing: Mapping[str, Any],
    source_audit: Mapping[str, Any],
    matrix: Mapping[str, Any],
    junction: Mapping[str, Any],
    junction_verification: Mapping[str, Any],
    pinout_proof: Mapping[str, Any] | None=None,
    legacy_zone_drc_receipt: Mapping[str, Any] | None=None,
    compact_junction: Mapping[str, Any] | None=None,
    compact_junction_verification: Mapping[str, Any] | None=None,
) -> dict:
    """Attach source-bound firmware and junction design without physical authority.

    Supports *simulated and public-reference* machine evidence. Cannot turn a
    DRC clean PCB into a tested physical product.
    """
    if existing.get("physical_authority_granted") is not False:
        raise ValueError("earlier machine handoff already claims physical authority")
    project=MachineProject.model_validate(existing["project"])
    source=project.discipline_payloads.get("keyboard_splice",{}).get("reference_source_sha256")
    if (not source or
        source_audit.get("original_pcb_sha256")!=source or
        matrix.get("source_sha256")!=source or
        junction.get("source_sha256")!=source or
        junction_verification.get("source_sha256")!=source):
        raise ValueError("firmware / harness / original PCB evidence revisions differ")
    if source_audit.get("net_assignment_equivalence") is not True:
        raise ValueError("source schematic electrical mapping is not verified")
    if (matrix.get("ideal_directed_diode_matrix_model_passed") is not True
        or matrix.get("mismatched_ideal_patterns")!=0 or
        matrix.get("released_for_fabrication") is not False):
        raise ValueError("source full matrix simulation is unresolved")
    if junction.get("fabrication_release")!="BLOCKED_SOURCE_REFERENCE_JUNCTION_PREVIEW":
        raise ValueError("harness tried to grant physical authority")
    if (junction.get("physical_assembly_authorized") is not False or
        junction_verification.get("fabrication_release")!="BLOCKED_SOURCE_REFERENCE_JUNCTION_PREVIEW" or
        junction_verification.get("native_design_checks_passed") is not True or
        junction_verification.get("drc_violations")!=0 or
        junction_verification.get("unconnected_items")!=0):
        raise ValueError("native junction design proof missing or claims physical authority")
    if (junction.get("topology_sha256")!=
        project.discipline_payloads["keyboard_splice"]["model_sha256"]):
        raise ValueError("junction references different cut copper topology")
    if (junction.get("full_matrix_sha256")!=matrix.get("payload_sha256")
        or junction_verification.get("full_matrix_sha256")!=matrix.get("payload_sha256")
        or junction.get("independent_schematic_and_firmware_audit_sha256")
           !=source_audit.get("payload_sha256")):
        raise ValueError("firmware or source audit receipt mismatch")
    if junction.get("total_junction_board_pins")!=(
        junction.get("source_original_pads_with_only_one_wire_each",0)+
        junction.get("relocated_key_header_pins",0)
    ):
        raise ValueError("harness wire inventory is incomplete")
    official_gpio=None
    if pinout_proof is not None:
        body={k:v for k,v in pinout_proof.items() if k!="payload_sha256"}
        packed=json.dumps(body,sort_keys=True,ensure_ascii=False,separators=(",",":"))
        digest=hashlib.sha256(packed.encode()).hexdigest()
        if (digest!=pinout_proof.get("payload_sha256")
            or pinout_proof.get("original_source_sha256")!=source
            or pinout_proof.get("source_audit_sha256")!=source_audit.get("payload_sha256")
            or pinout_proof.get("full_matrix_proof_sha256")!=matrix.get("payload_sha256")
            or pinout_proof.get("firmware_total_gpio_assignments_verified")!=19
            or pinout_proof.get("source_original_controller_pads_positionally_verified")!=31
            or pinout_proof.get("fabrication_authorized") is not False):
            raise ValueError("source Teensy physical pin assignment evidence mismatch")
        official_gpio=pinout_proof
    legacy_drc=None
    if legacy_zone_drc_receipt is not None:
        legacy_drc=verify_legacy_refilled_copy_receipt(
            legacy_zone_drc_receipt,source
        )
    if (compact_junction is None) != (compact_junction_verification is None):
        raise ValueError("native compact IDC routing and native DRC must be supplied together")
    if compact_junction is not None:
        if (compact_junction.get("source_sha256")!=source
            or compact_junction.get("source_original_wiring_assignments")!=junction.get("total_junction_board_pins")
            or compact_junction.get("source_junction_original_net_groups")!=junction.get("unique_source_nets_joined")
            or compact_junction.get("independent_source_bus_net_count")!=junction.get("unique_source_nets_joined")
            or compact_junction.get("fabrication_authorized") is not False
            or compact_junction.get("release")!="BLOCKED_NATIVE_KICAD_COMPACT_IDC_PREVIEW"
            or compact_junction.get("source_original_junction_mutually_exclusive") is not True
            or compact_junction_verification.get("source_sha256")!=source
            or compact_junction_verification.get("full_source_junction_model_sha256")!=matrix["payload_sha256"]
            or compact_junction_verification.get("native_drc_passed") is not True
            or compact_junction_verification.get("errors")!=0
            or compact_junction_verification.get("warnings")!=0
            or compact_junction_verification.get("unconnected_items")!=0
            or compact_junction_verification.get("fabrication_release")!="BLOCKED_NATIVE_KICAD_COMPACT_IDC_PREVIEW"):
            raise ValueError("compact connector source-net identity, DRC or physical authority mismatch")
        if (compact_junction.get("IDC_used_pins")!=49
            or compact_junction.get("total_junction_pin_count",49)!=49
            or compact_junction.get("board_area_reduction_percent",0)<=0):
            raise ValueError("compact connector fails source lead count or reduction proof")

    subsystems=("remounted-key-pcb","source-bound-junction-bus")
    if any(s.subsystem_id in subsystems for s in project.subsystems):
        raise ValueError("already integrated source-junction hardware module")
    project.subsystems.extend([
        Subsystem(
            subsystem_id="remounted-key-pcb",
            name="Five detached source-key circuits represented by a new KiCad daughterboard",
            parent_subsystem_id="system",
            domain=Domain.ELECTRICAL,
        ),
        Subsystem(
            subsystem_id="source-bound-junction-bus",
            name="Source-net-pinned junction connector PCB, conditional only",
            parent_subsystem_id="system",
            domain=Domain.ELECTRICAL,
        ),
    ])
    for endpoint in ("donor-left-pcb","donor-right-pcb","remounted-key-pcb"):
        project.interfaces.append(Interface(
            interface_id="interface-junction-"+endpoint,
            name="Unverified physical cable between full source-net junction and "+endpoint,
            kind="electrical_wiring",
            endpoints=[
                InterfaceEndpoint(object_id="source-bound-junction-bus",port="source_net_header_clusters"),
                InterfaceEndpoint(object_id=endpoint,port="unverified_original_mating_pads"),
            ],
            contracts=[InterfaceContract(
                contract_type="original_source_net_reference",
                values={
                    "junction_net_clusters":junction["unique_source_nets_joined"],
                    "source_pins":junction["source_original_pads_with_only_one_wire_each"],
                    "remount_pins":junction["relocated_key_header_pins"],
                },
                unresolved_fields=[
                    "physical_donor_identity","cable_mpn","connector_mating",
                    "assembly_tolerance","strain_relief","firmware_validation",
                ],
                authority=AuthorityState.PROPOSED,
            )],
            authority=AuthorityState.PROPOSED,
        ))
    project.evidence.extend([
        EvidenceRef(
            evidence_id="f60-source-independent-schematic-firmware-audit",
            kind="public_schematic_vs_pcb_netlist_equality",
            basis="Independent SHA-pinned public schematic netlist and TMK firmware",
            ref=source_audit["payload_sha256"],
            supports=["system"],
            authority=AuthorityState.DECLARED,
            simulated=True,
        ),
        EvidenceRef(
            evidence_id="f60-62-key-ideal-matrix-press-test",
            kind="source_bound_ideal_keyboard_scan_model",
            basis="Original source-derived 62-key/62-diode controller matrix, no USB hardware",
            ref=matrix["payload_sha256"],
            supports=["system"],
            authority=AuthorityState.DECLARED,
            simulated=True,
        ),
        EvidenceRef(
            evidence_id="f60-kicad-source-junction-native-drc",
            kind="native_kicad_electrical_routing_check",
            basis="Twenty independent source-net junction buses; physical wiring not tested",
            ref=junction_verification["pcb_sha256"],
            supports=["system"],
            authority=AuthorityState.DECLARED,
            simulated=True,
        ),
    ])
    if official_gpio is not None:
        project.evidence.append(EvidenceRef(
            evidence_id="f60-pjrc-teensy2-original-controller-pad-mapping",
            kind="official_c_pinout_source_footprint_vs_firmware_GPIO",
            basis="31 external KiCad footprint pads, 19 source firmware GPIO and PJRC C-language pinout",
            ref=official_gpio["payload_sha256"],
            supports=["system"],
            authority=AuthorityState.DECLARED,
            simulated=True,
        ))
    if legacy_drc is not None:
        project.evidence.append(EvidenceRef(
            evidence_id="f60-refilled-legacy-zone-copy-native-drc",
            kind="native_kicad9_converted_source_copy_drc",
            basis="SHA-pinned original copper non-zone equivalence and converted zone-fill native DRC; original file unchanged",
            ref=legacy_drc["evidence_sha256"],
            supports=["system"],
            authority=AuthorityState.DECLARED,
            simulated=True,
        ))
    if compact_junction is not None:
        project.evidence.append(EvidenceRef(
            evidence_id="f60-compact-50pin-IDC-header-native-drc",
            kind="native_kicad_alternative_compact_wiring_board",
            basis="Original source-net grouped junction, 49 pins and 20 buses, actual standard KiCad latching IDC footprint",
            ref=compact_junction_verification["pcb_sha256"],
            supports=["system"],
            authority=AuthorityState.DECLARED,
            simulated=True,
        ))
    project.discipline_payloads["keyboard_splice"].update({
        "source_connected_schematic_pad_nodes":source_audit["matched_original_pcb_net_nodes"],
        "firmware_source_matrix_positions":source_audit["pcb_switch_diode_firmware_position_verified"],
        "simulated_ideal_press_patterns":matrix["total_ideal_press_patterns_tested"],
        "independent_schematic_audit_sha256":source_audit["payload_sha256"],
        "full_62_key_matrix_sha256":matrix["payload_sha256"],
        "native_junction_design_sha256":junction_verification["pcb_sha256"],
        "junction_source_net_groups":junction["unique_source_nets_joined"],
        "junction_donor_original_pad_wires":junction["source_original_pads_with_only_one_wire_each"],
        "junction_daughterboard_port_wires":junction["relocated_key_header_pins"],
        "native_source_pcb_full_drc_complete":False,
        "official_teensy2_source_pinout_19_signal_match":official_gpio is not None,
        "original_teensy_footprint_all_31_pads_source_matched":official_gpio is not None,
        "source_refilled_zone_copy_drc_no_errors":legacy_drc is not None,
        "source_refilled_zone_copy_drc_warnings":(
            legacy_drc["converted_zone_refill_drc_warnings"] if legacy_drc else None
        ),
        "source_original_byte_identical_full_drc_verified":False,
        "compact_IDC_source_net_preview_available":compact_junction is not None,
        "compact_IDC_area_reduction_percent":(
            compact_junction["board_area_reduction_percent"]
            if compact_junction else None
        ),
        "compact_and_original_full_junction_mutually_exclusive":(
            bool(compact_junction and
                 compact_junction["source_original_junction_mutually_exclusive"])
        ),
        "physical_harness_cable_verified":False,
        "original_teensy_firmware_compiled_flashed_or_verified":False,
        "physical_donor_verified":False,
        "fabrication_authorized":False,
    })
    gate=project.assess_release(ReleaseState.BUILD_READY)
    if gate.allowed or gate.achieved_state==ReleaseState.BUILD_READY:
        raise ValueError("source-only schematic and KiCad DRC cannot authorize physical build")
    return {
        "project":project.model_dump(mode="json"),
        "release_assessment":gate.model_dump(mode="json"),
        "physical_authority_granted":False,
        "canonical_summary":{
            "requested":gate.requested_state.value,
            "achieved":gate.achieved_state.value,
            "allowed":gate.allowed,
            "blocker_codes":[block.code for block in gate.blockers],
        },
    }
