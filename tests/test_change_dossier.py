"""Change evidence binds export, review, proposal and new revision, and keeps the failure.

The registered ``fielddeck-5`` case is replaced by a small executable fixture so
the engine path (sealed runs, revisions, check declarations) is the real one.
The Policy Lab review is a controlled stand-in with the review schema's fields;
the end-to-end replay with Policy Lab's own code is scripts/demo_change_dossier.py.
"""
from hashlib import sha256
import json
import sys

import pytest

from hardware_splicer import digital_cases as cases
from hardware_splicer import digital_project as digital
from hardware_splicer.change_dossier import (CHANGE_EVIDENCE_SCHEMA, REVISION_HEAD_SCHEMA, ChangeDossierError,
                                             build_change_evidence, export_revision_head, write_change_evidence)
from hardware_splicer.digital_engine import DigitalStudyEngine
from hardware_splicer.jobs import JobBackend, JobStore
from hardware_splicer.policy_layer import (REVIEW_SCHEMA, canonical_json_bytes, export_policy_evidence,
                                           validate_policy_feedback)
from hardware_splicer.project_store import ProjectStore, RevisionConflict

BUILD = '''from pathlib import Path
import json
p=Path(__file__).resolve().parent
r=json.loads((p/'requirements.json').read_text())
runtime=round(15/r['load_w'],3)
margin=round(10-r['load_w'],3)
checks=[{'id':'work_runtime','actual':runtime,'limit':r['minimum_work_runtime_h'],'unit':'h',
         'passed':runtime>=r['minimum_work_runtime_h']},
        {'id':'source_margin','actual':margin,'limit':r['minimum_margin_w'],'unit':'W',
         'passed':margin>=r['minimum_margin_w']}]
report={'case_id':'fielddeck-5','requirements':r,'constraints':checks,
        'metrics':{'runtime_h':runtime,'margin_w':margin},'requirements_met':all(c['passed'] for c in checks)}
(p/'parts/body.step').write_text('fixture:'+str(r['load_w']))
(p/'reports/engineering.json').write_text(json.dumps(report))
'''

VERIFY = '''from pathlib import Path
from hashlib import sha256
import json
p=Path(__file__).resolve().parent
e=json.loads((p/'reports/engineering.json').read_text())
hashes={n:sha256((p/n).read_bytes()).hexdigest() for n in ('parts/body.step','reports/engineering.json')}
(p/'reports/verification.json').write_text(json.dumps({'case_id':'fielddeck-5','artifact_integrity':True,
    'artifact_sha256':hashes,'engineering_acceptance':e['requirements_met']}))
'''


@pytest.fixture
def engine(tmp_path, monkeypatch):
    source = tmp_path / 'fixture-source'
    source.mkdir()
    (source / 'build.py').write_text(BUILD)
    (source / 'verify.py').write_text(VERIFY)
    case = cases.RegisteredCase(
        'fielddeck-5', 'Runtime fixture', source, ('build.py', 'verify.py'),
        ('parts/body.step', 'reports/engineering.json', 'reports/verification.json'),
        ('build.py', 'verify.py'), 'verify.py', 'reports/engineering.json', 'reports/verification.json',
        {'minimum_work_runtime_h': (2.5, .1, 24), 'load_w': (5, 1, 9), 'minimum_margin_w': (1, 0, 10)})
    monkeypatch.setitem(cases.CASES, case.case_id, case)
    monkeypatch.setitem(cases.CHECK_REQUIREMENTS, 'fielddeck-5', {
        'evaluator_sha256': {'build.py': sha256(BUILD.encode()).hexdigest()},
        'checks': {'work_runtime': ('minimum_work_runtime_h', 'load_w'),
                   'source_margin': ('load_w', 'minimum_margin_w')}})
    monkeypatch.setattr(digital, 'native_python', lambda: sys.executable)
    monkeypatch.setattr(digital, 'runtime_for_case', lambda *_: {'available': True, 'setup_hint': ''})
    backend = JobBackend(JobStore(tmp_path / 'jobs.db'), worker_count=0)
    engine = DigitalStudyEngine(ProjectStore(tmp_path / 'projects'), backend)
    yield engine
    backend.stop()


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value))
    return path


def _review(export_path, export, requirements, unmet):
    """A controlled stand-in carrying the fields of policylab.hardware_policy_review.v1."""
    return {'schema': REVIEW_SCHEMA, 'physical_authority_granted': False,
            'decision': 'BLOCKED' if unmet else 'ADMIT_WITH_LIMIT',
            'policy': {'id': 'runtime-fixture', 'version': '1.0.0'},
            'source_binding': {'evidence_sha256': sha256(export_path.read_bytes()).hexdigest(),
                               'project_id': export['project_id'], 'revision': export['revision'],
                               'run_id': export['run_id']},
            'unmet_constraints': unmet, 'revision_requirements': requirements}


UNMET = [{'id': 'engineering.work_runtime', 'reason': 'ENGINEERING_CONSTRAINT_FAILED', 'actual': 3.0,
          'limit': 3.5, 'unit': 'h'},
         {'id': 'work-runtime', 'fact': 'metric.runtime_h', 'operator': '>=', 'value': 3.5, 'unit': 'h',
          'actual': 3.0, 'passed': False, 'reason': 'TARGET_NOT_MET'}]


@pytest.fixture
def chain(engine, tmp_path):
    """Export r1, review it, validate the proposal in HS, apply it as r2, export and review r2."""
    root = tmp_path / 'exchange'
    project = engine.create(case_id='fielddeck-5')['project']['project_id']
    base_export = export_policy_evidence(engine, project, 1)
    base_path = _write(root / 'r1-export.json', base_export)
    review_path = _write(root / 'r1-review.json',
                         _review(base_path, base_export, {'minimum_work_runtime_h': 3.5}, UNMET))
    proposal = validate_policy_feedback(engine, base_path.read_bytes(), review_path.read_bytes())
    proposal_path = _write(root / 'proposal.json', proposal)
    applied = engine.run_revision(project, base_revision=1, requirements=proposal['resolved_requirements'],
                                  change_request='Apply Policy Lab runtime proposal')
    assert applied['ok'], applied
    candidate_export = export_policy_evidence(engine, project, 2)
    candidate_path = _write(root / 'r2-export.json', candidate_export)
    candidate_review = _write(root / 'r2-review.json',
                              _review(candidate_path, candidate_export, {'minimum_work_runtime_h': 3.5}, UNMET))
    files = {'base_export': base_path, 'base_review': review_path, 'proposal': proposal_path,
             'candidate_export': candidate_path, 'candidate_review': candidate_review}
    return engine, project, root, files


def _build(engine, project, root, files, **kwargs):
    return build_change_evidence(engine.projects, project, base_revision=kwargs.get('base', 1),
                                 candidate_revision=kwargs.get('candidate', 2), root=root, files=files)


def test_packet_binds_both_revisions_and_keeps_the_failing_rerun(chain):
    engine, project, root, files = chain
    packet = _build(engine, project, root, files)
    assert packet['schema'] == CHANGE_EVIDENCE_SCHEMA
    assert packet['authority_level'] == 'modeled' and packet['physical_authority_granted'] is False
    assert packet['base']['revision'] == 1 and packet['candidate']['revision'] == 2
    assert packet['candidate']['parent_revision'] == 1
    assert packet['candidate']['run_id'] == engine.study(project, 2)['run_id']
    assert packet['base']['package_sha256'] != packet['candidate']['package_sha256']
    for role, path in files.items():
        record = packet['files'][role]
        assert record['sha256'] == sha256(path.read_bytes()).hexdigest()
        assert record['path'] == path.relative_to(root).as_posix()
    assert packet['proposal']['requirement_changes'] == {'minimum_work_runtime_h': {'before': 2.5, 'after': 3.5}}
    assert packet['proposal']['policy_decision'] == 'BLOCKED'
    assert [row['required'] for row in packet['proposal']['unmet_targets']] == ['HS limit 3.5 h', '>= 3.5 h']
    [stale] = packet['check_delta']['stale']
    assert stale['check'] == 'work_runtime' and stale['from_revision'] == 1
    assert stale['result']['passed'] is True and stale['counts_for_candidate'] is False
    assert stale['rerun']['passed'] is False and stale['rerun']['revision'] == 2
    [retained] = packet['check_delta']['retained']
    assert retained['check'] == 'source_margin'
    failing = [row for row in packet['unresolved'] if row['kind'] == 'failing_check']
    assert failing == [{'kind': 'failing_check', 'check': 'work_runtime', 'revision': 2,
                        'run_id': packet['candidate']['run_id'], 'actual': 3.0, 'limit': 3.5, 'unit': 'h',
                        'transition': 'regressed'}]
    work = next(row for row in packet['candidate']['checks'] if row['id'] == 'work_runtime')
    assert work['passed'] is False
    assert packet['candidate']['requirements_met'] is False
    assert packet['not_linked'] == [] and packet['not_tested']
    text = json.dumps(packet).lower()
    assert '"ready"' not in text and 'approved' not in text


def test_missing_candidate_review_is_reported_as_not_linked(chain):
    engine, project, root, files = chain
    files.pop('candidate_review')
    packet = _build(engine, project, root, files)
    assert packet['not_linked'] == ['No Policy Lab review of revision 2 was supplied.']
    assert 'candidate_review' not in packet['files']


def test_changed_file_bytes_or_wrong_revision_are_refused(chain):
    engine, project, root, files = chain
    review = json.loads(files['base_review'].read_bytes())
    review['revision_requirements'] = {'minimum_work_runtime_h': 4.0}
    _write(files['base_review'], review)
    with pytest.raises(ChangeDossierError, match='proposal does not bind'):
        _build(engine, project, root, files)


def test_swapped_exports_are_refused(chain):
    engine, project, root, files = chain
    files['base_export'], files['candidate_export'] = files['candidate_export'], files['base_export']
    with pytest.raises(ChangeDossierError):
        _build(engine, project, root, files)


def test_a_later_revision_makes_the_packet_unbuildable_and_moves_the_head(chain):
    engine, project, root, files = chain
    before = export_revision_head(engine.projects, project)
    assert before['schema'] == REVISION_HEAD_SCHEMA and before['head']['revision'] == 2
    assert before['physical_authority_granted'] is False
    current = engine.study(project)
    assert engine.run_revision(project, base_revision=2,
                               requirements={**current['summary']['requirements'], 'minimum_work_runtime_h': 3.0})['ok']
    with pytest.raises(RevisionConflict):
        _build(engine, project, root, files)
    after = export_revision_head(engine.projects, project)
    assert after['head']['revision'] == 3 and after['head']['parent_revision'] == 2
    assert after['head']['run_id'] != before['head']['run_id']


def test_requirements_not_from_the_proposal_are_refused(engine, tmp_path):
    root = tmp_path / 'exchange'
    project = engine.create(case_id='fielddeck-5')['project']['project_id']
    export = export_policy_evidence(engine, project, 1)
    base_path = _write(root / 'r1-export.json', export)
    review_path = _write(root / 'r1-review.json', _review(base_path, export, {'minimum_work_runtime_h': 3.5}, UNMET))
    proposal_path = _write(root / 'proposal.json',
                           validate_policy_feedback(engine, base_path.read_bytes(), review_path.read_bytes()))
    # The revision that was actually run used a different target than the proposal.
    current = engine.study(project)
    assert engine.run_revision(project, base_revision=1,
                               requirements={**current['summary']['requirements'], 'minimum_work_runtime_h': 2.0})['ok']
    candidate_path = _write(root / 'r2-export.json', export_policy_evidence(engine, project, 2))
    with pytest.raises(ChangeDossierError, match='resolved requirements'):
        build_change_evidence(engine.projects, project, base_revision=1, candidate_revision=2, root=root,
                              files={'base_export': base_path, 'base_review': review_path,
                                     'proposal': proposal_path, 'candidate_export': candidate_path})


def test_written_packet_is_never_replaced(chain, tmp_path):
    engine, project, root, files = chain
    packet = _build(engine, project, root, files)
    receipt = write_change_evidence(tmp_path / 'out' / 'change.json', packet)
    assert receipt['sha256'] == sha256((tmp_path / 'out' / 'change.json').read_bytes()).hexdigest()
    with pytest.raises(FileExistsError):
        write_change_evidence(tmp_path / 'out' / 'change.json', packet)
