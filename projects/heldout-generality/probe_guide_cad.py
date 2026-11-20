"""Optional nominal probe aperture guide for a *real newly-added* KiCad test pad.

The full overlay has no populated-component clearance; inspection/CAD ONLY.
Bore geometry derives from exact revised source + independent native tap audit.
"""
from __future__ import annotations
import argparse,hashlib,json,math
from pathlib import Path
import cadquery as cq

BORE=0.6
HEIGHT=2.5

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def build(layout,tap,tap_audit,revised:Path,out:Path):
    if sha(revised)!=layout["pcb_sha256"] or tap["edited_sha256"]!=layout["pcb_sha256"]:
        raise ValueError("REVISION_BOUNDARY_CHANGED")
    if tap_audit.get("status")!="PASS" or tap_audit["revised_sha256"]!=layout["pcb_sha256"]:
        raise ValueError("ELECTRICAL_SOURCE_AUDIT_NOT_ACCEPTED")
    if abs(tap_audit.get("exposed_testpoint_diameter_mm",0)-1.0)>0.00001:
        raise ValueError("NATIVE_PAD_DIAMETER_NOT_PROVEN")
    if tap.get("native_drc",{}).get("errors")!=0 or tap["native_drc"]["unconnected"]!=0:
        raise ValueError("SOURCE_ROUTE_NOT_DRC_CLEAN")
    if tap["fabrication_authorized"] is not False or tap_audit["fabrication_authorized"] is not False:
        raise ValueError("FALSE_PHYSICAL_AUTHORIZATION")
    xx,yy,w,h=layout["bbox_source_mm"]
    abs_x,abs_y=tap_audit["new_access_xy"]
    x=round(abs_x-(xx+w/2),6)
    y=round((yy+h/2)-abs_y,6)
    guide=cq.Workplane("XY").polyline([tuple(p) for p in layout["outer_xy"]]).close().extrude(HEIGHT)
    for cutout in layout["cutout_xy"]:
        guide=guide.cut(cq.Workplane("XY").polyline([tuple(p) for p in cutout]).close().extrude(HEIGHT))
    # This clearance is digital-only. Its nominal radial margin for a 1.0mm
    # pad is 0.2mm BEFORE toolhead, alignment and printed-part uncertainties.
    bore=cq.Workplane("XY").center(x,y).circle(BORE/2).extrude(HEIGHT)
    before=guide.val().Volume()
    guide=guide.cut(bore)
    if before-guide.val().Volume()<math.pi*(BORE/2)**2*HEIGHT-.001:
        raise ValueError("PROBE_HOLE_OUTSIDE_BOARD_OR_WITHIN_SOURCE_CUTOUT")
    out.mkdir(parents=True,exist_ok=False)
    step=out/"source-bound-signal-probe-plate.step"
    stl=out/"source-bound-signal-probe-plate.stl"
    cq.exporters.export(guide,str(step))
    cq.exporters.export(guide,str(stl))
    loaded=cq.importers.importStep(str(step))
    if len(loaded.solids().vals())!=1 or not loaded.val().isValid():
        raise ValueError("CAD_PROBE_STEP_REIMPORT_FAILED")
    r={
        "schema":"hs.signal_probe_plate_digital_only.v1",
        "source_edited_pcb_sha256":sha(revised),
        "source_signal_net":tap["source_anchor_net"],
        "source_new_testpoint_ref":tap["new_testpoint"],
        "new_probe_abs_xy_mm":[abs_x,abs_y],
        "probe_guide_local_xy_mm":[x,y],
        "bore_diameter_mm":BORE,
        "nominal_test_pad_diameter_mm":1.0,
        "unvalidated_radial_registration_margin_mm":.2,
        "source_board_cutouts":len(layout["cutout_xy"]),
        "profile_vertices":len(layout["outer_xy"]),
        "nominal_plate_height_mm":HEIGHT,
        "reimported_step_volume_mm3":round(loaded.val().Volume(),6),
        "source_design_bound":True,
        "printed_fit":"NOT_PERFORMED",
        "powered_probe_test":"NOT_PERFORMED",
        "populated_component_keepouts":"UNKNOWN",
        "fabrication_authorized":False,
        "files_sha256":{p.name:sha(p) for p in (step,stl)},
    }
    (out/"probe-plate-receipt.json").write_text(json.dumps(r,sort_keys=True,indent=2)+"\n")
    return r

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--layout",type=Path,required=True)
    p.add_argument("--tap-receipt",type=Path,required=True)
    p.add_argument("--tap-audit",type=Path,required=True)
    p.add_argument("--revised-pcb",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    read=lambda p:json.loads(p.read_text())
    r=build(read(a.layout),read(a.tap_receipt),read(a.tap_audit),a.revised_pcb,a.out)
    print(json.dumps(r,sort_keys=True,indent=2))
