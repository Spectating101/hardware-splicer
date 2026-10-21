"""Conservative PCB/component-to-enclosure envelope screening, not CAD collision proof."""
from __future__ import annotations
import math
from collections.abc import Mapping


def screen_board_enclosure_fit(placement: Mapping, physical_assembly: Mapping) -> dict:
    board=placement.get('board',{}).get('dimensions_mm',{})
    enclosure=physical_assembly.get('enclosure',{})
    inner=enclosure.get('inner_dimensions_mm',{})
    offsets=physical_assembly.get('placements',{}).get('pcb',{}).get('origin_xyz_mm',[0,0,0])
    required=('w','d','t')
    def n(v):
        if not isinstance(v,(int,float)) or not math.isfinite(v):raise ValueError('invalid physical dimension')
        return float(v)
    if any(k not in board for k in required) or any(k not in inner for k in ('w','d','h')):
        raise ValueError('board or enclosure dimensions absent')
    bw,bd,bt=(n(board[k]) for k in required)
    iw,idep,ih=(n(inner[k]) for k in ('w','d','h'))
    if min(bw,bd,bt,iw,idep,ih)<=0 or len(offsets)!=3:raise ValueError('invalid assembly envelope')
    ox,oy,oz=map(n,offsets)
    floor=n(enclosure.get('floor_mm',0))
    findings=[]
    def check(ref,axis,available,required_mm,confidence):
        findings.append({'ref':ref,'axis':axis,'remaining_mm':round(available-required_mm,3),
                         'status':'block' if available<required_mm-1e-7 else 'pass',
                         'basis':confidence})
    # Board origin is in enclosure-centered XY; Z is relative to exterior floor.
    check('PCB','x',iw/2-abs(ox),bw/2,'board_dimension')
    check('PCB','y',idep/2-abs(oy),bd/2,'board_dimension')
    check('PCB','z_lower',oz-bt/2,floor,'board_dimension')
    check('PCB','z_upper',floor+ih-(oz+bt/2),0,'board_dimension')
    for part in placement.get('components',[]):
        xyz=part.get('size_xyz_mm',[]); xy=part.get('center_xy_mm',[])
        if len(xyz)!=3 or len(xy)!=2:raise ValueError('component envelope missing')
        sx,sy,sz=map(n,xyz);x,y=map(n,xy)
        if min(sx,sy,sz)<0:raise ValueError('negative component envelope')
        # Rotated rectangles require an axis-aligned bounding envelope.
        angle=math.radians(n(part.get('rotation_deg',0)))
        wx=abs(math.cos(angle))*sx+abs(math.sin(angle))*sy
        wy=abs(math.sin(angle))*sx+abs(math.cos(angle))*sy
        ref=str(part.get('ref') or 'unknown')
        check(ref,'x',iw/2-abs(ox+x),wx/2,'approximate_component_envelope')
        check(ref,'y',idep/2-abs(oy+y),wy/2,'approximate_component_envelope')
        side=str(part.get('layer','F.Cu'))
        top=oz+bt/2+sz if not side.startswith('B.') else oz-bt/2
        bottom=oz+bt/2 if not side.startswith('B.') else oz-bt/2-sz
        check(ref,'z_upper',floor+ih-top,0,'approximate_component_height')
        check(ref,'z_lower',bottom,floor,'approximate_component_height')
    blockers=[x for x in findings if x['status']=='block']
    return {'schema':'hardware_splicer.electromechanical_envelope_fit.v1',
            'status':'envelope_collision_detected' if blockers else 'envelope_screen_clear_unverified',
            'source_mode':placement.get('source_mode'),'checks':findings,'blocker_count':len(blockers),
            'exact_3d_collision_verified':False,'connector_mating_verified':False,
            'electrical_operation_verified':False,'fabrication_authorized':False}
