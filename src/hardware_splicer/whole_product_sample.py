"""Whole-device demonstrator synthesis from real HS function→component→assembly evidence.

This is a complete *digital product-level demonstration* with all externally
visible functional stations, operator workflow, product BOM, physical interface
routing and native 3D render inputs. It deliberately does not create usable
pressure-containing parts or claim a water-quality/physical test.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .function_intent_bridge import canonical
from .filter_assembly_gate import load, verified_artifact

SCHEMA="hardware_splicer.product_demonstrator.v1"
REPORT_SCHEMA="hardware_splicer.product_sample_acceptance.v1"


def sha(data:bytes)->str:
    return hashlib.sha256(data).hexdigest()


def require(ok:bool,msg:str)->None:
    if not ok:
        raise ValueError("Whole-product synthesis REFUSED: "+msg)


def validate_upstream(root:Path)->tuple[dict,dict,dict]:
    root=Path(root)
    receipt=load(root,"ASSEMBLY_RECEIPT.json")
    require(receipt.get("schema_version")=="hardware_splicer.filter_assembly_evidence_receipt.v1",
            "invalid upstream assembly receipt")
    expected={"ASSEMBLY_SOURCE.json","ASSEMBLY_GATE.json","EVIDENCE_REQUESTS.json",
              "UPSTREAM_COMPONENT_RECEIPT.json","UPSTREAM_NATIVE_CAD_EVIDENCE.json"}
    require(set(receipt.get("files",{}))==expected,"incomplete assembly evidence")
    for name,item in receipt["files"].items():
        verified_artifact(root,name,item)
    gate=load(root,"ASSEMBLY_GATE.json")
    source=load(root,"ASSEMBLY_SOURCE.json")
    measurement=load(root,"EVIDENCE_REQUESTS.json")
    require(gate.get("outcome")=="ASSEMBLY_DESIGN_BLOCKED_PENDING_EVIDENCE"
            and gate.get("project_id")==receipt.get("project_id")
            and gate.get("assembly_source_sha256")==receipt.get("assembly_source_sha256")
            and gate.get("assembly_source_sha256")==sha(canonical(source))
            and measurement.get("assembly_source_sha256")==gate.get("assembly_source_sha256"),
            "assembly source or readiness is inconsistent")
    require(gate.get("actual_native_clearance_meshes_checked") is True,
            "upstream OpenSCAD verification not executed")
    require(len(gate.get("interface_evidence_gates",[]))==6 and
            len(measurement.get("evidence_requests",[]))==7,
            "upstream interfaces or evidence requests missing")
    require(not any(gate["physical_authority"].values()) and
            gate.get("hydraulic_pressure_at_target_flow_psi") is None and
            gate.get("sku_specific_certification_verified") is False and
            gate.get("physical_water_test_executed") is False,
            "unqualified physical evidence promoted")
    return receipt,gate,measurement


def check_flow_graph(graph:dict)->dict:
    nodes=graph.get("nodes",[])
    edges=graph.get("edges",[])
    require(len(nodes)==6 and len(set(nodes))==6 and len(edges)==5,
            "product flowpath has missing/extra terminals")
    required={"nonpotable_feed","inlet_pressure_observation","manufacturer_filter_housing",
              "outlet_pressure_observation","sampling_valve","nonpotable_sample_vessel"}
    require(set(nodes)==required and
            graph.get("required_treatment_node")=="manufacturer_filter_housing" and
            graph.get("bypass_prohibited") is True and
            graph.get("flow_path_is_symbolic_not_physical") is True,
            "product fluid graph endpoints or authority invalid")
    adj={node:[] for node in nodes}
    for edge in edges:
        require(isinstance(edge,list) and len(edge)==2 and
                edge[0] in adj and edge[1] in adj and edge[0]!=edge[1],
                "invalid flowpath edge")
        adj[edge[0]].append(edge[1])
    def can_reach(start:str,goal:str,excluded:set[str])->bool:
        visited=set(excluded)
        todo=[start]
        while todo:
            node=todo.pop()
            if node in visited:continue
            if node==goal:return True
            visited.add(node)
            todo.extend(adj[node])
        return False
    require(can_reach("nonpotable_feed","nonpotable_sample_vessel",set()),
            "no complete input→output route")
    require(not can_reach("nonpotable_feed","nonpotable_sample_vessel",
                          {"manufacturer_filter_housing"}),
            "unfiltered water can bypass the selected filter core")
    require(len(set(tuple(v) for v in edges))==len(edges),
            "duplicate parallel flowpath")
    require(all(len(adj[n])<=1 for n in adj),"unreviewed alternate routing/branching")
    return {
      "symbolic_inlet_to_sample_connected":True,
      "every_symbolic_sample_path_traverses_filter":True,
      "actual_hydraulic_connectivity_assembled":False,
      "water_quality_verified":False,
      "pressure_and_leak_rating_verified":False,
    }


def validate_product(source:dict,assembly:dict)->dict:
    require(source.get("schema_version")==SCHEMA
            and source.get("functional_project_id")==assembly.get("project_id")
            and source.get("candidate_technology_id")=="passive_replaceable_depth_media"
            and source.get("product_id")=="clearbench_s1_nonpotable_001"
            and source.get("intended_use")=="non_potable_particle_challenge_only",
            "wrong product concept or functional purpose")
    require(source.get("source_integrity",{}).get("housing_part")=="158007"
            and source["source_integrity"].get("filter_part")=="155014-43"
            and source["source_integrity"].get("assembly_bracket_candidate")=="244047"
            and source["source_integrity"].get("illustrative_wrench_clearance_mm")==150
            and source["source_integrity"].get("manufacturer_pdf_bytes_archived") is False
            and source["source_integrity"].get("sku_compatible_fittings_selected") is False,
            "product source does not match manufacturer-bound assembly evidence")
    require(source.get("functional_target")=={
        "flow_l_min":0.5,"particle_turbidity_reduction_percent":70,
        "demonstrated":False,"validated":False},
        "function targets changed or performance untruthfully asserted")
    dims=source.get("platform_envelope_mm",{})
    require(dims=={"width":450,"depth":260,"height":740},
            "external demonstrator design envelope unexpected")
    lay=source.get("layout",{})
    tray=lay.get("tray",{})
    board=lay.get("back_panel",{})
    fh=lay.get("filter_housing",{})
    svc=lay.get("service_region",{})
    require(tray=={"width_mm":450,"depth_mm":260,"height_mm":14,
                  "origin_mm":[-225,-130,0],"type":"non_pressure_containing_concept"},
            "drip tray no longer fits reviewed product layout")
    require(board=={"width_mm":450,"thickness_mm":12,"height_mm":716,
                    "origin_mm":[-225,100,14],"type":"non_pressure_containing_concept"},
            "display panel geometry changed")
    require(fh=={"center_x_mm":-65,"center_y_mm":0,"bottom_z_mm":228,
                 "diameter_mm":118,"height_mm":308,"component_ref":"158007",
                 "geometry":"external_envelope_not_vendor_cad"},
            "vendor housing extent or location has drifted")
    require(svc=={"center_x_mm":-65,"center_y_mm":0,"bottom_z_mm":78,
                  "height_mm":150,"diameter_mm":118,"qualified":False},
            "service corridor promoted or no longer below housing")
    require(fh["bottom_z_mm"]==svc["bottom_z_mm"]+svc["height_mm"] and
            fh["bottom_z_mm"]+fh["height_mm"]<dims["height"]-100 and
            svc["bottom_z_mm"]>=tray["height_mm"]+50,
            "product assembly or maintenance footprint clips the base")
    indicators=lay.get("pressure_indicators",[])
    require(len(indicators)==2 and {i["id"] for i in indicators}=={"P_IN","P_OUT"}
            and all(i.get("component_status")=="symbolic_instrument_not_selected" and
                    i.get("diameter_mm")==54 for i in indicators),
            "instrumentation falsely completed or omitted")
    require({i["function"] for i in indicators}=={
              "inlet_pressure_only","outlet_pressure_only"},
            "pressure instrumentation cannot claim filtration performance")
    for indicator in indicators:
        x,y,z=indicator["center_mm"]
        require(abs(x)+indicator["diameter_mm"]/2<dims["width"]/2 and
                0<z<dims["height"] and -130<y<110,
                "pressure monitor outside product envelope")
    sample=lay.get("sample_cup",{})
    require(sample.get("component_status")=="conceptual_lab_sample_container" and
            sample.get("center_x_mm")==145 and sample.get("center_y_mm")==-35 and
            sample.get("bottom_z_mm")==32 and sample.get("height_mm")==75 and
            sample.get("diameter_mm")==66,
            "sample output station missing or moved")
    flow=lay.get("flow_paths",{})
    require(flow.get("path_location_source")==
            "diagrammatic_only_not_actual_housing_port_centers_or_rated_3_8in_NPT_fittings"
            and flow.get("pipe_diameter_visual_mm")==9
            and len(flow.get("upstream",[]))>=3 and
            len(flow.get("downstream",[]))>=3,
            "unqualified hose centerline assumed mechanically accurate")
    require(lay.get("mounting",{}).get("boss_pitch_mm") is None
            and lay["mounting"].get("load_rating_newton") is None
            and lay["mounting"].get("attachment_load_path_validated") is False,
            "mounting was falsely marked engineered")
    topology=check_flow_graph(source["functional_flow_graph"])
    bom=source.get("product_bom",[])
    require(len(bom)==11 and len({row.get("ref") for row in bom})==11
            and {row["ref"] for row in bom}==
            {"H1","F1","B1","W1","S1","P1","P2","A1","V1","C1","M1"},
            "complete demonstrator functional bill of materials missing")
    require(all(row.get("engineering_status") in {"CANDIDATE","UNQUALIFIED"}
                and row.get("quantity")==1 for row in bom),
            "product BOM silently qualified for procurement")
    require({row["part_number"] for row in bom if row["part_number"] is not None}==
            {"158007","155014-43","244047","150539","151121"},
            "manufacturer product variants changed")
    require(all(row.get("part_number") is None and row.get("manufacturer") is None
                for row in bom if row["engineering_status"]=="UNQUALIFIED"
                and row["ref"] in {"P1","P2","A1","V1","C1","M1"}),
            "unsourced fittings/instruments fabricated")
    work=source.get("operator_workflow",[])
    require([row["stage"] for row in work]==
            ["SETUP","CONNECT","MONITOR","SAMPLE","MAINTAIN"] and
            all(row.get("state")=="NOT_VERIFIED" for row in work),
            "operator workflow or physical validation missing")
    tests=source.get("product_acceptance",[])
    require({row["id"] for row in tests}==
            {"PA_VISUAL","PA_FLOW_GRAPH","PA_MECHANICAL","PA_HYDRAULIC",
             "PA_TREATMENT","PA_LEAK"} and
            all(row.get("status")=="BLOCKED" for row in tests
                if row["kind"]=="physical"),
            "physical acceptance criteria falsely completed")
    require(source.get("commercial_readiness")==
            "UNQUALIFIED_DIGITAL_PRODUCT_SAMPLE_ONLY" and
            source.get("physical_authority")=={
                "purchase":False,"assembly":False,"wet_operation":False,
                "pressure_activation":False,"manufacturing":False,
                "human_consumption":False},
            "nonexistent physical product authority")
    return topology


def scad(source:dict)->str:
    l=source["layout"]
    housing=l["filter_housing"];service=l["service_region"]
    indicators=l["pressure_indicators"];cup=l["sample_cup"];flow=l["flow_paths"]
    def coords(item:list)->str:return "["+",".join(str(x) for x in item)+"]"
    def tube_path(pts:list)->str:
        return "\n".join("  translate("+coords(p)+") sphere(d=pipe_d);" for p in pts)
    # All dimensions are taken from the product specification. No guessed NPT
    # threads, pressure-rated fittings, true bracket pattern or seal geometry.
    lines=[
        "// CLEARBENCH S1: CONCEPTUAL PRODUCT ASSEMBLY -- NOT FABRICABLE OR WATER SAFE",
        "// Genuine Pentair housing is represented by its OUTSIDE ENVELOPE only.",
        "// Symbolic hoses, instruments, bracket zone and flow: not measured/qualified.",
        "$fn=90;",
        "part=\"assembly\";",
        f"tray_w={l['tray']['width_mm']};tray_d={l['tray']['depth_mm']};tray_h={l['tray']['height_mm']};",
        f"board_h={l['back_panel']['height_mm']};board_t={l['back_panel']['thickness_mm']};",
        f"housing_x={housing['center_x_mm']};housing_y={housing['center_y_mm']};housing_z={housing['bottom_z_mm']};housing_d={housing['diameter_mm']};housing_h={housing['height_mm']};",
        f"service_z={service['bottom_z_mm']};service_h={service['height_mm']};",
        f"cup_x={cup['center_x_mm']};cup_y={cup['center_y_mm']};cup_z={cup['bottom_z_mm']};",
        f"pipe_d={flow['pipe_diameter_visual_mm']};",
        "module product_tray(){ translate([-tray_w/2,-tray_d/2,0]) cube([tray_w,tray_d,tray_h]); }",
        "module back_panel(){ translate([-tray_w/2,100,tray_h]) cube([tray_w,board_t,board_h]); }",
        "module housing_outline(){ translate([housing_x,housing_y,housing_z]) cylinder(d=housing_d,h=housing_h); }",
        "module service_volume(){ translate([housing_x,housing_y,service_z]) cylinder(d=housing_d,h=service_h); }",
        "module cap_visual(){ translate([housing_x,housing_y,housing_z+housing_h-36]) cylinder(d=housing_d,h=36); }",
        "module sampling_cup(){ translate([cup_x,cup_y,cup_z]) difference(){ cylinder(d=66,h=75); translate([0,0,3]) cylinder(d=59,h=75); } }",
        "module dial(pos){ translate(pos) rotate([90,0,0]) cylinder(d=54,h=9,center=true); }",
        "module path_between(a,b){ hull(){ translate(a) sphere(d=pipe_d); translate(b) sphere(d=pipe_d);} }",
        "module flow_lines(){",
    ]
    for group in ("upstream","downstream"):
        for a,b in zip(flow[group],flow[group][1:]):
            lines.append("  path_between("+coords(a)+","+coords(b)+");")
    lines += [
        "}",
        "module housing_cap_glyph(){",
        "  translate([housing_x,housing_y,housing_z+housing_h-28])",
        "    cylinder(d=housing_d+2,h=28);",
        "}",
        "module product_scene(){",
        "  color([0.10,0.18,0.22]) product_tray();",
        "  color([0.19,0.27,0.31]) back_panel();",
        "  color([0.32,0.79,0.96,0.65]) housing_outline();",
        "  color([0.04,0.26,0.71]) cap_visual();",
        "  color([1,0.64,0.20,0.20]) service_volume();",
        "  color([0.84,0.90,0.95]) sampling_cup();",
    ]
    for i in indicators:
        lines.append("  color([0.89,0.94,0.96]) dial("+coords(i["center_mm"])+");")
    lines += [
       "  color([0.08,0.81,0.83]) flow_lines();",
       '  color([0.98,0.74,0.22]) translate([-190,78,652]) linear_extrude(1.3) text("CLEARBENCH S1",size=22,font="Liberation Sans:style=Bold");',
       '  color([0.98,0.68,0.25]) translate([-188,78,610]) linear_extrude(1.2) text("NON-POTABLE",size=18);',
       '  color([0.93,0.94,0.96]) translate([-188,78,579]) linear_extrude(1.2) text("LAB DEMO ONLY",size=12);',
       "}",
       'if(part=="assembly") product_scene();',
       'else if(part=="tray") product_tray();',
       'else if(part=="panel") back_panel();',
       'else if(part=="housing") housing_outline();',
       'else if(part=="service") service_volume();',
       'else if(part=="sample") sampling_cup();',
       'else assert(false,"unknown concept-only product assembly component");'
    ]
    return "\n".join(lines)+"\n"


def build(assembly_root:Path,product_file:Path,out:Path)->dict:
    upstream,assembly,requests=validate_upstream(assembly_root)
    source=json.loads(Path(product_file).read_text())
    topology=validate_product(source,assembly)
    sourcehash=sha(canonical(source))
    product={
      "schema_version":REPORT_SCHEMA,
      "product_id":source["product_id"],
      "product_name":source["product_name"],
      "source_spec_sha256":upstream["source_spec_sha256"],
      "upstream_assembly_source_sha256":upstream["assembly_source_sha256"],
      "product_spec_sha256":sourcehash,
      "functional_product_package_created":True,
      "functional_flow_graph":topology,
      "product_level_roles":[row["role"] for row in source["product_bom"]],
      "native_cad_render_planned":True,
      "native_cad_render_executed":False,
      "operator_steps":[row["stage"] for row in source["operator_workflow"]],
      "complete_visual_system_components_count":11,
      "vendor_qualified_subassemblies_count":0,
      "qualifying_physical_tests_passed":0,
      "assembly_fit_verified":False,
      "complete_pressurized_fluid_path_verified":False,
      "actual_treatment_performance_verified":False,
      "release_tier":"DIGITAL_PRODUCT_DEMONSTRATOR_ONLY",
      "commercial_product_ready":False,
      "physical_authority":source["physical_authority"],
      "blocking_evidence_requests":[r["request_id"] for r in requests["evidence_requests"]],
    }
    contents={
      "PRODUCT_SPEC.json":canonical(source),
      "PRODUCT_ARCHITECTURE.json":canonical(product),
      "PRODUCT_BOM.json":canonical({"product_id":source["product_id"],
                                  "items":source["product_bom"],
                                  "complete_product_roles_defined":True,
                                  "vendor_fully_qualified_bom":False,
                                  "purchase_authorized":False}),
      "PRODUCT_OPERATOR_WORKFLOW.json":canonical({
          "product_id":source["product_id"],"steps":source["operator_workflow"],
          "physical_operation_tested":False}),
      "PRODUCT_SCENE.scad":scad(source).encode(),
      "UPSTREAM_ASSEMBLY_RECEIPT.json":
          (Path(assembly_root)/"ASSEMBLY_RECEIPT.json").read_bytes(),
    }
    out=Path(out)
    require(not out.exists() or (out.is_dir() and not any(out.iterdir())),
            "do not overwrite product revision")
    out.mkdir(parents=True,exist_ok=True)
    for name,body in contents.items():
        (out/name).write_bytes(body)
    receipt={
        "schema_version":"hardware_splicer.product_demonstrator_receipt.v1",
        "source_spec_sha256":product["source_spec_sha256"],
        "product_spec_sha256":sourcehash,
        "files":{name:{"sha256":sha(body),"bytes":len(body)}
                 for name,body in sorted(contents.items())},
        "physical_release":False,
    }
    (out/"PRODUCT_RECEIPT.json").write_bytes(canonical(receipt))
    return receipt
