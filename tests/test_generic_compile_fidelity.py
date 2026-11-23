"""Keep arbitrary circuit identity while refusing physical claims for generic pads."""
from copy import deepcopy
import json

import pytest

from hardware_splicer.auto_wire import compose_build_graph_from_canvas_nodes, compose_build_graph_from_module_ids
from hardware_splicer.design_quality import build_design_quality_gate
from hardware_splicer.kicad_diff import parse_kicad_sexp
from hardware_splicer.netlist.ir import CircuitNetlist
from hardware_splicer.netlist.lower import build_graph_to_netlist, netlist_to_build_graph
from hardware_splicer.netlist.quality_flags import finalize_launch_quality
from hardware_splicer.pcb.build_to_geometry import build_graph_to_geometry
from hardware_splicer.pcb.kicad_serializer import serialize_build_to_kicad_pcb
from hardware_splicer.plan_to_graph import splice_plan_to_build_graph


def unfamiliar(footprint="AuditOnly:QFN-8-EP_3x3mm_P0.5mm", ref="U37", connector="J42"):
    pins = ["A1", "A2", "B1", "B2", "C1", "C2", "D1", "EP"]
    return CircuitNetlist.from_dict({
        "source": "synthetic-input-perturbation",
        "components": [
            {"ref": ref, "value": "unfamiliar-audit-device", "footprint": footprint,
             "metadata": {"source_component_id": "source-original-37"}},
            {"ref": connector, "value": "unfamiliar-keyed-connector", "footprint": "AuditOnly:OffsetKeyed_2x4_P1.0mm"},
        ],
        "nets": [
            {"name": name, "pins": [{"component_ref": ref, "pin": pin},
                                      {"component_ref": connector, "pin": "K" + str(i + 1)}]}
            for i, (name, pin) in enumerate(zip(
                ["VDD_AUDIT", "CLK_AUDIT", "DIN_AUDIT", "DOUT_AUDIT", "CS_AUDIT", "IRQ_AUDIT", "RESET_AUDIT", "GND_AUDIT"], pins))
        ],
        "metadata": {"source_revision": "unseen-layout-4"},
    })


def pin_net_map(netlist):
    return {(pin.component_ref, pin.pin): net.name for net in netlist.nets for pin in net.pins}


def native_pin_net_map(text):
    result = {}
    tree = parse_kicad_sexp(text)
    for fp in tree[1:]:
        if not isinstance(fp, list) or not fp or fp[0] != "footprint":
            continue
        ref = next(row[2] for row in fp if isinstance(row, list) and row[:2] == ["fp_text", "reference"])
        for pad in fp:
            if isinstance(pad, list) and pad and pad[0] == "pad":
                net = next((row[2] for row in pad if isinstance(row, list) and row and row[0] == "net"), "")
                result[(ref, pad[1])] = net
    return result


def clean_quality():
    # Controlled receipts isolate input-fidelity gating from independent native/routing checks.
    return {"build_ready": True, "fabrication_ready": True, "build_graph_compiled": True,
            "electrical_safety_pass": True, "drc_pass": True, "bom_ready": True, "gerber_ready": True,
            "freerouting_ok": True, "freerouting_track_count": 30,
            "kicad_drc_pass": True, "kicad_drc_errors": 0, "kicad_erc_pass": True}


def test_unknown_catalog_request_preserves_all_identities_and_does_not_compile_known_subset():
    requested = ["usb-power-5v", "esp32-devkit", "donor:unidentified-driver", "donor:unidentified-driver"]
    result = compose_build_graph_from_module_ids(requested)
    assert result["composition_status"] == "unresolved"
    assert result["requested_module_ids"] == requested
    assert result["resolved_module_ids"] == requested[:2]
    assert result["unresolved_module_ids"] == requested[2:]
    assert result["graph"]["nodes"] == []
    assert "donor:unidentified-driver" in result["warnings"][0]
    graph, _, _, warnings = splice_plan_to_build_graph({
        "target": {"recommended_build_id": "sensor_logger"}, "custom_graph": result["graph"]})
    assert graph == result["graph"]  # Never replace the failed request with sensor_logger.
    assert "fallback is not allowed" in warnings[0]


def test_unknown_canvas_module_preserves_requested_node_identity_without_inventing_pads():
    nodes = [{"id": "kept-7", "moduleId": "esp32-devkit"}, {"id": "unknown-22", "moduleId": "salvaged-unknown"}]
    graph = compose_build_graph_from_canvas_nodes(nodes)
    assert not graph["nodes"] and not graph["wires"]
    assert graph["composition_request"]["requested_nodes"] == nodes
    assert graph["composition_request"]["unresolved_module_ids"] == ["salvaged-unknown"]


def test_public_compile_stage_preserves_unresolved_request_without_native_runner_or_catalog_fallback(tmp_path):
    from hardware_splicer.compile_stages import run_graph_stage_node
    request = compose_build_graph_from_module_ids(["usb-power-5v", "esp32-devkit", "unknown-salvaged-island"])
    result = run_graph_stage_node("sensor_logger", tmp_path, splice_plan={"custom_graph": request["graph"]})
    assert not result.ok and result.paths.kicad_pcb is None
    assert result.quality["composition_request"]["requested_module_ids"] == request["requested_module_ids"]
    assert result.quality["circuit_readiness"] == "unresolved_modules"
    assert any("unknown-salvaged-island" in reason for reason in result.quality["input_fidelity_blockers"])


def test_resolved_catalog_substitution_still_rewires_the_declared_sensor_interface():
    esp = compose_build_graph_from_module_ids(["usb-power-5v", "esp32-devkit", "bme280"])
    pico = compose_build_graph_from_module_ids(["usb-power-5v", "rpi-pico", "bme280"])
    for result in (esp, pico):
        assert result["composition_status"] == "resolved"
        assert result["unresolved_module_ids"] == []
        assert len(result["graph"]["nodes"]) == 3
    def i2c_pairs(result):
        return {(wire["from"]["pinId"], wire["to"]["pinId"]) for wire in result["graph"]["wires"] if wire["to"]["pinId"] in {"SDA", "SCL"}}
    assert i2c_pairs(esp) == {("GPIO21", "SDA"), ("GPIO22", "SCL")}
    assert i2c_pairs(pico) == {("GP4", "SDA"), ("GP5", "SCL")}


@pytest.mark.parametrize("package", ["AuditOnly:QFN-8-EP_3x3mm_P0.5mm", "AuditOnly:SOIC-8_3.9x4.9mm_P1.27mm"])
@pytest.mark.parametrize("refs", [("U37", "J42"), ("U901", "X808")])
def test_explicit_refs_physical_pin_ids_named_nets_and_source_metadata_survive_native_export(package, refs):
    circuit = unfamiliar(package, *refs)
    graph = netlist_to_build_graph(circuit)
    roundtrip = build_graph_to_netlist(graph)
    assert pin_net_map(roundtrip) == pin_net_map(circuit)
    assert [(c.ref, c.value, c.footprint, c.module_id) for c in roundtrip.components] == [(c.ref, c.value, c.footprint, c.module_id) for c in circuit.components]
    assert roundtrip.components[0].metadata["source_component_id"] == "source-original-37"
    assert roundtrip.metadata["source_revision"] == "unseen-layout-4"
    geometry = build_graph_to_geometry(graph)
    text = serialize_build_to_kicad_pcb(graph, geometry)
    assert native_pin_net_map(text) == pin_net_map(circuit)
    assert package in text
    assert "LOGICAL PREVIEW" in text
    assert "HardwareSplicerPreview:" + refs[0] in text
    fidelity = geometry["geometry_fidelity"]
    assert fidelity["status"] == "logical_preview"
    assert fidelity["requires_native_source_geometry"] is True
    assert fidelity["component_contracts_verified"] is False
    assert {row["declared_footprint"] for row in fidelity["synthetic_components"]} == {c.footprint for c in circuit.components}
    assert all(pad["type"] == "thru_hole" for fp in geometry["footprints"] for pad in fp["pads"])


def test_singleton_net_and_explicit_numeric_pins_do_not_disappear_or_inherit_catalog_pad_labels():
    circuit = CircuitNetlist.from_dict({
        "components": [{"ref": "U14", "value": "raw IC, not a breakout", "module_id": "bme280",
                        "footprint": "Package_LGA:Unexpected_8Pin"}],
        "nets": [{"name": "EXPOSED_GROUND", "pins": [{"component_ref": "U14", "pin": "8"}]}],
    })
    graph = netlist_to_build_graph(circuit)
    assert pin_net_map(build_graph_to_netlist(graph)) == {("U14", "8"): "EXPOSED_GROUND"}
    geometry = build_graph_to_geometry(graph)
    assert native_pin_net_map(serialize_build_to_kicad_pcb(graph, geometry)) == {("U14", "8"): "EXPOSED_GROUND"}
    assert geometry["geometry_fidelity"]["requires_native_source_geometry"]


def test_known_logical_module_without_registered_pad_layout_is_still_a_synthetic_preview():
    graph = compose_build_graph_from_module_ids(["usb-power-5v", "esp32-devkit", "mpu6050"])["graph"]
    geometry = build_graph_to_geometry(graph)
    fidelity = geometry["geometry_fidelity"]
    assert fidelity["requires_native_source_geometry"]
    assert {row["node_id"] for row in fidelity["synthetic_components"]} == {"n3"}


def test_ambiguous_source_pin_membership_is_rejected_instead_of_picking_a_net():
    body = unfamiliar().to_dict()
    body["nets"][1]["pins"][0] = deepcopy(body["nets"][0]["pins"][0])
    with pytest.raises(ValueError, match="multiple nets"):
        netlist_to_build_graph(CircuitNetlist.from_dict(body))


def test_placement_reordering_does_not_renumber_source_references_or_contacts():
    circuit = CircuitNetlist.from_dict({
        "components": [{"ref": ref, "value": ref, "footprint": "Audit:Unknown"} for ref in ("U37", "J42", "R99")],
        "nets": [
            {"name": "CLK", "pins": [{"component_ref": "U37", "pin": "A1"}, {"component_ref": "R99", "pin": "A"}]},
            {"name": "RET", "pins": [{"component_ref": "J42", "pin": "K1"}, {"component_ref": "R99", "pin": "B"}]},
        ],
    })
    graph = netlist_to_build_graph(circuit)
    geometry = build_graph_to_geometry(graph)
    assert geometry["footprints"][0]["ref"] == "R99"  # Highest connectivity is placed first.
    assert native_pin_net_map(serialize_build_to_kicad_pcb(graph, geometry)) == pin_net_map(circuit)


def test_clean_native_and_routing_receipts_cannot_promote_synthetic_package_geometry():
    geometry = build_graph_to_geometry(netlist_to_build_graph(unfamiliar()))
    quality = {**clean_quality(), "geometry_fidelity": geometry["geometry_fidelity"]}
    final = finalize_launch_quality(quality)
    assert final["build_ready"] is True  # Logical compilation remains usable.
    assert final["fabrication_ready"] is False
    assert final["fab_recommendation"] == "blocked_geometry_fidelity"
    assert final["circuit_readiness"] == "logical_preview"
    # The public gate independently observes fidelity even if a caller supplies a true flag.
    gate = build_design_quality_gate({**final, "fabrication_ready": True})
    assert not gate["fabrication_ready"]
    assert gate["circuit_readiness"] == "logical_preview"
    assert any("QFN" in reason for reason in gate["fabrication_blockers"])
    assert finalize_launch_quality(clean_quality())["fabrication_ready"] is True


def test_unresolved_request_cannot_be_reclassified_by_clean_downstream_checks():
    result = compose_build_graph_from_module_ids(["usb-power-5v", "esp32-devkit", "unidentified"])
    quality = {**clean_quality(), "composition_request": result["graph"]["composition_request"]}
    final = finalize_launch_quality(quality)
    assert not final["build_ready"] and not final["fabrication_ready"]
    assert final["circuit_readiness"] == "unresolved_modules"
    gate = build_design_quality_gate(final)
    assert not gate["build_ready"] and not gate["fabrication_ready"]
    assert any("unidentified" in reason for reason in gate["blockers"])


def test_actual_generic_compile_exports_logical_preview_with_unassessed_electrical_scope(tmp_path, monkeypatch):
    from hardware_splicer.pcb import geometry_compile
    # No native runner/routing work is needed to prove this independent input boundary.
    monkeypatch.setattr(geometry_compile, "run_kicad_cli_drc", lambda *a, **k: {"skipped": True, "pass": None})
    monkeypatch.setattr(geometry_compile, "_autoroute_enabled", lambda: False)
    result = geometry_compile.compile_graph_to_artifacts("unseen-package-audit", tmp_path,
        netlist_to_build_graph(unfamiliar()))
    quality = result["quality"]
    assert quality["geometry_fidelity"]["status"] == "logical_preview"
    assert quality["fabrication_ready"] is False
    assert quality["electrical_safety_scope"] == "known_catalog_rules_only"
    assert any("electrical contracts are unassessed" in warning for warning in quality["warnings"])
    saved = json.loads((tmp_path / "DESIGN_QUALITY.json").read_text())
    assert saved == quality
    native = (tmp_path / "main_ctrl_build.kicad_pcb").read_text()
    assert native_pin_net_map(native) == pin_net_map(unfamiliar())
