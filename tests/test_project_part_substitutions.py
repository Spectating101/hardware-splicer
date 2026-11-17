"""Retained substitutions must preserve source identity through project review."""
import base64
from copy import deepcopy
import hashlib
import io
import json
import zipfile

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from hardware_splicer.ai_project_orchestrator import build_ai_project_context
from hardware_splicer.engineering_source_ingestion import ingest_engineering_source
from hardware_splicer.machine_project import MachineProject
from hardware_splicer.project_api import create_project_router
from hardware_splicer.project_part_substitutions import (
    assess_project_substitution, export_substitution_bundle, load_substitution_assessment,
    propose_project_substitution,
)
from hardware_splicer.project_part_substitutions_api import create_project_part_substitutions_router
from hardware_splicer.project_review_store import ProjectReviewStore, ReviewConflict
from hardware_splicer.project_store import CorruptProject, ProjectStore, RevisionConflict


def fixture_specification():
    # Declared simulation fixtures, not purchased or manufacturer-rated parts.
    mount = {'holes_mm': [[2., 2.], [18., 2.], [2., 18.], [18., 18.]],
             'hole_diameter_mm': 2.5, 'fastener': 'declared M2 fixture'}
    supply = {'part_id': 'bank', 'name': 'Declared bank', 'manufacturer': 'Simulation Fixture', 'mpn': 'SUPPLY',
              'functions': ['power'], 'dimensions_mm': [20., 20., 10.], 'position_mm': [5., 5., 5.],
              'mount': mount, 'energy_wh': 30., 'usable_fraction': .8,
              'ports': [{'port_id': 'out', 'kind': 'power', 'direction': 'output',
                         'connector': 'fixture-2', 'pin_functions': {'1': 'V+', '2': 'GND'},
                         'voltage_range_v': [4.9, 5.1], 'current_a': 2.}]}
    load = {'part_id': 'controller', 'name': 'Declared controller', 'manufacturer': 'Simulation Fixture', 'mpn': 'CTRL-A',
            'functions': ['compute'], 'dimensions_mm': [20., 20., 10.], 'position_mm': [40., 5., 5.],
            'mount': mount, 'ports': [{'port_id': 'in', 'kind': 'power', 'direction': 'input',
                'connector': 'fixture-2', 'pin_functions': {'1': 'V+', '2': 'GND'},
                'voltage_range_v': [4.75, 5.25], 'current_a': .5}]}
    candidate = deepcopy(load)
    candidate.update(part_id='candidate-c', name='Replacement controller', mpn='CTRL-B', position_mm=None)
    candidate['ports'][0]['current_a'] = 1.
    return {'parts': [supply, load], 'connections': [{'connection_id': 'power',
        'from': {'part_id': 'bank', 'port_id': 'out'}, 'to': {'part_id': 'controller', 'port_id': 'in'}}],
        'replace_part_id': 'controller', 'candidate': candidate,
        'enclosure': {'minimum_mm': [0., 0., 0.], 'maximum_mm': [100., 80., 50.]}}


@pytest.fixture
def service(tmp_path):
    store = ProjectStore(tmp_path / 'projects')
    machine = MachineProject(project_id='example', name='Digital substitution fixture',
                             purpose='Compare declared replacement parts digitally.')
    store.save('example', {'projectId': 'example', 'machineProject': machine.model_dump(mode='json'),
                           'powerOnAuthorized': False}, expected_revision=0)
    spec = fixture_specification()
    profiles = {'supply': spec['parts'][0], 'load': spec['parts'][1], 'candidate': spec['candidate']}
    source = ingest_engineering_source({'project_id': 'example', 'filename': 'declared-profiles.json',
        'content_base64': base64.b64encode(json.dumps(profiles).encode()).decode()}, project_root=store.root)
    snapshot = store.load('example')['snapshot']
    snapshot['engineeringSources'] = [source.source_descriptor]
    store.save('example', snapshot, expected_revision=1)
    for row, pointer in [(spec['parts'][0], '/supply'), (spec['parts'][1], '/load'), (spec['candidate'], '/candidate')]:
        row['source'] = {'source_id': source.source_id, 'content_hash': source.content_hash, 'pointer': pointer}
    app = FastAPI()
    app.include_router(create_project_router(store))
    app.include_router(create_project_part_substitutions_router(store))
    return store, spec, TestClient(app)


def assess(store, spec, **kwargs):
    return assess_project_substitution(store, 'example', expected_revision=2, specification=spec, **kwargs)


def test_bound_substitution_preserves_project_and_exports_revised_build(service):
    store, spec, client = service
    before = store.load('example')
    response = client.post('/v1/projects/example/parts/substitutions',
                           json={'expected_revision': 2, 'specification': spec})
    assert response.status_code == 201, response.text
    result = response.json()
    record = result['assessment']
    assert record['report']['status'] == 'passes_declared_checks'
    assert all(row['status'] == 'registered_profile_bytes_match' for row in record['source_checks'])
    assert store.load('example') == before
    assert result['current_for_project'] is True
    replacement = next(row for row in record['report']['revised']['parts'] if row['part_id'] == 'controller')
    assert replacement['position_mm'] == [40., 5., 5.]
    assert replacement['mpn'] == 'CTRL-B'
    assert record['report']['construction_ready'] is False
    first = client.get(f'/v1/projects/example/parts/substitutions/{record["assessment_id"]}/bundle')
    assert first.status_code == 200
    assert first.content == export_substitution_bundle(store, 'example', record['assessment_id'])
    with zipfile.ZipFile(io.BytesIO(first.content)) as archive:
        manifest = json.loads(archive.read('MANIFEST.json'))
        assert archive.read('BOM.csv').count(b'CTRL-B') == 1 and b'CTRL-A' not in archive.read('BOM.csv')
        assert json.loads(archive.read('connections.json'))[0]['to']['part_id'] == 'controller'
        for name, digest in manifest['files'].items():
            assert 'sha256:' + hashlib.sha256(archive.read(name)).hexdigest() == digest
    assert assess(store, spec)['assessment']['assessment_id'] == record['assessment_id']


def test_foreign_and_changed_source_profiles_are_rejected_before_publication(service):
    store, spec, _ = service
    changed = deepcopy(spec)
    changed['candidate']['ports'][0]['current_a'] = .1
    with pytest.raises(ValueError, match='retained source pointer'):
        assess(store, changed)
    changed = deepcopy(spec)
    changed['candidate']['source']['source_id'] = 'foreign'
    with pytest.raises(ValueError, match='registered source'):
        assess(store, changed)
    assert not (store.root / 'example' / 'part_substitutions').exists()


def test_historical_study_exports_but_cannot_propose_over_changed_project(service):
    store, spec, _ = service
    result = assess(store, spec)
    identity = result['assessment']['assessment_id']
    store.save('example', {**store.load('example')['snapshot'], 'goal': 'Changed constraints'}, expected_revision=2)
    assert load_substitution_assessment(store, 'example', identity)['current_for_project'] is False
    assert export_substitution_bundle(store, 'example', identity)
    with pytest.raises(RevisionConflict):
        propose_project_substitution(store, 'example', identity, expected_revision=3)
    with pytest.raises(RevisionConflict):
        assess(store, spec)


def test_review_acceptance_retains_assembly_and_supports_a_second_substitution(service):
    store, spec, _ = service
    first = assess(store, spec)['assessment']
    proposal = propose_project_substitution(store, 'example', first['assessment_id'], expected_revision=2)
    assert proposal['review']['status'] == 'pending'
    assert store.load('example')['revision'] == 2
    ProjectReviewStore(store).decide('example', proposal['review']['review_id'], decision='accepted', actor='digital-test')
    snapshot = store.load('example')['snapshot']
    assert snapshot['powerOnAuthorized'] is False
    assert snapshot['partAssembly']['parts'][1]['mpn'] == 'CTRL-B'
    assert snapshot['sourceRevisionImpact']['families']['native_rule_checks']['status'] == 'requires_recheck'
    context = build_ai_project_context('example', 3, snapshot, mission='Adapt this assembly')
    assert context['project_summary']['partSubstitution']['assessment_id'] == first['assessment_id']
    second = {**deepcopy(snapshot['partAssembly']), 'replace_part_id': 'controller',
              'candidate': deepcopy(spec['parts'][1])}
    result = assess_project_substitution(store, 'example', expected_revision=3, specification=second)
    assert result['assessment']['baseline_binding'] == 'retained_part_assembly'
    assert result['assessment']['report']['revised']['parts'][1]['mpn'] == 'CTRL-A'


def test_assessment_and_review_tampering_cannot_be_accepted(service):
    store, spec, _ = service
    record = assess(store, spec)['assessment']
    proposal = propose_project_substitution(store, 'example', record['assessment_id'], expected_revision=2)
    path = store.root / 'example' / 'part_substitutions' / record['assessment_id'] / 'assessment.json'
    data = json.loads(path.read_text())
    data['report']['status'] = 'forged'
    path.write_text(json.dumps(data))
    with pytest.raises(CorruptProject):
        load_substitution_assessment(store, 'example', record['assessment_id'])
    with pytest.raises(ReviewConflict):
        ProjectReviewStore(store).decide('example', proposal['review']['review_id'], decision='accepted', actor='digital-test')
    assert store.load('example')['revision'] == 2


def test_registered_native_case_is_not_overwritten_by_a_nominal_study(service):
    store, spec, _ = service
    store.save('example', {**store.load('example')['snapshot'], 'mode': 'digital'}, expected_revision=2)
    record = assess_project_substitution(store, 'example', expected_revision=3, specification=spec)['assessment']
    with pytest.raises(ValueError, match='native contract'):
        propose_project_substitution(store, 'example', record['assessment_id'], expected_revision=3)
    assert store.load('example')['revision'] == 3


def test_unbound_donor_unknowns_and_bad_requests_remain_explicit(service):
    store, spec, client = service
    donor = deepcopy(spec)
    donor['candidate'] = {'part_id': 'junk', 'name': 'Unidentified donor'}
    result = assess(store, donor)['assessment']
    assert result['report']['status'] != 'passes_declared_checks'
    assert result['report']['unresolved']
    assert result['source_checks'][-1]['status'] == 'unbound_declaration'
    assert result['report']['revised']['parts'][1]['manufacturer'] is None
    with pytest.raises(ValueError, match='revised port mappings'):
        propose_project_substitution(store, 'example', result['assessment_id'], expected_revision=2)
    assert export_substitution_bundle(store, 'example', result['assessment_id'])
    assert client.post('/v1/projects/example/parts/substitutions',
        json={'expected_revision': True, 'specification': spec}).status_code == 422
    assert client.get('/v1/projects/example/parts/substitutions/../../outside').status_code != 200


def test_formula_descriptions_are_text_in_bom(service):
    store, spec, _ = service
    spec['candidate'].pop('source')
    spec['candidate']['name'] = '=DO_NOT_EXECUTE()'
    identity = assess(store, spec)['assessment']['assessment_id']
    with zipfile.ZipFile(io.BytesIO(export_substitution_bundle(store, 'example', identity))) as archive:
        assert b"'=DO_NOT_EXECUTE()" in archive.read('BOM.csv')


def test_generic_review_cannot_replay_a_stale_assessed_snapshot(service):
    store, spec, _ = service
    record = assess(store, spec)['assessment']
    original = propose_project_substitution(store, 'example', record['assessment_id'], expected_revision=2)
    old_candidate = original['review']['candidate_snapshot']
    store.save('example', {**store.load('example')['snapshot'], 'goal': 'Keep this later requirement'}, expected_revision=2)
    reviews = ProjectReviewStore(store)
    replay = reviews.create('example', old_candidate, base_revision=3, created_by='test')
    with pytest.raises(ReviewConflict, match='assessed source revision'):
        reviews.decide('example', replay['review_id'], decision='accepted', actor='test')
    assert store.load('example')['snapshot']['goal'] == 'Keep this later requirement'


def test_generic_review_cannot_promote_registered_digital_case_substitution(service):
    from hardware_splicer.project_part_substitutions import _candidate_snapshot
    store, spec, _ = service
    store.save('example', {**store.load('example')['snapshot'], 'mode': 'digital'}, expected_revision=2)
    record = assess_project_substitution(store, 'example', expected_revision=3, specification=spec)['assessment']
    candidate = _candidate_snapshot(store.load('example')['snapshot'], record,
        store.root / 'example' / 'part_substitutions' / record['assessment_id'])
    reviews = ProjectReviewStore(store)
    review = reviews.create('example', candidate, base_revision=3, created_by='test')
    with pytest.raises(ReviewConflict, match='native contract'):
        reviews.decide('example', review['review_id'], decision='accepted', actor='test')
    assert store.load('example')['revision'] == 3


def test_export_rechecks_geometry_bytes_after_loading_record(service, monkeypatch):
    from hardware_splicer import project_part_substitutions as module
    store, spec, _ = service
    raw = b'declared geometry integrity fixture'
    def geometry(report, directory):
        directory.mkdir()
        (directory / 'nominal_assembly.step').write_bytes(raw)
        return {'status': 'integrity_test_fixture', 'files': {
            'nominal_assembly.step': {'sha256': 'sha256:' + hashlib.sha256(raw).hexdigest(), 'size_bytes': len(raw)}}}
    monkeypatch.setattr('hardware_splicer.part_substitution_geometry.generate_substitution_geometry', geometry)
    record = assess(store, spec, generate_geometry=True)['assessment']
    original_read = module._read_file
    calls = 0
    def changed_second_read(directory, relative, **options):
        nonlocal calls
        content = original_read(directory, relative, **options)
        if relative == 'geometry/nominal_assembly.step':
            calls += 1
            if calls == 2:
                return b'changed between validation and export'
        return content
    monkeypatch.setattr(module, '_read_file', changed_second_read)
    with pytest.raises(CorruptProject, match='changed before export'):
        export_substitution_bundle(store, 'example', record['assessment_id'])
