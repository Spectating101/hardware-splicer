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
    # KiCad builds the nominal Edge.Cuts contour from actual line/arc items.
    # Curves become tessellated points; this is source geometry, not a
    # physical measurement, machining tolerance or final copper keep-out.
    outlines=k.SHAPE_POLY_SET()
    outlines_ok=bool(board.GetBoardPolygonOutlines(outlines))
    profile=[]
    if outlines_ok and outlines.OutlineCount()==1:
        chain=outlines.COutline(0)
        if chain.IsClosed() and 3<=chain.PointCount()<=512:
            profile=[{'x':_mm(chain.CPoint(j).x), 'y':_mm(chain.CPoint(j).y)}
                     for j in range(chain.PointCount())]
    # Conservative geometric envelope: Euclidean centre-to-edge distance
    # minus pad AABB half-diagonal is a lower bound on the closest pad edge.
    # It can overestimate risk for rotated/nonrectangular pads, never certify
    # copper clearance for full tracks/pours or a populated assembly.
    def edge_distance(pt,edges):
        distances=[]
        for a,b in zip(edges,edges[1:]+edges[:1]):
            dx=b[0]-a[0];dy=b[1]-a[1]
            denominator=dx*dx+dy*dy
            t=max(0.,min(1.,((pt[0]-a[0])*dx+(pt[1]-a[1])*dy)/denominator)) if denominator else 0.
            distances.append(math.hypot(pt[0]-(a[0]+t*dx),pt[1]-(a[1]+t*dy)))
        return min(distances) if distances else float('inf')
    edge_points=[(v['x'],v['y']) for v in profile]
    pad_clearance_risks=[]
    estimated_pad_count=0
    nominal_overlap=1.2
    caution_margin=0.45
    nonplated=[];mount_footprints=[];parts=[];plated_count=0
    for f in footprints:
        ref=f.GetReference();value=f.GetValue();footprint_id=str(f.GetFPID().GetLibItemName())
        at=f.GetPosition()
        pad_list=list(f.Pads())
        if len(pad_list)>350:raise ValueError('excessive pads per footprint')
        if 'mountinghole' in footprint_id.lower() or 'mountinghole' in value.replace(' ','').lower():
            mount_footprints.append(ref)
        for pad in pad_list:
            estimated_pad_count+=1
            if edge_points:
                pos=pad.GetPosition()
                point=(_mm(pos.x),_mm(pos.y))
                bbox_pad=pad.GetBoundingBox()
                width=_mm(bbox_pad.GetWidth());height=_mm(bbox_pad.GetHeight())
                radius=math.hypot(width/2,height/2)
                lower=edge_distance(point,edge_points)-radius
                if lower<=nominal_overlap+caution_margin:
                    pad_clearance_risks.append({
                        'reference':ref,'pad_number':pad.GetNumber(),
                        'bbox_mm':{'xmin':_mm(bbox_pad.GetX()),
                          'ymin':_mm(bbox_pad.GetY()),'width':width,'height':height},
                        'centre_xy_mm':{'x':point[0],'y':point[1]},
                        'conservative_min_edge_gap_mm':round(lower,4),
                        'on_front_copper':bool(pad.IsOnLayer(k.F_Cu)),
                        'on_back_copper':bool(pad.IsOnLayer(k.B_Cu)),
                        'note':'pad bounding rectangle proximity is conservative, not a proven contact or clearance',
                    })
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
      'edge_cuts_profile_mm':profile,
      'edge_cuts_profile_closed':bool(profile),
      'edge_cuts_profile_is_arc_tessellated':bool(profile),
      'edge_cuts_source_outline_count':outlines.OutlineCount() if outlines_ok else 0,
      'edge_cuts_source_profile_not_as_built_measurement':True,
      'footprint_count':len(parts),
      'footprint_placements':parts,
      'nonplated_drill_features':nonplated,
      'plated_drill_count':plated_count,
      'pad_count_all_layers':estimated_pad_count,
      'nominal_edge_capture_pad_overlap_mm':nominal_overlap,
      'edge_pad_clearance_caution_margin_mm':caution_margin,
      'nominal_edge_lip_pad_risk_candidates':pad_clearance_risks,
      'nominal_edge_lip_pad_risk_candidate_count':len(pad_clearance_risks),
      'all_copper_tracks_and_pours_clearance_verified':False,
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
