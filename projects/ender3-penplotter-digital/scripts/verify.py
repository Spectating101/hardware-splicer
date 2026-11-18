"""GPL-3.0-only. Independent export and trajectory verifier. Does not import build/simulate.

Exit 0 means artifact integrity. Requirement satisfaction is a separate JSON field.
This is digital evidence only and never opens hardware interfaces.
"""
import csv
import json
import math
import re
import sys
import xml.etree.ElementTree as ET
import cadquery as cq
import numpy as np
import trimesh
from common import ROOT, read_requirements, write_json, sha256


def verified_paper_bounds(layout, glb, req):
    """Read the sheet independently from both delivered world-space models."""
    candidates=[]
    for solid in layout.Solids():
        b=solid.BoundingBox()
        if abs(b.zmin)<1e-6 and abs(b.zmax-.1)<1e-6:
            candidates.append(solid)
    if len(candidates)!=1:
        raise ValueError('A single 0.1 mm paper sheet must be present in the exported STEP')
    paper=candidates[0];b=paper.BoundingBox()
    bounds=np.array([[b.xmin,b.ymin,b.zmin],[b.xmax,b.ymax,b.zmax]])
    pw,ph=req['paper_width_mm'],req['paper_height_mm']
    expected=np.array([[(235-pw)/2,(235-ph)/2,0],[(235+pw)/2,(235+ph)/2,.1]])
    if not np.allclose(bounds,expected,atol=.00001,rtol=0) or abs(paper.Volume()-pw*ph*.1)>.001:
        raise ValueError('Delivered STEP paper dimensions, position or volume differ from the request')
    meshes=[]
    for node in glb.graph.nodes_geometry:
        transform,name=glb.graph[node]
        if name.startswith('paper_'):
            m=glb.geometry[name].copy();m.apply_transform(transform);meshes.append(m)
    if len(meshes)!=1 or not np.allclose(meshes[0].bounds,bounds,atol=.0001,rtol=0):
        raise ValueError('Delivered GLB paper bounds disagree with independently reopened STEP')
    if abs(float(meshes[0].volume)-paper.Volume())>max(.001,paper.Volume()*.0001):
        raise ValueError('Delivered GLB paper volume disagrees with independently reopened STEP')
    return bounds


def main():
    req=read_requirements();checks=[];metrics={}
    def check(name,passed,detail):checks.append(dict(name=name,passed=bool(passed),detail=detail))
    try:
        provenance=json.loads((ROOT/'sources/manifest.json').read_text())
        expected_commit='88c7758cea9d0d00a54fdb238bedb3b33425f409'
        check('frozen_manufacturer_source',provenance['commit']==expected_commit and provenance['repository']=='https://github.com/Creality3DPrinting/Ender-3','Original Ender-3, manufacturer repository, frozen commit')
        skipped=[]
        for item in provenance['files']:
            path=ROOT/item['local']
            if not path.exists() and path.name=='01 MAIN ASM Ender_3.STEP':
                skipped.append(path.name);continue
            check('source_hash_'+path.name,path.is_file() and sha256(path)==item['sha256'],item['local'])
        check('source_license','GNU GENERAL PUBLIC LICENSE' in (ROOT/'sources/LICENSE').read_text() and 'Version 3' in (ROOT/'LICENSE').read_text(),'Full license accompanies new work and manufacturer sources')
        config=(ROOT/'sources/Configuration.h').read_text()
        check('stock_temperature_protection_evidence',all(re.search(r'^#define '+key+r'\s+'+val+r'\s*$',config,re.M) for key,val in [('TEMP_SENSOR_0','1'),('TEMP_SENSOR_BED','1'),('HEATER_0_MINTEMP','5'),('BED_MINTEMP','5')]) and '#define THERMAL_PROTECTION_HOTENDS' in config and '#define THERMAL_PROTECTION_BED' in config,'Both stock temperature sensors required at ambient above5C; protection unchanged; boot not tested')
        check('manufacturer_travel_limits',all(re.search(r'^#define '+key+r'\s+'+value+r'\s*$',config,re.M)
              for key,value in [('X_BED_SIZE','235'),('Y_BED_SIZE','235'),('X_MIN_POS','0'),('Y_MIN_POS','0'),
                                ('X_MAX_POS','X_BED_SIZE'),('Y_MAX_POS','Y_BED_SIZE')]),
              'Pinned manufacturer configuration defines a 235 mm bed and 0..235 mm XY travel')
        interface=json.loads((ROOT/'sources/interface.json').read_text())
        vendor=cq.importers.importStep(str(ROOT/'sources/E plate.step')).val()
        axes=[]
        for f in vendor.Faces():
            if f.geomType()=='CYLINDER':
                cyl=f._geomAdaptor().Cylinder();loc=cyl.Axis().Location().Coord();dire=cyl.Axis().Direction().Coord()
                if abs(cyl.Radius()-1.5)<1e-6 and abs(dire[2])>.999:
                    axes.append(loc[:2])
        centers=interface['mount_centers_uv_mm']
        check('manufacturer_interface_axes',all(any(math.dist(c,p)<1e-6 for p in axes) for c in centers) and abs(math.dist(*centers)-14)<1e-6,'Independent STEP cylinder extraction verifies both M3 axes and 14mm pitch')
        assembly=json.loads((ROOT/'sources/assembly_parts.json').read_text())
        erow=next(x for x in assembly if x['name']==interface['assembly_e_plate_instance'])
        nrow=next(x for x in assembly if x['name']==interface['assembly_nozzle_instance'])
        nozzle=cq.importers.importStep(str(ROOT/'sources/nozzle.step')).val()
        check('assembly_datum_match',abs(erow['volume']-vendor.Volume())<.001 and abs(nrow['volume']-nozzle.Volume())<.001,'Small source STEP volumes agree with frozen full assembly instance metadata within .001mm3')
        epos=erow['location'][0];npos=nrow['location'][0]
        actual_offset=[16.5-(npos[0]-epos[0]),-(32.2-(npos[2]-epos[2]))]
        check('tool_offset_datum',np.allclose(actual_offset,interface['pen_offset_from_nozzle_xy_mm'],atol=1e-6),str(actual_offset))
        shapes={}
        for name in ('pen_adapter','pen_clamp','hotend_parking_plate'):
            step=ROOT/'exports'/(name+'.step');stl=ROOT/'exports'/(name+'.stl')
            s=cq.importers.importStep(str(step)).val();m=trimesh.load_mesh(stl,process=True);shapes[name]=s
            check(name+'_STEP_solid',s.isValid() and len(s.Solids())==1 and s.Volume()>100,'Reopened STEP: one valid solid')
            check(name+'_STL_closed',m.is_watertight and m.is_winding_consistent and m.volume>0,'Independently loaded mesh is watertight, consistently wound, positive volume')
            diff=abs(s.Volume()-m.volume)/s.Volume();check(name+'_STEP_STL_volume',diff<.003,f'Relative volume difference {diff:.8f}')
            radii=[]
            for f in s.Faces():
                if f.geomType()=='CYLINDER':
                    c=f._geomAdaptor().Cylinder()
                    if abs(c.Axis().Direction().Y())>.999:radii.append(c.Radius())
            if name!='hotend_parking_plate':
                check(name+'_requested_pen_bore',any(abs(r-(req['pen_diameter_mm']+1.2)/2)<1e-6 for r in radii),'Bore radius agrees with current pen diameter plus 1.2mm liner allowance')
            metrics[name+'_reopened_volume_mm3']=s.Volume()
        interference=sum(shapes[name].intersect(vendor).Volume() for name in ('pen_adapter','pen_clamp'))
        check('donor_interference',interference<.001,f'Detailed manufacturer carriage intersection {interference:.9f}mm3')
        radiator=cq.importers.importStep(str(ROOT/'sources/Radiator.step')).val();mount_axes=[]
        for f in radiator.Faces():
            if f.geomType()=='CYLINDER':
                c=f._geomAdaptor().Cylinder()
                if abs(c.Radius()-1.6)<1e-6 and abs(c.Axis().Direction().X())>.999:mount_axes.append(c.Axis().Location().Y())
        check('parking_radiator_interface',any(abs(v-7)<1e-6 for v in mount_axes) and any(abs(v+7)<1e-6 for v in mount_axes),'Actual radiator CAD: 3.2mm through bores with 14mm pitch')
        profile=cq.importers.importStep(str(ROOT/'sources/2020 profile.step')).val().translate((0,0,-10))
        tnut=cq.importers.importStep(str(ROOT/'sources/M4 T-Slot Nut.step')).val().rotate((0,0,0),(0,0,1),90).translate((50,0,-3.5))
        check('parking_tnut_profile_fit',profile.intersect(tnut).Volume()<.001,'Actual vendor solids; 90deg nut orientation in slot')
        layout=cq.importers.importStep(str(ROOT/'exports/plotter.step')).val()
        glb=trimesh.load(ROOT/'exports/plotter.glb',force='scene')
        check('full_layout_exports',layout.isValid() and len(layout.Solids())>=20 and len(glb.geometry)>=20,'STEP/GLB reopened; detailed mount plus >=20 named bodies')
        paper_bounds=verified_paper_bounds(layout,glb,req)
        check('requested_paper_geometry',True,'Reopened STEP and transformed GLB agree with requested centered sheet dimensions and solid volume')
        # Reopen exported GLB in world space, compare total volume to independent STEP read.
        worldmesh=glb.to_geometry();meshvol=float(worldmesh.volume)
        check('GLB_STEP_volume',abs(meshvol-layout.Volume())/layout.Volume()<.003,'World-space GLB volume agrees with full STEP within 0.3%')
        check('explicit_envelopes',sum('REFERENCE_ENVELOPE' in name for name in glb.geometry)>=15,'Reference geometry labels preserved in GLB')
        export_manifest=json.loads((ROOT/'reports/export_manifest.json').read_text())
        check('export_hashes',all((ROOT/p).is_file() and sha256(ROOT/p)==h for p,h in export_manifest.items()),'Build-time export hashes match delivered bytes')
        for image in ('exports/device_render.png','simulation/plotted_drawing.png'):
            from PIL import Image
            with Image.open(ROOT/image) as im:
                im.verify()
            check('image_'+image,True,'PNG decoded independently')
        # Independent, strict subset G-code decoder. It does not call the author replay.
        code=(ROOT/'simulation/example.gcode').read_text();xyz=[117.5,117.5,req['pen_lift_mm']];rows=[];absolute=False;metric=False
        feed=1200.;durations=[];travel_length=0.
        for lineno,line in enumerate(code.splitlines(),1):
            line=line.split(';')[0].strip()
            if not line:continue
            tokens=line.split();cmd=tokens[0];words={}
            allowed=set('XYZF') if cmd in ('G0','G1') else ({'S'} if cmd in ('M104','M140') else set())
            for token in tokens[1:]:
                match=re.fullmatch(r'([A-Z])([+-]?(?:\d+(?:\.\d*)?|\.\d+))',token)
                if not match:raise ValueError('Malformed G-code word '+token)
                key,value=match.groups();value=float(value)
                if key not in allowed or key in words or not math.isfinite(value):raise ValueError('Unknown, duplicate or nonfinite G-code parameter '+key)
                words[key]=value
            if cmd=='G21':metric=True
            elif cmd=='G90':absolute=True
            elif cmd in ('G0','G1'):
                if not(metric and absolute):raise ValueError('Move before G21/G90')
                dest=[words.get(k,xyz[i]) for i,k in enumerate('XYZ')]
                feed=words.get('F',feed)
                if not 0<feed<=1200:raise ValueError('Feed outside digital study0..1200mm/min')
                durations.append((feed,math.dist(xyz,dest)/(feed/60)))
                draw=min(xyz[2],dest[2])==0 and max(xyz[2],dest[2])==0 and math.dist(xyz[:2],dest[:2])>1e-8
                if not draw:travel_length+=math.dist(xyz[:2],dest[:2])
                rows.append((lineno,xyz,dest,draw));xyz=dest
            elif cmd in ('M104','M140'):
                if words.get('S')!=0:raise ValueError('Nonzero heater request')
            elif cmd not in ('M107','M400'):raise ValueError('Unsupported command '+cmd)
        drawing_file = ROOT/'sources/prompt-drawing.json'
        enough_rows = bool(rows) if drawing_file.is_file() else len(rows)>100
        check('Gcode_strict_subset',enough_rows and 'G28' not in code and not re.search(r'\bE-?\d',code),'Metric absolute moves; zero heater commands; no extrusion, homing, machine I/O')
        saved=list(csv.DictReader((ROOT/'simulation/trajectory.csv').open()))
        csvmatch=len(rows)==len(saved)
        for (line,start,end,draw),stored in zip(rows,saved):
            csvmatch &= int(stored['line'])==line and int(stored['drawing'])==int(draw)
            csvmatch &= all(abs(float(stored[k])-v)<1e-7 for k,v in zip(('x0','y0','z0','x1','y1','z1'),start+end))
        csvmatch &= all(abs(float(s['feed_mm_min'])-f)<1e-8 and abs(float(s['duration_s'])-t)<1e-7 for s,(f,t) in zip(saved,durations))
        check('Gcode_CSV_roundtrip',csvmatch,'Independent G-code positions match every stored CSV segment')
        offset=interface['pen_offset_from_nozzle_xy_mm'];expected=[]
        for node in ET.parse(ROOT/'simulation/example.svg').getroot().iter():
            if node.tag.split('}')[-1]!='polyline':continue
            vals=[float(x) for x in re.split(r'[\s,]+',node.attrib['points'].strip())]
            if len(vals)<4 or len(vals)%2 or not all(math.isfinite(v) for v in vals):
                raise ValueError('Malformed source drawing polyline')
            if any(not 0<=x<=100 or not 0<=y<=80 for x,y in zip(vals[::2],vals[1::2])):
                raise ValueError('Source drawing exceeds its declared logical viewport')
            pts=[(117.5+(vals[i]-50)*req['drawing_width_mm']/100,
                  117.5+(40-vals[i+1])*req['drawing_height_mm']/80) for i in range(0,len(vals),2)]
            expected.extend(zip(pts[:-1],pts[1:]))
        if drawing_file.is_file():
            authored=[]
            for stroke in json.loads(drawing_file.read_text()):
                pts=[(117.5+(x-50)*req['drawing_width_mm']/100,
                      117.5+(y-40)*req['drawing_height_mm']/80) for x,y in stroke]
                authored.extend(zip(pts[:-1],pts[1:]))
            check('prompt_artwork_roundtrip',bool(authored) and len(authored)==len(expected)
                  and np.allclose(expected,authored,atol=.00011,rtol=0),
                  'SVG segments trace the archived prompt artwork')
        ink=[([[p[0]+offset[0],p[1]+offset[1]] for p in (start,end)]) for _,start,end,draw in rows if draw]
        check('SVG_Gcode_geometric_roundtrip',len(ink)==len(expected) and np.allclose(ink,expected,atol=.00011),'Every vector pen-down segment agrees after offset and scaling')
        if not ink:raise ValueError('The exported drawing contains no ink segments')
        ink_xy=np.array(ink).reshape(-1,2)
        ink_paper_margin=float(min((ink_xy-paper_bounds[0,:2]).min(),(paper_bounds[1,:2]-ink_xy).min()))
        half=np.array([req['drawing_width_mm'],req['drawing_height_mm']])/2
        ink_viewport_margin=float(min((ink_xy-(117.5-half)).min(),((117.5+half)-ink_xy).min()))
        check('emitted_ink_paper_margin',ink_paper_margin>=10-.00011,'Every decoded ink endpoint leaves 10 mm inside the delivered paper; 0.00011 mm serialization tolerance')
        check('emitted_ink_viewport_containment',ink_viewport_margin>=-.00011,'Decoded ink stays inside the requested source viewport; affine segments are bounded by their endpoints')
        drawlength=sum(math.dist(a,b) for a,b in ink)
        badtravel=sum(math.dist(start[:2],end[:2])>1e-8 and not draw and min(start[2],end[2])<req['pen_lift_mm']-1e-6 for _,start,end,draw in rows)
        check('requested_pen_up_lift',badtravel==0,'All non-drawing XY motion holds current requested Z lift')
        eng=json.loads((ROOT/'reports/engineering.json').read_text());sim=json.loads((ROOT/'reports/simulation.json').read_text())
        check('report_contract',eng['case_id']=='ender3-penplotter' and eng['requirements']==req and sim['requirements']==req and eng['physical_validation_performed'] is False and eng['owned_inventory_count']==0,'Requirements and digital-only donor identity agree')
        cons=eng['constraints'];check('constraint_consistency',len({c['id'] for c in cons})==len(cons) and all(isinstance(c['passed'],bool) for c in cons) and eng['requirements_met']==all(c['passed'] for c in cons),'Unique constraints; requirements_met derives from every constraint')
        actual={'adapter_volume_mm3':shapes['pen_adapter'].Volume(),'cap_volume_mm3':shapes['pen_clamp'].Volume(),'mount_interference_mm3':interference,'draw_length_mm':drawlength,'segment_count':len(rows),'non_drawing_XY_without_lift':badtravel}
        # Recompute EVERY engineering acceptance constraint and reported numeric metric.
        ab=shapes['pen_adapter'].BoundingBox();cb=shapes['pen_clamp'].BoundingBox()
        webfaces=[]
        for f in shapes['pen_adapter'].Faces():
            if f.geomType()=='CYLINDER':
                c=f._geomAdaptor().Cylinder();p=c.Axis().Location().Coord()
                if abs(c.Radius()-1.7)<1e-6 and abs(p[0]-9.5)<1e-6 and abs(p[1]-7.55)<1e-6:webfaces.append(f.BoundingBox())
        if not webfaces:raise ValueError('Missing delivered mounting bore')
        web=webfaces[0].zmax-webfaces[0].zmin;engagement=10-web
        pitch=math.dist(*centers);L=centers[0][1]-ab.ymin;I=ab.xlen*web**3/12
        delta=2*L**3/(3*1400*I);nut_overlap=profile.intersect(tnut).Volume()
        pts=np.array([[p[0]+offset[0],p[1]+offset[1],p[2]] for _,a,b,_ in rows for p in (a,b)])
        minbed=float(min(pts[:,:2].min(),235-pts[:,:2].max()))
        fixture_margin=min(ab.ymin,cb.ymin,vendor.BoundingBox().ymin)-interface['pen_tip_v_mm']-1.
        controller=np.array([b[:2] for _,a,b,d in rows]);ctrlmargin=float(min(controller.min(),235-controller.max()))
        parking_matches=[s for s in layout.Solids() if abs(s.Volume()-shapes['hotend_parking_plate'].Volume())<.001]
        if len(parking_matches)!=1:raise ValueError('Parking plate not uniquely found in exported layout')
        parking_frame_z=parking_matches[0].BoundingBox().zmax-shapes['hotend_parking_plate'].BoundingBox().ymax
        parked_z=parking_frame_z-30-(centers[0][1]-interface['original_nozzle_tip_v_mm'])
        pw,ph=(paper_bounds[1]-paper_bounds[0])[:2]
        paper_margin=float(min(paper_bounds[0,:2].min(),(235-paper_bounds[1,:2]).min()))
        drawing_paper_x=float((pw-req['drawing_width_mm'])/2)
        drawing_paper_y=float((ph-req['drawing_height_mm'])/2)
        viewport_controller_margin=float(min(value for size,delta in zip(
            (req['drawing_width_mm'],req['drawing_height_mm']),actual_offset)
            for value in (117.5-size/2-delta,235-(117.5+size/2-delta))))
        expected_cons={
            'manufacturer_mount_pitch':(pitch,14,abs(pitch-14)<1e-6),
            'donor_interference':(interference,.001,interference<.001),
            'bolt_engagement':(engagement,3,engagement>=3),
            'beam_proxy':(delta,.3,delta<=.3),
            'bed_limited_drawing_width':(req['drawing_width_mm'],190,req['drawing_width_mm']<=190),
            'paper_on_bed':(paper_margin,0,paper_margin>=0),
            'drawing_paper_margin_x':(drawing_paper_x,10,drawing_paper_x>=10),
            'drawing_paper_margin_y':(drawing_paper_y,10,drawing_paper_y>=10),
            'viewport_controller_travel':(viewport_controller_margin,0,viewport_controller_margin>=0),
            'bed_limited_drawing_height':(req['drawing_height_mm'],140,req['drawing_height_mm']<=140),
            'parking_tnut_profile_fit':(nut_overlap,.001,nut_overlap<.001),
            'parking_hotend_clearance':(parked_z-req['pen_lift_mm'],200,parked_z-req['pen_lift_mm']>200),
            'motion_pen_tip_on_bed':(minbed,0,minbed>=0),
            'motion_fixture_vertical_clearance':(fixture_margin,2,fixture_margin>=2),
            'motion_controller_travel':(ctrlmargin,0,ctrlmargin>=0),
            'motion_pen_up_travel':(badtravel,0,badtravel==0),
            'motion_pen_lift_clearance':(req['pen_lift_mm']-1,1,req['pen_lift_mm']>=2),
            'motion_ink_paper_margin':(ink_paper_margin,10,ink_paper_margin>=10-.00011),
            'motion_ink_in_viewport':(ink_viewport_margin,0,ink_viewport_margin>=-.00011),
            'motion_Z_travel':(float(pts[:,2].max()),req['pen_lift_mm'],pts[:,2].min()>=0 and pts[:,2].max()<=req['pen_lift_mm']+1e-6)}
        matching=set(expected_cons)=={c['id'] for c in cons}
        for c in cons:
            if c['id'] not in expected_cons:matching=False;continue
            a,l,p=expected_cons[c['id']]
            matching &= abs(c['actual']-a)<.001 and abs(c['limit']-l)<1e-8 and c['passed']==bool(p)
        check('all_acceptance_constraints_recomputed',matching,'Every claimed engineering actual, limit and pass flag independently derived from reopened geometry and emitted commands')
        sim_cons={c['id']:c for c in sim['constraints']}
        simmatching=set(sim_cons)=={k[7:] for k in expected_cons if k.startswith('motion_')}
        for key,(a,l,p) in expected_cons.items():
            if key.startswith('motion_'):
                c=sim_cons.get(key[7:],{})
                simmatching &= abs(c.get('actual',float('inf'))-a)<.001 and c.get('limit')==l and c.get('passed')==bool(p)
        check('simulation_constraints_recomputed',simmatching and sim['requirements_met']==all(p for k,(a,l,p) in expected_cons.items() if k.startswith('motion_')),'Motion requirement satisfaction recomputed separately')
        actual.update({'paper_width_mm':float(pw),'paper_height_mm':float(ph),'paper_bed_margin_mm':paper_margin,
            'drawing_paper_margin_x_mm':drawing_paper_x,'drawing_paper_margin_y_mm':drawing_paper_y,
            'viewport_controller_margin_mm':viewport_controller_margin,
            'ink_paper_margin_mm':ink_paper_margin,'ink_viewport_margin_mm':ink_viewport_margin,'mount_pitch_mm':pitch,'mount_boss_front_mm':7.,'mount_bolt_engagement_mm':engagement,
            'printed_mass_g_at_1_27_g_cm3':sum(s.Volume() for s in shapes.values())*.00127,
            'plate_to_adapter_airgap_mm':ab.zmin-2.5,'pen_tip_to_clamp_mm':ab.ymin-interface['pen_tip_v_mm'],
            'beam_proxy_deflection_mm_at_2N':delta,'clamp_open_gap_mm':cb.zmin-ab.zmax,
            'clamp_screw_tip_to_plate_mm':cb.zmax-40-2.5,'pen_lift_mm':req['pen_lift_mm'],
            'pen_diameter_mm':req['pen_diameter_mm'],'drawing_width_mm':req['drawing_width_mm'],
            'drawing_height_mm':req['drawing_height_mm'],'parking_plate_volume_mm3':shapes['hotend_parking_plate'].Volume(),
            'parking_tnut_profile_interference_mm3':nut_overlap,'parking_radiator_hole_pitch_mm':14.,
            'travel_length_mm':travel_length,'ideal_feed_time_s':sum(t for f,t in durations),
            'stroke_count':len([n for n in ET.parse(ROOT/'simulation/example.svg').getroot().iter() if n.tag.endswith('polyline')]),
            'pen_center_bed_margin_mm':minbed,'fixture_bed_clearance_mm':fixture_margin,'controller_travel_margin_mm':ctrlmargin,
            'minimum_commanded_Z_mm':float(pts[:,2].min()),'maximum_commanded_Z_mm':float(pts[:,2].max())})
        check('numeric_metric_coverage',set(eng['metrics'])==set(actual),'No unverified quantitative engineering summary fields')
        check('simulation_metrics_recomputed',all(k in actual and abs(v-actual[k])<max(.001,abs(v)*1e-6) for k,v in sim['metrics'].items()),'Every simulation metric independently recomputed')
        check('engineering_summary_recomputed',all(abs(eng['metrics'][k]-v)<max(.001,abs(v)*1e-6) for k,v in actual.items()),'Independent geometry and trajectory agree with numeric summary')
        metrics.update(actual);requirements_met=eng['requirements_met']
    except Exception as exc:
        check('verification_exception',False,type(exc).__name__+': '+str(exc));requirements_met=False;skipped=[]
    result=dict(case_id='ender3-penplotter',artifact_integrity=all(c['passed'] for c in checks),
        requirements_met=bool(requirements_met),physical_validation_performed=False,
        checks=checks,metrics=metrics,excluded_large_provenance_files=skipped,
        verification_scope='Independent local export reopening, source hashes, exact E-plate intersection, SVG/G-code/CSV roundtrip. No hardware or powered tests.')
    write_json(ROOT/'reports/verification.json',result)
    for c in checks:
        if not c['passed']:print('FAIL',c['name'],c['detail'])
    print('artifact_integrity=',result['artifact_integrity'],'requirements_met=',result['requirements_met'],'checks=',len(checks))
    return 0 if result['artifact_integrity'] else 1


if __name__=='__main__':sys.exit(main())
