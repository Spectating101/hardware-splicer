#!/usr/bin/env python3
"""Deliver the same HS-3G-B as a digital-only 3D assembly and physics study."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from hs3g_model import build_model, dump, sha
from hs3g_sim import run, assess, freefall_oracle
from study_requirements import validate, configure, constraints


def read_inputs(requirements=None):
    return (configure(json.loads((HERE/'simulation.json').read_text()), requirements),
            json.loads((HERE.parent/'revision_b/inputs/thrust_table.json').read_text()))


def plot_telemetry(out, simulations):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2,2,figsize=(12,8),layout='constrained')
    colours = ['#0784a0','#8a63c8','#d16a32']
    for (name, rows), colour in zip(simulations.items(), colours):
        t = [x['t_s'] for x in rows]
        axes[0,0].plot([x['pos_m_x'] for x in rows],[x['pos_m_y'] for x in rows],label=name,color=colour)
        axes[0,1].plot(t,[x['pos_m_z'] for x in rows],color=colour,label=name)
        error = [sum((x['pos_m_'+a]-x['target_m_'+a])**2 for a in 'xyz')**.5 for x in rows]
        axes[1,0].plot(t,error,color=colour,label=name)
    nominal = simulations['nominal']
    axes[0,0].plot([x['target_m_x'] for x in nominal],[x['target_m_y'] for x in nominal],'--',color='#b88b2e',label='target')
    axes[0,0].set(xlabel='x (m)',ylabel='y (m)',title='Actual simulated path');axes[0,0].axis('equal')
    axes[0,1].plot([x['t_s'] for x in nominal],[x['target_m_z'] for x in nominal],'--',color='#b88b2e',label='target')
    axes[0,1].set(xlabel='Time (s)',ylabel='Altitude (m)',title='Takeoff and ground contact')
    axes[1,0].set(xlabel='Time (s)',ylabel='Position error (m)',title='Tracking and injected motor loss')
    for i in range(4):
        axes[1,1].plot([x['t_s'] for x in nominal],[x[f'rpm_{i+1}'] for x in nominal],label=f'M{i+1}')
    axes[1,1].set(xlabel='Time (s)',ylabel='Motor speed (rpm)',title='Nominal motor outputs')
    for ax in axes.flat:
        ax.grid(alpha=.2);ax.legend(fontsize=8)
    fig.suptitle('HS-3G-B · Native PyBullet rigid-body simulation · Not physical measurements',fontsize=14)
    fig.savefig(out/'TELEMETRY.png',dpi=130);plt.close(fig)


def write_viewer(out, model, simulations, config):
    playback = {}
    stride = config['physics_hz']//config['control_hz']
    for name, rows in simulations.items():
        records = []
        angle = np.zeros(4)
        for tick, row in enumerate(rows):
            rpm = np.array([row[f'rpm_{i+1}'] for i in range(4)])
            angle = (angle+rpm*2*np.pi/60/config['physics_hz']*model['rotor_spin_signs'])%(2*np.pi)
            if tick%stride == 0 or tick == len(rows)-1:
                records.append({'t':row['t_s'], 'p':[row['pos_m_'+a] for a in 'xyz'],
                                'q':[row['quat_'+a] for a in 'xyzw'], 'target':[row['target_m_'+a] for a in 'xyz'],
                                'rpm':rpm.tolist(), 'angles':angle.tolist(),
                                'current':row['current_a_est'], 'phase':row['phase']})
        playback[name] = records
    data = {'model':model,'scenarios':playback,'playback_hz':config['control_hz'],
            'scenario_mass_kg': {s['id']: model['mass_kg'] + s.get('extra_mass_g', 0)/1000 for s in config['scenarios']}}
    vendor = (HERE/'vendor/three.min.js').read_text()
    page = (HERE/'viewer.html').read_text().replace('/*THREE_VENDOR*/',vendor)
    page = page.replace('/*MODEL_DATA*/',json.dumps(data,separators=(',',':'),allow_nan=False).replace('</',r'<\/'))
    (out/'VIEWER.html').write_text(page)
    shutil.copyfile(HERE/'vendor/THREE-LICENSE.txt',out/'THREE-LICENSE.txt')
    shutil.copyfile(HERE/'vendor/HS-LICENSE.txt',out/'HS-LICENSE.txt')


def build(design_dir: Path, out: Path, requirements=None):
    if out.exists() and any(out.iterdir()):
        raise ValueError('Use a new/empty output directory')
    out.mkdir(parents=True,exist_ok=True)
    requirements = validate(requirements)
    config, table = read_inputs(requirements)
    dump(out/'simulation-contract.json',config)
    dump(out/'thrust-table.json',table)
    shutil.copyfile(HERE/'hs3g_sim.py',out/'hs3g_sim.py')
    shutil.copyfile(HERE/'study_requirements.py',out/'study_requirements.py')
    shutil.copyfile(HERE/'rerun_simulation.py',out/'RERUN.py')
    (out/'REQUIREMENTS.txt').write_text('numpy>=2,<3\npybullet==3.2.7\npillow>=10\n')
    model = build_model(design_dir,out,requirements)
    simulations, results = {}, []
    for scenario in config['scenarios']:
        rows = run(model,table,config,scenario,out,render=scenario['id']=='nominal')
        simulations[scenario['id']] = rows
        result = assess(rows,model,config,scenario);results.append(result)
        print(json.dumps({'scenario':scenario['id'],'accepted':result['accepted'],'metrics':result['metrics']},allow_nan=False),flush=True)
    oracle = freefall_oracle(model,table,config)
    mass_constraints = constraints(model, requirements)
    simulation_ok = all(x['accepted'] for x in results) and oracle['accepted']
    report = {'schema':'hardware_splicer.hs3g_digital_simulation.v1',
              'requested_scope':'digital_only_3d_representation_and_simulation',
              'engine':'PyBullet DIRECT, 240 Hz native rigid-body integration',
              'controller':'Simulation position PID / SO(3) attitude PD, 60 Hz',
              'simulation_acceptance':simulation_ok,
              'requirements': requirements, 'constraints': mass_constraints,
              'requirements_met': simulation_ok and all(x['passed'] for x in mass_constraints),
              'scenarios':results,'gravity_oracle':oracle,
              'scope_limits':config['scope_limits'],
              'physical_work_requested':False, 'physical_validation':False,
              'source_sha256':model['source_sha256']}
    dump(out/'SIMULATION.json',report)
    plot_telemetry(out,simulations)
    write_viewer(out,model,simulations,config)
    (out/'README.md').write_text(
        '# HS-3G-B completed digital study\n\n'
        'The requested deliverable is digital only. No parts or hardware are needed.\n\n'
        f'Study payload: {requirements["payload_mass_g"]:.2f} g. Mass limit: {requirements["max_mass_g"]:.2f} g. '
        f'Gust force scale: {requirements["gust_scale"]:.2f}. Requirements met: {report["requirements_met"]}. '
        'A completed computation can retain failed engineering requirements; inspect `SIMULATION.json` and `verification.json`.\n\n'
        '**Start with `VIEWER.html`: open it directly in a WebGL browser.** It contains its 3D library, model and recorded states, and makes no network requests. Orbit, zoom, explode the assembly, choose a scenario, play, pause and scrub. PNG/GIF views are included if WebGL is unavailable.\n\n'
        '## Included results\n\n'
        '- `HS3G_B_ASSEMBLY.step`: named editable assembly in millimetres; native retained frame and explicitly representative components.\n'
        '- `HS3G_B_ASSEMBLY.glb`: coloured assembly in metres for ordinary 3D viewers.\n'
        '- `ASSEMBLY.png`, `EXPLODED.png`, `FLIGHT.gif`: actual native PyBullet camera renders.\n'
        '- `nominal.csv`, `mass_plus_5g.csv`, `motor_failure.csv`: full 240 Hz physics states, forces, targets, rotor RPMs and estimated current.\n'
        '- `TELEMETRY.png`: paths, altitude, position error and motor outputs.\n'
        '- `model.json`: geometry, mass proxies, centre of mass and inertia tensor.\n'
        '- `SIMULATION.json`, `simulation-contract.json`, `verification.json`: assumptions, acceptance results and artifact identities.\n\n'
        '## What was simulated\n\n'
        'The existing 137 mm HS-3G-B design is the model, rather than the separate legacy Crazyflie demonstration. '
        f'Its modeled mass is {model["mass_kg"]*1000:.2f} g. Native frame geometry and the retained component layout define the mass distribution. '
        'The sourced F1404 KV2900/GF3028-3 table defines rotor force; behavior below its first row is extrapolated. '
        'PyBullet integrates the body under per-rotor thrust, yaw torque, gravity, drag, a gust and ground contact. '
        'The controller reads the simulated state; it never resets the aircraft to its target. '
        'Nominal and +5 g mass-uncertainty missions request takeoff, square tracking, turning, gust recovery and landing. '
        'Telemetry and acceptance checks record what each mission achieved. '
        'The extra 5 g sensitivity case adds uncertainty at the modeled centre of mass; the controller still uses nominal mass. '
        'A requested study payload is a separate visible box above the top plate and changes nominal mass, centre of mass and inertia. '
        'The stopped-motor scenario deliberately loses control and reaches the ground; detecting that loss is the expected digital result.\n\n'
        'This is a parameterized representative, not a physically calibrated twin. The assembly uses simplified electronics and blades. '
        'The full calculated inertia tensor is recorded; the small off-diagonal terms are omitted by the dynamics model. '
        'Motor lag, yaw torque, drag and gains are declared assumptions. State feedback is ideal. '
        'There is no sensor/RF, INAV SITL, frame-flexibility, CFD, battery-chemistry or thermal simulation. '
        'Estimated current and short-mission energy are not measured endurance. '
        'The separate design package retains its firmware research; this simulation does not execute or flash that firmware.\n\n'
        '## Completion\n\n'
        'Digital completion requires the native assembly exports, working offline viewer, full mission telemetry, nominal/payload acceptance, detected motor-loss descent, analytic gravity comparison and separate artifact verification. '
        'Physical purchasing, fabrication, calibration and bench work are outside the requested scope and are not digital completion blockers. '
        'No physical performance or permission is established.\n\n'
        'Regenerate via the registered `hs3g_drone_digital` workshop case; see the source directory README for the command and dependencies.\n')
    with (out/'README.md').open('a') as handle:
        handle.write('\n## Run the physics from this folder or the ZIP\n\n'
                     'Install the small runtime into a virtual environment, then run:\n\n'
                     '```bash\npython -m pip install -r REQUIREMENTS.txt\npython RERUN.py --out /path/to/new/simulation-run\n'
                     '# Add --render for fresh camera PNG/GIF output.\n```\n\n'
                     'This runs the solver again from the included model, contract and thrust table. '
                     'It needs neither the full repository nor CadQuery, the browser viewer, a controller board or a network connection after installing the runtime. '
                     'Use a new output directory. The original exported CAD and viewer remain unchanged.\n')
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--design',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--requirements', type=Path, help='Validated digital study requirements JSON')
    args=p.parse_args()
    requirements = json.loads(args.requirements.read_text()) if args.requirements else None
    r=build(args.design,args.out,requirements)
    return 0 if r['requirements_met'] else 2


if __name__=='__main__':
    raise SystemExit(main())
