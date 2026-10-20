"""Bounded KiCad board-outline and mechanical-feature extraction.

Executed only against hash-verified, registered CAD source staged by HS.
Never guesses that a plated signal hole is a mechanical mount.
"""
from __future__ import annotations
import json,sys,math
import pcbnew as k


def _mm(value):return round(k.ToMM(value),4)
def main():
    if len(sys.argv)!=2:raise SystemExit('expected KiCad PCB path')
    board=k.LoadBoard(sys.argv[1])
    if board is None:raise ValueError('KiCad could not load the board')
    footprints=list(board.GetFootprints())
    if len(footprints)>2500:raise ValueError('excessive footprint count')
    box=board.GetBoardEdgesBoundingBox()
    if box.GetWidth()<=0 or box.GetHeight()<=0:raise ValueError('no valid board outline bounding box')
    nonplated=[];mount_footprints=[];parts=[];plated_count=0
    for f in footprints:
        ref=f.GetReference();value=f.GetValue();footprint_id=str(f.GetFPID().GetLibItemName())
        at=f.GetPosition()
        pad_list=list(f.Pads())
        if len(pad_list)>350:raise ValueError('excessive pads per footprint')
        if 'mountinghole' in footprint_id.lower() or 'mountinghole' in value.replace(' ','').lower():
            mount_footprints.append(ref)
        for pad in pad_list:
            drill=pad.GetDrillSize();dx=_mm(drill.x);dy=_mm(drill.y)
            if dx<=0 and dy<=0:continue
            position=pad.GetPosition();row={
              'reference':ref,'pad_number':pad.GetNumber(),
              'centre_mm':{'x':_mm(position.x),'y':_mm(position.y)},
              'drill_mm':{'x':dx,'y':dy},
              'footprint':footprint_id,
            }
            if pad.GetAttribute()==k.PAD_ATTRIB_NPTH:
                nonplated.append(row)
            else:
                plated_count+=1
        parts.append({'reference':ref,'value':value[:96],'footprint':footprint_id[:128],
                      'position_mm':{'x':_mm(at.x),'y':_mm(at.y)},
                      'pad_count':len(pad_list),'board_side':'bottom' if f.IsFlipped() else 'top'})
    result={
      'status':'extracted_kicad_source_geometry',
      'board_outline_aabb_mm':{'xmin':_mm(box.GetX()),'ymin':_mm(box.GetY()),
          'width':_mm(box.GetWidth()),'height':_mm(box.GetHeight())},
      'outline_is_actual_exact_contour':False,
      'footprint_count':len(parts),
      'footprint_placements':parts,
      'nonplated_drill_features':nonplated,
      'plated_drill_count':plated_count,
      'explicit_mounting_footprint_refs':sorted(mount_footprints),
      'mechanical_hole_centres_verified':False,
      'screw_retention_layout_resolved':False,
      'source_has_explicit_mounting_footprints':bool(mount_footprints),
      'connector_mating_clearance_verified':False,
      'component_height_verified':False,
      'board_source_coordinates_only':True,
      'warning':('Non-plated drill features may belong to components, not structural fasteners. '
           'Only independently designated/checked mounting centres can support standoffs.'),
      'physical_fit_authorized':False,
    }
    print(json.dumps(result,separators=(',',':')))
if __name__=='__main__':main()
