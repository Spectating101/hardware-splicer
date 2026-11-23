"""Uploaded native bytes must remain native through editable project revisions."""
import base64
import hashlib
import io
import json
import zipfile
from copy import deepcopy
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from hardware_splicer.artifact_retention import install_at_save_retention, read_pinned_artifact
from hardware_splicer.engineering_source_ingestion_api import create_engineering_source_ingestion_router
from hardware_splicer.project_api import create_project_router
from hardware_splicer.project_candidates import read_candidate_file
from hardware_splicer.project_candidates_api import create_project_candidates_router
from hardware_splicer.project_review_store import ProjectReviewStore, ReviewConflict
from hardware_splicer.project_store import ProjectStore, RevisionConflict
from hardware_splicer.source_project_editing import prepare_kicad_source_bundle, promote_kicad_source_bundle
from hardware_splicer.source_project_editing_api import create_source_project_editing_router


REFERENCE = Path(__file__).resolve().parents[1] / 'hardware/reference_designs/spi_flash_adapter_v1'


@pytest.fixture
def service(tmp_path, monkeypatch):
    monkeypatch.setenv('HARDWARE_SPLICER_OUTPUT_ROOT', str(tmp_path / 'output'))
    monkeypatch.setattr('hardware_splicer.project_candidates.run_candidate_checks',
                        lambda *a, **k: {'available': False, 'ran': False, 'reason': 'isolated_state_test'})
    store = ProjectStore(tmp_path / 'projects')
    app = FastAPI()
    app.include_router(create_project_router(store))
    app.include_router(create_engineering_source_ingestion_router(store))
    app.include_router(create_source_project_editing_router(store))
    app.include_router(create_project_candidates_router(store))
    store.save('source-test', {'projectName': 'Native source project', 'goal': 'Adapt supplied board.',
                              'powerOnAuthorized': False}, expected_revision=0)
    with TestClient(app) as client:
        yield client, store, tmp_path


def upload(client, name, data, revision, project='source-test'):
    response = client.post(f'/v1/projects/{project}/sources/ingest', json={
        'filename': name, 'content_base64': base64.b64encode(data).decode(),
        'expected_revision': revision,
    })
    assert response.status_code == 201, response.text
    return response.json()['revision'], response.json()['ingestion']['source_id']


def native_bundle(client, *, stem='supplied'):
    revision = 1
    ids = []
    contents = {}
    for extension in ('.kicad_pcb', '.kicad_sch', '.kicad_pro'):
        raw = (REFERENCE / ('spi_flash_adapter_v1' + extension)).read_bytes()
        contents[stem + extension] = raw
        revision, identity = upload(client, stem + extension, raw, revision)
        ids.append(identity)
    raw = b'(version 1)\n(rule "source-rule" (constraint clearance (min 0.4mm)))\n'
    contents[stem + '.kicad_dru'] = raw
    revision, identity = upload(client, stem + '.kicad_dru', raw, revision)
    ids.append(identity)
    return revision, ids, contents


def test_upload_promote_edit_keeps_exact_native_geometry_and_original_revision(service):
    client, store, _ = service
    revision, ids, contents = native_bundle(client)
    old = deepcopy(store.load('source-test'))
    response = client.post('/v1/projects/source-test/sources/promote-to-editable',
                           json={'expected_revision': revision, 'source_ids': ids})
    assert response.status_code == 201, response.text
    result = response.json()
    assert result['revision'] == revision + 1
    assert result['promotion']['check_scope'] == 'source_project_rules'
    assert result['physical_authority_granted'] is False
    assert store.load('source-test', revision)['snapshot'] == old['snapshot']
    snapshot = result['project']['snapshot']
    assert snapshot['powerOnAuthorized'] is False
    assert snapshot['sourceRevisionImpact']['families']['mechanical_fit']['status'] == 'requires_recheck'
    for name, raw in contents.items():
        assert (Path(snapshot['buildDir']) / 'build_compilation' / name).read_bytes() == raw
    assert read_pinned_artifact(store, 'source-test', revision + 1, 'pcb')[0].encode() == contents['supplied.kicad_pcb']
    edited = client.post('/v1/projects/source-test/candidates', json={
        'kind': 'pcb', 'base_revision': revision + 1, 'author': 'test',
        'ops': [{'op': 'move', 'ref': 'R2', 'x_mm': 123.45, 'y_mm': 82.55}],
    })
    assert edited.status_code == 201, edited.text
    candidate = edited.json()['candidate']
    data, _ = read_candidate_file(store, 'source-test', candidate['candidate_id'], 'pcb')
    assert data != contents['supplied.kicad_pcb'] and b'123.45' in data
    assert store.load('source-test')['revision'] == revision + 1
    assert read_pinned_artifact(store, 'source-test', revision + 1, 'pcb')[0].encode() == contents['supplied.kicad_pcb']
    exported = client.get(f'/v1/projects/source-test/candidates/{candidate["candidate_id"]}/native-bundle')
    assert exported.status_code == 200, exported.text
    repeated = client.get(f'/v1/projects/source-test/candidates/{candidate["candidate_id"]}/native-bundle')
    assert exported.content == repeated.content
    with zipfile.ZipFile(io.BytesIO(exported.content)) as archive:
        manifest = json.loads(archive.read('EDIT_MANIFEST.json'))
        assert set(archive.namelist()) == set(manifest['files']) | {'EDIT_MANIFEST.json'}
        assert archive.read('supplied.kicad_dru') == contents['supplied.kicad_dru']
        assert archive.read('supplied.kicad_pro') == contents['supplied.kicad_pro']
        assert manifest['physical_authority_granted'] is False


def test_board_only_is_editable_with_explicit_limited_check_scope(service):
    client, store, _ = service
    revision, source = upload(client, 'alone.kicad_pcb', (REFERENCE / 'spi_flash_adapter_v1.kicad_pcb').read_bytes(), 1)
    result = promote_kicad_source_bundle(store, 'source-test', expected_revision=revision, source_ids=[source])
    assert result['promotion']['check_scope'] == 'standalone_defaults_only'
    assert result['promotion']['warnings']


def test_native_check_uses_accepted_pin_and_historical_rule_bytes(service, monkeypatch):
    client, store, _ = service
    install_at_save_retention(store)  # Match the canonical product application's store.
    revision, ids, contents = native_bundle(client)
    promoted = promote_kicad_source_bundle(store, 'source-test', expected_revision=revision, source_ids=ids)
    base_revision = promoted['revision']
    candidate = client.post('/v1/projects/source-test/candidates', json={
        'kind': 'pcb', 'base_revision': base_revision, 'author': 'digital-test',
        'ops': [{'op': 'move', 'ref': 'R2', 'x_mm': 123.45, 'y_mm': 82.55}],
    }).json()['candidate']
    edited, _ = read_candidate_file(store, 'source-test', candidate['candidate_id'], 'pcb')
    ProjectReviewStore(store).decide('source-test', candidate['review_id'],
                                    decision='accepted', actor='digital-test')
    accepted_revision = store.load('source-test')['revision']
    # The retained blobs, rather than a mutable work directory, are authoritative.
    native_dir = Path(store.load('source-test')['snapshot']['buildDir'])
    paths = list(native_dir.rglob('*.kicad*'))
    assert paths
    for path in paths:
        path.write_text('changed after retention')
    observed = []
    def native_check(kind, before, after, *, sidecars):
        observed.append((kind, before.encode(), sidecars))
        assert before == after
        return {'available': True, 'ran': True, 'after': {'errors': 3, 'total': 3},
                'source_context': {'rule_scope': 'retained_project_and_custom_rules'}}
    monkeypatch.setattr('hardware_splicer.project_candidates.run_candidate_checks', native_check)
    for target, expected in ((accepted_revision, edited), (base_revision, contents['supplied.kicad_pcb'])):
        response = client.post('/v1/projects/source-test/native/check',
                               json={'expected_revision': target, 'kind': 'pcb'})
        assert response.status_code == 200, response.text
        checked = response.json()
        assert checked['source_revision'] == target
        assert checked['source_sha256'] == 'sha256:' + hashlib.sha256(expected).hexdigest()
        assert checked['check_executed'] is True
        assert checked['checks']['after']['errors'] == 3
        assert checked['manufacturing_approved'] is False
        assert observed[-1] == ('pcb', expected, {'project': contents['supplied.kicad_pro'],
                                                 'rules': contents['supplied.kicad_dru']})
    assert store.load('source-test')['revision'] == accepted_revision


def test_native_check_never_claims_execution_when_tool_is_unavailable(service):
    client, store, _ = service
    revision, source = upload(client, 'alone.kicad_pcb', (REFERENCE / 'spi_flash_adapter_v1.kicad_pcb').read_bytes(), 1)
    promoted = promote_kicad_source_bundle(store, 'source-test', expected_revision=revision, source_ids=[source])
    response = client.post('/v1/projects/source-test/native/check', json={'expected_revision': promoted['revision']})
    assert response.status_code == 200, response.text
    assert response.json()['check_executed'] is False
    assert response.json()['ok'] is False
    assert response.json()['checks']['reason'] == 'isolated_state_test'
    missing = client.post('/v1/projects/source-test/native/check', json={'expected_revision': 1})
    assert missing.status_code == 422
    invalid = client.post('/v1/projects/source-test/native/check', json={'expected_revision': True})
    assert invalid.status_code == 422


def test_stale_revision_and_foreign_or_ambiguous_selection_publish_nothing(service):
    client, store, tmp_path = service
    revision, ids, _ = native_bundle(client)
    with pytest.raises(RevisionConflict):
        prepare_kicad_source_bundle(store, 'source-test', expected_revision=1)
    with pytest.raises(ValueError, match='not registered'):
        prepare_kicad_source_bundle(store, 'source-test', expected_revision=revision, source_ids=['foreign-id'])
    revision, _ = upload(client, 'other.kicad_pcb', b'(kicad_pcb (version 20240108))', revision)
    with pytest.raises(ValueError, match='Select one'):
        prepare_kicad_source_bundle(store, 'source-test', expected_revision=revision)
    assert store.load('source-test')['revision'] == revision
    assert not list((tmp_path / 'output').glob('source_edits/*/*'))


def test_tampered_source_and_traversal_names_never_become_editable(service):
    client, store, _ = service
    revision, identity = upload(client, '../escape.kicad_pcb', b'(kicad_pcb (version 20240108))', 1)
    with pytest.raises(ValueError, match='safe basename'):
        prepare_kicad_source_bundle(store, 'source-test', expected_revision=revision, source_ids=[identity])
    assert store.load('source-test')['revision'] == revision


def test_source_blob_tampering_and_failed_publication_leave_no_workspace(service, monkeypatch):
    client, store, tmp_path = service
    revision, ids, _ = native_bundle(client)
    row = store.load('source-test')['snapshot']['engineeringSources'][0]
    blob = store.root / 'source-test' / row['metadata']['blob_ref']
    original = blob.read_bytes()
    blob.write_bytes(original + b'\n')
    with pytest.raises(ValueError, match='content_hash'):
        prepare_kicad_source_bundle(store, 'source-test', expected_revision=revision, source_ids=ids)
    blob.write_bytes(original)
    def conflict(*args, **kwargs):
        raise RevisionConflict('another revision won')
    monkeypatch.setattr(store, 'save', conflict)
    with pytest.raises(RevisionConflict):
        promote_kicad_source_bundle(store, 'source-test', expected_revision=revision, source_ids=ids)
    assert not list((tmp_path / 'output').glob('source_edits/*/bundle-*'))
    assert store.load('source-test')['revision'] == revision


def test_explicit_primary_selects_one_native_project_and_keeps_other_sources(service):
    client, store, _ = service
    revision, ids, _ = native_bundle(client)
    revision, other = upload(client, 'other.kicad_pcb', b'(kicad_pcb (version 20240108))', revision)
    result = promote_kicad_source_bundle(store, 'source-test', expected_revision=revision, primary_source_id=ids[0])
    assert result['promotion']['primary_source_id'] == ids[0]
    assert other not in result['promotion']['source_ids']
    assert any(row['source_id'] == other for row in result['project']['snapshot']['engineeringSources'])


def test_unsupported_rule_include_is_rejected_before_any_revision_is_published(service):
    client, store, tmp_path = service
    revision, _ = upload(client, 'unsafe.kicad_pcb', (REFERENCE / 'spi_flash_adapter_v1.kicad_pcb').read_bytes(), 1)
    revision, _ = upload(client, 'unsafe.kicad_dru', b'(version 1)\n(include "/tmp/outside.kicad_dru")\n', revision)
    with pytest.raises(ValueError, match='unsupported|Unsupported|not supported'):
        promote_kicad_source_bundle(store, 'source-test', expected_revision=revision)
    assert store.load('source-test')['revision'] == revision
    assert not list((tmp_path / 'output').glob('source_edits/*/bundle-*'))


def test_post_commit_save_failure_keeps_source_bytes_referenced_by_immutable_revision(service, monkeypatch):
    client, store, _ = service
    revision, ids, _ = native_bundle(client)
    save = store.save
    def committed_then_failed(*args, **kwargs):
        save(*args, **kwargs)
        raise OSError('manifest publication failed after revision write')
    monkeypatch.setattr(store, 'save', committed_then_failed)
    with pytest.raises(OSError):
        promote_kicad_source_bundle(store, 'source-test', expected_revision=revision, source_ids=ids)
    written = store.load('source-test', revision=revision + 1)
    root = Path(written['snapshot']['buildDir'])
    assert (root / 'build_compilation/supplied.kicad_pcb').is_file()


def test_custom_rule_only_bundle_has_explicit_non_default_scope(service):
    client, store, _ = service
    revision, source = upload(client, 'rules.kicad_pcb', (REFERENCE / 'spi_flash_adapter_v1.kicad_pcb').read_bytes(), 1)
    revision, rule = upload(client, 'rules.kicad_dru', b'(version 1)\n(rule "wide" (constraint track_width (min 0.5mm)))\n', revision)
    result = promote_kicad_source_bundle(store, 'source-test', expected_revision=revision, source_ids=[source, rule])
    assert result['promotion']['check_scope'] == 'custom_rules_without_project_settings'


def test_source_change_invalidates_passed_verification_in_existing_release_gate():
    from hardware_splicer.machine_project import MachineProject, ReleaseState
    from hardware_splicer.source_revision_impact import invalidate_source_derived_outputs
    snapshot = {'machineProject': {'project_id': 'source-test', 'name': 'Source', 'purpose': 'Edit',
        'evidence': [{'evidence_id': 'old', 'kind': 'analysis', 'basis': 'previous native revision'}],
        'verifications': [{'verification_id': 'v1', 'name': 'Previous check', 'method_type': 'analysis',
                           'status': 'passed', 'evidence_ids': ['old']}]},
        'power_on_authorized': False}
    changed = invalidate_source_derived_outputs(snapshot, changed_artifact_kinds=['pcb'], basis='test_edit')
    assert snapshot['machineProject']['verifications'][0]['status'] == 'passed'
    assert changed['machineProject']['verifications'][0]['status'] == 'blocked'
    assessment = MachineProject.model_validate(changed['machineProject']).assess_release(ReleaseState.DESIGN_READY)
    assert any(row.code == 'verification_not_passed' and row.object_id == 'v1' for row in assessment.blockers)
    assert changed['power_on_authorized'] is False


def test_legacy_machine_identity_is_preserved_but_disagreeing_aliases_are_rejected(service):
    client, store, tmp_path = service
    revision, ids, _ = native_bundle(client)
    snapshot = store.load('source-test')['snapshot']
    snapshot['machine_project'] = {'project_id': 'original-machine', 'name': 'Original', 'purpose': 'Keep source identity.'}
    envelope = store.save('source-test', snapshot, expected_revision=revision)
    result = promote_kicad_source_bundle(store, 'source-test', expected_revision=envelope['revision'], source_ids=ids)
    assert result['promotion']['machine_project_id'] == 'original-machine'
    assert result['project']['snapshot']['machineProject']['project_id'] == 'original-machine'
    snapshot = deepcopy(result['project']['snapshot'])
    snapshot['machine_project']['name'] = 'Conflicting alias'
    envelope = store.save('source-test', snapshot, expected_revision=result['revision'])
    count = len(list((tmp_path / 'output').glob('source_edits/*/bundle-*')))
    with pytest.raises(ValueError, match='disagree'):
        prepare_kicad_source_bundle(store, 'source-test', expected_revision=envelope['revision'])
    assert len(list((tmp_path / 'output').glob('source_edits/*/bundle-*'))) == count


def test_general_review_acceptance_cannot_bypass_candidate_byte_checks(service):
    client, store, _ = service
    revision, ids, _ = native_bundle(client)
    imported = promote_kicad_source_bundle(store, 'source-test', expected_revision=revision, source_ids=ids)
    response = client.post('/v1/projects/source-test/candidates', json={
        'kind': 'pcb', 'base_revision': imported['revision'], 'author': 'test',
        'ops': [{'op': 'move', 'ref': 'R2', 'x_mm': 123.45, 'y_mm': 82.55}],
    })
    assert response.status_code == 201, response.text
    candidate = response.json()['candidate']
    # Read the candidate's own pending snapshot, rather than guessing its path.
    reviews = ProjectReviewStore(store)
    review = reviews.get('source-test', candidate['review_id'])
    directory = Path(review['candidate_snapshot']['buildDir'])
    (directory / candidate['files']['pcb']['relative']).write_text('(kicad_pcb (version 20240108))')
    with pytest.raises(ReviewConflict):
        reviews.decide('source-test', candidate['review_id'], decision='accepted', actor='test')
    assert store.load('source-test')['revision'] == imported['revision']
