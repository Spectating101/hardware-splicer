"""Dual Waveshare touchscreen product trial through *existing* HS engines.

Reuses Mecha-Splicer bundle+CGAL sweep and HS MachineProject release assessment.
No firmware loaded, physical panel connected, or SSH session created.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
CYBER = HERE.parent
REPO = HERE.parents[2]
sys.path.insert(0, str(CYBER))
sys.path.insert(0, str(REPO / "src"))

from produce_terminal import run as run_native_mecha
from hardware_splicer.machine_project import (
    AuthorityState, Component, ComponentSource, Domain, EvidenceRef,
    Interface, InterfaceContract, InterfaceEndpoint, MachineProject, PartIdentity,
    ReleaseState, Requirement, RequirementKind, Subsystem,
    VerificationMethod, VerificationType, VerificationStatus,
)


def build_product_case(cad_report: dict) -> MachineProject:
    """Canonical cross-domain requirements/evidence graph; no custom authority model."""
    reqs = [
        ("r-hinge", "Two rigid 4.3-inch panels shall fold on an ordinary metal pin hinge", RequirementKind.FUNCTIONAL, "v-geometry", "v-hinge-physical"),
        ("r-dual-touch", "Each 800x480 panel must receive and respond to its own touch events", RequirementKind.FUNCTIONAL, "v-panel-touch"),
        ("r-keyboard", "Lower virtual keyboard shall deliver Ctrl/Esc/Tab/Enter/arrows to upper SSH PTY exactly once", RequirementKind.FUNCTIONAL, "v-keys"),
        ("r-link", "Two 2-pin HY2.0 RS485 ports shall exchange key events over hinge without LCD FPC", RequirementKind.INTERFACE, "v-link"),
        ("r-power", "Dual 5V boards shall have documented safe current, common reference and protected USB feed", RequirementKind.SAFETY, "v-power"),
        ("r-security", "Upper SSH shall validate out-of-band pinned host key before any credentials", RequirementKind.SAFETY, "v-host-key"),
        ("r-portability", "Enclosure dimensions, cable bend and mass shall be demonstrated physically", RequirementKind.PERFORMANCE, "v-physical-fit"),
    ]
    requirements = []
    for row in reqs:
        rid, statement, kind, *vers = row
        requirements.append(Requirement(
            requirement_id=rid, statement=statement, kind=kind,
            verification_method_ids=vers, authority=AuthorityState.DECLARED))
    subsystems = [
        Subsystem(subsystem_id="upper", name="Upper touch SSH controller",
                  domain=Domain.ELECTRICAL, component_ids=["upper-lcd", "optiplex"]),
        Subsystem(subsystem_id="lower", name="Lower touch virtual keyboard",
                  domain=Domain.ELECTRICAL, component_ids=["lower-lcd"]),
        Subsystem(subsystem_id="shell", name="Mechanical dual-tray hinge",
                  domain=Domain.MECHANICAL, component_ids=["base-shell", "lid-shell", "hinge-pin"]),
        Subsystem(subsystem_id="link", name="Inter-half RS485 and power",
                  domain=Domain.ELECTRICAL, component_ids=["hinge-wire", "bench-usb"]),
    ]
    w = PartIdentity(manufacturer="Waveshare",
        manufacturer_part_number="ESP32-S3-Touch-LCD-4.3",
        datasheet_ref="https://docs.waveshare.com/ESP32-S3-Touch-LCD-4.3",
        provenance="public manufacturer documentation; no unit acquired")
    components = [
        Component(component_id="upper-lcd",name="Upper ESP32-S3 4.3-inch touch display",
                  domain=Domain.ELECTRICAL,subsystem_id="upper",source=ComponentSource.NEW,
                  part=w,authority=AuthorityState.PROPOSED),
        Component(component_id="lower-lcd",name="Lower ESP32-S3 4.3-inch touch display",
                  domain=Domain.ELECTRICAL,subsystem_id="lower",source=ComponentSource.NEW,
                  part=w,authority=AuthorityState.PROPOSED),
        Component(component_id="optiplex",name="Remote Optiplex Linux SSH host",
                  domain=Domain.SOFTWARE,subsystem_id="upper",source=ComponentSource.EXTERNAL,
                  authority=AuthorityState.PROPOSED,
                  metadata={"identity":"owner-authorized remote system, no SSH tested by cyberdeck"}),
        Component(component_id="base-shell",name="PETG case base",
                  domain=Domain.MECHANICAL,subsystem_id="shell",
                  source=ComponentSource.GENERATED,authority=AuthorityState.PROPOSED),
        Component(component_id="lid-shell",name="PETG display lid",
                  domain=Domain.MECHANICAL,subsystem_id="shell",
                  source=ComponentSource.GENERATED,authority=AuthorityState.PROPOSED),
        Component(component_id="hinge-pin",name="Unpurchased steel 2mm hinge pin",
                  domain=Domain.MECHANICAL,subsystem_id="shell",source=ComponentSource.NEW),
        Component(component_id="hinge-wire",name="2-pin RS485 A/B harness with ground reference",
                  domain=Domain.ELECTRICAL,subsystem_id="link",source=ComponentSource.NEW),
        Component(component_id="bench-usb",name="Unselected protected USB supply 5V 2A minimum",
                  domain=Domain.ELECTRICAL,subsystem_id="link",source=ComponentSource.NEW),
    ]
    interfaces = [
        Interface(interface_id="link-rs485",name="Differential-keyboard packet bridge",
            kind="serial_rs485_half_duplex",
            endpoints=[InterfaceEndpoint(object_id="upper-lcd",port="HY2.0_RS485_2P"),
                       InterfaceEndpoint(object_id="lower-lcd",port="HY2.0_RS485_2P")],
            contracts=[InterfaceContract(contract_type="RS485",values={
                "onboard_transceiver":"SP3485 on both boards",
                "tx_gpio":15,"rx_gpio":16,"uart_baud_scenario":115200,
                "physical_screen_ribbon_over_hinge":False,
                "line_protocol":"sequence, CRC, ACK and timeout to be implemented"},
                unresolved_fields=["A/B terminal polarity", "common_ground",
                                   "termination_and_bias", "packet_firmware",
                                   "measured_cable_flex_life"],
                authority=AuthorityState.PROPOSED)]),
        Interface(interface_id="usb-power",name="Both designated USB-C power ports",
            kind="power_5v",
            endpoints=[InterfaceEndpoint(object_id="bench-usb",port="5V"),
                       InterfaceEndpoint(object_id="upper-lcd",port="designated_USB_C"),
                       InterfaceEndpoint(object_id="lower-lcd",port="designated_USB_C")],
            contracts=[InterfaceContract(contract_type="power_budget",values={
                "nominal_board_draw_mA_each":450,"nominal_total_5V_W":4.5,
                "prototype_supply_minimum":"5V 2A, dual USB outputs"},
                unresolved_fields=["peak_current_measured", "external_5V_USB_supply",
                                    "real_power_connector", "safe_common_ground"],
                authority=AuthorityState.PROPOSED)]),
        Interface(interface_id="ssh-link",name="Host identity and SSH session",
            kind="ssh",
            endpoints=[InterfaceEndpoint(object_id="upper-lcd",port="WiFi_2.4GHz"),
                       InterfaceEndpoint(object_id="optiplex",port="SSH")],
            contracts=[InterfaceContract(contract_type="ssh_host_identity",
                values={"known_host_pinning_mandatory":True,
                        "private_key_material_in_repo":False},
                unresolved_fields=["out_of_band_host_key_pin", "library_port",
                                   "actual_ssh_handshake", "network_security_route"],
                authority=AuthorityState.PROPOSED)]),
    ]
    simulated_evidence = [
        EvidenceRef(evidence_id="cad-mesh",kind="OpenSCAD CGAL mesh audit",
                    basis="native shell STL audited with zero non-manifold edges",
                    ref="evidence/native_mecha/design_evidence.json",
                    supports=["base-shell","lid-shell","r-hinge"],
                    authority=AuthorityState.PROPOSED,simulated=True),
        EvidenceRef(evidence_id="cad-sweep",kind="6-angle digital interference check",
                    basis="CGAL shell intersection empty at each sampled angle",
                    ref="evidence/native_mecha/design_evidence.json",
                    supports=["r-hinge"],authority=AuthorityState.PROPOSED,
                    simulated=True),
    ]
    if any(x["nonmanifold_edges"] != 0 for x in cad_report["mesh"].values()):
        raise ValueError("CAD mesh evidence not passing")
    if any(x["interference_mesh"]!="EMPTY" for x in cad_report["cgal_interference_sweep"]):
        raise ValueError("CAD interference evidence not passing")
    verifications=[
        VerificationMethod(verification_id="v-geometry",name="CAD mesh watertightness",
            method_type=VerificationType.ANALYSIS,status=VerificationStatus.PASSED,
            requirement_ids=["r-hinge"],evidence_ids=["cad-mesh"],
            target_ids=["base-shell","lid-shell"]),
        VerificationMethod(verification_id="v-hinge-physical",name="Actual printed hinge open-close cycles",
            method_type=VerificationType.TEST,requirement_ids=["r-hinge"]),
        VerificationMethod(verification_id="v-panel-touch",name="Two independently functioning capacitive displays",
            method_type=VerificationType.TEST,requirement_ids=["r-dual-touch"]),
        VerificationMethod(verification_id="v-keys",name="All terminal control keys on target board",
            method_type=VerificationType.DEMONSTRATION,requirement_ids=["r-keyboard"]),
        VerificationMethod(verification_id="v-link",name="RS485 polarity, power reference, CRC/ACK test",
            method_type=VerificationType.TEST,requirement_ids=["r-link"]),
        VerificationMethod(verification_id="v-power",name="USB current/ground/peak and battery isolation",
            method_type=VerificationType.TEST,requirement_ids=["r-power"]),
        VerificationMethod(verification_id="v-host-key",name="Pinned SSH host key success and mismatch rejection",
            method_type=VerificationType.TEST,requirement_ids=["r-security"]),
        VerificationMethod(verification_id="v-physical-fit",name="PCB Z, mounts, ports, antenna, cable fit and closed thickness",
            method_type=VerificationType.INSPECTION,requirement_ids=["r-portability"]),
    ]
    return MachineProject(
        project_id="HS-DUAL-TOUCH-S1",
        name="Thin, folding two-ESP32 touchscreen SSH terminal",
        purpose="Use upper touchscreen as Optiplex SSH terminal and lower as virtual command keyboard.",
        lifecycle_state="design",
        requested_release_state=ReleaseState.OPERATIONALLY_AUTHORIZED,
        requirements=requirements,subsystems=subsystems,
        components=components,interfaces=interfaces,
        evidence=simulated_evidence,verifications=verifications,
        metadata={"physical_items_count":0,
                  "existing_mecha_splicer_used":True,
                  "manufacturer_model_exact":True,
                  "cad_not_physical_release":True},
    )


def run(spec_path: Path, output: Path, renderer: str) -> dict:
    cad=run_native_mecha(spec_path, output, renderer)
    if cad["closed_envelope"]["lower_input_type"] != "dual_touch":
        raise ValueError("Not the dual touchscreen target")
    project=build_product_case(cad)
    (output/"machine_project.json").write_text(
        json.dumps(project.model_dump(mode="json"),indent=2)+"\n",encoding="utf-8")
    release=project.assess_release(ReleaseState.OPERATIONALLY_AUTHORIZED)
    release_data=release.model_dump(mode="json")
    if release.allowed or release.achieved_state==ReleaseState.OPERATIONALLY_AUTHORIZED:
        raise ValueError("No physical authority: release gate must reject CAD-only candidate")
    (output/"hs_release_assessment.json").write_text(
        json.dumps(release_data,indent=2)+"\n",encoding="utf-8")
    sources=json.loads((HERE/"sources_20261106.json").read_text(encoding="utf-8"))
    lines=sources["parts_price_scenario"]
    budget=sum(row["subtotal_twd"] for row in lines)
    if budget != 2965: raise ValueError(f"Unreviewed budget drift: {budget}")
    budget_record={
        "budget_scenario_twd":budget, "screen_subtotal_twd":2500,
        "screen_ratio":round(2500/budget,3),
        "quote_obtained":False,"parts_obtained":False,
        "shipping_included":False, "battery_included":False,
        "labor_included":False,
        "electricity_5V_nominal_W":sources["workbench_power"]["nominal_total_W"],
        "candidate_status":"CAD_ONLY_PENDING_SOURCE_FIT_ELECTRICAL_FIRMWARE_TESTS",
        "screen_price_origin":sources["board"]["price_tw_source"],
        "lines":lines
    }
    (output/"budget.json").write_text(json.dumps(budget_record,indent=2)+"\n",encoding="utf-8")
    result={
        "status":"DESIGN_ONLY_PHYSICAL_BUILD_BLOCKED",
        "existing_hs_mecha":"Mecha-Splicer native generates shell STL and 6-angle CGAL check",
        "existing_hs_system":"MachineProject assess_release",
        "native_cad":cad,
        "release":release_data,
        "budget":budget_record,
        "real_SSH_sessions":0,
        "real_ESP32_boards":0,
    }
    print("HS MECH native",sorted(cad["native_outputs"]),
          "mesh nonmanifold",[(x,y["nonmanifold_edges"]) for x,y in cad["mesh"].items()])
    print("6 pose mesh collision",len(cad["cgal_interference_sweep"]),"passed")
    print("Canonical HS release",release.achieved_state.value,"requested",
          release.requested_state.value, "allowed",release.allowed,
          "blockers",len(release.blockers))
    print("Dual 4.3 screens NT$2500 + other assumptions =>",budget,"TWD parts only")
    print("No hardware was acquired, powered, linked or used to SSH")
    return result


def main()->None:
    p=argparse.ArgumentParser()
    p.add_argument("--spec",type=Path,default=HERE/"dual_touch_spec.json")
    p.add_argument("--out",type=Path,default=HERE/"evidence"/"native_mecha")
    p.add_argument("--openscad",default=shutil.which("openscad"))
    a=p.parse_args()
    if not a.openscad:raise SystemExit("OpenSCAD is required for real CGAL, not an imagined pass")
    run(a.spec,a.out,a.openscad)

if __name__=="__main__":main()
