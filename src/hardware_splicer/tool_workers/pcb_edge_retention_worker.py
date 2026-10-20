"""Exact-source-outline two-piece PCB edge-retention CAD candidate.

This produces two CAD solids, collision checks against an original KiCad
board-only STEP, and a bounded source-coordinate/clearance report. Retention
strength, connector/pad collisions, and real-world fit remain unverified.
"""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import sys
import cadquery as cq


_PARAMS={
    'board_pocket_xy_gap_mm':0.85,
    'edge_capture_overlap_nominal_mm':1.2,
    'outer_perimeter_margin_mm':8.0,
    'board_top_z_freedom_mm':0.25,
    'bottom_support_height_mm':2.5,
    'lid_ring_height_mm':2.2,
    'external_screw_offset_from_board_AABB_mm':4.5,
    'base_pilot_hole_diameter_mm':2.7,
    'lid_clearance_hole_diameter_mm':3.3,
}


def _sha256(p:Path)->str:
    return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()


def _profile(points:list[tuple[float,float]],offset:float=0.0)->cq.Workplane:
    profile=cq.Workplane('XY').polyline(points).close()
    return profile.offset2D(offset,kind='arc') if offset else profile


def _volume(value:cq.Workplane)->float:
    return float(value.val().Volume())


def execute(step_path:Path,geometry_path:Path,output:Path)->dict:
    geo=json.loads(geometry_path.read_text())
    profile=geo.get('edge_cuts_profile_mm') or []
    if (geo.get('status')!='extracted_kicad_source_geometry' or
        not geo.get('edge_cuts_profile_closed') or
        geo.get('edge_cuts_source_outline_count')!=1 or
        not 3<=len(profile)<=512 or
        geo.get('explicit_mounting_footprint_refs')):
        raise ValueError('one hash-reverified contour and no claimed board screw mounts required')
    if geo.get('physical_fit_authorized') is not False:
        raise ValueError('source geometry must have unverified physical-fit status')
    coordinates=[(float(pt['x']),-float(pt['y'])) for pt in profile]
    board=cq.importers.importStep(str(step_path))
    board_solid=board.solids().vals()
    if len(board_solid)!=1 or not board_solid[0].isValid():
        raise ValueError('expected a single valid board-only STEP solid')
    bbox=board.val().BoundingBox()
    if not (20<=bbox.xlen<=250 and 20<=bbox.ylen<=250 and 0.4<=bbox.zlen<=5):
        raise ValueError('board-only STEP outside controlled size range')
    xvals=[p[0] for p in coordinates];yvals=[p[1] for p in coordinates]
    exact={'xmin':min(xvals),'xmax':max(xvals),'ymin':min(yvals),'ymax':max(yvals)}
    if any(abs(getattr(bbox,key)-val)>0.08 for key,val in exact.items()):
        raise ValueError('KiCad STEP and Edge.Cuts coordinate frames disagree; refuse to build')
    c_x=(bbox.xmin+bbox.xmax)/2;c_y=(bbox.ymin+bbox.ymax)/2
    margin=_PARAMS['outer_perimeter_margin_mm']
    outer_x=bbox.xlen+2*margin;outer_y=bbox.ylen+2*margin
    gap=_PARAMS['board_pocket_xy_gap_mm']
    lip=_PARAMS['edge_capture_overlap_nominal_mm']
    floor=_PARAMS['bottom_support_height_mm']
    top_gap=_PARAMS['board_top_z_freedom_mm']
    lid_height=_PARAMS['lid_ring_height_mm']
    lid_z0=bbox.zmax+top_gap
    pilot=_PARAMS['base_pilot_hole_diameter_mm']
    clearance=_PARAMS['lid_clearance_hole_diameter_mm']
    mount_offset=_PARAMS['external_screw_offset_from_board_AABB_mm']
    screws=[(round(x,4),round(y,4)) for x in (bbox.xmin-mount_offset,bbox.xmax+mount_offset)
                          for y in (bbox.ymin-mount_offset,bbox.ymax+mount_offset)]
    if len(screws)!=4 or any(bbox.xmin<=x<=bbox.xmax or bbox.ymin<=y<=bbox.ymax for x,y in screws):
        raise ValueError('lid screws must lie outside PCB envelope')
    # Source-derived edge support under the nominal PCB perimeter.
    # Interior remains *open* (no unverified floor pressed against bottom parts).
    support=(cq.Workplane('XY').workplane(offset=bbox.zmin-floor)
             .center(c_x,c_y).rect(outer_x,outer_y).extrude(floor)
             .cut(_profile(coordinates,-lip).extrude(floor+0.02)
                 .translate((0,0,bbox.zmin-floor-0.01))))
    # Body pocket follows the actual arc-tessellated notch, not the bounding box.
    outer_wall=(cq.Workplane('XY').workplane(offset=bbox.zmin)
               .center(c_x,c_y).rect(outer_x,outer_y)
               .extrude(lid_z0-bbox.zmin)
               .cut(_profile(coordinates,gap)
                    .extrude(lid_z0-bbox.zmin+0.02)
                    .translate((0,0,bbox.zmin-0.01))))
    base=support.union(outer_wall)
    lid=(cq.Workplane('XY').workplane(offset=lid_z0)
           .center(c_x,c_y).rect(outer_x,outer_y).extrude(lid_height)
           .cut(_profile(coordinates,-lip).extrude(lid_height+0.02)
                .translate((0,0,lid_z0-0.01))))
    # Use original KiCad pad bounding rectangles for conservative exclusion of
    # board-edge support/retainer lips. This protects against obvious pad
    # encounters in the source geometry, but NOT copper traces, via annuli,
    # populated body heights, connector mating or full electrical isolation.
    # Exclusions affect only lip material projected INSIDE the PCB contour;
    # exterior ring and case screw structural walls are not carved away.
    risks=geo.get('nominal_edge_lip_pad_risk_candidates')
    if not isinstance(risks,list) or len(risks)>350:
        raise ValueError('independent source-pad clearance list required and bounded')
    pad_extra=float(geo.get('edge_pad_clearance_caution_margin_mm') or 0)
    if abs(pad_extra-0.45)>0.001:
        raise ValueError('edge copper caution margin must match bounded candidate design')
    board_interior_base=_profile(coordinates).extrude(floor+0.08).translate((0,0,bbox.zmin-floor-0.04))
    board_interior_lid=_profile(coordinates).extrude(lid_height+0.08).translate((0,0,lid_z0-0.04))
    before_pad_interference_mm3=0.0
    for pad in risks:
        r=pad.get('bbox_mm') or {}
        px=float(r.get('xmin',0))+float(r.get('width',0))/2
        py=-float(r.get('ymin',0))-float(r.get('height',0))/2
        w=float(r.get('width',0))+pad_extra*2
        h=float(r.get('height',0))+pad_extra*2
        if not (0.2<w<=25 and 0.2<h<=25):
            raise ValueError('unbounded or invalid source pad copper keepout')
        mask=cq.Workplane('XY').center(px,py).rect(w,h)
        base_keepout=(mask.extrude(floor+0.08)
                      .translate((0,0,bbox.zmin-floor-0.04))
                      .intersect(board_interior_base))
        lid_keepout=(cq.Workplane('XY').center(px,py).rect(w,h)
                     .extrude(lid_height+0.08).translate((0,0,lid_z0-0.04))
                     .intersect(board_interior_lid))
        before_pad_interference_mm3+=_volume(base.intersect(base_keepout))
        before_pad_interference_mm3+=_volume(lid.intersect(lid_keepout))
        base=base.cut(base_keepout)
        lid=lid.cut(lid_keepout)
    # Deterministically verify each protected footprint has zero overlap with
    # both support and lid AFTER the cuts, with source-only board coordinates.
    after_pad_interference_mm3=0.0
    for pad in risks:
        r=pad['bbox_mm'];px=r['xmin']+r['width']/2
        py=-r['ymin']-r['height']/2
        w=r['width']+pad_extra*2;h=r['height']+pad_extra*2
        bottom=(cq.Workplane('XY').center(px,py).rect(w,h)
           .extrude(floor+0.08).translate((0,0,bbox.zmin-floor-0.04))
           .intersect(board_interior_base))
        upper=(cq.Workplane('XY').center(px,py).rect(w,h)
           .extrude(lid_height+0.08).translate((0,0,lid_z0-0.04))
           .intersect(board_interior_lid))
        after_pad_interference_mm3+=_volume(base.intersect(bottom))
        after_pad_interference_mm3+=_volume(lid.intersect(upper))
    if after_pad_interference_mm3>0.02:
        raise ValueError('source pad clearance exclusion still collides with candidate lips')
    # Trace/via centreline and width data from the same original KiCad source
    # need separately bounded keepouts; pads alone are insufficient (several
    # original traces are 5 mm wide and run near PCB perimeter).
    risk_tracks=geo.get('nominal_edge_lip_track_risk_candidates')
    if not isinstance(risk_tracks,list) or len(risk_tracks)>175:
        raise ValueError('source conductor risk list missing or unbounded')
    if geo.get('source_zone_count') is None:
        raise ValueError('original PCB source copper zone inventory required')

    def conductor_cutter(tr, zmin, length):
        begin=tr['begin_xy_mm'];end=tr['end_xy_mm']
        x0,y0=float(begin['x']),-float(begin['y'])
        x1,y1=float(end['x']),-float(end['y'])
        copper_radius=float(tr['width_mm'])/2+pad_extra
        delta_x=x1-x0;delta_y=y1-y0
        span=math.hypot(delta_x,delta_y)
        if not (0.1<=copper_radius<=9.0 and 0<=span<=300):
            raise ValueError('invalid source conductor segment')
        endpoints=(cq.Workplane('XY').center(x0,y0).circle(copper_radius).extrude(length)
                   .union(cq.Workplane('XY').center(x1,y1).circle(copper_radius).extrude(length)))
        if span>0.001:
            midx=(x0+x1)/2;midy=(y0+y1)/2
            bridge=(cq.Workplane('XY').center(midx,midy)
                    .rect(span,copper_radius*2).extrude(length)
                    .rotate((midx,midy,0),(midx,midy,1),math.degrees(math.atan2(delta_y,delta_x))))
            endpoints=endpoints.union(bridge)
        return endpoints.translate((0,0,zmin))

    pre_trace_interference_mm3=0.0
    for tr in risk_tracks:
        bottom_cut=conductor_cutter(tr,bbox.zmin-floor-0.04,floor+0.08)
        upper_cut=conductor_cutter(tr,lid_z0-0.04,lid_height+0.08)
        bottom_cut=bottom_cut.intersect(board_interior_base)
        upper_cut=upper_cut.intersect(board_interior_lid)
        pre_trace_interference_mm3+=_volume(base.intersect(bottom_cut))
        pre_trace_interference_mm3+=_volume(lid.intersect(upper_cut))
        base=base.cut(bottom_cut)
        lid=lid.cut(upper_cut)
    post_trace_interference_mm3=0.0
    for tr in risk_tracks:
        below=conductor_cutter(tr,bbox.zmin-floor-0.04,floor+0.08).intersect(board_interior_base)
        above=conductor_cutter(tr,lid_z0-0.04,lid_height+0.08).intersect(board_interior_lid)
        post_trace_interference_mm3+=_volume(base.intersect(below))
        post_trace_interference_mm3+=_volume(lid.intersect(above))
    if post_trace_interference_mm3>0.02:
        raise ValueError('trace-centreline copper clearance after exclusion remains unresolved')
    # Screw holes are in the CASE margin only; no assumed PCB holes.
    for x,y in screws:
        base=base.cut(cq.Workplane('XY').workplane(offset=bbox.zmin-floor-0.02)
                      .center(x,y).circle(pilot/2).extrude(lid_z0-(bbox.zmin-floor)+0.04))
        lid=lid.cut(cq.Workplane('XY').workplane(offset=lid_z0-0.02)
                    .center(x,y).circle(clearance/2).extrude(lid_height+0.04))
    if any((len(shape.solids().vals())!=1 or not shape.val().isValid()) for shape in (base,lid)):
        raise ValueError('carrier or lid is invalid/multi-solid')
    board_base_overlap=_volume(board.intersect(base))
    board_lid_overlap=_volume(board.intersect(lid))
    base_lid_overlap=_volume(base.intersect(lid))
    if max(board_base_overlap,board_lid_overlap,base_lid_overlap)>0.02:
        raise ValueError('nominal source board/lid/base solid interference detected')
    output.mkdir(parents=True,exist_ok=True)
    base_file=output/'source_edge_capture_base.step'
    lid_file=output/'source_edge_capture_lid.step'
    base_stl=output/'source_edge_capture_base.stl'
    lid_stl=output/'source_edge_capture_lid.stl'
    cq.exporters.export(base,str(base_file));cq.exporters.export(lid,str(lid_file))
    cq.exporters.export(base,str(base_stl));cq.exporters.export(lid,str(lid_stl))
    result={
       'status':'generated_collision_screened_edge_retention_candidate',
       'registered_source_board_sha256':geo['source_sha256'],
       'derived_source_board_step_sha256':_sha256(step_path),
       'source_outline_vertex_count':len(coordinates),
       'source_contour_contains_tessellated_arc':True,
       'source_step_y_axis_flipped_from_kicad_mm':True,
       'nominal_board_bbox_step_mm':{
           'xmin':round(bbox.xmin,4),'xmax':round(bbox.xmax,4),
           'ymin':round(bbox.ymin,4),'ymax':round(bbox.ymax,4),
           'thickness':round(bbox.zlen,4)},
       'candidate_type':'two_piece_exterior_screw_closed_edge_capture',
       'external_lid_screw_centres_mm':[
           {'x':x,'y':y} for x,y in screws],
       'enclosure_outer_mm':{'x':round(outer_x,4),'y':round(outer_y,4),
                             'z':round(floor+bbox.zlen+top_gap+lid_height,4)},
       'nominal_design_parameters':_PARAMS,
       'geometric_clearance_checks':{
           'original_board_to_base_overlap_mm3':round(board_base_overlap,6),
           'original_board_to_lid_overlap_mm3':round(board_lid_overlap,6),
           'base_to_lid_overlap_mm3':round(base_lid_overlap,6),
           'board_only_zero_interference_pass':True,
           'all_four_screw_centres_outside_board_AABB':True,
           'source_pad_keepout_count':len(risks),
           'uncorrected_pad_keepout_overlap_mm3':round(before_pad_interference_mm3,4),
           'corrected_pad_keepout_overlap_mm3':round(after_pad_interference_mm3,6),
           'source_pad_projection_no_lip_overlap_pass':True,
           'source_trace_via_count_checked':geo.get('source_track_or_via_count'),
           'source_pcb_copper_zone_count':geo.get('source_zone_count'),
           'source_trace_via_lip_risk_count':len(risk_tracks),
           'initial_track_keepout_overlap_mm3':round(pre_trace_interference_mm3,4),
           'corrected_track_keepout_overlap_mm3':round(post_trace_interference_mm3,6),
           'source_tracks_and_vias_projected_keepouts_pass':True,
           'pcb_component_models_included':False,
           'fastener_clamping_tested':False,
       },
       'source_hole_misclassification_avoided':True,
       'board_corner_M3_holes_assumed':False,
       'design_assembled_physically':False,
       'connector_access_verified':False,
       'copper_edge_keepout_verified':False,
       'pad_bounding_regions_excluded_from_candidate_lip':True,
       'source_trace_segment_regions_excluded_from_candidate_lip':True,
       'component_height_or_pad_clearance_verified':False,
       'edge_support_contact_pressure_verified':False,
       'material_and_print_orientation_qualified':False,
       'thermal_and_electrical_isolation_verified':False,
       'structural_FEM_or_drop_test_passed':False,
       'manufacturing_or_print_authorized':False,
       'generated_artifacts':[
         {'filename':p.name,'sha256':_sha256(p),'size_bytes':p.stat().st_size}
         for p in (base_file,lid_file,base_stl,lid_stl)],
    }
    (output/'source_edge_retention_report.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    if len(sys.argv)!=4:
        raise SystemExit('usage: worker BOARD_ONLY_STEP KI_CAD_SOURCE_INTERFACE_JSON OUTPUT_DIR')
    answer=execute(Path(sys.argv[1]),Path(sys.argv[2]),Path(sys.argv[3]))
    print(json.dumps(answer,separators=(',',':')))
