#!/usr/bin/env python3
"""Read the produced CAD, meshes and physics logs independently of their summary."""
from __future__ import annotations

import argparse
import csv
import json
import itertools
from pathlib import Path
import re
import sys

# Verification must not create import caches in the package being inspected.
sys.dont_write_bytecode = True

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from hs3g_model import dump, sha, source_hashes
from hs3g_sim import assess, freefall_oracle
from build_digital import read_inputs
from study_requirements import validate, constraints, verdict_basis


def read_rows(path):
    with path.open() as handle:
        return [{key:value if key=='phase' else float(value) for key,value in row.items()} for row in csv.DictReader(handle)]


def recording_framing(model,rows,config):
    """Project the complete aircraft envelope at every recorded video frame."""
    import pybullet as p
    c=config['camera'];width,height=c['width_px'],c['height_px']
    lo,hi=np.array(model['bounds_m'])-model['centre_of_mass_m']
    corners=np.array(list(itertools.product(*zip(lo,hi))))
    view=np.array(p.computeViewMatrixFromYawPitchRoll(c['target_m'],c['distance_m'],c['yaw_deg'],c['pitch_deg'],0,2)).reshape(4,4,order='F')
    proj=np.array(p.computeProjectionMatrixFOV(c['fov_deg'],width/height,.01,8)).reshape(4,4,order='F')
    pixels=[]
    for row in rows[::config['physics_hz']//config['render_hz']]:
        R=np.array(p.getMatrixFromQuaternion([row['quat_'+a] for a in 'xyzw'])).reshape(3,3)
        points=corners@R.T+np.array([row['pos_m_'+a] for a in 'xyz'])
        clip=np.c_[points,np.ones(8)]@(proj@view).T
        ndc=clip[:,:3]/clip[:,3:]
        pixels.extend(np.c_[(ndc[:,0]+1)*width/2,(1-ndc[:,1])*height/2])
    pixels=np.array(pixels);low=pixels.min(axis=0);high=pixels.max(axis=0)
    return {'accepted':bool(low[0]>=8 and high[0]<=width-8 and low[1]>=c['header_px']+8 and high[1]<=height-8),
            'min_xy_px':low.tolist(),'max_xy_px':high.tolist(),'header_bottom_px':c['header_px'],'margin_px':8}


def verify(out: Path, design_dir: Path):
    import cadquery as cq
    import trimesh
    from PIL import Image
    model = json.loads((out/'model.json').read_text())
    requirements = validate(model.get('requirements'))
    config, table = read_inputs(requirements)
    report = json.loads((out/'SIMULATION.json').read_text())
    design = json.loads((design_dir/'results.json').read_text())
    checks = {}
    checks['source_identity'] = model.get('source_sha256')==source_hashes()==report.get('source_sha256')
    checks['same_verified_design'] = model.get('design_results_sha256')==sha(design_dir/'results.json') and model.get('design_verification_sha256')==sha(design_dir/'verification.json')
    checks['declared_simulation_contract'] = json.loads((out/'simulation-contract.json').read_text())==config
    checks['packaged_thrust_table'] = json.loads((out/'thrust-table.json').read_text())==table
    checks['standalone_runtime_source'] = sha(out/'hs3g_sim.py')==sha(HERE/'hs3g_sim.py') and sha(out/'RERUN.py')==sha(HERE/'rerun_simulation.py')
    checks['standalone_requirements_source'] = sha(out/'study_requirements.py')==sha(HERE/'study_requirements.py')
    checks['redistributed_licences'] = sha(out/'THREE-LICENSE.txt')==sha(HERE/'vendor/THREE-LICENSE.txt') and sha(out/'HS-LICENSE.txt')==sha(HERE/'vendor/HS-LICENSE.txt')
    checks['same_aircraft_mass'] = abs(model['mass_kg']*1000-design['mass']['auw_g']-requirements['payload_mass_g'])<1e-8
    payloads = [p for p in model['mass_proxies'] if p['id']=='study_payload']
    checks['declared_payload_mass'] = (len(payloads)==1 and payloads[0]['mass_g']==requirements['payload_mass_g']) if requirements['payload_mass_g'] else not payloads
    payload_parts = [p for p in model['parts'] if p['id']=='study_payload']
    checks['payload_geometry'] = not payload_parts and not requirements['payload_mass_g']
    if requirements['payload_mass_g'] and len(payload_parts)==1 and len(payloads)==1:
        vertices = np.array(payload_parts[0]['vertices_m'])
        f = design['frame_parameters']
        expected_centre = [.016, 0, (f['bottom_t_mm']+f['standoff_len_mm']+f['top_t_mm']+4)/1000]
        checks['payload_geometry'] = bool(np.allclose(np.ptp(vertices,axis=0),[.014,.012,.008],atol=1e-7)
                                           and np.allclose(vertices.mean(axis=0),expected_centre,atol=1e-7)
                                           and np.allclose(payloads[0]['centre_m'],expected_centre,atol=1e-9))
    payload_parts = [p for p in model['parts'] if p['id']=='study_payload']
    if requirements['payload_mass_g']:
        expected_centre = [0.016, 0, (design['frame_parameters']['bottom_t_mm'] + design['frame_parameters']['standoff_len_mm'] + design['frame_parameters']['top_t_mm'] + 4)/1000]
        checks['payload_geometry_and_location'] = len(payload_parts)==1 and np.allclose(
            np.ptp(np.array(payload_parts[0]['vertices_m']), axis=0), [.014, .012, .008], atol=1e-7) and np.allclose(
            payloads[0]['centre_m'], expected_centre, atol=1e-7)
    else:
        checks['payload_geometry_and_location'] = not payload_parts
    checks['same_rotor_layout'] = np.allclose(np.array(model['rotor_centres_m'])[:,:2],np.array(design['measured']['motor_centres_mm'])/1000,atol=1e-9)
    checks['four_rotors'] = sum(p['rotor_index'] is not None for p in model['parts'])==4
    checks['native_frame_identified'] = {p['id'] for p in model['parts'] if p['native_frame']}=={'bottom_plate','top_plate'}
    proxy_mass = sum(x['mass_g'] for x in model['mass_proxies'])/1000
    cg = sum(x['mass_g']*np.array(x['centre_m']) for x in model['mass_proxies'])/(proxy_mass*1000)
    tensor = np.zeros((3,3))
    for x in model['mass_proxies']:
        delta = np.array(x['centre_m'])-cg
        tensor += np.array(x['inertia_about_own_centre_kg_m2']) + x['mass_g']/1000*(np.dot(delta,delta)*np.eye(3)-np.outer(delta,delta))
    checks['mass_inertia_rollup'] = abs(proxy_mass-model['mass_kg'])<1e-10 and np.allclose(cg,model['centre_of_mass_m'],atol=1e-10) and np.allclose(tensor,model['inertia_tensor_kg_m2'],atol=1e-12)
    checks['positive_inertia'] = bool((np.linalg.eigvalsh(tensor)>0).all())
    checks['small_omitted_products_of_inertia'] = model['inertia_off_diagonal_relative_max']<.05
    assembly = cq.importers.importStep(str(out/'HS3G_B_ASSEMBLY.step'))
    solids = assembly.val().Solids()
    checks['native_step_assembly'] = len(solids)==len(model['parts']) and all(s.isValid() for s in solids)
    for plate, key in [('bottom','bottom_volume_mm3'),('top','top_volume_mm3')]:
        checks['retained_native_'+plate+'_volume'] = any(abs(s.Volume()-design['measured'][key])<.02 for s in solids)
    glb = trimesh.load(out/'HS3G_B_ASSEMBLY.glb',force='scene')
    checks['glb_geometry_and_scale'] = len(glb.geometry)==len(model['parts']) and np.allclose(glb.bounds,model['bounds_m'],atol=1e-6)
    bb = assembly.val().BoundingBox()
    checks['step_and_glb_dimensions'] = np.allclose([bb.xlen,bb.ylen,bb.zlen],np.ptp(glb.bounds,axis=0)*1000,atol=.05)
    for item in model['parts']:
        mesh = trimesh.Trimesh(item['vertices_m'],item['faces'],process=True)
        checks['mesh_'+item['id']] = bool(mesh.is_watertight and mesh.volume>0)
    page = (out/'VIEWER.html').read_text()
    inline = re.search(r'<script id="model-data" type="application/json">(.*?)</script>',page,re.S)
    viewer = json.loads(inline.group(1)) if inline else {}
    checks['offline_viewer_contains_native_model'] = viewer.get('model')==model and (HERE/'vendor/three.min.js').read_text() in page
    checks['viewer_scenario_masses'] = viewer.get('scenario_mass_kg') == {s['id']: model['mass_kg']+s.get('extra_mass_g',0)/1000 for s in config['scenarios']}
    application = page.rsplit('<script>',1)[-1]
    checks['viewer_no_network_dependency'] = not re.search(r'<script[^>]+src=|<link[^>]+href=["\']https?://',page) and 'fetch(' not in application
    assessments = [];framing=None
    for scenario in config['scenarios']:
        name = scenario['id']
        rows = read_rows(out/(name+'.csv'))
        if name=='nominal':
            framing=recording_framing(model,rows,config)
            checks['nominal_recording_framing']=framing['accepted']
        evaluated = assess(rows,model,config,scenario)
        assessments.append(evaluated)
        for key,value in evaluated['checks'].items():checks[name+'_'+key]=bool(value)
        checks[name+'_complete_duration'] = len(rows)==round(scenario.get('duration_s',config['duration_s'])*config['physics_hz'])
        expected_records = rows[::config['physics_hz']//config['control_hz']]
        if expected_records[-1] is not rows[-1]:expected_records.append(rows[-1])
        actual_records = viewer.get('scenarios',{}).get(name,[])
        checks[name+'_viewer_matches_physics'] = len(actual_records)==len(expected_records) and all(
            actual['t']==expected['t_s'] and actual['p']==[expected['pos_m_'+axis] for axis in 'xyz']
            and actual['q']==[expected['quat_'+axis] for axis in 'xyzw']
            and actual['rpm']==[expected[f'rpm_{i}'] for i in range(1,5)]
            for actual,expected in zip(actual_records,expected_records))
    simulation_ok = all(x['accepted'] for x in assessments) and report.get('gravity_oracle',{}).get('accepted') is True
    mass_constraints = constraints(model,requirements,assessments)
    checks['simulation_summary_matches_logs'] = assessments==report.get('scenarios') and report.get('simulation_acceptance') == simulation_ok
    checks['requirements_match_model'] = report.get('requirements') == requirements
    checks['constraints_match_model'] = report.get('constraints') == mass_constraints
    requirements_met = simulation_ok and all(x['passed'] for x in mass_constraints)
    checks['requirements_summary_matches'] = report.get('requirements_met') == requirements_met
    for constraint in mass_constraints:
        checks[constraint['id']+'_requirement'] = constraint['passed']
    oracle = freefall_oracle(model,table,config)
    checks['native_zero_thrust_gravity_oracle'] = oracle['accepted'] and oracle==report.get('gravity_oracle')
    for name in ['ASSEMBLY.png','EXPLODED.png','TELEMETRY.png']:
        with Image.open(out/name) as pic:
            checks[name+'_readable'] = pic.width>=700 and pic.height>=400
    with Image.open(out/'FLIGHT.gif') as gif:
        checks['native_flight_animation'] = gif.n_frames>=config['duration_s']*config['render_hz']-1 and gif.width>=480
    checks['digital_scope_only'] = report.get('requested_scope')=='digital_only_3d_representation_and_simulation' and report.get('physical_work_requested') is False and report.get('physical_validation') is False
    accepted = all(checks.values())
    # A valid computation may fail engineering requirements. Never publish corrupt
    # telemetry/CAD as a valid revision, but retain an honest failed design study.
    integrity_checks = dict(checks)
    integrity_checks.pop('small_omitted_products_of_inertia')
    for c in mass_constraints:
        integrity_checks.pop(c['id']+'_requirement')
    for assessed in assessments:
        for key in assessed['checks']:
            if key not in {'finite_state','timebase','position_velocity_consistency','native_force_balance'}:
                integrity_checks.pop(assessed['scenario']['id']+'_'+key)
    result = {'schema':'hardware_splicer.hs3g_digital_verification.v1',
              'digital_objective_complete':accepted,'engineering_acceptance':accepted,
              'artifact_integrity': all(integrity_checks.values()),
              'integrity_checks': integrity_checks, 'requirements_met': accepted,
              'mass_budget': all(c['passed'] for c in mass_constraints if c.get('kind')=='mass_budget'),
              'verdict_basis': verdict_basis(requirements),
              'scope':'Native 3D representative, offline physics playback and parameterized PyBullet mission/failure study',
              'checks':checks,'failed_checks':[k for k,v in checks.items() if not v],
              'scenarios':assessments,'native_gravity_oracle':oracle,'recording_framing':framing,
              'physical_work_requested':False,'physical_validation':False,
              'fabrication_authorized':False,'power_on_authorized':False,'flight_authorized':False,
              'scope_limits':config['scope_limits'],
              'open_actions':[] if accepted else ['Resolve failed digital acceptance checks.']}
    result['artifact_sha256']={p.relative_to(out).as_posix():sha(p) for p in sorted(out.rglob('*')) if p.is_file() and p.name!='verification.json' and '__pycache__' not in p.parts}
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('package',type=Path);p.add_argument('--design',type=Path,required=True)
    p.add_argument('--study',action='store_true',help='Accept intact runs even when engineering requirements fail')
    p.add_argument('--out',type=Path,help='Write JSON outside the verified directory (default: stdout)')
    args=p.parse_args()
    if args.out and args.out.resolve().is_relative_to(args.package.resolve()):
        p.error('--out must be outside the verified directory')
    try:
        r=verify(args.package,args.design)
    except (OSError,ValueError,KeyError) as exc:
        r={'engineering_acceptance':False,'digital_objective_complete':False,'error':str(exc)}
    if args.out:
        dump(args.out,r)
    else:
        print(json.dumps(r,indent=2,allow_nan=False))
    if 'error' in r:
        print(r['error'],file=sys.stderr);return 1
    accepted = r['artifact_integrity'] if args.study else r['digital_objective_complete']
    return 0 if accepted else 1


if __name__=='__main__':
    raise SystemExit(main())
