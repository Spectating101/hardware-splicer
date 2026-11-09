"""Physical-architecture evidence from actual revision-pinned KiCad netlists.

The source is Gekkio's CC BY 4.0 reverse-engineered Game Boy DMG-CPU-06
schematics, NOT a fictitious model-provided pinout or an observed target PCB.
The derived JSON is from kicad-cli netlist export; per-net references can be
compared against the pinned source artifacts. All claims stay DECLARED.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from .engineering_source_graph import build_engineering_source_graph
from .repair_intake import extract_repair_context
from .restoration_reasoning_agent import SCHEMA, sha

DATA = Path(__file__).resolve().parents[2] / "examples/restoration_video_bench/real_schematic"
SCHEMATIC_MAIN = "DMG-CPU-06/DMG-CPU-06.kicad_sch"
SCHEMATIC_POWER = "DC-CONV-DMG-AB/DC-CONV-DMG-AB.kicad_sch"
MANDATORY_PARTS = {"BT1", "DC1", "SW1", "D1", "J1"}
CASE_SOURCE = "https://revamp.top/gameboy/gameboy-dmg-no-power-battery-contact/"


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_reference(
    data_dir: Path = DATA,
    source_checkout: Path | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest = json.loads((data_dir/"source_gb_dmg_manifest.json").read_text())
    raw = (data_dir/"dmg_netlist_snapshot.json").read_bytes()
    if _digest(raw) != manifest["derived_snapshot_sha256"]:
        raise ValueError("derived real schematic netlist snapshot hash mismatch")
    parsed = json.loads(raw)
    if parsed["schema"] != "hs.restoration.real_kicad_netlist_snapshot.v1":
        raise ValueError("unexpected netlist source schema")
    if parsed["source_commit"] != manifest["commit"]:
        raise ValueError("schematic commit was substituted")
    if manifest["repository"] != "https://github.com/Gekkio/gb-schematics":
        raise ValueError("unrecognized reference design source")
    if "CC-BY-4.0" not in manifest["license"]:
        raise ValueError("source attribution and license missing")
    for board in ("DMG-CPU-06","DC-CONV-DMG-AB"):
        v = parsed["reference_boards"][board]
        if len(v["components"]) != v["component_count"] or len(v["nets"]) != v["net_count"]:
            raise ValueError("inconsistent real netlist counts")
        refs = [c["ref"] for c in v["components"]]
        nets = [n["name"] for n in v["nets"]]
        if len(set(refs))!=len(refs) or len(set(nets))!=len(nets):
            raise ValueError("duplicate component reference or net label")
        for net in v["nets"]:
            if not net["nodes"] or any(node["ref"] not in refs for node in net["nodes"]):
                raise ValueError("net connects an unknown component")
    if source_checkout is not None:
        # Verify actual downloaded KiCad source against the pinned hash list.
        for rel,digest in manifest["files"].items():
            path=source_checkout/rel
            if path.is_symlink() or not path.is_file() or _digest(path.read_bytes())!=digest:
                raise ValueError("reference KiCad file missing or does not match pinned commit: "+rel)
    return manifest,parsed


def source_connected_nets(
    board: Mapping[str, Any], component_references: set[str]
) -> list[dict[str, Any]]:
    actual={c["ref"] for c in board["components"]}
    unknown = component_references-actual
    if unknown:
        raise ValueError("requested physical components absent from reference design: "+repr(sorted(unknown)))
    matches=[]
    for net in board["nets"]:
        selected=[n for n in net["nodes"] if n["ref"] in component_references]
        if selected:
            matches.append({
                "name":net["name"],
                "selected_terminals":selected,
                "all_terminals":net["nodes"],
                "component_terminal_count":len(net["nodes"]),
            })
    return matches


def build_reference_tool_result(
    *, reported_board_revision: str | None,
    data_dir: Path = DATA, source_checkout: Path | None = None,
) -> dict[str, Any]:
    manifest,snapshot=load_reference(data_dir,source_checkout=source_checkout)
    main=snapshot["reference_boards"]["DMG-CPU-06"]
    converter=snapshot["reference_boards"]["DC-CONV-DMG-AB"]
    revision_match=(reported_board_revision or "").strip().upper()=="DMG-CPU-06"
    # Explicitly fail closed for a board revision the repair report did not
    # identify. No model may guess an unknown target has the same pinout.
    if not revision_match:
        return {
            "schema":"hs.restoration.real_schematic_reference_tool.v1",
            "status":"board_revision_unmatched_pin_mapping_withheld",
            "reported_target_board":reported_board_revision or "not_reported",
            "reference_board":"DMG-CPU-06",
            "target_board_physically_verified":False,
            "source_commit":manifest["commit"],
            "source_uri":manifest["repository"],
            "reason":"The reported board revision is not exactly DMG-CPU-06; physical terminal mapping cannot be applied.",
            "pin_specific_evidence_available":False,
            "candidate_battery_nets":[],
            "repair_authorized":False,
        }
    selected=source_connected_nets(main,MANDATORY_PARTS)
    expected={"BT1","SW1","DC1","D1","J1"}
    actual=set(c["ref"] for c in main["components"])
    if not expected<=actual:
        raise ValueError("power-path components not available in pinned schematic")
    facts=[]
    for row in selected:
        # Do not pretend two sides of a diode or a switch are conductive;
        # each connection is one actual KiCad net, NOT a tested voltage path.
        facts.append({
            "net":row["name"],
            "terminals":row["all_terminals"],
            "selected_terminals":row["selected_terminals"],
            "source_file":SCHEMATIC_MAIN,
            "source_file_sha256":manifest["files"][SCHEMATIC_MAIN],
            "physical_measurement":False,
            "reference_circuit_only":True,
        })
    ledger=build_engineering_source_graph([
        {
            "source_id":"gekkio-dmg-cpu-06-schematic",
            "source_type":"schematic",
            "uri":f'{manifest["repository"]}/blob/{manifest["commit"]}/{SCHEMATIC_MAIN}',
            "revision":manifest["commit"],
            "content_hash":"sha256:"+manifest["files"][SCHEMATIC_MAIN],
            "authority_ceiling":"declared",
            "claims":[
                {
                    "claim_id":f'S{i+1}',
                    "subject_id":"DMG-CPU-06::"+fact["net"],
                    "predicate":"kicad_net_connections",
                    "value":fact,
                    "authority":"declared",
                    "path":SCHEMATIC_MAIN,
                    "metadata":{
                        "derived_by":"kicad-cli sch export netlist --format kicadxml",
                        "target_board_verification":"reported_not_independently_verified",
                    },
                } for i,fact in enumerate(facts)
            ],
        },
        {
            "source_id":"gekkio-dc-conv-ab-reference",
            "source_type":"schematic",
            "uri":f'{manifest["repository"]}/blob/{manifest["commit"]}/{SCHEMATIC_POWER}',
            "revision":manifest["commit"],
            "content_hash":"sha256:"+manifest["files"][SCHEMATIC_POWER],
            "authority_ceiling":"declared",
            # No power-board physical claims: its variant is NOT verified.
            "claims":[],
        },
    ], unresolved_source_ids=[
        "actual_power_converter_board_variant_not_confirmed",
        "board_revision_reported_by_website_not_verified_from_photo",
        "actual_continuity_and_supply_measurements_not_performed",
        "no_verified_meter_observations",
        "no_component_datasheet_provided",
        "reference_netlist_does_not_prove_live_conduction",
    ])
    if len(ledger.claims)!=len(facts) or any(x.authority.value!="declared" for x in ledger.claims):
        raise ValueError("schematic claims incorrectly promoted to measured truth")
    required_test_nets=["/Power/BT+","/Power/SW1-VCC","VCC","VDD"]
    if not set(required_test_nets)<={x["net"] for x in facts}:
        raise ValueError("battery-to-switched-circuit reference topology incomplete")
    return {
        "schema":"hs.restoration.real_schematic_reference_tool.v1",
        "status":"reference_netlist_available_reported_revision_match_only",
        "reported_target_board":reported_board_revision,
        "reference_board":"DMG-CPU-06",
        "target_board_physically_verified":False,
        "power_board_type_physically_verified":False,
        "source_repo":manifest["repository"],
        "source_commit":manifest["commit"],
        "source_license":"CC-BY-4.0; attribution to Gekkio",
        "schematic_file_sha256":manifest["files"][SCHEMATIC_MAIN],
        "reference_snapshot_sha256":manifest["derived_snapshot_sha256"],
        "native_HS_engineering_source_graph_sha256":sha(ledger.model_dump(mode="json")),
        "native_HS_source_graph_schema":ledger.schema_version,
        "source_graph_claim_authority":"declared",
        "unresolved_source_ids":ledger.unresolved_source_ids,
        "mainboard_components_extracted":main["component_count"],
        "mainboard_nets_extracted":main["net_count"],
        "converter_reference_components_extracted":converter["component_count"],
        "converter_reference_nets_extracted":converter["net_count"],
        "converter_netlist_withheld_from_target_pin_inference":True,
        "pin_specific_evidence_available":True,
        "candidate_battery_nets":facts,
        "no_inferred_conduction_through_components":True,
        "instrument_measurements_by_HS":False,
        "repair_authorized":False,
    }


def build_case_context(*, reported_board_revision:str, tool_reference:Mapping[str,Any]|None = None)->dict[str, Any]:
    native=extract_repair_context({"repair_intake":{
        "device_hint":"Nintendo Game Boy DMG-01",
        "symptoms":[
            "Repair account reports that original Game Boy does not power on from four AA cells.",
            "Same device reportedly powers up from a compatible external DC adapter.",
            f"Repair account labels the mainboard {reported_board_revision}; this is not independently verified.",
        ],
    }})
    evidence=[{
        "id":f"E{i+1}","kind":"publisher_reported_symptom",
        "text":text,"source":CASE_SOURCE,"stage":"public_intake_pre_repair_only",
    } for i,text in enumerate(native["symptoms"])]
    context={
        "schema":SCHEMA,"case_id":"dmg_reported_battery_only_failure",
        "device":native["device_hint"],
        "source_url":CASE_SOURCE,
        "native_HS_repair_intake_schema":native["schema_version"],
        "hazards":["low_voltage_batteries","mains_power_adapter_external_only","corroded_alkaline_cell"],
        "evidence_stage":"title_and_early_symptoms_excluding_repair_actions",
        "preceding_receipt_sha256":None,
        "evidence":evidence,"evidence_sha256":sha(evidence),
        "repair_authorized":False,
    }
    if tool_reference is not None:
        if tool_reference["reported_target_board"]!=reported_board_revision:
            raise ValueError("reference board claim differs from case report")
        if tool_reference["status"]!="reference_netlist_available_reported_revision_match_only":
            raise ValueError("unknown or unmatched schematic cannot supply pin references")
        context["engineering_reference"] = dict(tool_reference)
    return context
