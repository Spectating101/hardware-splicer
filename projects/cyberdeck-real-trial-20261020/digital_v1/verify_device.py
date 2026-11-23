"""Inspect the delivered STEP/STL solids, not just authoring success flags."""
from pathlib import Path
import hashlib
import itertools
import json
import math
import cadquery as cq
import numpy as np
import trimesh
from study_contract import validate_calculation_record
from author_cad import validate_fixed_geometry

ROOT=Path(__file__).resolve().parent


def volume(shape):return sum(s.Volume() for s in shape.Solids())
def common(a,b):return volume(a.intersect(b))
def cyl(x,y,z,r,h):return cq.Workplane('XY').circle(r).extrude(h).translate((x,y,z)).val()
def ring(x,y,z,outer,inner,h=.1):
    return cyl(x,y,z,outer,h).cut(cyl(x,y,z-.01,inner,h+.02))
def hex_prism(x,y,z,af,h):
    return cq.Workplane('XY').polygon(6,af/math.cos(math.pi/6)).extrude(h).translate((x,y,z)).val()
def bounds(shape):
    b=shape.BoundingBox()
    return (b.xmin,b.ymin,b.zmin,b.xmax,b.ymax,b.zmax)
def boxes_overlap(a,b):
    return all(a[i]<b[i+3]-1e-7 and b[i]<a[i+3]-1e-7 for i in range(3))


def verify_fasteners(g,world,display,purchased):
    """Nominal hardware and explicitly sized tools, checked against exports.

    Cap heads: M3 diameter 5.5 / height 3; M2.5 diameter 4.5 / height 2.5.
    DIN 934 nuts: M3 AF 5.5 / height 2.4; M2.5 AF 5 / height 2.
    These are the selected supplier dimensions, not invented thread BReps.
    Tool envelopes are requirements on future tools, not proof of every tool.
    """
    board=purchased['pi4_board_envelope']
    pi_components=[(n,s) for n,s in purchased.items() if n.startswith('pi4_') and n!='pi4_board_envelope']
    custom=list(world.items())
    tray=[(n,s) for n,s in custom if n.startswith('tray_')]
    seam_stage=[(n,s) for n,s in custom if n.startswith(('tray_','seam_plate_','foot_'))]
    tray_compound=cq.Compound.makeCompound([s for _,s in tray])
    face_compound=cq.Compound.makeCompound([s for n,s in custom if n.startswith('face_')])
    assembled=custom+[('display',display)]+list(purchased.items())
    cached_bounds={id(s):bounds(s) for _,s in assembled}
    checks=[]

    def check_empty(label,probe,objects):
        pb=bounds(probe)
        for name,shape in objects:
            if boxes_overlap(pb,cached_bounds[id(shape)] if id(shape) in cached_bounds else bounds(shape)):
                assert common(probe,shape)<.01,f'{label}: blocked by {name}'
        checks.append(label)

    def check_seat(label,probe,shape):
        assert common(probe,shape)>.98*volume(probe),f'{label}: bearing surface missing'
        checks.append(label)

    for x,y in g['seam_fastener_centres_mm']:
        check_empty('seam head',cyl(x,y,-3,2.75,3),assembled)
        check_empty('seam shank and exposed tip',cyl(x,y,0,1.5,10),assembled)
        check_empty('seam nut',hex_prism(x,y,6,5.5,2.4),assembled)
        check_empty('seam underside driver',cyl(x,y,-25,2.8,21.9),seam_stage)
        check_empty('seam nut socket before modules: OD8',cyl(x,y,6.01,4,20),seam_stage)
        check_seat('seam head seat',ring(x,y,0,2.65,1.7),tray_compound)
    for x,y in g['top_fastener_centres_mm']:
        check_empty('face head',cyl(x,y,64,2.75,3),assembled)
        check_empty('face shank',cyl(x,y,54,1.5,10),assembled)
        check_empty('face captured nut',hex_prism(x,y,56.8,5.5,2.4),assembled)
        direction=1 if x<77.5 or 155<x<232.5 else -1
        insertion=hex_prism(x,y,56.8,5.5,2.4).fuse(hex_prism(x+10*direction,y,56.8,5.5,2.4))
        insertion=insertion.fuse(cq.Workplane('XY').box(10,5.5,2.4,centered=(False,True,False)).translate((min(x,x+10*direction),y,56.8)).val())
        check_empty('face nut side insertion before face',insertion,tray+[('display',display)]+list(purchased.items()))
        # The screw must clamp the roof, not merely clamp its own face sheet.
        roof=cyl(x,y,59.25,2.65,1.7).cut(cyl(x,y,59.2,1.7,1.8))
        check_seat('face captive nut roof',roof,tray_compound)
        check_empty('face driver from above',cyl(x,y,67.01,2.8,30),assembled)
        check_seat('face head seat',ring(x,y,63.9,2.65,1.7),face_compound)
    for x,y in g['pi_mount_centres_mm']:
        check_empty('Pi head',cyl(x,y,8.6,2.25,2.5),assembled)
        check_empty('Pi shank and underside tip',cyl(x,y,-1.4,1.25,10),assembled)
        check_empty('Pi nut',hex_prism(x,y,.2,5,2),assembled)
        check_empty('Pi nut insertion from below',hex_prism(x,y,-6,5,8.2),tray)
        check_empty('Pi driver before display/face',cyl(x,y,11.11,2.8,30),tray+pi_components)
        check_seat('Pi screw bearing on board',ring(x,y,8.5,2.15,1.45),board)
    for x,y in g['display_case_mount_centres_mm']:
        check_empty('display screw head',cyl(x,y,47.04,2.25,2.5),assembled)
        # Engagement above Z52.54 is intentional in the vendor pilot holes.
        check_empty('display shank below threaded lug',cyl(x,y,49.54,1.25,2.99),assembled)
        check_empty('display screw insertion from below',cyl(x,y,-6,2.35,55.53),custom)
        check_empty('display driver shaft: OD5.6',cyl(x,y,-25,2.8,72.03),assembled)
        check_seat('display screw head seat',ring(x,y,49.54,2.15,1.5),tray_compound)
    for x,y in itertools.product((16,48),(214.5,246.5)):
        check_empty('fan head',cyl(x,y,66,2.75,3),assembled)
        check_empty('fan 25mm shank and exposed tip',cyl(x,y,41,1.5,25),assembled)
        check_empty('fan nut below duct flange',hex_prism(x,y,46.6,5.5,2.4),assembled)
        # Loose rear-left face is held outside the case for nut/driver access.
        loose=[(n,world[n]) for n in ('face_rear_left','fan_guard','fan_duct')]
        check_empty('fan nut socket before face install: OD8',cyl(x,y,25,4,23.99),loose)
        check_empty('fan driver from above',cyl(x,y,69.01,2.8,30),assembled)
        check_seat('fan nut bearing on duct flange',ring(x,y,49,2.65,1.7),world['fan_duct'])
        check_seat('fan head bearing on guard',ring(x,y,65.9,2.65,1.7),world['fan_guard'])
    bom=json.loads((ROOT/'bom.json').read_text())
    by_id={p['id']:p for p in bom['items']}
    for name,quantity in [('m3_10',36),('m3_25',4),('m3_nut',40),('m25_10',4),('m25_nut',4),('m25_6',4)]:
        assert by_id[name]['quantity']==quantity,f'{name}: BOM fastener count differs from geometry'
    assert by_id['m3_25']['specification'].startswith('M3x25'),'Fan clamp needs selected M3x25'
    return {'envelope_checks':len(checks),'screws':48,'nuts':44,
            'fan_stack_mm':17,'fan_nut_height_mm':2.4,'fan_screw_length_mm':25,'fan_tip_beyond_nut_mm':5.6,
            'tool_envelope_requirements':{'driver_shaft_diameter_mm':5.6,'nut_socket_outer_diameter_mm':8},
            'assembly_sequence':'Tray seams, Pi, display, then rear-left face with fan/duct preassembled outside case.',
            'limits':'Nominal rigid heads/nuts/shanks and sized tool paths; vendor lug threads, torque, printer fits, full tool handles, cables and physical retention remain unproven.'}


def main():
    validate_fixed_geometry(json.loads((ROOT/'design.json').read_text()))
    calculations=validate_calculation_record(ROOT)
    g=json.loads((ROOT/'cad/geometry_report.json').read_text())
    findings=[];rows=[];world={}
    assert not g['collision_findings'],g['collision_findings']
    assert g['source_spec_sha256']==hashlib.sha256((ROOT/'design.json').read_bytes()).hexdigest(),'stale design geometry'
    assert g['source_author_sha256']==hashlib.sha256((ROOT/'author_cad.py').read_bytes()).hexdigest(),'stale author geometry'
    assert g['source_vendor_step_sha256']==hashlib.sha256((ROOT/'sources/touch_display2_7inch.step').read_bytes()).hexdigest(),'stale vendor geometry'
    for p in g['parts']:
        if not p['printable']:continue
        name=p['name'];step=ROOT/'cad/print'/f'{name}.step';stl=step.with_suffix('.stl')
        s=cq.importers.importStep(str(step)).val();m=trimesh.load(stl,force='mesh',process=True)
        b=s.BoundingBox();dims=[b.xlen,b.ylen,b.zlen]
        assert s.isValid() and len(s.Solids())==1,name
        assert abs(volume(s)-p['volume_mm3'])<max(.1,p['volume_mm3']*.0001),name
        assert all(abs(a-b)<.03 for a,b in zip(dims,p['print_dimensions_mm'])),name
        assert dims[0]<220 and dims[1]<220,name
        assert m.is_watertight and m.is_winding_consistent and m.volume>0,name
        assert abs(m.volume-volume(s))/volume(s)<.015,name
        for key,path in [('step_sha256',step),('stl_sha256',stl)]:assert hashlib.sha256(path.read_bytes()).hexdigest()==p[key],name
        world[name]=s.translate(tuple(p['bounds_mm'][:3]))
        rows.append({'name':name,'valid_closed_step':True,'watertight_stl':True,'bed_fit_220mm':True,'mesh_volume_error_percent':round(100*abs(m.volume-volume(s))/volume(s),3)})
    expected={p['name']+ext for p in g['parts'] if p['printable'] for ext in ('.step','.stl')}
    assert expected=={p.name for p in (ROOT/'cad/print').iterdir() if p.suffix in ('.step','.stl')},'stale or missing print files'
    native=cq.importers.importStep(str(ROOT/'sources/touch_display2_7inch.step')).val()
    assert native.isValid() and len(native.Solids())==5
    # Independently extract the nominal outer mounting-hole axes from the
    # unmodified manufacturer BRep, not from the authoring code's hole list.
    axes=set()
    for face in native.Faces():
        if face.geomType()!='CYLINDER':continue
        c=face._geomAdaptor().Cylinder();p=c.Location();d=c.Axis().Direction()
        if abs(c.Radius()-1)<.001 and abs(abs(d.Z())-1)<1e-6 and abs(abs(p.X())-35.355)<.02:
            axes.add((round(157.935-p.Y(),3),round(210+p.X(),3)))
    assert len(axes)==4,axes
    assert axes=={tuple(round(v,3) for v in p) for p in g['display_case_mount_centres_mm']}
    display=native.rotate((0,0,0),(0,0,1),90).translate((157.935,210,56.98))
    for (an,a),(bn,b) in itertools.combinations(world.items(),2):
        v=common(a,b)
        if v>.1:findings.append({'a':an,'b':bn,'intersection_mm3':v})
    for name,s in world.items():
        v=common(s,display)
        if v>.1:findings.append({'a':name,'b':'vendor_display','intersection_mm3':v})
    tray=cq.Compound.makeCompound([s for n,s in world.items() if n.startswith('tray_')])
    face=cq.Compound.makeCompound([s for n,s in world.items() if n.startswith('face_')])
    for x,y in axes:
        assert common(tray,cyl(x,y,49.55,1.35,2.97))<.01,'display screw hole blocked'
        annulus=cyl(x,y,50,4.7,2).cut(cyl(x,y,49.9,1.6,2.2))
        assert common(tray,annulus)>.98*volume(annulus),'display support seat missing'
        assert common(tray,cyl(x,y,-.1,2.9,49.5))<.01,'underside tool shaft blocked'
    for x,y in g['pi_mount_centres_mm']:
        assert common(tray,cyl(x,y,-.1,1.35,7.2))<.01,'Pi fastener hole blocked'
        ring=cyl(x,y,4,3.2,2.8).cut(cyl(x,y,3.9,1.6,3))
        assert common(tray,ring)>.98*volume(ring),'Pi support missing'
    for x,y in g['top_fastener_centres_mm']:
        assert common(face,cyl(x,y,60.9,1.5,3.2))<.01,'face fastener hole blocked'
    assembly=cq.importers.importStep(str(ROOT/'cad/FIELDDECK_7.step')).val()
    assert assembly.isValid()
    assert len(assembly.Solids())==sum(p['solids'] for p in g['parts'])
    remaining=list(assembly.Solids())

    def consume_exact(label,expected):
        for source in expected.Solids():
            candidates=[s for s in remaining if all(abs(a-b)<.005 for a,b in zip(bounds(s),bounds(source)))
                        and abs(volume(s)-volume(source))<.01]
            match=next((s for s in candidates if common(s,source)>.999999*volume(source)),None)
            assert match is not None,f'assembly placement/shape differs: {label}'
            remaining.remove(match)
    for name,shape in world.items():consume_exact(name,shape)
    consume_exact('unmodified vendor display',display)
    # Match every nominal module solid to its authoring inventory as well.
    # Those envelopes remain approximate; exact purchased detail is not claimed.
    purchased={}
    for p in g['parts']:
        if p['printable'] or p['kind']=='manufacturer_step':continue
        pb=p['bounds_mm']
        selected=[s for s in remaining if all(bounds(s)[i]>=pb[i]-.005 and bounds(s)[i+3]<=pb[i+3]+.005 for i in range(3))]
        assert len(selected)==p['solids'] and abs(sum(volume(s) for s in selected)-p['volume_mm3'])<.01,p['name']
        compound=cq.Compound.makeCompound(selected)
        assert all(abs(a-b)<.005 for a,b in zip(bounds(compound),pb)),p['name']
        purchased[p['name']]=compound
        for s in selected:remaining.remove(s)
    assert not remaining,'assembly contains unaccounted solids'
    fasteners=verify_fasteners(g,world,display,purchased)
    # GLB is the actual source for the rendered views. Check its part inventory,
    # world bounds and closed-mesh volumes against the STEP authoring inventory.
    scene=trimesh.load(ROOT/'cad/FIELDDECK_7.glb',force='scene')
    assert set(scene.graph.nodes_geometry)=={p['name'] for p in g['parts']},'GLB part inventory differs'
    for p in g['parts']:
        transform,name=scene.graph[p['name']]
        m=scene.geometry[name].copy();m.apply_transform(transform)
        assert all(abs(a-b)<.3 for a,b in zip(m.bounds.flatten(),p['bounds_mm'])),p['name']
        if p['kind']=='manufacturer_step':
            # Vendor CAD tessellation includes open rendering seams. Its signed
            # mesh volume is not a solid volume; compare triangles to an
            # independent tessellation of the actual unmodified vendor BRep.
            vertices,faces=display.tessellate(.25,.2)
            expected_mesh=trimesh.Trimesh(np.array([[v.x,v.y,v.z] for v in vertices]),np.array(faces),process=True)
            assert m.vertices.shape==expected_mesh.vertices.shape and np.allclose(m.vertices,expected_mesh.vertices,atol=.001,rtol=0),p['name']
            assert np.array_equal(m.faces,expected_mesh.faces),p['name']
        else:
            assert m.is_watertight and abs(m.volume-p['volume_mm3'])/p['volume_mm3']<.015,p['name']
    b=assembly.BoundingBox()
    # Rear connector shells project 0.7 mm beyond the 285 mm enclosure.
    assert abs(b.xlen-310)<.05 and abs(b.ylen-285.7)<.05 and abs(b.zlen-72)<.05
    assert not findings,findings
    out={'status':'digital_geometry_checks_passed','source':'reimported exported STEP/STL plus unmodified manufacturer BRep',
      'assembly_valid':True,'assembly_solids':len(assembly.Solids()),'custom_parts':rows,
      'display_mount_axes_independently_extracted':sorted(axes),'screw_holes_and_support_seats_checked':True,
      'exported_custom_pair_and_display_intersections_mm3_over_0_1':findings,
      'authoring_model_other_nominal_module_intersections':g['collision_findings'],
      'assembly_placement_and_shape_inventory_checked':True,'glb_part_bounds_checked':True,'glb_custom_and_nominal_volumes_checked':True,
      'glb_vendor_triangles_match_independent_step_tessellation':True,
      'glb_vendor_render_mesh_closed':False,
      'fastener_checks':fasteners,'calculation_input_sha256':calculations['input_sha256'],
      'engineering_acceptance':calculations['requirements_met'],
      'all_flexible_cables_and_fasteners_modelled':False,'physical_fit_or_operation_proven':False,
      'scope':'Rigid source and nominal envelope geometry only; no manufacturing calibration, full contact/structural/thermal analysis or ARM boot.',
      'assembly_step_sha256':hashlib.sha256((ROOT/'cad/FIELDDECK_7.step').read_bytes()).hexdigest(),
      'author_cad_sha256':hashlib.sha256((ROOT/'author_cad.py').read_bytes()).hexdigest()}
    verified=[ROOT/'cad/FIELDDECK_7.step',ROOT/'cad/FIELDDECK_7.glb',ROOT/'cad/geometry_report.json',
              ROOT/'sources/touch_display2_7inch.step',ROOT/'author_cad.py',ROOT/'verify_device.py',
              ROOT/'design.json',ROOT/'bom.json',ROOT/'analysis/calculations.json',ROOT/'engineering.py',ROOT/'study_contract.py']
    verified.extend((ROOT/'cad/print').glob('*.step'));verified.extend((ROOT/'cad/print').glob('*.stl'))
    if (ROOT/'requirements.json').is_file():verified.append(ROOT/'requirements.json')
    out['verified_files_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(verified)}
    (ROOT/'analysis/verification.json').write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps({'status':out['status'],'custom_closed_parts':len(rows),'display_mount_axes':len(axes),'assembly_solids':len(assembly.Solids())}))


if __name__=='__main__':main()
