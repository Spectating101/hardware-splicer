"""Parametric board-only carrier: a fabricated-design CANDIDATE, not approved fit."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys
import cadquery as cq


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit('usage: pcb_carrier_worker INPUT_BOARD_STEP OUTPUT_DIR')
    model_path=Path(sys.argv[1]);out=Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
    board=cq.importers.importStep(str(model_path))
    bbox=board.val().BoundingBox()
    board_x=float(bbox.xlen);board_y=float(bbox.ylen);board_z=float(bbox.zlen)
    if not (10 <= board_x <= 450 and 10 <= board_y <= 450 and 0.2 <= board_z <= 15):
        raise ValueError('board geometry out of bounded PCB carrier design range')
    clearance=1.25
    wall=2.25
    floor=2.50
    rim_height=5.0
    interior_x=board_x+2*clearance
    interior_y=board_y+2*clearance
    outer_x=interior_x+2*wall
    outer_y=interior_y+2*wall
    plate=cq.Workplane('XY').box(outer_x,outer_y,floor,centered=(True,True,False))
    ring=(cq.Workplane('XY')
          .box(outer_x,outer_y,rim_height,centered=(True,True,False))
          .cut(cq.Workplane('XY').box(interior_x,interior_y,rim_height+0.1,centered=(True,True,False)))
          .translate((0,0,floor)))
    carrier=plate.union(ring)
    if not carrier.val().isValid():raise ValueError('CAD solid is invalid')
    step=out/'pcb_envelope_carrier_candidate.step'
    stl=out/'pcb_envelope_carrier_candidate.stl'
    cq.exporters.export(carrier,str(step))
    cq.exporters.export(carrier,str(stl))
    envelope_clearance=round(min((interior_x-board_x)/2,(interior_y-board_y)/2),4)
    result={'status':'generated_valid_solid_candidate',
            'source_board_step_sha256':'sha256:'+hashlib.sha256(model_path.read_bytes()).hexdigest(),
            'cad_kernel':'CadQuery/OpenCascade','board_bbox_mm':{'x':round(board_x,3),'y':round(board_y,3),'thickness':round(board_z,3)},
            'carrier_outer_mm':{'x':round(outer_x,3),'y':round(outer_y,3),'z':floor+rim_height},
            'pcb_to_envelope_xy_clearance_mm':envelope_clearance,
            'wall_mm':wall,'floor_mm':floor,'rim_height_mm':rim_height,
            'carrier_volume_mm3':round(carrier.val().Volume(),3),
            'validated_single_solid':len(carrier.solids().vals())==1,
            'source_board_components_omitted':True,
            'mounting_holes_provided':False,
            'retention_compatibility_verified':False,
            'enclosure_clearance_verified':False,
            'functional_part_fit_verified':False,
            'printer_material_selected':False,
            'build_authorized':False,
            'generated_artifacts':[
               {'name':p.name,'sha256':'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest(),
                'size_bytes':p.stat().st_size} for p in [step,stl]]}
    print(json.dumps(result,separators=(',',':')))

if __name__=='__main__':main()
