"""The existing HS-3G-B CAD and mass layout, expressed as a digital assembly.

Frame solids are native STEP. Electronics, blades and other components are
explicitly representative geometry. SI units are used for dynamics and GLB;
the named editable STEP assembly retains the source millimetre convention.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
sys.path.insert(0, str(BASE))
import hs3g_design as design
from study_requirements import validate


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_hashes():
    paths = [*sorted(HERE.glob('*.py')), HERE / 'simulation.json', HERE / 'viewer.html',
             *sorted((HERE / 'vendor').glob('*'))]
    return {p.relative_to(HERE).as_posix(): sha(p) for p in paths if p.is_file()}


def mesh_of(shape):
    import trimesh
    vertices, faces = shape.tessellate(0.08)
    return trimesh.Trimesh(vertices=np.array([v.toTuple() for v in vertices]) / 1000,
                           faces=np.array(faces), process=True)


def mass_properties(proxies):
    """Combine volume-derived inertia tensors using the parallel-axis theorem."""
    total = sum(m for _, m in proxies)
    centre = sum(mesh.center_mass * m for mesh, m in proxies) / total
    tensor = np.zeros((3, 3))
    for mesh, mass in proxies:
        props = mesh.mass_properties
        delta = props.center_mass - centre
        tensor += props.inertia * (mass / props.mass)
        tensor += mass * (np.dot(delta, delta) * np.eye(3) - np.outer(delta, delta))
    return total, centre, tensor


def build_model(design_dir: Path, out: Path, requirements=None):
    import cadquery as cq
    import trimesh
    requirements = validate(requirements)
    r = json.loads((design_dir / 'results.json').read_text())
    receipt = json.loads((design_dir / 'verification.json').read_text())
    if receipt.get('engineering_acceptance') is not True:
        raise ValueError('The same source drone must pass its digital design checks first')
    for name, digest in receipt['artifact_sha256'].items():
        if sha(design_dir / name) != digest:
            raise ValueError('Design artifact changed after verification: ' + name)
    f = r['frame_parameters']
    masses = {x['id']: x['total_g'] for x in r['mass']['rows']}
    assembly = cq.Assembly(name='HS3G_B_DIGITAL_REPRESENTATIVE')
    visuals, proxies, proxy_records = [], [], []
    colours = {'carbon': [0.09, 0.13, 0.18, 1], 'gold': [0.91, 0.65, 0.22, 1],
               'pcb': [0.08, 0.43, 0.35, 1], 'battery': [0.12, 0.24, 0.46, 1],
               'front': [0.22, 0.78, 0.96, 1], 'back': [0.96, 0.38, 0.22, 1]}

    def box(size, centre):
        return cq.Workplane('XY').box(*size).val().translate(tuple(centre))

    def cylinder(radius, height, centre):
        return cq.Workplane('XY').circle(radius).extrude(height).val().translate(tuple(centre))

    def add(name, label, shape, colour, explode, *, rotor=None):
        mesh = mesh_of(shape)
        if not mesh.is_watertight or mesh.volume <= 0:
            raise ValueError('Invalid representative mesh: ' + name)
        assembly.add(shape, name=name, color=cq.Color(*colour))
        entry = {'id': name, 'label': label, 'colour': colour,
                 'vertices_m': np.round(mesh.vertices, 7).tolist(), 'faces': mesh.faces.tolist(),
                 'explode_m': explode, 'rotor_index': rotor,
                 'native_frame': name in {'bottom_plate', 'top_plate'}}
        visuals.append((entry, mesh))
        return mesh

    def mass(name, mesh, grams):
        proxies.append((mesh, grams / 1000))
        proxy_records.append({'id': name, 'mass_g': grams,
                              'centre_m': mesh.center_mass.tolist(),
                              'inertia_about_own_centre_kg_m2': (mesh.mass_properties.inertia * grams / 1000 / mesh.mass_properties.mass).tolist()})

    frame_volume = sum(r['measured'][k] for k in ['bottom_volume_mm3', 'top_volume_mm3'])
    for name, volume in [('bottom_plate', 'bottom_volume_mm3'), ('top_plate', 'top_volume_mm3')]:
        shape = cq.importers.importStep(str(design_dir / 'finished_geometry' / ('hs3g_' + name + '.step'))).val()
        if name == 'top_plate':
            shape = shape.translate((0, 0, f['bottom_t_mm'] + f['standoff_len_mm']))
        mesh = add(name, name.replace('_', ' ').title(), shape, colours['carbon'], [0, 0, 0.06 if name == 'top_plate' else 0])
        mass(name, mesh, masses['frame_cut'] * r['measured'][volume] / frame_volume)

    motors = r['measured']['motor_centres_mm']
    layout = design.layout(f, r['parts'], motors)
    rotor_centres = []
    counter = {}
    for item in layout:
        pid = item['id']
        if pid == 'top_plate':
            continue
        counter[pid] = counter.get(pid, 0) + 1
        name = f'{pid}_{counter[pid]}'
        x, y = item['xy']
        if pid == 'battery':
            x = r['cg']['battery_x_mm']
        low, high = item['z']
        centre = [x, y, (low + high) / 2]
        size = [2 * item['half'][0], 2 * item['half'][1], high - low]
        proxy = box(size, centre)
        colour, explode = colours['pcb'], [0, 0, 0.03]
        if pid == 'motor':
            shape = cylinder(item['half'][0], high - low, [x, y, low])
            colour = colours['front' if x > 0 else 'back']; explode = [x / 1600, y / 1600, 0.025]
            mesh = add(name, f'Motor M{counter[pid]}', shape, colour, explode)
            mass(name, mesh, masses['motor'] / 4)
            rotor_centres.append([x / 1000, y / 1000, high / 1000])
            continue
        if pid == 'standoff':
            shape = cq.Workplane('XY').polygon(6, 2 * f['standoff_af_mm'] / np.sqrt(3)).extrude(high-low)
            shape = shape.cut(cq.Workplane('XY').circle(1.25).extrude(high-low)).val().translate((x, y, low))
            mesh = add(name, 'Frame standoff', shape, colours['gold'], [x / 1500, y / 1500, 0.02])
            mass(name, mesh, masses['standoff'] / 4)
            continue
        if pid == 'stack':
            # Display two PCBs; retain the declared envelope as the inertia proxy.
            mass('stack_envelope', mesh_of(proxy), masses['stack'])
            for board, z in [('ESC', low + 0.8), ('FC', high - 0.8)]:
                add('stack_' + board, board + ' circuit board', box([32, 35, 1.6], [x, y, z]), colours['pcb'], [0, 0, 0.04 if board == 'FC' else 0.02])
                for sx in [-1, 1]:
                    for sy in [-1, 1]:
                        add(f'{board}_grommet_{sx}_{sy}', 'Stack damper', cylinder(2.6, 3, [sx*10, sy*10, z-1.5]), colours['carbon'], [0, 0, 0.04 if board == 'FC' else 0.02])
            continue
        if pid == 'battery':
            colour, explode = colours['battery'], [0, 0, -0.04]
        elif pid == 'gps':
            colour, explode = [0.83, 0.76, 0.58, 1], [0, 0, 0.085]
        elif pid == 'camera':
            colour, explode = colours['carbon'], [0.035, 0, 0.015]
        mesh = add(name, pid.upper() if pid in {'gps', 'vtx'} else pid.title(), proxy, colour, explode)
        mass(name, mesh, masses[pid])
        if pid == 'camera':
            lens = cq.Workplane('YZ').circle(3.5).extrude(3).val().translate((x+size[0]/2, y, centre[2]))
            add('camera_lens', 'Representative lens', lens, [0.08, 0.24, 0.30, 1], explode)

    prop = design.part(r['parts'], 'prop')
    radius = prop['diameter_mm'] / 2
    for i, (x, y, z) in enumerate(rotor_centres):
        z *= 1000; x *= 1000; y *= 1000
        hub = cq.Workplane('XY').circle(3.1).extrude(prop['hub_height_mm'])
        for angle in [0, 120, 240]:
            blade = cq.Workplane('XY').polyline([(2, -2), (radius*0.8, -4), (radius, -1), (radius*0.93, 2), (8, 3.5)]).close().extrude(0.85)
            hub = hub.union(blade.rotate((0,0,0), (0,0,1), angle))
        shape = hub.val().translate((x, y, z))
        mesh = add(f'prop_{i+1}', f'Propeller M{i+1}', shape, colours['front' if x > 0 else 'back'], [x/1600, y/1600, 0.065], rotor=i)
        mass(f'prop_{i+1}', mesh, masses['prop'] / 4)

    spread = r['mass']['auw_g'] - sum(m * 1000 for _, m in proxies)
    if not 25 < spread < 28:
        raise ValueError('Unexpected wiring/hardware mass remainder')
    mass('hardware_and_wiring_allowance', mesh_of(box([f['body_l_mm'], f['body_w_mm'], 16], [0, 0, 8])), spread)
    # Representative strap, excluded from the mass model because hardware is already budgeted.
    for z in [-33.75, f['bottom_t_mm'] + 0.75]:
        add('strap_' + ('bottom' if z < 0 else 'top'), 'Battery strap', box([43, 10, 1.5], [0, 0, z]), [0.16, 0.17, 0.19, 1], [0,0,-0.04 if z < 0 else 0])
    if requirements['payload_mass_g']:
        # Explicit representative mounted above the front of the retained top plate.
        # Assigned mass, not material density or a claim of a physical attachment.
        z = f['bottom_t_mm'] + f['standoff_len_mm'] + f['top_t_mm'] + 4
        payload = add('study_payload', 'Study payload', box([14, 12, 8], [16, 0, z]),
                      [0.66, 0.35, 0.91, 1], [0, 0, .065])
        mass('study_payload', payload, requirements['payload_mass_g'])
    total, cg, tensor = mass_properties(proxies)
    scene = trimesh.Scene()
    for entry, mesh in visuals:
        mesh.visual.face_colors = (np.array(entry['colour']) * 255).astype(np.uint8)
        scene.add_geometry(mesh, node_name=entry['id'], geom_name=entry['id'])
    assembly.save(str(out / 'HS3G_B_ASSEMBLY.step'))
    (out / 'HS3G_B_ASSEMBLY.glb').write_bytes(scene.export(file_type='glb'))
    bounds = np.array([mesh.bounds for _, mesh in visuals])
    bmin, bmax = bounds[:,0,:].min(axis=0), bounds[:,1,:].max(axis=0)
    off_diagonal = tensor - np.diag(np.diag(tensor))
    model = {'schema': 'hardware_splicer.hs3g_digital_model.v1', 'revision': 'HS-3G-B',
             'units': 'metres, kilograms, seconds; editable STEP uses millimetres',
             'requirements': requirements,
             'payload_representation': '14 x 12 x 8 mm box above front top plate; assigned mass; rigid attachment assumed.',
             'parts': [entry for entry, _ in visuals], 'mass_proxies': proxy_records,
             'mass_kg': total, 'centre_of_mass_m': cg.tolist(),
             'inertia_tensor_kg_m2': tensor.tolist(), 'dynamics_inertia_diagonal_kg_m2': np.diag(tensor).tolist(),
             'inertia_off_diagonal_relative_max': float(np.max(np.abs(off_diagonal)) / np.min(np.diag(tensor))),
             'inertia_approximation': 'Body axes use the calculated diagonal; small products of inertia are omitted and reported.',
             'rotor_centres_m': rotor_centres, 'rotor_spin_signs': [1,-1,1,-1],
             'bounds_m': [bmin.tolist(), bmax.tolist()],
             'collision_approximation': 'One axis-aligned assembly envelope; rigid ground contact, no flexible-frame or blade contact model.',
             'design_results_sha256': sha(design_dir / 'results.json'),
             'design_verification_sha256': sha(design_dir / 'verification.json'),
             'representation': 'Native frame plus representative components and propeller blades; not vendor-detailed CAD.',
             'source_sha256': source_hashes()}
    dump(out / 'model.json', model)
    return model
