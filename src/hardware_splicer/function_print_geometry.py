"""Function-driven printable CAD candidate generation with bounded claims.

Actual CadQuery BRep authoring, STEP roundtrip, watertight STL and
nominal board-interface collision checks; the ranking is explicitly
conditional on hypothetical board mass, lateral load and effective
filament density. No independent slicer, FEA, ESD or physical fit proof.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
from pathlib import Path
from typing import Any, Mapping

from .function_intent_bridge import parse_intent

SCHEMA = "hs.functional_print_design.v1"
RESULT = "hs.function_to_printable_cad_trial.v1"


def canonical(data: Any) -> bytes:
    return (json.dumps(data, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _positive(x: Any, name: str, minimum: float, maximum: float) -> float:
    if isinstance(x, bool) or not isinstance(x, (int,float)) or not math.isfinite(x) or not minimum <= x <= maximum:
        raise ValueError(f"invalid {name}: expected finite value in [{minimum}, {maximum}]")
    return float(x)


def validate_design(req: Mapping[str, Any]) -> dict[str, Any]:
    if req.get("schema") != SCHEMA or req.get("model") != "unpowered_pcb_vertical_service_stand":
        raise ValueError("unsupported functional geometry design")
    board,fit,printer,stability,safety = [req[x] for x in ("board","fit","printer","stability","safety")]
    _positive(board["nominal_width_mm"], "board width", 40, 150)
    _positive(board["nominal_height_mm"], "board height", 25, 150)
    _positive(board["nominal_thickness_mm"], "board thickness", .8, 4)
    _positive(board["nominal_mass_g"], "board assumed mass", 5, 150)
    _positive(fit["per_side_clearance_mm"],"per-side slot clearance",.1,.8)
    _positive(fit["minimum_wall_mm"],"minimum wall",2,6)
    _positive(fit["minimum_support_spacing_fraction"],"support separation",.3,.8)
    if not (isinstance(printer["bed_mm"],list) and len(printer["bed_mm"]) == 3):
        raise ValueError("printer bed envelope must be 3D")
    for value in printer["bed_mm"]:
        _positive(value,"printer travel",50,1000)
    _positive(printer["nozzle_mm"],"nozzle diameter",.2,1.2)
    _positive(printer["material_nominal_density_g_cm3"],"nominal solid density",.8,2)
    _positive(printer["effective_density_fraction_assumption"],"assumed effective printed density",.2,1)
    _positive(stability["hypothetical_lateral_force_n"],"assumed static push",.01,1)
    _positive(stability["min_modelled_factor"],"minimum static tip proxy",1,5)
    for k in ("dimensions_physically_measured",):
        if board.get(k) is not False:
            raise ValueError("board dimension measurement is unverified")
    for k in ("nonpowered_fixture_only",):
        if safety.get(k) is not True:
            raise ValueError("pilot cannot be used for powered fixture")
    for k in ("ESD_certified","FEA_completed","physical_fit_verified","print_approved"):
        if safety.get(k) is not False:
            raise ValueError(f"unverified physical authority: {k}")
    if printer.get("profile_verified") is not False or stability.get("board_mass_measured") is not False:
        raise ValueError("no calibrated printer or board mass data supplied")
    alts = req.get("alternatives")
    if not isinstance(alts,list) or not 2 <= len(alts) <= 16:
        raise ValueError("need 2 to 16 competing geometries")
    names = set()
    for alt in alts:
        name=alt.get("id")
        if not isinstance(name,str) or not re.fullmatch(r"[a-z][a-z0-9_]{2,36}",name) or name in names:
            raise ValueError("duplicate or invalid candidate identifier")
        names.add(name)
        if alt.get("style") not in ("plate","open_rail"):
            raise ValueError("unregistered fabrication topology")
        _positive(alt.get("depth_mm"),"foot depth",30,150)
        _positive(alt.get("foot_width_mm"),"foot width",12,40)
        _positive(alt.get("beam_width_mm"),"beam width",4,150)
        if alt["style"]=="plate" and alt["beam_width_mm"] != alt["depth_mm"]:
            raise ValueError("solid base plate must fill declared depth")
        if alt["style"]=="open_rail" and alt["beam_width_mm"]>=alt["depth_mm"]:
            raise ValueError("open support rail cannot be a full base plate")
    return dict(req)


def function_intent(req: Mapping[str, Any]) -> dict[str, Any]:
    """Adapt the physical brief to the existing HS MachineProject contract."""
    def r(ident, kind, statement, acceptance, procedure):
        return {
            "id":ident,"kind":kind,"statement":statement,"priority":"must",
            "verification":{"method_type":"test","procedure":procedure,
                            "acceptance":acceptance,"evidence_status":"not_collected"}
        }
    requirements=[
        r("R_SLOT","interface","Nominal PCB edge captured by top-open slot with specified clearance.",
          {"per_side_clearance_mm":req["fit"]["per_side_clearance_mm"]},
          "Measure actual PCB and printed slot, insert/withdraw, inspect edge contact and wobble."),
        r("R_ACCESS","functional","Two separated supports allow viewing both board faces.",
          {"support_count":2},"Photograph board access from each face with a nonpowered dummy PCB."),
        r("R_TIP","performance","Static tip-proxy margin under declared lateral push.",
          {"minimum_factor":req["stability"]["min_modelled_factor"]},
          "Measure real printed part and PCB mass, then record controlled lateral dummy-board loading."),
        r("R_PRINT","constraint","Geometry within FDM bed and minimum thin-wall limit.",
          {"bed_mm":req["printer"]["bed_mm"],"minimum_wall_mm":req["fit"]["minimum_wall_mm"]},
          "Independently slice, print and measure slot, outer dimensions, and wall quality."),
        r("R_MATERIAL","performance","Choose lowest CAD-solid volume among feasible modelled alternatives.",
          {"objective":"minimum solid volume with all declared numeric gates"},
          "Cross-import STEP/STL to compare geometry mass proxies; validate real sliced material later."),
    ]
    return {
        "schema_version":"hardware_splicer.function_intent.v1",
        "project_id":req["project_id"],"name":"PCB Service Stand — function first",
        "purpose":"Create a parametric unpowered inspection stand, not a physically qualified repair fixture",
        "intended_use":"general_device","claims":[],
        "inputs":[{"id":"unpowered_pcb","medium":"solid board"}],
        "outputs":[{"id":"supported_pcb","medium":"mechanical support"}],
        "requirements":requirements,
        "functions":[
            {"id":"F_CAPTURE","name":"Capture nominal board edge",
             "requirements":["R_SLOT","R_ACCESS"],"subsystems":["S_STAND","S_BOARD"]},
            {"id":"F_STABLE","name":"Resist lateral tip",
             "requirements":["R_TIP"],"subsystems":["S_STAND"]},
            {"id":"F_MAKE","name":"Fabricate material-efficient stand",
             "requirements":["R_PRINT","R_MATERIAL"],"subsystems":["S_STAND"]},
        ],
        "subsystems":[
            {"id":"S_STAND","name":"Print stand","domain":"mechanical",
             "purpose":"Support unpowered board at two edge slots",
             "requirements":[r["id"] for r in requirements]},
            {"id":"S_BOARD","name":"Unmeasured target board","domain":"mechanical",
             "purpose":"Provide declared nominal envelope without physical measurement","requirements":[]},
        ],
        "interfaces":[
            {"id":"I_SLOT","name":"Edge capture","from":"S_BOARD","to":"S_STAND",
             "medium":"mechanical","requirements":["R_SLOT"],
             "unresolved":["board actual thickness and corner geometry",
                           "FDM shrinkage and repeatability",
                           "ESD-safety qualification",
                           "printed fixture physical fit and durability"]},
        ],
    }


def build_cad(req: Mapping[str, Any], alt: Mapping[str, Any]) -> Any:
    """Author one real additive solid, not just a metadata shape."""
    import cadquery as cq
    w = req["board"]["nominal_width_mm"]
    gap = req["board"]["nominal_thickness_mm"]+2*req["fit"]["per_side_clearance_mm"]
    span=w+24.
    depth=alt["depth_mm"]
    foot=alt["foot_width_mm"]
    base_thickness=4.
    upright_depth=12.
    height=26.
    slot_bottom=14.
    # The floor beam and footpads form a single printable footprint.
    width_y=depth if alt["style"]=="plate" else alt["beam_width_mm"]
    shape=cq.Workplane("XY").box(span,width_y,base_thickness,centered=(True,True,False))
    for xc in (-(w/2-10),w/2-10):
        shape=shape.union(
            cq.Workplane("XY").box(foot,depth,base_thickness,centered=(True,True,False)).translate((xc,0,0))
        )
        shape=shape.union(
            cq.Workplane("XY").box(foot,upright_depth,height,centered=(True,True,False)).translate((xc,0,4))
        )
        # Open vertical PCB groove, no ceiling / unsupported internal bridge.
        shape=shape.cut(
            cq.Workplane("XY").box(foot+2,gap,24,centered=(True,True,False)).translate((xc,0,slot_bottom))
        )
    return shape.combine().clean()


def evaluate_cad(req: Mapping[str,Any], alt:Mapping[str,Any],shape:Any,out:Path)->dict[str,Any]:
    import cadquery as cq
    import trimesh
    if not shape.val().isValid() or len(shape.solids().vals())!=1:
        raise ValueError("CAD failed solid validity or single-body requirement")
    name=alt["id"]
    out.mkdir(parents=True,exist_ok=False)
    step=out/(name+".step")
    stl=out/(name+".stl")
    shape.val().exportStep(str(step))
    shape.val().exportStl(str(stl),tolerance=.02,angularTolerance=.2)
    roundtrip=cq.importers.importStep(str(step))
    mesh=trimesh.load(str(stl),force="mesh")
    rawvol=float(shape.val().Volume())
    stepvol=float(roundtrip.val().Volume())
    meshvol=float(mesh.volume)
    dims=[float(shape.val().BoundingBox().xlen),
          float(shape.val().BoundingBox().ylen),
          float(shape.val().BoundingBox().zlen)]
    v_err_percent=100*abs(rawvol-stepvol)/rawvol
    mesh_err_percent=100*abs(rawvol-meshvol)/rawvol
    board=req["board"]
    gap=board["nominal_thickness_mm"]+2*req["fit"]["per_side_clearance_mm"]
    wall=(12-gap)/2
    bed=req["printer"]["bed_mm"]
    footprint_stable=alt["depth_mm"]>=30
    supports=2*(board["nominal_width_mm"]/2-10)
    support_fraction=supports/board["nominal_width_mm"]
    # Nominal board and slot are both declared geometry. BREP tests can
    # disprove a collision, but cannot prove physical insertion success.
    surrogate=(cq.Workplane("XY").box(
        board["nominal_width_mm"],board["nominal_thickness_mm"],board["nominal_height_mm"],
        centered=(True,True,False)
    ).translate((0,0,14)))
    interference=float(shape.intersect(surrogate).val().Volume()) if shape.intersect(surrogate).solids().vals() else 0.
    effective_density=(req["printer"]["material_nominal_density_g_cm3"]
                       *req["printer"]["effective_density_fraction_assumption"])
    part_mass_proxy=rawvol/1000*effective_density
    total_mass_proxy=(part_mass_proxy+board["nominal_mass_g"])/1000
    nominal_tip_Nm=total_mass_proxy*9.81*(alt["depth_mm"]/2)/1000
    assumed_push_Nm=req["stability"]["hypothetical_lateral_force_n"]*(
        14+board["nominal_height_mm"]
    )/1000
    nominal_factor=nominal_tip_Nm/assumed_push_Nm
    checks={
        "brep_single_valid_solid":len(shape.solids().vals())==1 and shape.val().isValid(),
        "step_volume_roundtrip_0_5pct":v_err_percent<.5,
        "stl_watertight":bool(mesh.is_watertight) and meshvol>0,
        "stl_volume_0_5pct":mesh_err_percent<.5,
        "nominal_board_noninterference":interference<.001,
        "slot_has_positive_declared_clearance":gap>board["nominal_thickness_mm"],
        "upright_wall_minimum":wall>=req["fit"]["minimum_wall_mm"],
        "min_support_spacing":support_fraction>=req["fit"]["minimum_support_spacing_fraction"],
        "fits_declared_build_volume":all(d<=b for d,b in zip(dims,bed)),
        "static_tip_proxy_under_assumptions":nominal_factor>=req["stability"]["min_modelled_factor"],
        "open_top_unroofed_slot":True,
    }
    return {
        "id":name,"style":alt["style"],"geometry_spec":dict(alt),
        "geometry":{"bounds_mm":[round(x,3) for x in dims],
                    "volume_mm3":round(rawvol,3),
                    "step_volume_mm3":round(stepvol,3),
                    "stl_volume_mm3":round(meshvol,3),
                    "mesh_triangles":int(len(mesh.faces)),"stl_watertight":bool(mesh.is_watertight),
                    "slot_opening_mm":gap,"slot_bottom_z_mm":14,
                    "minimum_upright_wall_mm":wall,
                    "board_nominal_interference_mm3":round(interference,6)},
        "modelled_stability":{"assumed_board_mass_g":board["nominal_mass_g"],
                              "assumed_effective_print_density_g_cm3":effective_density,
                              "estimated_part_mass_g":round(part_mass_proxy,3),
                              "hypothetical_force_n":req["stability"]["hypothetical_lateral_force_n"],
                              "modelled_tip_factor":round(nominal_factor,3),
                              "physical_test_completed":False},
        "checks":checks,"numeric_feasible":all(checks.values()),
        "source_sha256":{"step":file_sha(step),"stl":file_sha(stl)},
        "CAD_authority":"native_CadQuery_BREP_only",
        "actual_slicer_used":False,"actual_print_completed":False,
        "ESD_material_qualified":False,
    }


def run_design(req: Mapping[str,Any],out:Path)->dict[str,Any]:
    validated=validate_design(req)
    if out.exists():
        raise ValueError("refusing to overwrite previously generated candidate CAD")
    intent=function_intent(validated)
    project,gate=parse_intent(intent)
    if gate["status"]!="FUNCTIONAL_CONCEPT_ONLY" or gate["functional_traceability_pass"] is not True:
        raise ValueError("native HS MachineProject rejected function traceability")
    if gate["physical_authority"]["fabrication"] is not False:
        raise ValueError("cannot promote this to fabrication approval")
    out.mkdir(parents=True)
    (out/"function_intent.json").write_bytes(canonical(intent))
    rows=[]
    for alt in validated["alternatives"]:
        candidate=build_cad(validated,alt)
        rows.append(evaluate_cad(validated,alt,candidate,out/"candidates"/alt["id"]))
    feasible=[x for x in rows if x["numeric_feasible"]]
    selection=min(feasible,key=lambda r:(r["geometry"]["volume_mm3"],r["id"])) if feasible else None
    if selection:
        selected_dir=out/"candidates"/selection["id"]
        for suffix in (".step",".stl"):
            shutil.copyfile(selected_dir/(selection["id"]+suffix),out/("selected_holder"+suffix))
    baseline=next((x for x in rows if x["id"]=="solid_plate"),None)
    report={
        "schema":RESULT,"project_id":validated["project_id"],
        "source_design_sha256":hashlib.sha256(canonical(validated)).hexdigest(),
        "function_intent_sha256":file_sha(out/"function_intent.json"),
        "existing_HS_machine_project_traceability":gate,
        "actual_native_geometry_written":True,"authoring_tool":"CadQuery 2.6.1",
        "alternatives":rows,
        "ranked_feasible":[r["id"] for r in sorted(feasible,key=lambda r:(r["geometry"]["volume_mm3"],r["id"]))],
        "selected":selection["id"] if selection else None,
        "selection_reason":"lowest BRep solid volume among geometries satisfying declared fit/volume/stability proxy assumptions",
        "baseline_plate_volume_mm3":baseline["geometry"]["volume_mm3"] if baseline else None,
        "vs_plate_solid_volume_reduction_pct": (
            round(100*(1-selection["geometry"]["volume_mm3"]/baseline["geometry"]["volume_mm3"]),1)
            if baseline and selection else None
        ),
        "authority":{"physical_board_measured":False,"slicer_profile_verified":False,
                     "actual_print_completed":False,"physical_fit_test_completed":False,
                     "static_or_fatigue_FEA_completed":False,
                     "ESD_safety_verified":False,"fabrication_release_authorized":False},
        "known_uncertainties":[
            "Nominal PCB mass/width/height/thickness are defined test assumptions, not source measurements.",
            "Static tipping calculation is a simple quasistatic model, not a real push/load or stability test.",
            "CAD solid volume is not slicer-estimated filament usage; effective density is explicitly assumed.",
            "No slicer G-code, layer preview or FDM profile validation performed.",
            "Ordinary PLA is NOT verified ESD-safe for sensitive electronics.",
            "No tolerance print coupon, deformation/impact/retention test or actual fabricated part.",
            "Slots are gravity-supported: no positive fastener or locking retention.",
        ],
    }
    (out/"FUNCTION_GEOMETRY_EVALUATION.json").write_bytes(canonical(report))
    return report


def audit_bundle(req: Mapping[str,Any],out:Path)->dict[str,Any]:
    """Independent native STEP/STL re-import and original design-source audit."""
    import cadquery as cq
    import trimesh
    source=validate_design(req)
    report=json.loads((out/"FUNCTION_GEOMETRY_EVALUATION.json").read_text())
    if report.get("schema")!=RESULT or report["source_design_sha256"]!=hashlib.sha256(canonical(source)).hexdigest():
        raise ValueError("design source and output experiment do not match")
    if report["function_intent_sha256"]!=file_sha(out/"function_intent.json"):
        raise ValueError("existing HS functional intent artifact changed")
    if json.loads((out/"function_intent.json").read_text())!=function_intent(source):
        raise ValueError("functional requirement graph changed after CAD generation")
    if [x["id"] for x in report["alternatives"]]!=[x["id"] for x in source["alternatives"]]:
        raise ValueError("CAD candidate set or order changed")
    validated=[]
    for row,alt in zip(report["alternatives"],source["alternatives"]):
        cad=out/"candidates"/row["id"]
        step=cad/(row["id"]+".step")
        stl=cad/(row["id"]+".stl")
        if file_sha(step)!=row["source_sha256"]["step"] or file_sha(stl)!=row["source_sha256"]["stl"]:
            raise ValueError("exported native CAD geometry changed after run")
        original=cq.importers.importStep(str(step))
        if len(original.solids().vals())!=1 or not original.val().isValid():
            raise ValueError("reimported STEP topology is invalid")
        mesh=trimesh.load(str(stl),force="mesh")
        if not mesh.is_watertight or mesh.volume<=0:
            raise ValueError("STL mesh is not watertight")
        if not math.isclose(original.val().Volume(),row["geometry"]["volume_mm3"],abs_tol=.05):
            raise ValueError("STEP volume does not match reported CAD outcome")
        if not math.isclose(float(mesh.volume),row["geometry"]["volume_mm3"],rel_tol=.005):
            raise ValueError("STL mesh volume does not match reported CAD outcome")
        # Independently reconstruct the complete intended solid from the
        # versioned source spec, rather than trusting declared JSON scores.
        expected=build_cad(source,alt)
        if not math.isclose(expected.val().Volume(),original.val().Volume(),abs_tol=.05):
            raise ValueError("native STEP shape differs from requested source design")
        bounds=original.val().BoundingBox()
        dims=[round(bounds.xlen,3),round(bounds.ylen,3),round(bounds.zlen,3)]
        if dims!=row["geometry"]["bounds_mm"]:
            raise ValueError("reported CAD envelope does not match source solid")
        board=source["board"]
        gap=board["nominal_thickness_mm"]+2*source["fit"]["per_side_clearance_mm"]
        wall=(12-gap)/2
        surrogate=cq.Workplane("XY").box(
            board["nominal_width_mm"],board["nominal_thickness_mm"],
            board["nominal_height_mm"],centered=(True,True,False)
        ).translate((0,0,14))
        intrusion=original.intersect(surrogate)
        interference=(intrusion.val().Volume() if intrusion.solids().vals() else 0.)
        effective_density=(source["printer"]["material_nominal_density_g_cm3"]
                           *source["printer"]["effective_density_fraction_assumption"])
        mass=original.val().Volume()/1000*effective_density
        moment=(mass+board["nominal_mass_g"])/1000*9.81*(alt["depth_mm"]/2)/1000
        push=source["stability"]["hypothetical_lateral_force_n"]*(14+board["nominal_height_mm"])/1000
        factor=moment/push
        if (row["geometry"]["slot_opening_mm"]!=gap
                or row["geometry"]["minimum_upright_wall_mm"]!=wall
                or row["modelled_stability"]["modelled_tip_factor"]!=round(factor,3)
                or row["modelled_stability"]["estimated_part_mass_g"]!=round(mass,3)):
            raise ValueError("reported slot/weight/tipping result differs from source-derived calculation")
        expected_checks={
            "brep_single_valid_solid":True,
            "step_volume_roundtrip_0_5pct":True,
            "stl_watertight":True,
            "stl_volume_0_5pct":abs(mesh.volume-original.val().Volume())/original.val().Volume()<.005,
            "nominal_board_noninterference":interference<.001,
            "slot_has_positive_declared_clearance":gap>board["nominal_thickness_mm"],
            "upright_wall_minimum":wall>=source["fit"]["minimum_wall_mm"],
            "min_support_spacing":(board["nominal_width_mm"]-20)/board["nominal_width_mm"]>=source["fit"]["minimum_support_spacing_fraction"],
            "fits_declared_build_volume":all(d<=b for d,b in zip(dims,source["printer"]["bed_mm"])),
            "static_tip_proxy_under_assumptions":factor>=source["stability"]["min_modelled_factor"],
            "open_top_unroofed_slot":True,
        }
        if expected_checks!=row["checks"] or row["numeric_feasible"]!=all(expected_checks.values()):
            raise ValueError("native candidate gate or print feasibility classification was altered")
        validated.append(row["id"])
    feasible=[x for x in report["alternatives"] if x["numeric_feasible"]]
    should=min(feasible,key=lambda x:(x["geometry"]["volume_mm3"],x["id"])) if feasible else None
    if report["selected"]!=(should["id"] if should else None):
        raise ValueError("selected candidate is not the lowest-volume feasible shape")
    if should:
        for suffix in (".step",".stl"):
            cand=out/"candidates"/should["id"]/(should["id"]+suffix)
            if file_sha(out/("selected_holder"+suffix))!=file_sha(cand):
                raise ValueError("selected exported part not identical to ranked candidate")
    if any(report["authority"].values()):
        raise ValueError("model trial falsely claims physical or fabrication authorization")
    return {
        "schema":"hs.function_to_printable_cad_native_audit.v1",
        "source_design_sha256":report["source_design_sha256"],
        "native_shape_count":len(validated),
        "verified_candidates":validated,
        "selected":report["selected"],
        "nonfabrication_authority_preserved":True,
        "source_concept_traceability_verified":True,
        "real_CAD_and_STL_roundtrip_verified":True,
    }
