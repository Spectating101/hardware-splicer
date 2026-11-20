"""KiCad native polygon -> source-derived *unpowered* inspection CAD.

Real BRep STEP solids, including internal Edge.Cuts cutouts. Native board
outline is a tessellated approximation of original arcs; not an exact arc CAD
reconstruction. No populated-board height / connector / material fitting.
"""
from __future__ import annotations
import argparse, csv, hashlib, json
from pathlib import Path
import cadquery as cq

DOCK=(188.,168.,4.)
CARTRIDGE=(180.,160.,6.)
KEYS=((-83.,-73.),(83.,73.))
GAP=.45
POCKET_FLOOR_Z=3.85
BOARD_THICKNESS_ASSUMED=1.6

def sha(p:Path):return hashlib.sha256(p.read_bytes()).hexdigest()
def outer_wire(layout):
    return cq.Workplane("XY").polyline([tuple(p) for p in layout["outer_xy"]]).close()

def board_solid(layout):
    solid=outer_wire(layout).extrude(BOARD_THICKNESS_ASSUMED)
    for ring in layout["cutout_xy"]:
        hole=cq.Workplane("XY").polyline([tuple(p) for p in ring]).close().extrude(BOARD_THICKNESS_ASSUMED)
        solid=solid.cut(hole)
    for mount in layout["source_mounts"]:
        hole=(cq.Workplane("XY").center(mount["x"],mount["y"])
              .circle(mount["drill_mm"]/2).extrude(BOARD_THICKNESS_ASSUMED))
        solid=solid.cut(hole)
    return solid

def build(layout, source:Path, out:Path):
    if layout.get("schema")!="hs.source_edgecuts_polygon.v1":
        raise ValueError("UNKNOWN_NATIVE_CONTOUR_SCHEMA")
    if sha(source)!=layout["pcb_sha256"]:
        raise ValueError("STALE_PCB_SOURCE_REVISION")
    w,h=layout["bbox_source_mm"][2:]
    if not(w<=150 and h<=130 and len(layout["outer_xy"])>=3):
        raise ValueError("OUTLINE_NOT_IN_SUPPORTED_ENVELOPE")
    if layout["mounting_strategy"] not in ("source-hole-registration","non-clamping-edge-nest"):
        raise ValueError("INVALID_MOUNTING_STRATEGY")
    if layout["mounting_strategy"]=="source-hole-registration" and len(layout["source_mounts"])<3:
        raise ValueError("UNSUPPORTED_MOUNT_HOLE_SOURCE")
    out.mkdir(parents=True,exist_ok=False)
    # Real board geometry, not its rectangular bounding box.
    board=board_solid(layout)
    # Common dock identical across source projects, with asymmetric key location.
    dock=cq.Workplane("XY").rect(DOCK[0],DOCK[1]).extrude(DOCK[2])
    for x,y in KEYS:
        dock=dock.union(cq.Workplane("XY").workplane(offset=DOCK[2])
                        .center(x,y).circle(1.7).extrude(2.))
    carrier=cq.Workplane("XY").rect(CARTRIDGE[0],CARTRIDGE[1]).extrude(CARTRIDGE[2])
    for x,y in KEYS:
        carrier=carrier.cut(cq.Workplane("XY").center(x,y).circle(1.9).extrude(CARTRIDGE[2]))
    # The pocket is cut from the *actual* outer contour (rounded, slotted,
    # concave or irregular) and not from bbox, with an unverified .45mm gap.
    pocket=(outer_wire(layout).offset2D(GAP,kind="arc").extrude(
            CARTRIDGE[2]-POCKET_FLOOR_Z)
            .translate((0,0,POCKET_FLOOR_Z)))
    carrier=carrier.cut(pocket)
    # Mount-hole guide (when source holes exist) vs contour go/no-go mask.
    if layout["mounting_strategy"]=="source-hole-registration":
        guide=outer_wire(layout).extrude(2.)
        for mount in layout["source_mounts"]:
            guide=guide.cut(cq.Workplane("XY").center(mount["x"],mount["y"])
                .circle((mount["drill_mm"]+.25)/2).extrude(2.))
        strategy="HOLE_REFERENCED_DISCONNECTED_FROM_ELECTRICAL_TEST"
    else:
        guide=cq.Workplane("XY").rect(CARTRIDGE[0],CARTRIDGE[1]).extrude(2.)
        opening=outer_wire(layout).offset2D(GAP,kind="arc").extrude(2.)
        guide=guide.cut(opening)
        strategy="NON_CLAMPING_CONTOUR_TRAY_NO_INVENTED_HOLES"
    solids={"common-inspection-dock":dock,"source-outline-cartridge":carrier,
            "nominal-unpopulated-PCB":board,"inspection-gauge":guide}
    model_metrics={}
    for name,solid in solids.items():
        path=out/(name+".step")
        cq.exporters.export(solid,str(path))
        loaded=cq.importers.importStep(str(path))
        if len(loaded.solids().vals())!=1 or not loaded.val().isValid() or loaded.val().Volume()<=0:
            raise ValueError("STEP_IMPORT_BREP_INVALID:"+name)
        b=loaded.val().BoundingBox()
        model_metrics[name]={"volume_mm3":round(loaded.val().Volume(),6),
                             "bbox_mm":[round(b.xlen,5),round(b.ylen,5),round(b.zlen,5)],
                             "reimported_valid":True}
        cq.exporters.export(solid,str(out/(name+".stl")))
    compound=cq.Compound.makeCompound([
        dock.val(),carrier.val().translate(cq.Vector(0,0,10)),
        board.val().translate(cq.Vector(0,0,23)),
        guide.val().translate(cq.Vector(0,0,29))])
    cq.exporters.export(compound,str(out/"exploded-UNASSEMBLED.step"))
    with (out/"native-hole-map.csv").open("w",newline="") as f:
        wtr=csv.writer(f);wtr.writerow(["reference","x_model_mm","y_model_mm","source_drill_mm","physical_verified"])
        for p in layout["source_mounts"]:
            wtr.writerow([p["ref"],p["x"],p["y"],p["drill_mm"],"NO"])
    result={
        "schema":"hs.native_contour_3d_study.v1",
        "source_board_sha256":layout["pcb_sha256"],
        "source_outline_vertices":layout["source_outline_vertices"],
        "source_board_cutouts":layout["native_internal_edgecuts_cutouts"],
        "mount_strategy":layout["mounting_strategy"],
        "mounting_strategy_provisional":strategy,
        "source_nominal_area_mm2":layout["native_board_polygon_area_mm2"],
        "source_bbox_mm":layout["bbox_source_mm"],
        "source_mount_count":len(layout["source_mounts"]),
        "common_dock_mm":list(DOCK),
        "pocket_gap_mm_assumed":GAP,
        "nominal_board_thickness_mm_assumed":BOARD_THICKNESS_ASSUMED,
        "cad":model_metrics,
        "claims_excluded":["analytic_arc_fidelity","populated_body_clearance",
                           "printed_or_machined_tolerances","retention_pullout",
                           "physical_fit","electrical_probe_access"],
        "fabrication_authorized":False,
        "physical_measurements":False,
        "file_sha256":{p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file()},
    }
    (out/"cad-receipt.json").write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--layout",type=Path,required=True)
    p.add_argument("--source",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    r=build(json.loads(a.layout.read_text()),a.source,a.out)
    print(json.dumps({k:v for k,v in r.items() if k!="file_sha256"},indent=2))
