"""Revision-bound substitution studies and reviewable declared assembly changes."""
from __future__ import annotations

from copy import deepcopy
import csv
import errno
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
from uuid import uuid4
import zipfile

from .project_materials import _canonical, _digest
from .project_store import CorruptProject, ProjectNotFound, ProjectStore, RevisionConflict, _atomic_write_json
from .project_wiring import _pointer
from .source_revision_impact import invalidate_source_derived_outputs
from .stored_source_parser import read_registered_source_bytes

SCHEMA = 'hardware_splicer.project_part_substitution.v1'
_ID = re.compile(r'substitution-[a-f0-9]{32}\Z')
MAX_RECORD_BYTES = 4_000_000
MAX_EXPORT_BYTES = 64 * 1024 * 1024


def _evaluator():
    from . import part_substitution
    return part_substitution


def _evaluator_hash():
    return hashlib.sha256(Path(_evaluator().__file__).read_bytes()).hexdigest()


def _directory(store, project_id, *, create=False):
    project = store._project_dir(project_id)
    path = project / 'part_substitutions'
    if path.is_symlink():
        raise CorruptProject('Substitution directory cannot be a symbolic link.')
    if create:
        path.mkdir(exist_ok=True)
    return path


def _record_path(store, project_id, assessment_id):
    if not isinstance(assessment_id, str) or not _ID.fullmatch(assessment_id):
        raise ValueError('Invalid substitution assessment ID.')
    return _directory(store, project_id) / assessment_id


def _read_file(directory, relative, *, limit=MAX_EXPORT_BYTES):
    # Generated inventories contain only flat geometry/ filenames and data files.
    if (not isinstance(relative, str) or '\\' in relative or '\x00' in relative
            or Path(relative).is_absolute() or '..' in Path(relative).parts
            or relative != Path(relative).as_posix()):
        raise CorruptProject('Invalid substitution artifact name.')
    current = directory
    if current.is_symlink():
        raise CorruptProject('Unsafe substitution artifact directory.')
    for part in Path(relative).parts:
        current = current / part
        if current.is_symlink():
            raise CorruptProject('Substitution artifacts cannot be symbolic links.')
    if not current.is_file() or current.stat().st_size > limit:
        raise CorruptProject('Substitution artifact is missing or exceeds its limit.')
    return current.read_bytes()


def _source_checks(store, project_id, snapshot, spec):
    sources = snapshot.get('engineeringSources') or []
    cache, checks = {}, []
    profiles = [*spec.parts, spec.candidate]
    for index, profile in enumerate(profiles):
        role = 'candidate' if index == len(spec.parts) else 'assembly_part'
        binding = profile.source
        if binding is None:
            checks.append({'part_id': profile.part_id, 'role': role, 'status': 'unbound_declaration',
                           'authority': 'declared_digital_profile_only'})
            continue
        selected = [row for row in sources if isinstance(row, dict)
                    and row.get('source_id') == binding.source_id
                    and row.get('content_hash') == binding.content_hash]
        if len(selected) != 1:
            raise ValueError('Part source binding must match one registered source in this project revision.')
        if binding.source_id not in cache:
            raw = read_registered_source_bytes(project_id, selected[0], project_root=store.root)
            if len(raw) > 2_000_000:
                raise ValueError('Part profile JSON source exceeds 2 MB.')
            cache[binding.source_id] = json.loads(raw)
            if sum(len(_canonical(item)) for item in cache.values()) > 8_000_000:
                raise ValueError('Selected part source data exceeds 8 MB.')
        data = _pointer(cache[binding.source_id], binding.pointer)
        if not isinstance(data, dict):
            raise ValueError('Part source pointer must identify a profile object.')
        source_profile = type(profile).model_validate({**data, 'source': None})
        excluded = {'part_id', 'position_mm', 'source', 'replacement_profile_id'}
        if source_profile.model_dump(exclude=excluded) != profile.model_dump(exclude=excluded):
            raise ValueError('Declared part profile differs from its retained source pointer.')
        checks.append({'part_id': profile.part_id, 'role': role,
                       'status': 'registered_profile_bytes_match',
                       **binding.model_dump(mode='json'), 'authority': 'declared_contract_only',
                       'binding_scope': 'intrinsic_profile_specs_without_instance_id_or_placement'})
    return checks


def _assembly(spec, *, revised=None):
    data = spec.model_dump(mode='json', by_alias=True)
    return {'parts': data['parts'] if revised is None else revised['parts'],
            'connections': data['connections'] if revised is None else revised['connections'],
            'enclosure': data.get('enclosure'), 'scenarios': data.get('scenarios', [])}


def assess_project_substitution(
    store: ProjectStore, project_id: str, *, expected_revision: int,
    specification, generate_geometry: bool = False,
) -> dict:
    if type(expected_revision) is not int or expected_revision < 1 or type(generate_geometry) is not bool:
        raise ValueError('expected_revision must be a positive integer and generate_geometry must be boolean.')
    envelope = store.load(project_id)
    if envelope['revision'] != expected_revision:
        raise RevisionConflict('The project changed. Reload before assessing a substitution.')
    core = _evaluator()
    spec = core.SubstitutionSpecification.model_validate(specification)
    if len(_canonical(spec.model_dump(mode='json', by_alias=True))) > 2_000_000:
        raise ValueError('Part substitution input exceeds 2 MB.')
    existing = envelope['snapshot'].get('partAssembly')
    if existing is not None and existing != _assembly(spec):
        raise ValueError('The supplied baseline differs from this revision\'s retained partAssembly.')
    source_checks = _source_checks(store, project_id, envelope['snapshot'], spec)
    report = core.evaluate_substitution(spec)
    stage = _directory(store, project_id, create=True) / ('stage-' + uuid4().hex)
    stage.mkdir(mode=0o700)
    try:
        geometry = {'status': 'not_requested', 'files': {}}
        if generate_geometry:
            from .part_substitution_geometry import generate_substitution_geometry
            geometry = generate_substitution_geometry(report, stage / 'geometry')
        record = {
            'schema_version': SCHEMA, 'project_id': project_id, 'source_revision': expected_revision,
            'source_snapshot_sha256': _digest(envelope['snapshot']),
            'baseline_binding': 'retained_part_assembly' if existing is not None else 'provided_assembly_declaration',
            'specification': spec.model_dump(mode='json', by_alias=True), 'source_checks': source_checks,
            'evaluator_sha256': _evaluator_hash(), 'report': report, 'geometry': geometry,
            'physical_authority_granted': False, 'manufacturing_approved': False,
        }
        record['assessment_id'] = 'substitution-' + _digest(record)[:32]
        if len(_canonical(record)) > MAX_RECORD_BYTES:
            raise ValueError('Substitution assessment exceeds 4 MB.')
        if store.load(project_id)['revision'] != expected_revision:
            raise RevisionConflict('The project changed while assessing the substitution.')
        _atomic_write_json(stage / 'assessment.json', record, exclusive=True)
        destination = _record_path(store, project_id, record['assessment_id'])
        if destination.exists():
            return load_substitution_assessment(store, project_id, record['assessment_id'])
        try:
            stage.rename(destination)
        except OSError as exc:
            if exc.errno not in {errno.EEXIST, errno.ENOTEMPTY}:
                raise
            return load_substitution_assessment(store, project_id, record['assessment_id'])
        return load_substitution_assessment(store, project_id, record['assessment_id'])
    finally:
        if stage.exists() and not stage.is_symlink():
            shutil.rmtree(stage)


def load_substitution_assessment(store: ProjectStore, project_id: str, assessment_id: str) -> dict:
    directory = _record_path(store, project_id, assessment_id)
    if not directory.exists():
        raise ProjectNotFound('Substitution assessment not found in this project.')
    try:
        record = json.loads(_read_file(directory, 'assessment.json', limit=MAX_RECORD_BYTES))
        expected_keys = {'schema_version', 'project_id', 'source_revision', 'source_snapshot_sha256',
                         'baseline_binding', 'specification', 'source_checks', 'evaluator_sha256',
                         'report', 'geometry', 'physical_authority_granted', 'manufacturing_approved', 'assessment_id'}
        if not isinstance(record, dict) or set(record) != expected_keys:
            raise ValueError('Unexpected assessment fields.')
        unsigned = {key: value for key, value in record.items() if key != 'assessment_id'}
        if (record['schema_version'] != SCHEMA or record['project_id'] != project_id
                or record['assessment_id'] != assessment_id or 'substitution-' + _digest(unsigned)[:32] != assessment_id
                or type(record['source_revision']) is not int or record['source_revision'] < 1
                or record['physical_authority_granted'] is not False or record['manufacturing_approved'] is not False):
            raise ValueError('Assessment identity or content hash differs.')
        source = store.load(project_id, revision=record['source_revision'])
        if _digest(source['snapshot']) != record['source_snapshot_sha256']:
            raise ValueError('Assessment source revision changed.')
        spec = _evaluator().SubstitutionSpecification.model_validate(record['specification'])
        if _source_checks(store, project_id, source['snapshot'], spec) != record['source_checks']:
            raise ValueError('Part source bindings differ.')
        current_evaluator = record['evaluator_sha256'] == _evaluator_hash()
        if current_evaluator and _evaluator().evaluate_substitution(spec) != record['report']:
            raise ValueError('Assessment claims differ from their inputs.')
        total_bytes = 0
        files = record['geometry'].get('files', {})
        if not isinstance(files, dict) or len(files) > 16:
            raise ValueError('Invalid geometry artifact inventory.')
        for name, entry in files.items():
            raw = _read_file(directory, 'geometry/' + name)
            digest = hashlib.sha256(raw).hexdigest()
            if digest != str(entry['sha256']).removeprefix('sha256:') or len(raw) != entry['size_bytes']:
                raise ValueError('Geometry artifact failed hash verification.')
            total_bytes += len(raw)
        if total_bytes > MAX_EXPORT_BYTES:
            raise ValueError('Geometry artifact set exceeds 64 MiB.')
    except (TypeError, KeyError, ValueError) as exc:
        raise CorruptProject('Invalid substitution assessment: ' + str(exc)) from exc
    return {'ok': True, 'assessment': record,
            'current_for_project': store.load(project_id)['revision'] == record['source_revision'],
            'evaluator_matches_current': current_evaluator}


def _candidate_snapshot(snapshot, record, directory):
    from .project_candidates import rewrite_snapshot_build_dirs
    core = _evaluator()
    spec = core.SubstitutionSpecification.model_validate(record['specification'])
    candidate = rewrite_snapshot_build_dirs(snapshot, str(directory))
    candidate['buildDir'] = str(directory)
    assembly = _assembly(spec, revised=record['report']['revised'])
    # Keep the accepted assembly usable as the baseline for another assessment.
    # An exploratory report may still export unresolved connections.
    try:
        core.SubstitutionSpecification.model_validate({
            **assembly, 'replace_part_id': spec.replace_part_id,
            'candidate': spec.candidate.model_dump(mode='json'),
        })
    except ValueError as exc:
        raise ValueError('Resolve revised port mappings and scenario inputs before proposing this assembly.') from exc
    candidate['partAssembly'] = assembly
    candidate['partSubstitution'] = {
        'assessment_id': record['assessment_id'], 'source_revision': record['source_revision'],
        'assessment_sha256': _digest(record), 'status': record['report']['status'],
        'geometry_basis': 'declared_nominal_envelopes_only',
        'native_electrical_design_regenerated': False, 'physical_authority_granted': False,
    }
    return invalidate_source_derived_outputs(
        candidate, changed_source_ids=[row['source_id'] for row in record['source_checks'] if row.get('source_id')],
        changed_artifact_kinds=['part_assembly'], basis='part_substitution',
    )


def propose_project_substitution(store, project_id, assessment_id, *, expected_revision, author='sdk', note=''):
    from .project_review_store import ProjectReviewStore
    if type(expected_revision) is not int or expected_revision < 1:
        raise ValueError('expected_revision must be a positive integer.')
    loaded = load_substitution_assessment(store, project_id, assessment_id)
    record = loaded['assessment']
    if (record['source_revision'] != expected_revision or not loaded['current_for_project']
            or not loaded['evaluator_matches_current']):
        raise RevisionConflict('Substitution proposals require a current assessment of this exact revision.')
    snapshot = store.load(project_id, revision=expected_revision)['snapshot']
    if snapshot.get('mode') == 'digital':
        raise ValueError('Registered digital cases keep their native contract; export this separate declared assembly study instead.')
    candidate = _candidate_snapshot(snapshot, record, _record_path(store, project_id, assessment_id))
    review = ProjectReviewStore(store).create(project_id, candidate, base_revision=expected_revision,
                                             created_by=author, note=note)
    return {'ok': True, 'assessment_id': assessment_id, 'review': review,
            'candidate_accepted': False, 'physical_authority_granted': False}


def validate_substitution_review(store, project_id, review):
    """Keep generic review acceptance bound to the retained substitution study."""
    candidate = review.get('candidate_snapshot') or {}
    marker = candidate.get('partSubstitution')
    if marker is None:
        return
    if not isinstance(marker, dict):
        raise ValueError('Invalid substitution review binding.')
    loaded = load_substitution_assessment(store, project_id, marker.get('assessment_id'))
    record = loaded['assessment']
    spec = _evaluator().SubstitutionSpecification.model_validate(record['specification'])
    expected = _candidate_snapshot(store.load(project_id, revision=record['source_revision'])['snapshot'], record,
                                   _record_path(store, project_id, record['assessment_id']))
    if marker != expected['partSubstitution'] or candidate.get('partAssembly') != _assembly(spec, revised=record['report']['revised']):
        raise ValueError('Substitution review differs from its retained candidate assembly.')
    base = store.load(project_id, revision=review['base_revision'])['snapshot']
    if marker != base.get('partSubstitution'):
        if not loaded['evaluator_matches_current']:
            raise ValueError('Substitution evaluator changed; reassess before accepting this assembly.')
        if review['base_revision'] != record['source_revision']:
            raise ValueError('New substitution review must use its assessed source revision.')
        if store.load(project_id, revision=record['source_revision'])['snapshot'].get('mode') == 'digital':
            raise ValueError('Registered digital cases keep their native contract; this assembly is assessment-only.')
        if candidate != expected:
            raise ValueError('New substitution review must match the assessed candidate snapshot.')


def export_substitution_bundle(store, project_id, assessment_id) -> bytes:
    record = load_substitution_assessment(store, project_id, assessment_id)['assessment']
    directory = _record_path(store, project_id, assessment_id)
    payload = {'assessment.json': (json.dumps(record, indent=2, sort_keys=True) + '\n').encode(),
               'revised-assembly.json': (json.dumps(record['report']['revised'], indent=2, sort_keys=True) + '\n').encode()}
    output = io.StringIO(newline='')
    writer = csv.writer(output)
    writer.writerow(['part_id', 'name', 'manufacturer', 'mpn', 'quantity', 'basis'])
    for part in record['report']['revised']['parts']:
        values = [part['part_id'], part['name'], part.get('manufacturer') or '', part.get('mpn') or '', 1, 'declared digital profile']
        writer.writerow(["'" + value if isinstance(value, str) and value.startswith(('=', '+', '-', '@', '\t', '\r')) else value for value in values])
    payload['BOM.csv'] = output.getvalue().encode()
    payload['connections.json'] = (json.dumps(record['report']['revised']['connections'], indent=2, sort_keys=True) + '\n').encode()
    for name, entry in record['geometry'].get('files', {}).items():
        raw = _read_file(directory, 'geometry/' + name)
        if (hashlib.sha256(raw).hexdigest() != str(entry['sha256']).removeprefix('sha256:')
                or len(raw) != entry['size_bytes']):
            raise CorruptProject('Substitution geometry changed before export.')
        payload['geometry/' + name] = raw
    if sum(map(len, payload.values())) > MAX_EXPORT_BYTES:
        raise ValueError('Substitution export exceeds 64 MiB.')
    payload['MANIFEST.json'] = (json.dumps({
        'schema_version': SCHEMA, 'project_id': project_id, 'assessment_id': assessment_id,
        'files': {name: 'sha256:' + hashlib.sha256(raw).hexdigest() for name, raw in payload.items()},
        'physical_authority_granted': False, 'manufacturing_approved': False,
    }, sort_keys=True, indent=2) + '\n').encode()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, raw in sorted(payload.items()):
            archive.writestr(zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0)), raw,
                             compress_type=zipfile.ZIP_DEFLATED)
    return buffer.getvalue()
