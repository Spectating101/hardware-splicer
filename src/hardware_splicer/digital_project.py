"""Saved digital studies using the existing project store and native job queue.

The HS-3G-B is a registered proving case. Artifacts belong to a project/run,
are immutable after publication, and are checked against a server-owned seal.
Client snapshots cannot supply filesystem paths or substitute result claims.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
import zipfile
from functools import lru_cache

from .project_store import CorruptProject, ProjectNotFound, RevisionConflict, validate_project_id
from . import digital_cases as cases

CASE = Path(__file__).resolve().parents[2] / 'examples/drone_proving_ground/digital'
DESIGN = CASE.parent / 'revision_b/reference'
ARTIFACTS = frozenset({
    'ASSEMBLY.png', 'EXPLODED.png', 'FLIGHT.gif', 'HS-LICENSE.txt', 'HS3G_B_ASSEMBLY.glb',
    'HS3G_B_ASSEMBLY.step', 'README.md', 'REQUIREMENTS.txt', 'RERUN.py', 'SIMULATION.json',
    'TELEMETRY.png', 'THREE-LICENSE.txt', 'VIEWER.html', 'hs3g_sim.py', 'mass_plus_5g.csv',
    'model.json', 'motor_failure.csv', 'nominal.csv', 'simulation-contract.json',
    'thrust-table.json', 'study_requirements.py', 'verification.json',
})
RUN_RE = re.compile(r'[a-f0-9]{32}\Z')


@lru_cache(maxsize=1)
def requirement_tools():
    spec = importlib.util.spec_from_file_location('hs_registered_study_requirements', CASE / 'study_requirements.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    try:
        value = json.loads(Path(path).read_text())
        if not isinstance(value, dict):
            raise ValueError('Digital JSON must contain an object.')
        return value
    except (OSError, ValueError) as exc:
        raise CorruptProject('Digital study artifact is missing or unreadable.') from exc


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n')


def native_python():
    configured = os.getenv('HARDWARE_SPLICER_DIGITAL_PYTHON') or os.getenv('HARDWARE_SPLICER_CAD_PYTHON')
    if configured:
        return configured
    if importlib.util.find_spec('cadquery') and importlib.util.find_spec('pybullet'):
        return sys.executable
    cached = CASE.parents[2] / '.cache/hardware-splicer/digital-native-venv/bin/python'
    return str(cached) if cached.is_file() else sys.executable


@lru_cache(maxsize=4)
def _runtime(interpreter):
    try:
        result = subprocess.run([interpreter, '-B', '-c',
                                 'import cadquery, pybullet, trimesh, numpy, scipy, PIL, matplotlib'],
                                capture_output=True, timeout=30, check=False)
        available = result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        available = False
    return {'available': available, 'engine': 'CadQuery + PyBullet DIRECT',
            'setup_hint': '' if available else
            'Install the drone-sim extra (pip install -e ".[drone-sim]") in the API environment, '
            'or set HARDWARE_SPLICER_DIGITAL_PYTHON to a Python with that extra. Saved studies remain viewable.'}


def runtime():
    return _runtime(native_python())


@lru_cache(maxsize=4)
def _device_runtime(interpreter, *, substitution=False):
    imports = 'import cadquery, trimesh, numpy, PIL, matplotlib'
    if substitution:
        imports += '; from pydantic import model_validator'
    try:
        result = subprocess.run([interpreter, '-B', '-c', imports],
                                capture_output=True, timeout=30, check=False)
        available = result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        available = False
    dependencies = 'CadQuery, trimesh, numpy, Pillow and matplotlib'
    if substitution:
        dependencies += ' and Pydantic v2'
    return {'available': available, 'engine': 'CadQuery + registered engineering scripts',
            'setup_hint': '' if available else f'Set HARDWARE_SPLICER_DIGITAL_PYTHON to a Python with {dependencies}.'}


def runtime_for_case(case_id=cases.DEFAULT_CASE):
    cases.validate_case_id(case_id)
    return runtime() if case_id == cases.DEFAULT_CASE else _device_runtime(
        native_python(), substitution=case_id == 'fielddeck-5')


def artifact_names(case_id=cases.DEFAULT_CASE, *, case=None):
    return ARTIFACTS if case_id == cases.DEFAULT_CASE else (case or cases.registered(case_id)).artifacts


def case_id_for(seal):
    value = seal.get('case_id', cases.DEFAULT_CASE)
    try:
        return cases.validate_case_id(value)
    except ValueError as exc:
        raise CorruptProject('Digital run has an unknown registered case.') from exc


def case_for_run(seal):
    case_id = case_id_for(seal)
    if case_id == cases.DEFAULT_CASE:
        return None
    if 'case_contract' in seal:
        return cases.archived(seal['case_contract'], case_id)
    # Compatibility for the first registered-case snapshots made before the
    # adapter itself was archived. New publications always carry a definition.
    if (case_id == 'fielddeck-7'
            and set(seal.get('artifact_sha256', {})) == cases.FIELDDECK_V1.artifacts | {'STUDY.zip'}):
        return cases.FIELDDECK_V1
    return cases.registered(case_id)


def resolve_requirements(seal, change_request='', requirements=None):
    case_id = case_id_for(seal)
    if case_id == cases.DEFAULT_CASE:
        return requirement_tools().resolve(seal['summary']['requirements'], change_request, requirements)
    return revision_case(seal).resolve(seal['summary']['requirements'], change_request, requirements)


def revision_case(seal):
    case_id = case_id_for(seal)
    # Fielddeck 5 revisions change numeric goals against the parent's exact
    # assembly and evaluator, even if today's checkout has another variant.
    if case_id == 'fielddeck-5' or cases.DRAWING in seal['artifact_sha256']:
        return case_for_run(seal)
    return cases.registered(case_id)


def run_dir(store, project_id, run_id):
    validate_project_id(project_id)
    if not isinstance(run_id, str) or not RUN_RE.fullmatch(run_id):
        raise CorruptProject('Invalid digital run identity.')
    base = store.root / project_id / 'digital-runs'
    path = base / run_id
    # Reject symlinks at every owned boundary, including a deleted/replaced project.
    for item in (store.root / project_id, base, path):
        if item.is_symlink():
            raise CorruptProject('Digital study directories cannot be symbolic links.')
    if path.resolve().parent != base.resolve():
        raise CorruptProject('Digital run escaped its project.')
    return path


def checked_file(directory, name, hashes, *, case_id=cases.DEFAULT_CASE, case=None):
    if name not in artifact_names(case_id, case=case) | {'STUDY.zip'} or name not in hashes:
        raise ProjectNotFound('Digital artifact not found.')
    path = cases.safe_file(directory, name)
    if digest(path) != hashes[name]:
        raise CorruptProject('Digital artifact changed after verification: ' + name)
    return path


def verified_package(directory, *, check_sources=False):
    receipt = read_json(directory / 'verification.json')
    if receipt.get('artifact_integrity') is not True:
        raise CorruptProject('Digital package has not passed independent artifact verification.')
    hashes = receipt.get('artifact_sha256', {})
    if set(hashes) != ARTIFACTS - {'verification.json'}:
        raise CorruptProject('Digital artifact inventory does not match the registered case.')
    for name in hashes:
        checked_file(directory, name, hashes)
    model = read_json(directory / 'model.json')
    if check_sources:
        sources = sorted(CASE.glob('*.py')) + [CASE / 'simulation.json', CASE / 'viewer.html'] + sorted((CASE / 'vendor').glob('*'))
        expected = {p.relative_to(CASE).as_posix(): digest(p) for p in sources if p.is_file()}
        if model.get('source_sha256') != expected:
            raise CorruptProject('The reference study must be regenerated for the current native sources.')
    return receipt, model, read_json(directory / 'SIMULATION.json')


def summarize(receipt, model, report, config=None):
    nominal = next(s for s in report['scenarios'] if s['scenario']['id'] == 'nominal')
    constraints = list(report['constraints'])
    config = config if config is not None else read_json(CASE / 'simulation.json')
    for scenario in report['scenarios']:
        for key, passed in scenario['checks'].items():
            if key in {'finite_state', 'timebase', 'position_velocity_consistency', 'native_force_balance'}:
                continue
            constraints.append({'id': scenario['scenario']['id'] + '_' + key,
                                'label': scenario['scenario']['id'].replace('_', ' ') + ' · ' + key.replace('_', ' '),
                                'actual': scenario['metrics'].get(key), 'limit': config['acceptance'].get(key),
                                'unit': 'm' if key.endswith('_m') else '', 'passed': passed})
    return {'requirements': model['requirements'], 'requirements_met': receipt['engineering_acceptance'],
            'artifact_integrity': True, 'mass_g': model['mass_kg'] * 1000,
            'mass_margin_g': model['requirements']['max_mass_g'] - model['mass_kg'] * 1000,
            'centre_of_mass_mm': [v * 1000 for v in model['centre_of_mass_m']],
            'inertia_diagonal_kg_m2': model['dynamics_inertia_diagonal_kg_m2'],
            'parts': len(model['parts']), 'metrics': nominal['metrics'], 'constraints': constraints,
            'scope_limits': report['scope_limits'], 'source_sha256': model['source_sha256'],
            'engine': report['engine'], 'physical_work_requested': False,
            'note': 'Ideal state feedback; low-throttle thrust/current extrapolation. Gust scale multiplies '
                    'a declared [0.12, -0.08, 0] N force; it is not a wind-speed estimate.'}


def stage_run(store, project_id, source, *, change_request, parent_revision, job_id=None,
              expected_requirements=None, attempt_id=None, case_id=cases.DEFAULT_CASE, registered_case=None):
    if case_id == cases.DEFAULT_CASE:
        receipt, model, report = verified_package(source)
        summary = summarize(receipt, model, report, read_json(source / 'simulation-contract.json'))
    else:
        registered_case = registered_case or cases.registered(case_id)
        if registered_case.case_id != case_id:
            raise CorruptProject('The registered adapter belongs to a different case.')
        summary = cases.verified_package(registered_case, source)
    if expected_requirements is not None and summary.get('requirements') != expected_requirements:
        raise CorruptProject('Computed model does not match the requested requirements.')
    artifacts = artifact_names(case_id, case=registered_case)
    run_id = uuid.uuid4().hex
    destination = run_dir(store, project_id, run_id)
    destination.mkdir(parents=True, exist_ok=False)
    try:
        for name in artifacts:
            (destination / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / name, destination / name)
        # Exact files only: bytecode, logs and other users' paths never enter a bundle.
        with zipfile.ZipFile(destination / 'STUDY.zip', 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for name in sorted(artifacts):
                archive.write(destination / name, name)
        seal = {'schema': 'hardware_splicer.digital_run.v1', 'project_id': project_id, 'run_id': run_id,
                'parent_revision': parent_revision, 'change_request': change_request, 'job_id': job_id,
                'attempt_id': attempt_id,
                'summary': summary,
                'artifact_sha256': {name: digest(destination / name) for name in sorted(artifacts | {'STUDY.zip'})}}
        if case_id != cases.DEFAULT_CASE:
            seal['case_id'] = case_id
            seal['case_contract'] = registered_case.definition()
        write_json(destination / 'sealed-run.json', seal)
        return seal
    except BaseException:
        shutil.rmtree(destination)
        raise


def snapshot_for(project_id, seal, previous=None):
    snapshot = dict(previous or {})
    snapshot.update({'projectId': project_id, 'projectName': snapshot.get('projectName') or 'HS-3G-B digital study',
                     'mode': 'digital', 'currentStage': 'digital',
                     'digitalStudy': {'run_id': seal['run_id'], 'requirements': seal['summary']['requirements'],
                                      'parent_revision': seal['parent_revision'], 'change_request': seal['change_request']}})
    if case_id_for(seal) != cases.DEFAULT_CASE:
        snapshot['digitalStudy']['case_id'] = seal['case_id']
    return snapshot


def create_project(store, *, name='HS-3G-B digital study', case_id=cases.DEFAULT_CASE, brief_plan=None):
    cases.validate_case_id(case_id)
    if case_id != cases.DEFAULT_CASE:
        case = cases.registered(case_id)
        if not runtime_for_case(case_id)['available']:
            raise RuntimeError(runtime_for_case(case_id)['setup_hint'])
        # New cases execute their native stages before the first publication.
        # Later revisions use the same stages through the existing job runner.
        with tempfile.TemporaryDirectory(prefix='hs-registered-baseline-') as scratch:
            package = Path(scratch) / 'study'
            requirements = case.defaults()
            initial = {'projectName': name}
            if brief_plan is not None:
                requirements = case.resolve(requirements, overrides=brief_plan['requirements'])
                initial['designBrief'] = brief_plan
            drawing = brief_plan.get('drawing') if brief_plan else None
            if drawing is not None:
                case = cases.with_drawing(case)
            cases.prepare(case, package, requirements, drawing=drawing)
            env = dict(os.environ)
            env.pop('PYTHONOPTIMIZE', None)  # Native verifier assertions must execute.
            env.update({key: '1' for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS')})
            for stage in case.stages:
                completed = subprocess.run([native_python(), '-B', str(package / stage)],
                                           capture_output=True, text=True, timeout=600, env=env)
                if completed.returncode != 0:
                    raise RuntimeError('Registered native stage failed (' + stage + '): ' +
                                       (completed.stdout + completed.stderr)[-2000:])
            cases.seal_package(case, package)
            project_id = 'digital-' + uuid.uuid4().hex
            seal = stage_run(store, project_id, package, change_request=(
                'Digital build from design brief' if brief_plan is not None else 'Verified native baseline'),
                             parent_revision=None, case_id=case_id, registered_case=case)
            try:
                return store.save(project_id, snapshot_for(project_id, seal, initial), expected_revision=0,
                                  metadata={'source': 'digital_study', 'run_id': seal['run_id']})
            except BaseException:
                shutil.rmtree(run_dir(store, project_id, seal['run_id']))
                raise
    _, model, _ = verified_package(CASE / 'reference', check_sources=True)
    if model.get('requirements') != requirement_tools().validate():
        raise CorruptProject('The registered reference must contain the default baseline requirements.')
    project_id = 'digital-' + uuid.uuid4().hex
    seal = stage_run(store, project_id, CASE / 'reference', change_request='Verified baseline', parent_revision=None)
    try:
        return store.save(project_id, snapshot_for(project_id, seal, {'projectName': name}), expected_revision=0,
                          metadata={'source': 'digital_study', 'run_id': seal['run_id']})
    except BaseException:
        shutil.rmtree(run_dir(store, project_id, seal['run_id']))
        raise


def load_run(store, project_id, revision=None):
    envelope = store.load(project_id, revision=revision)
    snapshot = envelope['snapshot']
    if snapshot.get('mode') != 'digital' or not isinstance(snapshot.get('digitalStudy'), dict):
        raise ProjectNotFound('This project has no digital study.')
    run_id = snapshot['digitalStudy'].get('run_id')
    directory = run_dir(store, project_id, run_id)
    if (directory / 'sealed-run.json').is_symlink():
        raise CorruptProject('Digital run seal cannot be a symbolic link.')
    seal = read_json(directory / 'sealed-run.json')
    if (not isinstance(seal, dict) or seal.get('schema') != 'hardware_splicer.digital_run.v1'
            or seal.get('project_id') != project_id or seal.get('run_id') != run_id):
        raise CorruptProject('Digital run belongs to a different project.')
    if snapshot['digitalStudy'].get('case_id', cases.DEFAULT_CASE) != case_id_for(seal):
        raise CorruptProject('Digital run belongs to a different registered case.')
    if (seal.get('attempt_id') is not None
            and envelope.get('metadata', {}).get('attempt_id') != seal['attempt_id']):
        raise CorruptProject('Digital run does not match its recorded execution attempt.')
    parent = seal.get('parent_revision')
    if ((parent is None and envelope['revision'] != 1)
            or (parent is not None and (isinstance(parent, bool) or not isinstance(parent, int)
                                       or parent < 1 or envelope['revision'] != parent + 1))):
        raise CorruptProject('Digital run does not belong to this project revision.')
    return envelope, directory, seal


def validated_run(store, project_id, revision=None):
    """Bind cached claims to their immutable model, contract and verified result."""
    envelope, directory, seal = load_run(store, project_id, revision)
    case_id = case_id_for(seal)
    if case_id != cases.DEFAULT_CASE:
        try:
            case = case_for_run(seal)
            if set(seal['artifact_sha256']) != artifact_names(case_id, case=case) | {'STUDY.zip'}:
                raise ValueError('Invalid registered artifact inventory')
            for name in artifact_names(case_id, case=case):
                checked_file(directory, name, seal['artifact_sha256'], case_id=case_id, case=case)
            summary = cases.verified_package(case, directory)
            if summary != seal['summary']:
                raise ValueError('Stored summary differs from the verified result')
        except (KeyError, TypeError, ValueError, AttributeError, OverflowError) as exc:
            raise CorruptProject('Digital result claims do not match their verified artifacts.') from exc
        return envelope, directory, seal
    try:
        hashes = seal['artifact_sha256']
        if set(hashes) != ARTIFACTS | {'STUDY.zip'}:
            raise ValueError('Invalid artifact inventory')
        values = {name: read_json(checked_file(directory, name, hashes))
                  for name in ('verification.json', 'model.json', 'SIMULATION.json', 'simulation-contract.json')}
        receipt, model = values['verification.json'], values['model.json']
        report, contract = values['SIMULATION.json'], values['simulation-contract.json']
        requirements = requirement_tools().validate(model['requirements'])
        if (receipt.get('artifact_integrity') is not True or not receipt.get('integrity_checks')
                or not all(v is True for v in receipt['integrity_checks'].values())
                or set(receipt['artifact_sha256']) != ARTIFACTS - {'verification.json'}
                or any(hashes[name] != value for name, value in receipt['artifact_sha256'].items())
                or model['source_sha256'] != report['source_sha256']
                or report['requirements'] != requirements or contract['requirements'] != requirements
                or report['requirements_met'] is not receipt['engineering_acceptance']
                or receipt['scenarios'] != report['scenarios']
                or receipt['requirements_met'] is not receipt['engineering_acceptance']
                or any(receipt.get(key) is not False for key in ('physical_work_requested','physical_validation',
                        'fabrication_authorized','power_on_authorized','flight_authorized'))):
            raise ValueError('Inconsistent verified inputs or result')
        summary = summarize(receipt, model, report, contract)
        json.dumps(summary, allow_nan=False)
        if summary != seal['summary']:
            raise ValueError('Stored summary differs from the verified result')
    except (KeyError, TypeError, ValueError, AttributeError, StopIteration, OverflowError) as exc:
        raise CorruptProject('Digital result claims do not match their verified artifacts.') from exc
    return envelope, directory, seal


def describe(store, project_id, revision=None):
    envelope, directory, seal = validated_run(store, project_id, revision)
    return {'revision': envelope['revision'], 'saved_at': envelope['saved_at'],
            'attempt_id': seal.get('attempt_id'),
            **{key: seal[key] for key in ('run_id', 'parent_revision', 'change_request', 'job_id', 'summary')},
            'artifacts': {name: f'/v1/projects/{project_id}/digital/revisions/{envelope["revision"]}/artifacts/{name}'
                          for name in sorted(seal['artifact_sha256'])}}


def duplicate_project(store, project_id, target_id):
    validate_project_id(target_id)
    if (store.root / target_id).exists():
        raise RevisionConflict('Target project already exists.')
    envelope, source, old_seal = load_run(store, project_id)
    case_id = case_id_for(old_seal)
    case = case_for_run(old_seal)
    for name in artifact_names(case_id, case=case):
        checked_file(source, name, old_seal['artifact_sha256'], case_id=case_id, case=case)
    seal = stage_run(store, target_id, source, change_request='Copied digital study', parent_revision=None,
                     case_id=case_id, registered_case=case)
    previous = dict(envelope['snapshot'])
    previous['projectName'] = previous.get('projectName', 'Digital study') + ' (copy)'
    try:
        return store.save(target_id, snapshot_for(target_id, seal, previous), expected_revision=0,
                          metadata={'source': 'digital_study', 'duplicated_from': project_id})
    except BaseException:
        shutil.rmtree(run_dir(store, target_id, seal['run_id']))
        raise


def _active(backend, job):
    current = backend.store.get_job(job.job_id)
    return bool(not backend._stop.is_set() and current and current.status == 'running'
                and current.started_at == job.started_at and current.attempt_id == job.attempt_id)


def _command(backend, job, args, log):
    env = dict(os.environ)
    env.pop('PYTHONOPTIMIZE', None)  # Applies to both device and legacy drone stages.
    env.update({key: '1' for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS')})
    with log.open('wb') as handle:
        process = subprocess.Popen([native_python(), '-B', *map(str, args)], stdout=handle, stderr=subprocess.STDOUT, env=env)
        deadline = time.monotonic() + 600
        try:
            while process.poll() is None:
                if time.monotonic() > deadline:
                    raise RuntimeError('The registered native stage exceeded its 600 second execution limit.')
                if not _active(backend, job):
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill(); process.wait(timeout=5)
                    return None
                time.sleep(.2)
            return process.returncode
        finally:
            if process.poll() is None:
                process.kill(); process.wait(timeout=5)


def execute_study(backend, job):
    """Fresh native generation and independent verification before a CAS save."""
    store = backend.project_store
    payload = job.options['payload']
    project_id, base_revision = payload['project_id'], payload['base_revision']
    parent, parent_directory, parent_seal = load_run(store, project_id, base_revision)
    case_id = case_id_for(parent_seal)
    if payload.get('case_id', cases.DEFAULT_CASE) != case_id:
        raise CorruptProject('Digital job targets a different registered case.')
    if store.load(project_id)['revision'] != base_revision:
        raise RevisionConflict('The project changed before this run started. Reload and run from the latest revision.')
    case = None if case_id == cases.DEFAULT_CASE else revision_case(parent_seal)
    requirements = (requirement_tools().validate(payload['requirements']) if case is None
                    else case.validate(payload['requirements']))
    attempt = Path(job.output_dir) / (job.attempt_id or uuid.uuid4().hex)
    attempt.mkdir(parents=True, exist_ok=False)
    write_json(attempt / 'requirements.json', requirements)
    package = attempt / 'study'
    if case is not None:
        source = parent_directory if case_id == 'fielddeck-5' or cases.DRAWING in case.inputs else None
        if source is not None:
            for name in case.inputs:
                checked_file(source, name, parent_seal['artifact_sha256'], case_id=case_id, case=case)
        drawing = (payload.get('design_brief') or {}).get('drawing')
        if drawing is not None and cases.DRAWING not in case.inputs:
            case = cases.with_drawing(case)
        cases.prepare(case, package, requirements, source=source, drawing=drawing)
        for index, stage in enumerate(case.stages):
            log = attempt / f'{index + 1}-{Path(stage).stem}.log'
            code = _command(backend, job, [package / stage], log)
            if code is None:
                return
            if code != 0:
                raise RuntimeError('Registered native stage failed (' + stage + '): ' +
                                   log.read_text(errors='replace')[-2000:])
        cases.seal_package(case, package)
    else:
        _execute_drone_stages(backend, job, attempt, package)
    if not _active(backend, job):
        return
    seal = stage_run(store, project_id, package, change_request=payload['change_request'] or 'Updated study requirements',
                     parent_revision=base_revision, job_id=job.job_id, expected_requirements=requirements,
                     attempt_id=job.attempt_id, case_id=case_id, registered_case=case)
    published = False
    try:
        def publish():
            # Deletion during a run must not resurrect the project.
            store.load(project_id)
            snapshot = snapshot_for(project_id, seal, parent['snapshot'])
            if 'design_brief' in payload:
                snapshot['designBrief'] = payload['design_brief']
            envelope = store.save(project_id, snapshot,
                                  expected_revision=base_revision,
                                  metadata={'source': 'digital_study', 'job_id': job.job_id, 'run_id': seal['run_id'],
                                            'attempt_id': job.attempt_id})
            return {'project_id': project_id, 'revision': envelope['revision'], 'run_id': seal['run_id'],
                    'requirements_met': seal['summary']['requirements_met'], 'artifact_integrity': True}
        published = backend.store.complete_with_publication(job, publish)
    finally:
        if not published:
            shutil.rmtree(run_dir(store, project_id, seal['run_id']), ignore_errors=True)


def _execute_drone_stages(backend, job, attempt, package):
    design = CASE.parent / 'revision_b' / 'reference'
    code = _command(backend, job, [CASE / 'build_digital.py', '--design', design, '--out', package,
                                    '--requirements', attempt / 'requirements.json'], attempt / 'build.log')
    if code is None:
        return
    if code not in (0, 2):
        raise RuntimeError('Native digital generation failed: ' + (attempt / 'build.log').read_text(errors='replace')[-1000:])
    code = _command(backend, job, [CASE / 'verify_digital.py', package, '--design', design, '--study'],
                    attempt / 'verification.log')
    if code is None:
        return
    if code != 0:
        raise RuntimeError('Independent digital artifact verification failed: ' +
                           (attempt / 'verification.log').read_text(errors='replace')[-1000:])
