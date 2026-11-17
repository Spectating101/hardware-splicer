"""Inspect the delivered STEP/STL solids, not just authoring success flags."""
from pathlib import Path
import hashlib
import itertools
import json
import math
import cadquery as cq
import trimesh

ROOT=Path(__file__).resolve().parent


def volume(shape):return sum(s.Volume() for s in shape.Solids())
def common(a,b):return volume(a.intersect(b))
def cyl(x,y,z,r,h):return cq.Workplane('XY').circle(r).extrude(h).translate((x,y,z)).val()


def main():
    g=json.loads((ROOT/'cad/geometry_report.json').read_text())
    findings=[];rows=[];world={}
    assert not g['collision_findings'],g['collision_findings']
    assert g['source_spec_sha256']==hashlib.sha256((ROOT/'design.json').read_bytes()).hexdigest()
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
    b=assembly.BoundingBox()
    # Rear connector shells project 0.7 mm beyond the 285 mm enclosure.
    assert abs(b.xlen-310)<.05 and abs(b.ylen-285.7)<.05 and abs(b.zlen-72)<.05
    assert not findings,findings
    out={'status':'digital_geometry_checks_passed','source':'reimported exported STEP/STL plus unmodified manufacturer BRep',
      'assembly_valid':True,'assembly_solids':len(assembly.Solids()),'custom_parts':rows,
      'display_mount_axes_independently_extracted':sorted(axes),'screw_holes_and_support_seats_checked':True,
      'exported_custom_pair_and_display_intersections_mm3_over_0_1':findings,
      'authoring_model_other_nominal_module_intersections':g['collision_findings'],
      'all_flexible_cables_and_fasteners_modelled':False,'physical_fit_or_operation_proven':False,
      'scope':'Rigid source and nominal envelope geometry only; no manufacturing calibration, full contact/structural/thermal analysis or ARM boot.',
      'assembly_step_sha256':hashlib.sha256((ROOT/'cad/FIELDDECK_7.step').read_bytes()).hexdigest(),
      'author_cad_sha256':hashlib.sha256((ROOT/'author_cad.py').read_bytes()).hexdigest()}
    (ROOT/'analysis/verification.json').write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps({'status':out['status'],'custom_closed_parts':len(rows),'display_mount_axes':len(axes),'assembly_solids':len(assembly.Solids())}))


if __name__=='__main__':main()
