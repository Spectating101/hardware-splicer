"""Prove each CHECK_REQUIREMENTS declaration against the evaluator it names.

A declaration narrows which requirement changes make a check stale. It is only
safe if no check changes result when a requirement it does not declare changes.
Each case below reruns its real evaluator with one requirement changed at a time
and asserts exactly that. Fielddeck 7 calls its pure calculation directly; the
plotter and the drone run their native stages when the runtime is available.
"""
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import subprocess

import pytest

from hardware_splicer import digital_cases as cases
from hardware_splicer import digital_project as digital
from hardware_splicer.study_evidence import _result

ROOT = Path(__file__).resolve().parents[1]
CASE_ROOTS = {'fielddeck-5': ROOT, 'fielddeck-7': cases.FIELDDECK.root,
              'ender3-penplotter': cases.PLOTTER.root, cases.DEFAULT_CASE: digital.CASE}
REQUIREMENT_NAMES = {'fielddeck-5': set(cases.FIELDDECK_5.requirements),
                     'fielddeck-7': set(cases.FIELDDECK.requirements),
                     'ender3-penplotter': set(cases.PLOTTER.requirements),
                     cases.DEFAULT_CASE: {'payload_mass_g', 'gust_scale', 'max_mass_g'}}


def _sources(case_id):
    root = CASE_ROOTS[case_id]
    return {name: sha256((root / name).read_bytes()).hexdigest()
            for name in cases.CHECK_REQUIREMENTS[case_id]['evaluator_sha256']}


def _assert_declared(case_id, base, changed_runs):
    """base: {check: result}; changed_runs: {requirement: {check: result}}."""
    declared = cases.CHECK_REQUIREMENTS[case_id]['checks']
    assert set(base) == set(declared), 'every evaluator check is declared, and nothing else'
    moved = set()
    for requirement, run in changed_runs.items():
        assert set(run) == set(base)
        changed = {check for check in base if run[check] != base[check]}
        moved |= changed
        undeclared = {check for check in changed if requirement not in declared[check]}
        assert not undeclared, f'{requirement} changed {sorted(undeclared)} without being declared'
    assert moved, 'the perturbations must change at least one check, or the proof is vacuous'
    return moved


@pytest.mark.parametrize('case_id', sorted(CASE_ROOTS))
def test_declaration_names_the_current_evaluator_files(case_id):
    declared = cases.CHECK_REQUIREMENTS[case_id]
    for name, digest in declared['evaluator_sha256'].items():
        assert sha256((CASE_ROOTS[case_id] / name).read_bytes()).hexdigest() == digest, (
            f'{name} changed: re-read which requirements each check uses, then update the declaration')
    assert set().union(*map(set, declared['checks'].values())) <= REQUIREMENT_NAMES[case_id]


@pytest.mark.parametrize('case_id,evaluator', [
    (case_id, name) for case_id in sorted(CASE_ROOTS) for name in cases.CHECK_REQUIREMENTS[case_id]['evaluator_sha256']])
def test_an_edited_evaluator_falls_back_to_every_requirement(tmp_path, case_id, evaluator):
    requirements = {name: 1.0 for name in REQUIREMENT_NAMES[case_id]}
    every = tuple(sorted(requirements))
    sources = _sources(case_id)
    checks = cases.CHECK_REQUIREMENTS[case_id]['checks']
    for check, names in checks.items():
        assert cases.check_requirements(case_id, check, requirements, sources) == (
            tuple(sorted(names)), 'declared_for_evaluator')
    edited = tmp_path / Path(evaluator).name
    edited.write_bytes((CASE_ROOTS[case_id] / evaluator).read_bytes() + b'\n')
    sources[evaluator] = sha256(edited.read_bytes()).hexdigest()
    for check in checks:
        assert cases.check_requirements(case_id, check, requirements, sources) == (every, 'every_study_input')


def _perturbed(case, base):
    """One changed value per requirement: its bound farthest from the default."""
    result = {}
    for name, (_, low, high) in case.requirements.items():
        result[name] = high if abs(high - base[name]) >= abs(base[name] - low) else low
    return result


def test_fielddeck7_declaration_matches_the_calculation():
    root = cases.FIELDDECK.root
    spec = importlib.util.spec_from_file_location('fielddeck7_study_contract', root / 'study_contract.py')
    contract = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(contract)
    design, geometry, bom = (json.loads((root / name).read_text())
                             for name in ('design.json', 'cad/geometry_report.json', 'bom.json'))
    base = cases.FIELDDECK.defaults()

    def run(requirements):
        report = contract.calculate(design, geometry, bom, requirements)
        return {c['id']: _result(c) for c in report['constraints']}

    runs = {}
    for name, (_, low, high) in cases.FIELDDECK.requirements.items():
        for value in (low, high):
            if value != base[name]:
                runs.setdefault(name, []).append(run({**base, name: value}))
    reference = run(base)
    moved = set()
    for name, results in runs.items():
        for result in results:
            moved |= _assert_declared('fielddeck-7', reference, {name: result})
    # usb_current_limit is declared but not seen to move: the fixed high-power
    # keyboard scenario dominates its maximum across the keyboard_current_a bounds.
    assert moved >= {'work_runtime', 'supply_current_margin', 'sensitivity_supply_limit',
                     'case_width', 'case_depth', 'case_height', 'print_bed_x', 'print_bed_y'}


def _native():
    if not digital.runtime_for_case('ender3-penplotter')['available']:
        pytest.skip('Native CAD runtime is not available; set HARDWARE_SPLICER_DIGITAL_PYTHON')
    return digital.native_python()


def test_plotter_declaration_matches_native_reruns(tmp_path):
    python = _native()
    case = cases.PLOTTER
    base = case.defaults()
    variants = {'base': base, **{name: {**base, name: value} for name, value in _perturbed(case, base).items()}}

    def run(label):
        directory = tmp_path / label
        cases.prepare(case, directory, variants[label])
        for stage in ('scripts/build.py', 'scripts/simulate.py'):
            subprocess.run([python, '-B', str(directory / stage)], check=True, capture_output=True, timeout=600)
        report = json.loads((directory / case.calculation).read_text())
        return label, {c['id']: _result(c) for c in report['constraints']}

    with ThreadPoolExecutor(max_workers=len(variants)) as pool:
        results = dict(pool.map(run, variants))
    base_result = results.pop('base')
    moved = _assert_declared('ender3-penplotter', base_result, results)
    assert {'bed_limited_drawing_width', 'parking_hotend_clearance', 'motion_pen_lift_clearance'} <= moved


def test_drone_declaration_matches_native_reruns(tmp_path):
    if not digital.runtime()['available']:
        pytest.skip('Drone native runtime (CadQuery, PyBullet) is not available; set HARDWARE_SPLICER_DIGITAL_PYTHON')
    python = digital.native_python()
    design = digital.CASE.parent / 'revision_b' / 'reference'
    base = {'payload_mass_g': 0.0, 'gust_scale': 1.0, 'max_mass_g': 250.0}
    # Far bounds that move the flight and the mass checks.
    variants = {'base': base, 'payload_mass_g': {**base, 'payload_mass_g': 40.0},
                'gust_scale': {**base, 'gust_scale': 3.0}, 'max_mass_g': {**base, 'max_mass_g': 150.0}}

    def run(label):
        requirements = tmp_path / (label + '.json')
        requirements.write_text(json.dumps(variants[label]))
        out = tmp_path / label
        subprocess.run([python, '-B', str(digital.CASE / 'build_digital.py'), '--design', str(design),
                        '--out', str(out), '--requirements', str(requirements)],
                       capture_output=True, timeout=900, check=False)
        model, report, config = (json.loads((out / name).read_text())
                                 for name in ('model.json', 'SIMULATION.json', 'simulation-contract.json'))
        # The backend names the flight checks; reuse its summary, not a copy of it.
        summary = digital.summarize({'engineering_acceptance': None}, model, report, config)
        return label, {c['id']: _result(c) for c in summary['constraints']}

    with ThreadPoolExecutor(max_workers=len(variants)) as pool:
        results = dict(pool.map(run, variants))
    base_result = results.pop('base')
    moved = _assert_declared(cases.DEFAULT_CASE, base_result, results)
    assert {'nominal_mass', 'nominal_tracking_rms_m'} <= moved
