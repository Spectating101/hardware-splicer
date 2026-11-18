"""Server-owned digital cases; this registry is not an arbitrary CAD/code runner.

The drone keeps its existing contract. The device cases share the existing
project/job lifecycle, but declare their own native stages, files and metrics.
Only these repository-owned inputs are copied into an execution workspace.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import shutil

from .project_store import CorruptProject

DEFAULT_CASE = 'hs3g-b'
ROOT = Path(__file__).resolve().parents[2]
CONTRACT = 'study-contract.json'
RECEIPT = 'study-verification.json'
ENTRYPOINT = 'STUDY_README.md'


@dataclass(frozen=True)
class RegisteredCase:
    case_id: str
    name: str
    root: Path
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    stages: tuple[str, ...]
    verifier: str
    calculation: str
    verification: str
    requirements: dict[str, tuple[float, float, float]]

    @property
    def artifacts(self):
        return frozenset((*self.inputs, *self.outputs, 'requirements.json', CONTRACT, RECEIPT,
                          ENTRYPOINT, 'LICENSE_HS.txt'))

    def validate(self, values=None):
        if values is None:
            values = {}
        if not isinstance(values, dict) or set(values) - set(self.requirements):
            raise ValueError('Supported requirements for ' + self.case_id + ': ' + ', '.join(self.requirements))
        result = {}
        for name, (default, minimum, maximum) in self.requirements.items():
            value = values.get(name, default)
            try:
                valid = (not isinstance(value, bool) and isinstance(value, (int, float))
                         and math.isfinite(value) and minimum <= value <= maximum)
            except OverflowError:
                valid = False
            if not valid:
                raise ValueError(f'{name} must be a finite number between {minimum:g} and {maximum:g}.')
            result[name] = float(value)
        if self.case_id == 'ender3-penplotter':
            for axis in ('width', 'height'):
                # Archived four-setting adapters keep their original square paper.
                paper = result.get(f'paper_{axis}_mm', 180.)
                if result[f'drawing_{axis}_mm'] + 20 > paper:
                    raise ValueError('The drawing viewport needs at least 10 mm of paper on each side.')
        return result

    def resolve(self, current, change_request='', overrides=None):
        if overrides is not None and not isinstance(overrides, dict):
            raise ValueError('Requirements must be an object.')
        if change_request.strip() and not overrides:
            raise ValueError('This registered case requires explicit numeric requirements; change_request is only a label.')
        if not isinstance(current, dict):
            raise ValueError('The saved requirements must be an object.')
        return self.validate({**current, **(overrides or {})})

    def definition(self):
        return {'schema': 'hardware_splicer.registered_case_adapter.v1', 'case_id': self.case_id,
                'name': self.name, 'inputs': list(self.inputs), 'outputs': list(self.outputs),
                'stages': list(self.stages), 'verifier': self.verifier, 'calculation': self.calculation,
                'verification': self.verification,
                'requirements': {key: list(value) for key, value in self.requirements.items()}}

    def defaults(self):
        values = {}
        if self.case_id == 'fielddeck-7':
            design = read(safe_file(self.root, 'design.json'))
            values.update(design.get('engineering_requirements', {}))
            assumptions = design['engineering_assumptions']
            values['pi_work_current_a'] = assumptions['pi_current_a']['work']
            values['keyboard_current_a'] = assumptions['keyboard_current_a']['normal_allocation']
        return self.validate(values)

    def describe(self):
        missing = [name for name in self.inputs if not (self.root / name).is_file()]
        defaults = self.defaults() if not missing else self.validate()
        return {'case_id': self.case_id, 'name': self.name, 'source_inputs_available': not missing,
                'missing_inputs': missing,
                'requirements': {name: {'default': defaults[name], 'minimum': low, 'maximum': high}
                                 for name, (default, low, high) in self.requirements.items()},
                'scope': 'Registered digital engineering case; no physical validation or authority.'}


_FIELD_PARTS = ('seam_plate_1', 'seam_plate_2', 'seam_plate_3', 'seam_plate_4', 'seam_plate_5',
                'seam_plate_6', 'tray_front_left', 'tray_front_right', 'tray_rear_left', 'tray_rear_right',
                'face_front_left', 'face_front_right', 'face_rear_left', 'face_rear_right',
                'fan_guard', 'fan_duct', 'foot_1', 'foot_2', 'foot_3', 'foot_4')
# Preserve the first registered artifact contract for pre-adapter snapshots.
# Evolve active cases by deriving a new definition, not editing this legacy set.
FIELDDECK_V1 = RegisteredCase(
    'fielddeck-7', 'Fielddeck 7 digital engineering',
    ROOT / 'projects/cyberdeck-real-trial-20261020/digital_v1',
    ('design.json', 'bom.json', 'study_contract.py', 'author_cad.py', 'engineering.py',
     'render_device.py', 'verify_device.py', 'sources/touch_display2_7inch.step',
     'sources/touch_display2_LICENSE.txt', 'sources/references.json', 'README.md', 'ASSEMBLY.md', 'CONNECTIONS.md',
     'software/README.md', 'software/setup.sh', 'software/healthcheck.sh'),
    ('cad/FIELDDECK_7.step', 'cad/FIELDDECK_7.glb', 'cad/geometry_report.json',
     'analysis/calculations.json', 'analysis/verification.json', 'analysis/power_runtime.png', 'BOM.csv',
     'views/assembled.png', 'views/exploded.png', 'views/internal.png',
     'views/dimensioned_layout.png', 'views/dimensioned_layout.svg',
     *(f'cad/print/{name}.{ext}' for name in _FIELD_PARTS for ext in ('step', 'stl'))),
    ('author_cad.py', 'engineering.py', 'render_device.py', 'verify_device.py'),
    'verify_device.py', 'analysis/calculations.json', 'analysis/verification.json',
    {'minimum_work_runtime_h': (2.5, .1, 24), 'minimum_supply_margin_a': (.3, 0, 2),
     'maximum_case_width_mm': (320, 100, 1000), 'maximum_case_depth_mm': (300, 100, 1000),
     'maximum_case_height_mm': (75, 20, 500), 'printer_bed_x_mm': (220, 100, 1000),
     'printer_bed_y_mm': (220, 100, 1000), 'pi_work_current_a': (1, .4, 2.5),
     'keyboard_current_a': (.1, .02, .5)})

FIELDDECK = replace(FIELDDECK_V1, inputs=(*FIELDDECK_V1.inputs, 'BACKEND.md'))

_FIELDDECK_REPO = 'projects/cyberdeck-real-trial-20261020'
_SWAP = _FIELDDECK_REPO + '/display_swap'
_BASE = _FIELDDECK_REPO + '/digital_v1'
_CHANGED_FIELD_PARTS = ('face_rear_left', 'face_rear_right', 'tray_rear_left', 'tray_rear_right')
FIELDDECK_5 = RegisteredCase(
    'fielddeck-5', 'Fielddeck 5 display revision', ROOT,
    (*(f'{_SWAP}/{name}' for name in ('build.py', 'assess.py', 'study_contract.py', 'study_build.py', 'study_verify.py',
                                     'sources/evidence.json', 'sources/vendor5.zip')),
     'src/hardware_splicer/part_substitution.py',
     *(f'{_BASE}/{name}' for name in ('cad/FIELDDECK_7.step', 'cad/geometry_report.json', 'analysis/verification.json',
                                      'design.json', 'bom.json', 'sources/touch_display2_LICENSE.txt')),
     *(f'{_BASE}/cad/print/{name}.{ext}' for name in _FIELD_PARTS if name not in _CHANGED_FIELD_PARTS
       for ext in ('step', 'stl'))),
    (*(f'revision/{name}' for name in ('geometry.json', 'power.json', 'engineering.json', 'verification.json',
                                      'BOM.json', 'BOM.csv', 'substitution.json', 'connections.json',
                                      'source-evidence.json', 'display5-LICENSE.txt', 'cad/FIELDDECK_5.step',
                                      'cad/FIELDDECK_5.glb')),
     *(f'revision/cad/changed_parts/{name}.{ext}' for name in (*_CHANGED_FIELD_PARTS, 'display_spacer_1')
       for ext in ('step', 'stl'))),
    (f'{_SWAP}/study_build.py', f'{_SWAP}/study_verify.py'), f'{_SWAP}/study_verify.py',
    'revision/engineering.json', 'revision/verification.json',
    {'minimum_work_runtime_h': (2.5, .1, 24), 'minimum_supply_margin_a': (.3, 0, 2),
     'pi_work_current_a': (1., .4, 2.5), 'keyboard_current_a': (.1, .02, .5)},
)

PLOTTER = RegisteredCase(
    'ender3-penplotter', 'Ender-3 reference-donor pen plotter',
    ROOT / 'projects/ender3-penplotter-digital',
    ('scripts/common.py', 'scripts/build.py', 'scripts/simulate.py', 'scripts/verify.py',
     'README.md', 'ASSEMBLY.md', 'BOM.md', 'VALIDATION.md', 'LICENSE', 'NOTICE.md',
     'sources/LICENSE', 'sources/manifest.json', 'sources/E plate.step', 'sources/E plate.pdf',
     'sources/E plate.SLDPRT', 'sources/Configuration.h', 'sources/Ender-3 BOM.XLS',
     'sources/interface.json', 'sources/assembly_parts.json', 'sources/nozzle.step', 'sources/README.md',
     'sources/Radiator.step', 'sources/2020 profile.step', 'sources/M4 T-Slot Nut.step'),
    ('exports/pen_adapter.step', 'exports/pen_adapter.stl', 'exports/pen_clamp.step',
     'exports/pen_clamp.stl', 'exports/plotter.step', 'exports/plotter.glb', 'exports/device_render.png',
     'exports/hotend_parking_plate.step', 'exports/hotend_parking_plate.stl',
     'simulation/example.svg', 'simulation/example.gcode', 'simulation/trajectory.csv',
     'simulation/plotted_drawing.png', 'reports/engineering.json', 'reports/simulation.json',
     'reports/verification.json', 'reports/export_manifest.json'),
    ('scripts/build.py', 'scripts/simulate.py', 'scripts/verify.py'),
    'scripts/verify.py', 'reports/engineering.json', 'reports/verification.json',
    {'drawing_width_mm': (100, 60, 190), 'drawing_height_mm': (80, 40, 140),
     'pen_diameter_mm': (10, 8, 12), 'pen_lift_mm': (3, 2, 5),
     'paper_width_mm': (180, 100, 220), 'paper_height_mm': (180, 100, 220)})

CASES = {case.case_id: case for case in (FIELDDECK, FIELDDECK_5, PLOTTER)}


def registered(case_id):
    if not isinstance(case_id, str) or case_id not in CASES:
        raise ValueError('Unknown registered digital case: ' + str(case_id))
    return CASES[case_id]


def validate_case_id(case_id):
    if case_id != DEFAULT_CASE:
        registered(case_id)
    return case_id


def archived(definition, case_id):
    """Restore a server-sealed adapter, never a client-supplied execution plan.

The definition travels with the exact source files. Evolving today's registry
cannot invalidate old evidence or select a different historical verifier.
"""
    current = registered(case_id)
    expected = {'schema', 'case_id', 'name', 'inputs', 'outputs', 'stages', 'verifier',
                'calculation', 'verification', 'requirements'}
    try:
        if (not isinstance(definition, dict) or set(definition) != expected
                or definition['schema'] != 'hardware_splicer.registered_case_adapter.v1'
                or definition['case_id'] != case_id
                or not isinstance(definition['name'], str) or not 1 <= len(definition['name']) <= 100):
            raise ValueError('Invalid adapter identity')
        for key in ('inputs', 'outputs', 'stages'):
            names = definition[key]
            if (not isinstance(names, list) or not 1 <= len(names) <= 256
                    or any(not valid_name(name) for name in names) or len(set(names)) != len(names)):
                raise ValueError('Invalid adapter paths')
        inputs, outputs = set(definition['inputs']), set(definition['outputs'])
        reserved = {CONTRACT, RECEIPT, ENTRYPOINT, 'requirements.json', 'LICENSE_HS.txt', 'STUDY.zip', 'sealed-run.json'}
        if (inputs & outputs or (inputs | outputs) & reserved
                or not set(definition['stages']) <= inputs
                or any(not stage.endswith('.py') for stage in definition['stages'])
                or definition['verifier'] != definition['stages'][-1]
                or definition['calculation'] not in outputs or definition['verification'] not in outputs):
            raise ValueError('Invalid adapter entrypoints')
        bounds = definition['requirements']
        if not isinstance(bounds, dict) or not 1 <= len(bounds) <= 64:
            raise ValueError('Invalid adapter requirements')
        for key, values in bounds.items():
            if (not isinstance(key, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,63}', key)
                    or not isinstance(values, list) or len(values) != 3
                    or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in values)
                    or not values[1] <= values[0] <= values[2]):
                raise ValueError('Invalid adapter requirement bounds')
        return RegisteredCase(case_id, definition['name'], current.root,
                              tuple(definition['inputs']), tuple(definition['outputs']), tuple(definition['stages']),
                              definition['verifier'], definition['calculation'], definition['verification'],
                              {key: tuple(value) for key, value in bounds.items()})
    except (ValueError, KeyError, TypeError, OverflowError) as exc:
        raise CorruptProject('The archived registered case definition is invalid.') from exc


def valid_name(name):
    return (isinstance(name, str) and 0 < len(name) <= 256 and '\\' not in name and '\x00' not in name
            and name == PurePosixPath(name).as_posix() and not PurePosixPath(name).is_absolute()
            and '..' not in PurePosixPath(name).parts and name != '.')


def safe_file(directory, name):
    """Check every nested component, including symlinks to other owned files."""
    if not valid_name(name):
        raise CorruptProject('Invalid digital artifact path.')
    directory = Path(directory)
    path = directory
    for part in PurePosixPath(name).parts:
        path = path / part
        if path.is_symlink():
            raise CorruptProject('Digital artifact paths cannot contain symbolic links.')
    if not path.is_file():
        raise CorruptProject('Digital artifact is missing: ' + name)
    return path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    try:
        result = json.loads(Path(path).read_text())
        if not isinstance(result, dict):
            raise ValueError('Expected an object')
        return result
    except (OSError, ValueError) as exc:
        raise CorruptProject('Registered study JSON is missing or invalid.') from exc


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n')


DRAWING = 'sources/prompt-drawing.json'


def with_drawing(case):
    if case.case_id != 'ender3-penplotter':
        raise ValueError('Prompt artwork requires a pen plotter.')
    return replace(case, inputs=(*case.inputs, DRAWING))


def prepare(case, destination, requirements, *, source=None, drawing=None):
    source = Path(source) if source is not None else case.root
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    for name in case.inputs:
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if name == DRAWING and drawing is not None:
            write(target, drawing)
        else:
            shutil.copyfile(safe_file(source, name), target)
    # Scripts use their own path, never process cwd, and write only here.
    for name in case.outputs:
        (destination / name).parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / 'LICENSE', destination / 'LICENSE_HS.txt')
    requirements = case.validate(requirements)
    write(destination / 'requirements.json', requirements)
    write(destination / CONTRACT, {
        'schema': 'hardware_splicer.registered_case_contract.v1', 'case_id': case.case_id,
        'adapter': case.definition(),
        'requirements': requirements, 'source_sha256': {name: sha(destination / name) for name in case.inputs},
        'physical_work_requested': False, 'physical_authority_granted': False})
    write_readme(case, destination, requirements)


def write_readme(case, directory, requirements):
    stages = '\n'.join('python -B ' + stage for stage in case.stages)
    rows = '\n'.join(f'| `{name}` | {value:g} |' for name, value in requirements.items())
    docs = '\n'.join(f'- [{name}](<{name}>)' for name in case.inputs if name.endswith('.md'))
    dependencies = ('CadQuery, trimesh, numpy, Pillow, matplotlib and Pydantic v2' if case.case_id == 'fielddeck-5'
                    else 'CadQuery, trimesh, numpy, Pillow and matplotlib')
    text = f'''# {case.name}

This is an executable digital study for the registered case `{case.case_id}`.
The backend generated its outputs in an isolated workspace and ran the native
verifier before sealing this package. No physical fit, operation, fabrication,
purchase or ownership of a donor is established by these results.

Start with [engineering results](<{case.calculation}>) and
[native verification](<{case.verification}>). The engineering report records
whether the selected numeric goals pass; a failed goal can be a valid completed
study. [Requirements](requirements.json), [source contract]({CONTRACT}) and
[artifact receipt]({RECEIPT}) preserve the case identity, source hashes, computed
claims and exact payload hashes. The backend export response supplies the project
and revision identity and SHA256 of the enclosing ZIP.

## Reproduce the native study

Extract this archive into a new working directory. Use a Python environment with
{dependencies}, and run these included scripts
from the extracted directory:

```sh
{stages}
```

The scripts use their own directory to locate inputs. The last stage checks the
exported geometry and recomputes the retained engineering evidence. Re-running
scripts changes local outputs and invalidates the old artifact receipt; submit a
new revision through the backend to obtain a new sealed package. The backend
accepts only the named numeric requirements for this case.

| Requirement | Selected value |
| --- | ---: |
{rows}

## Included source documentation

{docs or 'The source manifest and engineering reports describe the retained inputs.'}

Captured source documentation may also describe a separate standalone delivery.
Its HS-import and standalone publication helpers are outside this executable
backend package. Use this page and the included scripts for this sealed study.
The [Hardware Splicer license](LICENSE_HS.txt) covers the backend package glue.
Vendor and case-specific source licenses remain beside their retained files.
'''
    (directory / ENTRYPOINT).write_text(text)


def summarize(case, directory):
    contract = read(safe_file(directory, CONTRACT))
    requirements = case.validate(read(safe_file(directory, 'requirements.json')))
    report = read(safe_file(directory, case.calculation))
    verification = read(safe_file(directory, case.verification))
    if (contract.get('schema') != 'hardware_splicer.registered_case_contract.v1'
            or contract.get('case_id') != case.case_id or report.get('case_id') != case.case_id
            or contract.get('requirements') != requirements or report.get('requirements') != requirements
            or contract.get('physical_work_requested') is not False
            or contract.get('physical_authority_granted') is not False):
        raise CorruptProject('Registered study case or requirements differ from the execution contract.')
    if contract.get('adapter', case.definition()) != case.definition():
        raise CorruptProject('Registered study adapter differs from its archived execution contract.')
    authority_flags = ('physical_work_requested', 'physical_authority_granted', 'physical_validation',
                       'physical_validation_performed', 'fabrication_authorized', 'power_on_authorized',
                       'firmware_authorized', 'flight_authorized')
    if any(record.get(key, False) is not False
           for record in (contract, report, verification) for key in authority_flags):
        raise CorruptProject('Registered digital evidence cannot grant or claim physical authority.')
    source_hashes = {name: sha(safe_file(directory, name)) for name in case.inputs}
    if contract.get('source_sha256') != source_hashes:
        raise CorruptProject('Registered study source inputs changed after execution.')
    if case.case_id == 'fielddeck-7':
        intact = (verification.get('status') == 'digital_geometry_checks_passed'
                  and verification.get('assembly_valid') is True
                  and verification.get('physical_fit_or_operation_proven') is False
                  and verification.get('assembly_step_sha256') == sha(directory / 'cad/FIELDDECK_7.step'))
    elif case.case_id == 'fielddeck-5':
        hashes = {name: sha(safe_file(directory, name)) for name in case.outputs if name != case.verification}
        intact = (verification.get('artifact_integrity') is True
                  and verification.get('case_id') == case.case_id
                  and verification.get('engineering_acceptance') is report.get('requirements_met')
                  and verification.get('artifact_sha256') == hashes)
    else:
        intact = verification.get('artifact_integrity') is True
    if not intact:
        raise CorruptProject('The registered native verifier did not establish artifact integrity.')
    constraints = report.get('constraints')
    metrics = report.get('metrics')
    if (not isinstance(constraints, list) or not constraints
            or any(not isinstance(c, dict) or not isinstance(c.get('id'), str)
                   or type(c.get('passed')) is not bool for c in constraints)
            or len({c['id'] for c in constraints}) != len(constraints)
            or not isinstance(metrics, dict) or not metrics
            or any(isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v)
                   for v in metrics.values())):
        raise CorruptProject('The registered engineering result has invalid constraints or metrics.')
    acceptance = all(c['passed'] for c in constraints)
    if report.get('requirements_met') is not acceptance:
        raise CorruptProject('The engineering acceptance claim differs from its constraints.')
    result = {'case_id': case.case_id, 'requirements': requirements, 'requirements_met': acceptance,
              'artifact_integrity': True, 'metrics': metrics, 'constraints': constraints,
              'source_sha256': source_hashes, 'engine': 'Registered native CAD and engineering case',
              'physical_work_requested': False, 'physical_authority_granted': False,
              'scope_limits': ['Digital geometry and declared calculation/simulation models only.',
                               'No purchased/owned hardware, physical fit, operation or fabrication is established.']}
    json.dumps(result, allow_nan=False)
    return result


def seal_package(case, directory):
    summary = summarize(case, directory)
    hashes = {name: sha(safe_file(directory, name)) for name in sorted(case.artifacts - {RECEIPT})}
    write(directory / RECEIPT, {'schema': 'hardware_splicer.registered_case_verification.v1',
                              'case_id': case.case_id, 'artifact_integrity': True,
                              'summary': summary, 'artifact_sha256': hashes})
    return summary


def verified_package(case, directory):
    receipt = read(safe_file(directory, RECEIPT))
    hashes = receipt.get('artifact_sha256')
    if (receipt.get('schema') != 'hardware_splicer.registered_case_verification.v1'
            or receipt.get('case_id') != case.case_id or receipt.get('artifact_integrity') is not True
            or not isinstance(hashes, dict) or set(hashes) != case.artifacts - {RECEIPT}):
        raise CorruptProject('Registered digital artifact inventory or verification is invalid.')
    for name, digest in hashes.items():
        if sha(safe_file(directory, name)) != digest:
            raise CorruptProject('Digital artifact changed after verification: ' + name)
    summary = summarize(case, directory)
    if receipt.get('summary') != summary:
        raise CorruptProject('Registered digital claims differ from their verified artifacts.')
    return summary
