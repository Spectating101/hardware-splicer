"""Completion of the user's digital-only drone, not unbuilt physical hardware."""
from __future__ import annotations

import csv
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest

from hardware_splicer import workshop_operator as op

ROOT = Path(__file__).resolve().parents[1]
DIGITAL = ROOT/'examples/drone_proving_ground/digital'
DESIGN = ROOT/'examples/drone_proving_ground/revision_b/reference'
REFERENCE = DIGITAL/'reference'


def module(name, file):
    spec=importlib.util.spec_from_file_location(name,DIGITAL/file)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod


def test_digital_scope_does_not_require_parts_or_claim_firmware_execution():
    cfg=json.loads((DIGITAL/'simulation.json').read_text())
    assert cfg['objective'].startswith('Complete a digital-only')
    assert {s['id'] for s in cfg['scenarios']}=={'nominal','mass_plus_5g','motor_failure'}
    assert any('no sensor' in x.lower() for x in cfg['scope_limits'])
    assert any('INAV SITL' in x for x in cfg['scope_limits'])


def test_preview_runs_no_simulation(tmp_path,monkeypatch):
    monkeypatch.setattr(op,'_native_drone_digital',lambda *a:pytest.fail('preview ran physics'))
    result=op.run_workshop_operator(op.DIGITAL_ID,out_dir=tmp_path/'preview')
    assert result['status']=='planned_not_executed'
    assert not result['engineering_acceptance']
    assert result['canonical_machine_release']['allowed'] is False


def test_base_design_acceptance_cannot_complete_a_forged_digital_package(tmp_path,monkeypatch):
    source=ROOT/op.REGISTERED[op.DIGITAL_ID]['source']
    monkeypatch.setattr(op,'_registered_source_files',lambda *a:[source/'hs3g_frame.py'])
    def base(run_dir,source,report):
        stage=run_dir/'source_copy';stage.mkdir()
        shutil.copyfile(source/'hs3g_frame.py',stage/'hs3g_frame.py')
        report['engineering_acceptance']=True
    monkeypatch.setattr(op,'_native_drone',base)
    def fake(*a,**kwargs):
        package=tmp_path/'forged/candidate/digital';package.mkdir(parents=True,exist_ok=True)
        (package/'verification.json').write_text(json.dumps({'engineering_acceptance':True,'digital_objective_complete':True,'checks':{},'artifact_sha256':{},'physical_work_requested':False,'physical_validation':False,'fabrication_authorized':False,'power_on_authorized':False,'flight_authorized':False}))
        return SimpleNamespace(returncode=0,stdout='claimed complete',stderr='')
    monkeypatch.setattr(op.subprocess,'run',fake)
    result=op.run_workshop_operator(op.DIGITAL_ID,out_dir=tmp_path/'forged',execute=True)
    assert result['engineering_acceptance'] is False
    assert result['digital_objective_complete'] is False
    assert result['status']=='blocked_digital_independent_verification'
    assert result['canonical_machine_release']['allowed'] is False


@pytest.fixture(scope='module')
def native(tmp_path_factory):
    pytest.importorskip('numpy');pytest.importorskip('cadquery');pytest.importorskip('pybullet')
    build=module('hs3g_digital_build_test','build_digital.py')
    model_module=module('hs3g_digital_model_test','hs3g_model.py')
    sim=module('hs3g_digital_sim_test','hs3g_sim.py')
    verifier=module('hs3g_digital_verify_test','verify_digital.py')
    out=tmp_path_factory.mktemp('drone-digital-fresh')
    model=model_module.build_model(DESIGN,out)
    config,table=build.read_inputs()
    return model,config,table,sim,verifier,out


@pytest.mark.requires_cadquery
def test_native_assembly_uses_the_same_mass_rotors_and_positive_inertia(native):
    import numpy as np
    model,config,table,sim,verify,out=native
    assert model['mass_kg']==pytest.approx(.2349,abs=1e-10)
    assert len(model['rotor_centres_m'])==4
    assert (np.linalg.eigvalsh(model['inertia_tensor_kg_m2'])>0).all()
    assert model['inertia_off_diagonal_relative_max']<.05
    assert (out/'HS3G_B_ASSEMBLY.step').stat().st_size>10000
    assert (out/'HS3G_B_ASSEMBLY.glb').stat().st_size>10000


@pytest.mark.requires_cadquery
@pytest.mark.parametrize('scenario_id',['nominal','mass_plus_5g','motor_failure'])
def test_real_native_flight_and_failure_respond_to_rotor_forces(native,scenario_id):
    model,config,table,sim,verify,out=native
    scenario=next(s for s in config['scenarios'] if s['id']==scenario_id)
    rows=sim.run(model,table,config,scenario,out)
    result=sim.assess(rows,model,config,scenario)
    assert result['accepted'],result
    assert result['metrics']['force_balance_rms_m_s2']<1e-8
    assert result['metrics']['fault_detected']==(scenario_id=='motor_failure')
    assert max(row['pos_m_z'] for row in rows)>.6
    assert max(row['pos_m_x'] for row in rows)>.35


@pytest.mark.requires_cadquery
def test_zero_motor_thrust_matches_analytic_gravity(native):
    model,config,table,sim,verify,out=native
    oracle=sim.freefall_oracle(model,table,config)
    assert oracle['accepted']
    assert oracle['actual_z_m']<.8
    assert oracle['actual_vz_m_s']<0


@pytest.mark.requires_cadquery
def test_video_camera_keeps_the_aircraft_clear_of_its_header(native):
    model,config,table,sim,verify,out=native
    rows=verify.read_rows(REFERENCE/'nominal.csv')
    assert verify.recording_framing(model,rows,config)['accepted']
    too_low=copy.deepcopy(config);too_low['camera']['target_m'][2]=.31
    assert not verify.recording_framing(model,rows,too_low)['accepted']


@pytest.mark.requires_cadquery
def test_completed_artifacts_are_reimported_and_reconciled(native,tmp_path):
    model,config,table,sim,verify,out=native
    copy=tmp_path/'reference';shutil.copytree(REFERENCE,copy)
    receipt=verify.verify(copy,DESIGN)
    assert receipt['digital_objective_complete'],receipt['failed_checks']
    assert receipt['engineering_acceptance']
    assert receipt['open_actions']==[]
    assert all(receipt[k] is False for k in ['physical_work_requested','physical_validation','fabrication_authorized','power_on_authorized','flight_authorized'])


@pytest.mark.requires_cadquery
def test_packaged_simulation_runs_without_the_cad_builder(native,tmp_path):
    completed=subprocess.run([sys.executable,str(REFERENCE/'RERUN.py'),'--out',str(tmp_path/'run')],capture_output=True,text=True,timeout=60)
    assert completed.returncode==0,completed.stderr
    result=json.loads((tmp_path/'run/SIMULATION.json').read_text())
    assert result['simulation_acceptance'] is True
    assert all(s['accepted'] for s in result['scenarios'])
    assert result['physical_work_requested'] is False


@pytest.mark.requires_cadquery
@pytest.mark.parametrize('tamper',['teleport','mass'])
def test_independent_verifier_rejects_changed_physics_or_mass(native,tmp_path,tamper):
    model,config,table,sim,verify,out=native
    copy=tmp_path/'modified';shutil.copytree(REFERENCE,copy)
    if tamper=='teleport':
        path=copy/'nominal.csv'
        with path.open() as handle:rows=list(csv.DictReader(handle))
        rows[1000]['pos_m_x']=str(float(rows[1000]['pos_m_x'])+.25)
        with path.open('w',newline='') as handle:
            writer=csv.DictWriter(handle,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
        failed='nominal_position_velocity_consistency'
    else:
        path=copy/'model.json';m=json.loads(path.read_text());m['mass_kg']+=.1;path.write_text(json.dumps(m))
        failed='same_aircraft_mass'
    receipt=verify.verify(copy,DESIGN)
    assert receipt['digital_objective_complete'] is False
    assert failed in receipt['failed_checks']


@pytest.fixture
def battery_inputs():
    pytest.importorskip('numpy')
    build=module('hs3g_battery_build_test','build_digital.py')
    sim=module('hs3g_battery_sim_test','hs3g_sim.py')
    config,table=build.read_inputs()
    return config,table,sim


def test_simulated_battery_uses_revision_b_overrides(tmp_path,monkeypatch):
    pytest.importorskip('numpy')
    build=module('hs3g_battery_revision_build_test','build_digital.py')
    candidate=json.loads((build.revision_b.HERE/'inputs/candidate.json').read_text())
    config,_=build.read_inputs()
    assert config['battery']['capacity_mah']['value']==candidate['part_overrides']['battery']['capacity_mah']==850
    for key in ['capacity_mah','c_continuous']:
        assert config['battery'][key]['source']==f'../revision_b/inputs/candidate.json#part_overrides/battery/{key}'
    assert config['battery']['cells']['value']==4
    assert config['battery']['cells']['source']=='../inputs/parts.json#parts/battery/cells'

    staged_inputs=tmp_path/'inputs';staged_inputs.mkdir()
    shutil.copyfile(build.revision_b.HERE/'inputs/thrust_table.json',staged_inputs/'thrust_table.json')
    changed={'capacity_mah':400,'cells':3,'c_continuous':25}
    candidate['part_overrides']['battery'].update(changed)
    (staged_inputs/'candidate.json').write_text(json.dumps(candidate))
    monkeypatch.setattr(build.revision_b,'HERE',tmp_path)
    updated,_=build.read_inputs()
    for key,value in changed.items():
        assert updated['battery'][key]['value']==value
        assert updated['battery'][key]['source']==f'../revision_b/inputs/candidate.json#part_overrides/battery/{key}'


def test_voltage_sag_lowers_available_full_throttle_thrust(battery_inputs):
    import numpy as np
    config,table,sim=battery_inputs
    motor=sim.MotorTable(table,config)
    requested=np.full(4,motor.max_rpm)
    voltage,_,rpms=sim.Battery(config,motor).load(requested)
    ideal=copy.deepcopy(config);ideal['battery']['internal_resistance_ohm']['value']=0
    ideal_voltage,_,ideal_rpms=sim.Battery(ideal,motor).load(requested)
    assert voltage<ideal_voltage
    assert np.sum(motor.force_at_rpm(rpms))<np.sum(motor.force_at_rpm(ideal_rpms))


def test_tiny_capacity_fails_terminal_voltage_gate(battery_inputs,tmp_path):
    pytest.importorskip('pybullet')
    config,table,sim=battery_inputs
    config['battery']['capacity_mah']['value']=.001
    model=json.loads((REFERENCE/'model.json').read_text())
    scenario=config['scenarios'][0]
    rows=sim.run(model,table,config,scenario,tmp_path)
    assessment=sim.assess(rows,model,config,scenario)
    assert assessment['checks']['terminal_voltage'] is False
    assert assessment['accepted'] is False


def test_current_requirements_state_mass_budget_only_and_expose_tight_margin():
    requirements=module('hs3g_mass_requirements_test','study_requirements.py')
    current=requirements.validate({'payload_mass_g':10})
    model={'mass_kg':.2449,'inertia_off_diagonal_relative_max':0}
    checks=requirements.constraints(model,current)
    assert requirements.verdict_basis(current)=='mass_budget_only'
    assert all(c['verdict_basis']=='mass_budget_only' for c in checks)
    mass_checks=[c for c in checks if c.get('kind')=='mass_budget']
    assert len(mass_checks)==2
    assert all(c['mass_budget']==c['passed'] and c['margin_g']==c['margin'] for c in mass_checks)
    assert mass_checks[1]['margin_g']==pytest.approx(.1)


def test_performance_requirements_need_an_assessment():
    requirements=module('hs3g_performance_requirements_test','study_requirements.py')
    requested={'min_hover_endurance_min':10,'min_thrust_to_weight':2.5}
    model={'mass_kg':.2349,'inertia_off_diagonal_relative_max':0}
    checks=requirements.constraints(model,requested)
    assert all(c['status']=='not_evaluated' and c['passed'] is None for c in checks[-2:])
    assessment={'metrics':{'estimated_hover_endurance_min':9,'thrust_to_weight_at_min_voltage':3}}
    checked=requirements.constraints(model,requested,assessment)
    assert checked[-2]['passed'] is False
    assert checked[-1]['passed'] is True


@pytest.mark.requires_cadquery
def test_verifier_leaves_package_byte_identical(native,tmp_path):
    _,_,_,_,verify,_=native
    package=tmp_path/'package';shutil.copytree(REFERENCE,package)
    def identities():
        return {p.relative_to(package).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                for p in package.rglob('*') if p.is_file()}
    before=identities()
    verify.verify(package,DESIGN)
    assert identities()==before


def test_verifier_cli_prints_or_writes_outside_package(tmp_path,monkeypatch,capsys):
    pytest.importorskip('numpy')
    verify=module('hs3g_readonly_verify_test','verify_digital.py')
    package=tmp_path/'package';package.mkdir()
    sentinel=package/'verification.json';sentinel.write_bytes(b'existing receipt\n')
    monkeypatch.setattr(verify,'verify',lambda *a:{'digital_objective_complete':True,'artifact_integrity':True})
    receipt=tmp_path/'receipt.json'
    monkeypatch.setattr(sys,'argv',['verify_digital.py',str(package),'--design',str(DESIGN)])
    assert verify.main()==0
    assert json.loads(capsys.readouterr().out)['digital_objective_complete'] is True
    assert list(package.iterdir())==[sentinel]
    monkeypatch.setattr(sys,'argv',['verify_digital.py',str(package),'--design',str(DESIGN),'--out',str(receipt)])
    assert verify.main()==0
    assert json.loads(receipt.read_text())['digital_objective_complete'] is True
    assert sentinel.read_bytes()==b'existing receipt\n'
    monkeypatch.setattr(sys,'argv',['verify_digital.py',str(package),'--design',str(DESIGN),'--out',str(sentinel)])
    with pytest.raises(SystemExit):verify.main()
    assert sentinel.read_bytes()==b'existing receipt\n'
