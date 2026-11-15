"""Source-agnostic PCB donor intake and replay verdicts.

This is a strict reference-only viability evaluation, not a generic ability to
reverse-engineer unknown junk from photos. It explicitly distinguishes a
modeled copper graph from a physically functional or saleable keyboard.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Mapping


def triage_reference_pcb(board: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(board.get("source_sha256"), str) or len(board["source_sha256"]) != 64:
        raise ValueError("unidentified PCB bytes cannot acquire model authority")
    footprints = list(board.get("footprints") or [])
    switches = list(board.get("switch_positions") or [])
    pads = list(board.get("pads") or [])
    tracks = list(board.get("tracks") or [])
    zones = [z for z in board.get("filled_zones") or [] if z.get("net")]
    missing_fill = [z.get("net") for z in zones
                    if not z.get("is_filled") or not z.get("polygons")]
    conductive = len(tracks) + sum(len(z.get("polygons") or []) for z in zones
                                    if z.get("is_filled"))
    copper_layers = int(board.get("copper_layer_count") or 0)
    blockers = []
    if copper_layers != 2:
        blockers.append("UNSUPPORTED_LAYER_STACK")
    if len(switches) < 2:
        blockers.append("INSUFFICIENT_DETECTED_KEY_SWITCHES")
    if not pads or conductive == 0:
        blockers.append("NO_COMPLETE_ROUTED_COPPER")
    if missing_fill:
        blockers.append("SOURCE_CONDUCTIVE_ZONES_NOT_FILLED")
    if not any(str(f.get("ref", "")).upper().startswith(("IC", "U", "J", "X"))
               for f in footprints):
        blockers.append("NO_IDENTIFIABLE_CONTROLLER_OR_CONNECTOR")
    methods = Counter(str(f.get("switch_detected_from", "unknown")) for f in switches)
    warnings = list(board.get("source_warnings") or [])
    if any(m == "candidate_switch_footprint_or_ref" for m in methods):
        warnings.append("SWITCH_IDENTITY_NEEDS_PHYSICAL_CONFIRMATION")
    return {
        "schema": "hs.arbitrary-keyboard-intake.v1",
        "reference_source_sha256": board["source_sha256"],
        "reference_source_filename": board.get("source_label"),
        "source_kind": "EXTERNAL_KICAD_REFERENCE_NOT_PHYSICAL_JUNK",
        "copper_layers": copper_layers,
        "footprints": len(footprints),
        "key_switch_candidates": len(switches),
        "switch_detection_methods": dict(sorted(methods.items())),
        "routed_track_count": len(tracks),
        "plated_via_count": len(board.get("vias") or []),
        "routed_conductive_zone_count": len(zones),
        "unfilled_conductive_zone_names": sorted(set(str(n) for n in missing_fill)),
        "source_warnings": warnings,
        "eligible_for_bounded_virtual_reconstruction": not blockers,
        "blocker_codes": blockers,
        "claimed_physical_donor_present": False,
        "physical_authority_granted": False,
    }


def assess_arbitrary_outcome(
    intake: Mapping[str, Any],
    *,
    path: Mapping[str, Any] | None = None,
    topology: Mapping[str, Any] | None = None,
    interposer: Mapping[str, Any] | None = None,
    source_drc: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if intake.get("eligible_for_bounded_virtual_reconstruction") is not True:
        status = "SOURCE_REJECTED_BEFORE_MODEL"
        gates = {}
    elif not path or not topology:
        status = "ELECTRICAL_ANALYSIS_INCOMPLETE"
        gates = {}
    else:
        source = intake["reference_source_sha256"]
        if (source != path.get("source_sha256") or source != topology.get("source_sha256")
            or topology.get("cut_path_sha256") != path.get("payload_sha256")):
            raise ValueError("cross-source or cross-cut receipt mismatch")
        if topology.get("qualified_for_build") is not False:
            raise ValueError("virtual solver attempted physical release")
        if topology.get("release") != "BLOCKED_REFERENCE_TOPOLOGY_ONLY":
            raise ValueError("unexpected virtual model release state")
        model_connected = (
            topology.get("model_replay_remaining_required_components") == 0
            and topology.get("damaged_electrical_pad_count") == 0
        )
        base_integrity = topology.get("preexisting_unconnected_terminal_net_count") == 0
        collision_counts = path.get("collision_counts") or {}
        clear_path = (
            set(collision_counts) == {"pads", "vias", "switches", "critical"}
            and all(v == 0 for v in collision_counts.values())
        )
        native_interposer = (
            bool(interposer)
            and interposer.get("source_sha256") == source
            and interposer.get("topology_sha256") == topology.get("payload_sha256")
            and interposer.get("native_design_checks_passed") is True
            and interposer.get("fabrication_release") == "BLOCKED_PREVIEW_ONLY"
        )
        original_drc = (
            bool(source_drc)
            and source_drc.get("source") == intake.get("reference_source_filename")
            and not source_drc.get("violations")
            and not source_drc.get("unconnected_items")
        )
        issues = topology.get("issues") or []
        model_exact = not any(
            str(issue).startswith((
                "SOURCE_IMPORT_WARNINGS", "MULTILAYER_PCB_UNSUPPORTED",
                "PAD_SHAPE_UNSUPPORTED", "OVAL_PAD_APPROXIMATION",
                "ZONE_BOUNDARY_RECONSTRUCTED", "RELEVANT_COPPER_ZONE_UN",
                "UNMODELED_COPPER", "ROUNDRECT_PAD_RADIUS"
            )) for issue in issues
        )
        gates = {
            "required_reconnection_complete_in_model": bool(model_connected),
            "source_terminals_connected_in_model": bool(base_integrity),
            "modeled_cut_clear_of_components": bool(clear_path),
            "original_native_drc_clean": bool(original_drc),
            "bridge_native_drc_clean": bool(native_interposer),
            "source_geometry_reliable_without_legacy_repairs": bool(model_exact),
        }
        if not model_connected:
            status = "REPAIR_INCOMPLETE"
        elif not base_integrity:
            status = "RECONNECTED_BUT_SOURCE_PREEXISTING_GAPS"
        elif not clear_path:
            status = "RECONNECTED_BUT_CUT_COLLIDES"
        elif not original_drc or not model_exact or not native_interposer:
            status = "RECONNECTED_BUT_SOURCE_OR_BRIDGE_NOT_VERIFIED"
        else:
            status = "REFERENCE_DIGITAL_ELECTRICAL_PASS"
    return {
        "schema": "hs.arbitrary-keyboard-benchmark-verdict.v1",
        "status": status,
        "gates": gates,
        "strict_reference_digital_pass": status == "REFERENCE_DIGITAL_ELECTRICAL_PASS",
        "source_sha256": intake["reference_source_sha256"],
        "actual_discarded_keyboard_tested": False,
        "arbitrary_unphotographed_junk_supported": False,
        "real_keyboard_function_verified": False,
        "physical_release": "BLOCKED_NOT_TESTED",
        "build_ready": False,
    }
