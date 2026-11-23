"""Promote retained upload bytes into an editable native KiCad workspace."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
from typing import Any, Mapping, Sequence
from uuid import uuid4
import zipfile

from .artifact_retention import retain_revision_artifacts, validate_kicad_rule_bytes
from .build_files_security import assert_build_dir_allowed
from .kicad_diff import parse_kicad_sexp
from .machine_project import MachineProject
from .project_candidates import (
    _ensure_dir_chain, _output_root, _rmtree_nofollow, _write_named_create_only,
    rewrite_snapshot_build_dirs,
)
from .project_store import ProjectStore, RevisionConflict, validate_project_id
from .source_revision_impact import invalidate_source_derived_outputs
from .stored_source_parser import read_registered_source_bytes


SCHEMA = 'hardware_splicer.source_project_editing.v1'
SUFFIXES = {'.kicad_pcb', '.kicad_sch', '.kicad_pro', '.kicad_dru'}
MAX_FILES = 16


def _filename(source: Mapping[str, Any]) -> str:
    metadata = source.get('metadata') or {}
    if not isinstance(metadata, Mapping):
        raise ValueError('Source metadata must be an object.')
    name = metadata.get('original_filename')
    if (not isinstance(name, str) or not name or len(name) > 255
            or name != Path(name).name or '/' in name or '\\' in name
            or name.startswith('.') or ':' in name or any(ord(c) < 32 for c in name)):
        raise ValueError('Editable source filenames must be safe basenames.')
    return name


def _selected_sources(snapshot, source_ids, primary_source_id):
    rows = [row for row in snapshot.get('engineeringSources', []) if isinstance(row, Mapping)]
    if source_ids is not None:
        if (not isinstance(source_ids, (list, tuple)) or not 1 <= len(source_ids) <= MAX_FILES
                or any(not isinstance(value, str) or not value for value in source_ids)
                or len(set(source_ids)) != len(source_ids)):
            raise ValueError('source_ids must contain distinct registered source IDs.')
        rows = [row for row in rows if row.get('source_id') in source_ids]
        if {row.get('source_id') for row in rows} != set(source_ids):
            raise ValueError('Selected source ID is not registered in this project.')
    eligible = []
    for row in rows:
        metadata = row.get('metadata') or {}
        if not isinstance(metadata, Mapping):
            raise ValueError('Source metadata must be an object.')
        raw = metadata.get('original_filename', '')
        if not isinstance(raw, str) or Path(raw).suffix.lower() not in SUFFIXES:
            if source_ids is not None:
                raise ValueError('Only native KiCad files and rule companions can be promoted.')
            continue
        name = _filename(row)
        if Path(name).suffix not in SUFFIXES:
            raise ValueError('Native KiCad filename extensions must use canonical lowercase.')
        eligible.append((row, name))
    mains = [(row, name) for row, name in eligible if Path(name).suffix in {'.kicad_pcb', '.kicad_sch'}]
    if primary_source_id is not None:
        if not isinstance(primary_source_id, str) or not primary_source_id:
            raise ValueError('primary_source_id must identify a registered PCB or schematic.')
        matches = [(row, name) for row, name in mains if row.get('source_id') == primary_source_id]
        if len(matches) != 1:
            raise ValueError('primary_source_id must select exactly one PCB or schematic.')
        primary, primary_name = matches[0]
    else:
        boards = [(row, name) for row, name in mains if name.endswith('.kicad_pcb')]
        choices = boards or mains
        if len(choices) != 1:
            raise ValueError('Select one native project with source_ids or primary_source_id.')
        primary, primary_name = choices[0]
    stem = Path(primary_name).stem
    selected = [(row, name) for row, name in eligible if Path(name).stem == stem]
    if source_ids is not None and len(selected) != len(eligible):
        raise ValueError('Selected files must belong to the same native project stem.')
    names = [name for row, name in selected]
    if not selected or len(selected) > MAX_FILES or len(set(names)) != len(names):
        raise ValueError('Native project filenames must have unambiguous source identities.')
    return selected, primary, primary_name


def _validate_bytes(name: str, raw: bytes) -> None:
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError as exc:
        raise ValueError('Native KiCad project files must be UTF-8 text.') from exc
    if '\x00' in text:
        raise ValueError('Native KiCad files cannot contain NUL bytes.')
    suffix = Path(name).suffix
    if suffix in {'.kicad_pcb', '.kicad_sch'}:
        tree = parse_kicad_sexp(text)
        expected = 'kicad_pcb' if suffix == '.kicad_pcb' else 'kicad_sch'
        if not isinstance(tree, list) or not tree or tree[0] != expected:
            raise ValueError('Source content does not match its native KiCad filename.')
        if suffix == '.kicad_sch' and any(isinstance(item, list) and item and item[0] == 'sheet' for item in tree):
            raise ValueError('Hierarchical schematic promotion needs sheet dependencies; select board/project files for PCB-only editing.')
    elif suffix == '.kicad_pro':
        def invalid_constant(value):
            raise ValueError('Nonfinite number in KiCad project configuration.')
        if not isinstance(json.loads(text, parse_constant=invalid_constant), dict):
            raise ValueError('KiCad project configuration must be a JSON object.')
    else:
        validate_kicad_rule_bytes(raw)


def prepare_kicad_source_bundle(
    store: ProjectStore, project_id: str, *, expected_revision: int,
    source_ids: Sequence[str] | None = None, primary_source_id: str | None = None,
) -> dict[str, Any]:
    """Create an isolated native workspace; caller publishes exactly one revision."""
    project_id = validate_project_id(project_id)
    if type(expected_revision) is not int or expected_revision < 1:
        raise ValueError('expected_revision must be a positive integer.')
    envelope = store.load(project_id)
    if envelope['revision'] != expected_revision:
        raise RevisionConflict('The source project changed; reload before promotion.')
    snapshot = deepcopy(envelope['snapshot'])
    if snapshot.get('mode') == 'digital':
        raise ValueError('Registered digital studies publish through their own jobs; import native sources into a separate editable project.')
    selected, primary, primary_name = _selected_sources(snapshot, source_ids, primary_source_id)
    canonical = snapshot.get('machineProject')
    legacy = snapshot.get('machine_project')
    project = MachineProject.model_validate(canonical or legacy) if canonical or legacy else MachineProject(
        project_id=project_id, name=str(snapshot.get('projectName') or Path(primary_name).stem),
        purpose=str(snapshot.get('goal') or 'Edit the supplied native hardware design.'),
    )
    if canonical and legacy and project != MachineProject.model_validate(legacy):
        raise ValueError('machineProject and machine_project disagree; native source promotion is ambiguous.')
    payload = {}
    for row, name in selected:
        raw = read_registered_source_bytes(project_id, row, project_root=store.root)
        _validate_bytes(name, raw)
        payload[name] = raw
    if sum(map(len, payload.values())) > 32 * 1024 * 1024:
        raise ValueError('Selected native bundle exceeds the 32 MiB workspace limit.')
    root = _output_root()
    root.mkdir(parents=True, exist_ok=True)
    bundle_id = 'bundle-' + uuid4().hex
    workspace = _ensure_dir_chain(root, ('source_edits', project_id, bundle_id), last_exist_ok=False)
    try:
        assert_build_dir_allowed(workspace)
        compilation = _ensure_dir_chain(workspace, ('build_compilation',), last_exist_ok=False)
        for name, raw in payload.items():
            _write_named_create_only(compilation, name, raw)
        stem = Path(primary_name).stem
        context = ('source_project_rules' if stem + '.kicad_pro' in payload else
                   'custom_rules_without_project_settings' if stem + '.kicad_dru' in payload else
                   'standalone_defaults_only')
        promotion = {
            'schema_version': SCHEMA, 'bundle_id': bundle_id, 'project_id': project_id,
            'machine_project_id': project.project_id,
            'source_revision': expected_revision, 'build_dir': str(workspace),
            'primary_source_id': primary['source_id'], 'primary_filename': primary_name,
            'source_ids': [row['source_id'] for row, name in selected],
            'sources': {name: {'source_id': row['source_id'], 'content_hash': row['content_hash'],
                               'sha256': 'sha256:' + hashlib.sha256(payload[name]).hexdigest()}
                        for row, name in selected},
            'editable_kinds': [kind for extension, kind in (('.kicad_pcb', 'pcb'), ('.kicad_sch', 'schematic'))
                               if stem + extension in payload],
            'check_scope': context,
            'warnings': [] if context == 'source_project_rules' else [
                'No matching .kicad_pro was selected; checks cannot establish original project-rule equivalence.'],
            'native_source_bytes_unchanged': True,
            'physical_authority_granted': False, 'manufacturing_approved': False,
        }
        _write_named_create_only(workspace, 'SOURCE_EDITING.json', (json.dumps(promotion, indent=2) + '\n').encode())
        snapshot = rewrite_snapshot_build_dirs(snapshot, str(workspace))
        snapshot['buildDir'] = str(workspace)
        snapshot['sourceEditing'] = promotion
        if not snapshot.get('machineProject'):
            snapshot['machineProject'] = project.model_dump(mode='json')
        snapshot = invalidate_source_derived_outputs(
            snapshot, changed_source_ids=promotion['source_ids'],
            changed_artifact_kinds=promotion['editable_kinds'], basis='registered_source_promotion',
        )
        return {'snapshot': snapshot, 'promotion': promotion, 'build_dir': str(workspace)}
    except BaseException:
        _rmtree_nofollow(workspace)
        raise


def discard_prepared_kicad_source_bundle(prepared: Mapping[str, Any], *, store: ProjectStore | None = None) -> None:
    """Remove only this preparation's server-owned, unpublished workspace."""
    promotion = prepared['promotion']
    path = Path(prepared['build_dir'])
    expected = _output_root() / 'source_edits' / validate_project_id(promotion['project_id']) / promotion['bundle_id']
    if (path != expected or not promotion['bundle_id'].startswith('bundle-')
            or len(promotion['bundle_id']) != 39):
        raise ValueError('Refusing cleanup outside the prepared source workspace.')
    if store is not None:
        from .project_store import ProjectNotFound
        try:
            committed = store.load(promotion['project_id'], revision=promotion['source_revision'] + 1)
        except ProjectNotFound:
            committed = None
        if committed:
            saved = committed['snapshot'].get('sourceEditing') or {}
            if saved.get('bundle_id') == promotion['bundle_id'] and saved.get('build_dir') == str(path):
                # The immutable revision can commit before a manifest write
                # fails. Never delete the source bytes that revision references.
                return
    _rmtree_nofollow(path)


def promote_kicad_source_bundle(store: ProjectStore, project_id: str, **options) -> dict[str, Any]:
    prepared = prepare_kicad_source_bundle(store, project_id, **options)
    try:
        saved = store.save(project_id, prepared['snapshot'], expected_revision=options['expected_revision'],
                           metadata={'source': 'registered_source_promotion', 'automatic_authorization': False,
                                     'source_ids': prepared['promotion']['source_ids']})
    except BaseException:
        discard_prepared_kicad_source_bundle(prepared, store=store)
        raise
    pin = retain_revision_artifacts(store, project_id, saved['revision'], basis='at_save')
    if pin is None:
        raise ValueError('Native source workspace was saved but could not be retained for editing.')
    return {'ok': True, 'project_id': project_id, 'revision': saved['revision'],
            'project': saved, 'promotion': prepared['promotion'], 'artifact_pin': pin,
            'physical_authority_granted': False}


def check_retained_native_design(
    store: ProjectStore, project_id: str, *, expected_revision: int, kind: str = 'pcb',
) -> dict[str, Any]:
    """Check the exact retained revision, including its original rule companions.

    This read-only check can target a historical revision. It never substitutes
    uploaded originals or mutable build-directory files for the pinned design.
    """
    from .artifact_retention import read_pinned_artifact_bytes, read_pinned_artifact_sidecars
    from .project_candidates import run_candidate_checks

    project_id = validate_project_id(project_id)
    if type(expected_revision) is not int or expected_revision < 1:
        raise ValueError('expected_revision must be a positive integer.')
    if kind not in {'pcb', 'schematic'}:
        raise ValueError('kind must be pcb or schematic.')
    store.load(project_id, revision=expected_revision)
    retained = read_pinned_artifact_bytes(store, project_id, expected_revision, kind)
    if retained is None:
        raise ValueError('The requested revision has no retained native artifact of this kind.')
    raw, entry = retained
    text = raw.decode('utf-8')
    companions = read_pinned_artifact_sidecars(store, project_id, expected_revision, kind)
    checks = run_candidate_checks(kind, text, text,
                                  sidecars={role: value[0] for role, value in companions.items()})
    executed = checks.get('ran') is True
    return {
        'ok': executed, 'schema_version': SCHEMA, 'project_id': project_id,
        'source_revision': expected_revision, 'kind': kind,
        'source_filename': Path(entry['relative']).name, 'source_sha256': entry['sha256'],
        'source_context': checks.get('source_context', {}), 'checks': checks,
        'check_executed': executed, 'status': 'completed' if executed else 'unavailable',
        'manufacturing_approved': False, 'physical_authority_granted': False,
    }


def native_candidate_bundle(store: ProjectStore, project_id: str, candidate_id: str) -> bytes:
    """Download the edited design with its exact rule companions and manifest."""
    from .project_candidates import (
        _candidate_build_dir, _read_named_nofollow, CandidateIntegrityError,
        load_candidate, read_candidate_file, sanitise_filename, validate_candidate_review_artifacts,
    )
    from .build_files_security import max_kicad_content_bytes

    record = load_candidate(store, project_id, candidate_id)
    validate_candidate_review_artifacts(store, project_id, record['review_id'])
    payload = {}
    for kind, entry in record['files'].items():
        if entry is not None:
            payload[sanitise_filename(entry['relative'], kind)] = read_candidate_file(store, project_id, candidate_id, kind)[0]
    for entries in record.get('sidecars', {}).values():
        for entry in entries.values():
            raw = _read_named_nofollow(_candidate_build_dir(project_id, candidate_id), entry['relative'],
                                      limit=max_kicad_content_bytes())
            if 'sha256:' + hashlib.sha256(raw).hexdigest() != entry['sha256']:
                raise CandidateIntegrityError('Candidate rule bytes changed before export.')
            payload[entry['relative']] = raw
    if sum(map(len, payload.values())) > 64 * 1024 * 1024:
        raise ValueError('Native candidate bundle exceeds the 64 MiB export limit.')
    manifest = {'schema_version': SCHEMA, 'project_id': project_id, 'candidate_id': candidate_id,
                'review_id': record['review_id'], 'base_revision': record['base_revision'],
                'source_sha256': record['base_sha256'], 'native_checks': record['checks'],
                'files': {name: 'sha256:' + hashlib.sha256(raw).hexdigest() for name, raw in payload.items()},
                'manufacturing_approved': False, 'physical_authority_granted': False}
    payload['EDIT_MANIFEST.json'] = (json.dumps(manifest, sort_keys=True, indent=2) + '\n').encode()
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, raw in sorted(payload.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            archive.writestr(info, raw, compress_type=zipfile.ZIP_DEFLATED)
    return output.getvalue()
