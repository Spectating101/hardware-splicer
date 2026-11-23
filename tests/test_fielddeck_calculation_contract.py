"""Regression coverage for study inputs that previously did not change results."""
import copy
import importlib.util
import json
from pathlib import Path
import shutil

import pytest

CASE = Path(__file__).resolve().parents[1] / 'projects/cyberdeck-real-trial-20261020/digital_v1'
spec = importlib.util.spec_from_file_location('fielddeck_calculation_contract', CASE / 'study_contract.py')
contract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contract)


@pytest.fixture
def inputs():
    return tuple(json.loads((CASE / name).read_text()) for name in ('design.json', 'cad/geometry_report.json', 'bom.json'))


def scenario(result, name):
    return next(row for row in result['load_scenarios'] if row['name'] == name)


def test_battery_energy_uses_cell_voltage_and_declared_losses(inputs):
    design, geometry, bom = inputs
    result = contract.calculate(*inputs)
    assert result['usable_output_energy_wh'] == pytest.approx([22.95, 32.4])
    assert scenario(result, 'work')['power_w'] == pytest.approx(8.25)
    assert scenario(result, 'work')['runtime_h'] == pytest.approx([22.95 / 8.25, 32.4 / 8.25], abs=1e-6)
    changed = copy.deepcopy(design)
    changed['power_bank']['capacity_mah'] = 20000
    doubled = contract.calculate(changed, geometry, bom)
    assert doubled['battery_nominal_cell_energy_wh'] == 72
    assert scenario(doubled, 'work')['runtime_h'][0] == pytest.approx(2 * scenario(result, 'work')['runtime_h'][0], abs=2e-6)
    changed['engineering_assumptions']['conversion_efficiency_range'] = [.5, .5]
    assert contract.calculate(changed, geometry, bom)['usable_output_energy_wh'] == pytest.approx([30.6, 36])


def test_changed_design_load_and_explicit_override_both_take_effect(inputs):
    design, geometry, bom = inputs
    changed = copy.deepcopy(design)
    changed['engineering_assumptions']['pi_current_a']['work'] = 1.4
    derived = contract.calculate(changed, geometry, bom)
    explicit = contract.calculate(changed, geometry, bom, {'pi_work_current_a': 1.8})
    assert scenario(derived, 'work')['pi_current_a'] == 1.4
    assert scenario(explicit, 'work')['pi_current_a'] == 1.8
    assert scenario(explicit, 'work')['runtime_h'][0] < scenario(derived, 'work')['runtime_h'][0]


def test_overload_fails_even_when_assumed_stress_current_is_lower(inputs):
    result = contract.calculate(*inputs, {'pi_work_current_a': 2.5, 'keyboard_current_a': .5})
    assert result['requirements_met'] is False
    check = next(c for c in result['constraints'] if c['id'] == 'supply_current_margin')
    assert check['actual'] < 0 and check['passed'] is False
    assert result['largest_ordinary_scenario'] == 'work'
    assert result['cooling_sensitivity']['heat_assumption_w'] == scenario(result, 'work')['power_w']


def test_goals_fail_without_turning_model_integrity_into_physical_approval(inputs):
    result = contract.calculate(*inputs, {'minimum_work_runtime_h': 8, 'printer_bed_x_mm': 100})
    failed = {c['id'] for c in result['constraints'] if not c['passed']}
    assert {'work_runtime', 'print_bed_x'} <= failed
    assert result['physical_validation_performed'] is False
    assert result['thermal_acceptance_established'] is False


def test_structural_and_airflow_sensitivity_respond_to_inputs(inputs):
    design, geometry, bom = inputs
    initial = contract.calculate(*inputs)
    changed = copy.deepcopy(design)
    changed['engineering_assumptions']['petg_elastic_modulus_mpa'] *= 2
    changed['engineering_assumptions']['cooling']['delivered_flow_fraction'] = [.1, .2, .4, .8]
    result = contract.calculate(changed, geometry, bom)
    assert result['post_lateral_2g_check']['tip_deflection_mm'] == pytest.approx(initial['post_lateral_2g_check']['tip_deflection_mm'] / 2)
    assert result['cooling_sensitivity']['bulk_air_rise_c'][0] == pytest.approx(initial['cooling_sensitivity']['bulk_air_rise_c'][0] / 2)


@pytest.mark.parametrize('values', [{'pi_work_current_a': True}, {'keyboard_current_a': float('nan')}, {'minimum_work_runtime_h': float('inf')}, {'unknown': 1}, {'printer_bed_x_mm': 90}])
def test_rejects_invalid_revision_inputs(values):
    with pytest.raises(ValueError):
        contract.validate_requirements(values)


def test_calculation_record_refuses_changed_source_bytes(inputs, tmp_path):
    for name in ('design.json', 'bom.json', 'cad/geometry_report.json', 'engineering.py', 'study_contract.py'):
        destination = tmp_path / name
        destination.parent.mkdir(exist_ok=True, parents=True)
        shutil.copyfile(CASE / name, destination)
    (tmp_path / 'analysis').mkdir()
    result = contract.calculate(*inputs)
    result['input_sha256'] = contract.input_hashes(tmp_path)
    saved = tmp_path / 'analysis/calculations.json'
    saved.write_text(json.dumps(result))
    assert contract.validate_calculation_record(tmp_path)['case_id'] == 'fielddeck-7'
    (tmp_path / 'engineering.py').write_text('# changed calculation / plotting source\n')
    with pytest.raises(ValueError, match='differ'):
        contract.validate_calculation_record(tmp_path)
