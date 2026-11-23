"""Adapter layer from a verified HS product specimen to external engineering tools.

Uses the existing product spec and SHA-256 receipt. Builds external-tool INPUTS
only; verification levels are assigned by the independent CI jobs that actually
execute those tools. No external code is copied or vendored.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


def require(condition:bool,message:str)->None:
    if not condition: raise ValueError("Ecosystem product bridge refused: "+message)

def sha(payload:bytes)->str:
    return hashlib.sha256(payload).hexdigest()

def canonical(value:Any)->bytes:
    return (json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+"\n").encode()

def load_product(root:Path)->tuple[dict,dict,dict]:
    root=Path(root)
    receipt=json.loads((root/"PRODUCT_RECEIPT.json").read_text())
    require(receipt.get("schema_version")=="hardware_splicer.product_demonstrator_receipt.v1",
            "unknown HS product evidence contract")
    expected={"PRODUCT_SPEC.json","PRODUCT_ARCHITECTURE.json","PRODUCT_BOM.json",
              "PRODUCT_OPERATOR_WORKFLOW.json","PRODUCT_SCENE.scad",
              "UPSTREAM_ASSEMBLY_RECEIPT.json"}
    require(set(receipt.get("files",{}))==expected,"product evidence set incomplete")
    for name,entry in receipt["files"].items():
        body=(root/name).read_bytes()
        require(sha(body)==entry.get("sha256") and len(body)==entry.get("bytes"),
                "product evidence changed after verification: "+name)
    product=json.loads((root/"PRODUCT_SPEC.json").read_text())
    arch=json.loads((root/"PRODUCT_ARCHITECTURE.json").read_text())
    bom=json.loads((root/"PRODUCT_BOM.json").read_text())
    require(sha(canonical(product))==receipt["product_spec_sha256"]==
            arch["product_spec_sha256"],"different product specification or revision")
    require(product["product_id"]=="clearbench_s1_nonpotable_001" and
            product["intended_use"]=="non_potable_particle_challenge_only",
            "unsupported product model variant")
    require(arch["release_tier"]=="DIGITAL_PRODUCT_DEMONSTRATOR_ONLY"
            and bom["vendor_fully_qualified_bom"] is False
            and not any(arch["physical_authority"].values())
            and len(product["product_bom"])==11
            and len(bom["items"])==11,
            "upstream model falsely physically qualified or BOM incomplete")
    require(arch["functional_flow_graph"]["every_symbolic_sample_path_traverses_filter"]
            and not arch["functional_flow_graph"]["actual_hydraulic_connectivity_assembled"],
            "physical process is not a source-bound verified symbolic route")
    render=json.loads((root/"PRODUCT_RENDER_EVIDENCE.json").read_text())
    require(render.get("schema_version")=="hardware_splicer.whole_product_native_render.v1"
            and render.get("product_spec_sha256")==receipt["product_spec_sha256"]
            and render.get("product_build_ready") is False
            and render.get("native_pressure_containment_created") is False,
            "prior native CAD render or scope unverified")
    image=render["complete_product_assembly_image"]
    body=(root/image["file"]).read_bytes()
    require(sha(body)==image["sha256"] and len(body)==image["bytes"],
            "product visualization changed after source-linked native render")
    for item in render["independently_checked_native_geometry"].values():
        blob=(root/item["file"]).read_bytes()
        require(sha(blob)==item["sha256"] and len(blob)==item["bytes"],
                "source-native STL changed: "+item["file"])
    return product,receipt,render


def to_blueprint_spec(product:Mapping[str,Any],receipt:Mapping[str,Any])->dict:
    """Convert HS coordinate (x,y,up=z) to B2D (x,up=y,depth=z)."""
    layout=product["layout"]
    def coords(x:float,y:float,z:float)->list[float]:return [x,z,y]
    def part(id:str,label:str,shape:dict,position:list,material:str="metal",note:str="",
             explode:list|None=None)->dict:
        row={"id":id,"name":label,"note":note or "Visual concept: not physically qualified",
             "material":material,"shape":shape,
             "transform":{"pos":position}}
        if explode is not None:row["explode"]=explode
        return row
    tray=layout["tray"]; panel=layout["back_panel"]; housing=layout["filter_housing"]
    service=layout["service_region"];cup=layout["sample_cup"]
    parts=[
        part("tray","CATCH TRAY — CONCEPT",
             {"type":"box","size":[tray["width_mm"],tray["height_mm"],tray["depth_mm"]]},
             coords(0,0,tray["height_mm"]/2),"metal",
             "Concept only; no actual material/rating"),
        part("panel","BACK PANEL — CONCEPT",
             {"type":"box","size":[panel["width_mm"],panel["height_mm"],panel["thickness_mm"]]},
             coords(0,panel["origin_mm"][1]+panel["thickness_mm"]/2,
                    panel["origin_mm"][2]+panel["height_mm"]/2),"metal",
             "No verified bracket fastener pattern"),
        part("housing","PENTAIR 158007 — ENVELOPE",
             {"type":"cylinder","r":housing["diameter_mm"]/2,"h":housing["height_mm"],"segments":48},
             coords(housing["center_x_mm"],housing["center_y_mm"],
                    housing["bottom_z_mm"]+housing["height_mm"]/2),"glass",
             "Published external housing bounds only, not real manufacturer CAD",
             [0,0,140]),
        part("service","UNVERIFIED SERVICE CORRIDOR",
             {"type":"cylinder","r":service["diameter_mm"]/2,"h":service["height_mm"],"segments":40},
             coords(service["center_x_mm"],service["center_y_mm"],
                    service["bottom_z_mm"]+service["height_mm"]/2),"plastic",
             "Illustrative 150 mm allocation, not manufacturer-approved service clearance",
             [0,-105,0]),
        part("sample","SAMPLE VESSEL — CONCEPT",
             {"type":"cylinder","r":cup["diameter_mm"]/2,"h":cup["height_mm"],"segments":36},
             coords(cup["center_x_mm"],cup["center_y_mm"],
                    cup["bottom_z_mm"]+cup["height_mm"]/2),"glass",
             "Non-potable sampling concept; actual container not selected",
             [130,40,0]),
    ]
    for item in layout["pressure_indicators"]:
        x,y,z=item["center_mm"]
        parts.append(part(item["id"].lower(),item["id"]+" — UNQUALIFIED GAUGE",
             {"type":"cylinder","r":item["diameter_mm"]/2,"h":9,"segments":40},
             coords(x,y,z),"metal",
             "Instrument location only; no pressure reading, range or calibration",
             [140,0,0]))
    parts.append(part("inlet","INLET FLOW PATH — SYMBOLIC",
             {"type":"cylinder","r":4.5,"h":90,"segments":24},
             coords(-170,0,536),"plastic",
             "Diagrammatic pipe segment only; no measured fitting or pressure rating",
             [-90,0,0]))
    parts.append(part("outlet","OUTLET FLOW PATH — SYMBOLIC",
             {"type":"cylinder","r":4.5,"h":110,"segments":24},
             coords(66,0,536),"plastic",
             "Diagrammatic pipe segment; not pressure-tight nor connected",
             [110,0,0]))
    parts.append(part("sample_valve","SAMPLING VALVE — UNSELECTED",
        {"type":"box","size":[22,24,22]},coords(145,-35,160),"metal",
        "Function required; no rated valve chosen",[90,0,60]))
    parts.append(part("label","NON-POTABLE LABEL — CONCEPT",
        {"type":"box","size":[185,40,2]},coords(95,92,650),"plastic",
        "Never use or drink unverified output", [0,80,0]))
    # Viewer density is substantive: expose the *whole product* as distinct
    # conceptual interface / maintenance / documentation layers. These
    # display primitives are NOT additional BOM or pressure-bearing items.
    housing_center=coords(housing["center_x_mm"],housing["center_y_mm"],
                          housing["bottom_z_mm"]+housing["height_mm"]/2)
    additions=[
      part("p5_media","PENTEK P5 MEDIA — DOCUMENTED ENVELOPE",
           {"type":"cylinder","r":30.25,"h":251,"segments":40},
           coords(housing["center_x_mm"],housing["center_y_mm"],386),
           "plastic","Vendor P5 external media size only. Actual cartridge seating/seal UNVERIFIED",
           [0,150,0]),
      part("housing_cap_zone","HOUSING CAP REGION — ILLUSTRATIVE",
           {"type":"cylinder","r":59,"h":24,"segments":48},
           coords(housing["center_x_mm"],housing["center_y_mm"],521),
           "plastic","Cap detail is illustrative; not a real vendor thread or attachment",
           [0,180,0]),
      part("feed_marker","INLET STATION — NOT CONNECTED",
           {"type":"cylinder","r":9,"h":22,"segments":20},
           coords(-201,0,535),"metal","Symbolic feed port location; no rated fittings",
           [-120,0,0]),
      part("outlet_marker","EFFLUENT STATION — NOT CONNECTED",
           {"type":"cylinder","r":9,"h":22,"segments":20},
           coords(118,0,535),"metal","Symbolic outlet; real 3/8-in NPT geometry not modeled",
           [120,0,0]),
      part("delta_label","PRESSURE DIFFERENCE — INFORMATION",
           {"type":"box","size":[132,32,3]},coords(120,91,410),"plastic",
           "Difference is an observation requirement, not treatment performance",
           [140,70,0]),
      part("feed_label","RAW NON-POTABLE INPUT — LABEL",
           {"type":"box","size":[146,24,3]},coords(-137,91,575),"plastic",
           "Input challenge is unspecified until independently tested",
           [-90,60,0]),
      part("sample_label","NON-POTABLE SAMPLE — LABEL",
           {"type":"box","size":[138,26,3]},coords(144,90,245),"plastic",
           "Sampling is not permission to use for drinking",
           [150,60,0]),
      part("service_label","SERVICE ACCESS UNVERIFIED — LABEL",
           {"type":"box","size":[175,26,3]},coords(-80,91,168),"plastic",
           "150 mm lower corridor is an illustrative allocation only",
           [0,-120,0]),
      part("service_control_glyph","SERVICE HANDLE POSITION — CONCEPT",
           {"type":"box","size":[34,18,30]},coords(-65,0,207),"metal",
           "No real wrench or bracket mounting details qualified",
           [-80,-40,0]),
      part("sample_bay","SAMPLE COLLECTION BAY — CONCEPT",
           {"type":"box","size":[110,6,104]},coords(145,-34,28),"plastic",
           "Non-loaded placement guide, not a manufactured tray fixture",
           [90,-40,0]),
      part("left_trim","LEFT DRY PANEL EDGE — CONCEPT",
           {"type":"box","size":[12,710,12]},coords(-219,107,375),"metal",
           "Dry panel styling. No strength or fastening claims",
           [-70,0,0]),
      part("right_trim","RIGHT DRY PANEL EDGE — CONCEPT",
           {"type":"box","size":[12,710,12]},coords(219,107,375),"metal",
           "Dry panel styling. No strength or fastening claims",
           [70,0,0]),
      part("water_warning","NO POTABLE WATER CLAIM — LABEL",
           {"type":"box","size":[205,36,3]},coords(-8,90,690),"plastic",
           "Actual water quality, leak safety and fit UNTESTED",
           [0,120,0]),
      part("test_port_label","SAMPLING TEST POINT — SYMBOLIC",
           {"type":"box","size":[125,24,3]},coords(131,91,198),"plastic",
           "Not a calibrated observation, no test data",
           [120,0,0]),
    ]
    parts.extend(additions)
    require(len(parts)>=24,"external viewer cannot represent the complete product")
    # Actual animation channel(s), not just an inert driver shown in controls.
    for item in parts:
        if item["id"] in ("housing","p5_media","housing_cap_zone","sample","service",
                          "sample_valve","feed_marker","outlet_marker","p_in","p_out"):
            item["channels"]=[{"type":"explode","bind":"apart"}]
    # Functional engraving-like detail is illustrative, NOT a bolt pattern.
    for identifier in ("tray","panel","delta_label","sample_bay"):
        next(x for x in parts if x["id"]==identifier)["details"]=[
            {"kind":"panelLine","face":"front","count":2,"along":"u"}]
    visible=[p for p in parts if p["id"]!="service"]
    annotations={"callouts":[
        {"n":i+1,"text":p["name"],"anchor":p["id"]}
        for i,p in enumerate(visible) if i<24
    ],"dimensions":[
        {"label":"450 mm (concept)","from":[-225,0,-130],"to":[225,0,-130],
         "offset":[0,-45,0]},
        {"label":"740 mm (concept)","from":[-225,0,-130],"to":[-225,740,-130],
         "offset":[-50,0,0]},
        {"label":"260 mm (concept)","from":[225,0,-130],"to":[225,0,130],
         "offset":[50,0,0]},
    ]}
    return {
        "meta":{"id":"clearbench-s1","org":"HARDWARE SPLICER",
                "division":"Function-first product research",
                "title":"CLEARBENCH S1",
                "subtitle":"NON-POTABLE DIGITAL CONCEPT — NO PHYSICAL PERFORMANCE VALIDATED",
                "units":"mm","projection":"THIRD ANGLE",
                "researched":False,
                "titleBlock":{"drawingNo":"HS-CBS1-001","sheet":"1 OF 1",
                    "scale":"SCHEMATIC","rev":"CONCEPT","drawn":"HS",
                    "checked":"SOURCE-BOUND ONLY","status":"NOT BUILD READY"}},
        "bounds":{"length":450,"width":260,"height":740},
        "drivers":[{"id":"apart","min":0,"max":1,"init":0,"ease":3}],
        "parts":parts,"annotations":annotations,
        "explode":{"driver":"apart","scale":0.6,"trace":True},
        "views":[{"id":"iso","label":"ISO","az":38,"el":22},
                 {"id":"front","label":"FRONT","az":0,"el":0,
                  "projection":"orthographic"},
                 {"id":"side","label":"SIDE","az":90,"el":0,
                  "projection":"orthographic"},
                 {"id":"top","label":"TOP","az":0,"el":89,
                  "projection":"orthographic"},
                 {"id":"rear","label":"REAR","az":180,"el":0,
                  "projection":"orthographic"},
                 {"id":"section","label":"SECTION","az":34,"el":18,
                  "section":{"plane":"xy","at":0}}],
        "motions":[{"id":"apart","label":"EXPLODE","set":{"apart":1}},
                   {"id":"reset","label":"ASSEMBLE","set":{"apart":0}}],
        "instruments":[
            {"label":"ASSEMBLY EXPLODE (CONCEPT)","expr":"apart*100","format":"%.0f %"},
            {"label":"PHYSICAL TESTS PASSED","expr":"apart*0","format":"%.0f"},
            {"label":"PRESSURE READINGS VERIFIED","expr":"apart*0","format":"%.0f"},
            {"label":"RELEASE AUTHORITY (0=NO)","expr":"apart*0","format":"%.0f"},
        ],
    }


def to_decad_odbom(product:Mapping[str,Any],receipt:Mapping[str,Any])->dict:
    # Never invent physical fasteners or interference ordering from CAD visuals.
    # No disassembly execution plan until validated physical connector geometry.
    rows=product["product_bom"]
    return {
      "$schema":"https://open-disassembly.org/schemas/v0.1.0/odbom.schema.json",
      "metadata":{
        "odbom_version":"0.1.0",
        "product_id":"URN:HS:CLEARBENCH-S1-CONCEPT-001",
        "name":product["product_name"],
        "description":"UNVERIFIED DIGITAL PRODUCT CONCEPT ONLY. No physical fastener relationships or safe disassembly order measured. Empty disassembly plan is deliberate.",
        "created_by":"Hardware Splicer source-bound adapter",
        "x-hs-source-spec-sha256":receipt["product_spec_sha256"],
        "x-hs-physical_authority":False,
      },
      "nodes":[{
        "id":"node_"+row["ref"].lower(),
        "type":"sub_assembly" if row["ref"] in ("H1","F1") else "structural_part",
        "label":row["ref"]+" "+row["role"]+" — "+row["engineering_status"],
        "x-hs-procurement_status":row["engineering_status"],
      } for row in rows],
      "graph_edges":{"fasteners":[],"bonds":[],"interferences":[],"precedences":[]},
      "disassembly_execution_plan":[],
    }


def backend_readiness(product:Mapping[str,Any],receipt:Mapping[str,Any])->dict:
    stages=[
      ("blueprint-3d-sheet","interactive_offline_assembly_sheet",
       "EXPORT_READY_NATIVE_SCHEMA_PENDING_ACTUAL_UPSTREAM_CLI"),
      ("DeCAD","unverified_product_parts_odbom",
       "EXPORT_READY_NATIVE_SCHEMA_PENDING_ACTUAL_UPSTREAM_CLI"),
      ("CADCLAW","constraint_based_STEP_assembly_validation",
       "BLOCKED_MISSING_AUTHORED_STEP_AND_CONNECTOR_FRAMES"),
      ("MARB","independent_assembly_benchmark",
       "BLOCKED_NO_INDEPENDENT_REFERENCE_STEP_AND_GROUND_TRUTH"),
      ("Teardown","interactive_mechanism_explanation",
       "BLOCKED_NO_VERIFIED_OPERATION_KINEMATICS_OR_BACKEND"),
      ("SolidCraft","native_parametric_mechanical_authoring",
       "BLOCKED_NO_NATIVE_FEATURE_TIMELINE_OR_PART_CONNECTORS"),
      ("FieldCraft","validated_mechanics_and_fluid_simulation",
       "BLOCKED_NO_MEASURED_HYDRAULIC_INPUTS_OR_QUALIFIED_GEOMETRY"),
      ("re:trace","reverse_electronics_photo_analysis",
       "NOT_APPLICABLE_NO_REAL_BOARD_PHOTOS"),
    ]
    return {"schema_version":"hardware_splicer.product_backend_readiness.v1",
            "product_id":product["product_id"],
            "source_spec_sha256":receipt["product_spec_sha256"],
            "backends":[{"name":name,"purpose":purpose,"status":status,
                         "executed_in_this_export":False}
                        for name,purpose,status in stages],
            "all_physical_authorities":False,
            "external_licenses_must_be_respected":True,
            "cross_tool_handoff_preserves_source_hash":True}


def export(product_root:Path,out:Path)->dict:
    product,receipt,render=load_product(product_root)
    out=Path(out)
    require(not out.exists() or (out.is_dir() and not any(out.iterdir())),
            "refusing overwrite of existing external tool evidence")
    parts={
        "BLUEPRINT_ASSEMBLY_SPEC.json":to_blueprint_spec(product,receipt),
        "DECAD_CONCEPT_ODBOM.json":to_decad_odbom(product,receipt),
        "BACKEND_READINESS.json":backend_readiness(product,receipt),
    }
    out.mkdir(parents=True,exist_ok=True)
    written={}
    for name,value in parts.items():
        body=canonical(value)
        (out/name).write_bytes(body)
        written[name]={"sha256":sha(body),"bytes":len(body)}
    record={
       "schema_version":"hardware_splicer.product_ecosystem_handoff.v1",
       "product_id":product["product_id"],
       "source_spec_sha256":receipt["product_spec_sha256"],
       "hs_product_receipt_sha256":sha((Path(product_root)/"PRODUCT_RECEIPT.json").read_bytes()),
       "inputs_are_vendor_unqualified_digital_concepts":True,
       "external_backend_executed":False,
       "files":written,
       "physical_product_verified":False,
       "fabrication_authorized":False,
    }
    (out/"ECOSYSTEM_HANDOFF_RECEIPT.json").write_bytes(canonical(record))
    return record
