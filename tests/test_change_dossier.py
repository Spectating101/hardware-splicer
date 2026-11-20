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
from hardware_splicer.policy_layer import (REVIEW_SCHEMA, VERIFICATION_SCHEMA, canonical_json_bytes, export_policy_evidence,
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
            'target_results': [{'id': row['id'], 'passed': False} for row in unmet if 'operator' in row],
            'unmet_constraints': unmet, 'revision_requirements': requirements}


def _receipt(review_path):
    review = json.loads(review_path.read_bytes())
    return canonical_json_bytes({'schema': VERIFICATION_SCHEMA, 'verified': True, 'decision': review['decision'],
                                 'source_binding': review['source_binding'], 'physical_authority_granted': False,
                                 'review_sha256': sha256(review_path.read_bytes()).hexdigest()})


def _replay_file(review_path):
    path = review_path.with_name(review_path.stem + '-replay.json')
    path.write_bytes(_receipt(review_path))
    return path


def _feedback(engine, base_path, review_path):
    return validate_policy_feedback(engine, base_path.read_bytes(), review_path.read_bytes(),
                                    replay_receipt_bytes=_receipt(review_path))


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
    proposal = _feedback(engine, base_path, review_path)
    proposal_path = _write(root / 'proposal.json', proposal)
    applied = engine.run_revision(project, base_revision=1, requirements=proposal['resolved_requirements'],
                                  change_request='Apply Policy Lab runtime proposal')
    assert applied['ok'], applied
    candidate_export = export_policy_evidence(engine, project, 2)
    candidate_path = _write(root / 'r2-export.json', candidate_export)
    candidate_review = _write(root / 'r2-review.json',
                              _review(candidate_path, candidate_export, {'minimum_work_runtime_h': 3.5}, UNMET))
    files = {'base_export': base_path, 'base_review': review_path, 'base_review_replay': _replay_file(review_path),
             'proposal': proposal_path, 'candidate_export': candidate_path, 'candidate_review': candidate_review,
             'candidate_review_replay': _replay_file(candidate_review)}
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
    files.pop('candidate_review_replay')
    packet = _build(engine, project, root, files)
    assert packet['not_linked'] == ['No Policy Lab review of revision 2 was supplied.']
    assert 'candidate_review' not in packet['files']


def test_changed_file_bytes_or_wrong_revision_are_refused(chain):
    engine, project, root, files = chain
    review = json.loads(files['base_review'].read_bytes())
    review['revision_requirements'] = {'minimum_work_runtime_h': 4.0}
    _write(files['base_review'], review)
    with pytest.raises(ChangeDossierError, match='receipt does not bind the review'):
        _build(engine, project, root, files)
    # Even with a matching receipt, the proposal still binds the original review bytes.
    _write(files['base_review_replay'], json.loads(_receipt(files['base_review'])))
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
                           _feedback(engine, base_path, review_path))
    # The revision that was actually run used a different target than the proposal.
    current = engine.study(project)
    assert engine.run_revision(project, base_revision=1,
                               requirements={**current['summary']['requirements'], 'minimum_work_runtime_h': 2.0})['ok']
    candidate_path = _write(root / 'r2-export.json', export_policy_evidence(engine, project, 2))
    with pytest.raises(ChangeDossierError, match='resolved requirements'):
        build_change_evidence(engine.projects, project, base_revision=1, candidate_revision=2, root=root,
                              files={'base_export': base_path, 'base_review': review_path,
                                     'base_review_replay': _replay_file(review_path),
                                     'proposal': proposal_path, 'candidate_export': candidate_path})


def test_written_packet_is_never_replaced(chain, tmp_path):
    engine, project, root, files = chain
    packet = _build(engine, project, root, files)
    receipt = write_change_evidence(tmp_path / 'out' / 'change.json', packet)
    assert receipt['sha256'] == sha256((tmp_path / 'out' / 'change.json').read_bytes()).hexdigest()
    with pytest.raises(FileExistsError):
        write_change_evidence(tmp_path / 'out' / 'change.json', packet)


CANDIDATE = {'id': 'load-budget', 'kind': 'modelled_candidate_design_change', 'status': 'PROPOSED',
             'label': 'controlled stand-in', 'target': 'work-runtime', 'input': 'load_w', 'before': 5, 'after': 4,
             'requirement_overrides': {'load_w': 4}, 'model': 'runtime_inverse_to_work_power',
             'formula': 'R = 15 / load_w', 'numbers': {'runtime_h': 3.0}, 'assumptions': ['fixture'], 'basis': 'fixture'}


@pytest.fixture
def candidate_chain(chain):
    """Review the failing r2 with a candidate, apply it as r3, export and review r3."""
    engine, project, root, files = chain
    export = json.loads(files['candidate_export'].read_bytes())
    unmet = [dict(UNMET[0], actual=3.0), {**UNMET[1], 'fact': 'metric.runtime_h'}]
    review = _review(files['candidate_export'], export, {'minimum_work_runtime_h': 3.5}, unmet)
    review['target_results'] = [{'id': 'work-runtime', 'fact': 'metric.runtime_h', 'operator': '>=', 'value': 3.5,
                                 'unit': 'h', 'passed': False}]
    review['candidate_design_changes'] = [CANDIDATE]
    review_path = _write(root / 'r2-candidate-review.json', review)
    proposal = validate_policy_feedback(engine, files['candidate_export'].read_bytes(), review_path.read_bytes(),
                                        replay_receipt_bytes=_receipt(review_path), candidates=('load-budget',))
    proposal_path = _write(root / 'proposal-r3.json', proposal)
    assert engine.run_revision(project, base_revision=2, requirements=proposal['resolved_requirements'])['ok']
    r3_path = _write(root / 'r3-export.json', export_policy_evidence(engine, project, 3))
    return engine, project, root, {'base_export': files['candidate_export'], 'base_review': review_path,
                                   'base_review_replay': _replay_file(review_path),
                                   'proposal': proposal_path, 'candidate_export': r3_path}


def test_candidate_change_reports_native_outcome_and_unknown_physical_means(candidate_chain):
    engine, project, root, files = candidate_chain
    packet = build_change_evidence(engine.projects, project, base_revision=2, candidate_revision=3, root=root, files=files)
    [row] = packet['proposal']['candidate_design_changes']
    assert row['input'] == 'load_w' and row['after'] == 4
    assert row['physical_means'] == 'unknown / not tested'
    # Fixture runtime is 15 / load_w = 3.75 h against the 3.5 h target.
    assert row['native_outcome'] == {'target': 'work-runtime', 'fact': 'metric.runtime_h', 'operator': '>=',
                                     'required': 3.5, 'unit': 'h', 'native_value': 3.75, 'met': True,
                                     'basis': 'native HS rerun of the candidate revision; modeled, not measured'}
    assert packet['proposal']['requirement_changes'] == {'load_w': {'before': 5, 'after': 4}}
    assert 'Physical means of reaching load_w = 4: unknown / not tested.' in packet['not_tested']
    assert [r['check'] for r in packet['check_delta']['stale']] and packet['unresolved'] == []
    text = json.dumps(packet).lower()
    assert ' fix' not in text and 'approved' not in text and '"ready"' not in text


def test_candidate_altered_after_review_is_refused(candidate_chain):
    engine, project, root, files = candidate_chain
    proposal = json.loads(files['proposal'].read_bytes())
    proposal['applied_candidates'][0]['after'] = 3
    _write(files['proposal'], proposal)
    with pytest.raises(ChangeDossierError, match='differs from the Policy Lab review'):
        build_change_evidence(engine.projects, project, base_revision=2, candidate_revision=3, root=root, files=files)


def _rereview(files, mutate):
    """Rewrite the base review and its receipt; the proposal no longer binds it, so test only refusals before that."""
    review = json.loads(files['base_review'].read_bytes())
    mutate(review)
    _write(files['base_review'], review)
    _write(files['base_review_replay'], json.loads(_receipt(files['base_review'])))


def test_nested_authority_in_a_review_is_refused(chain):
    engine, project, root, files = chain
    _rereview(files, lambda review: review.setdefault('assessment', {}).update(fabrication_authorized=True))
    with pytest.raises(ChangeDossierError, match='cannot assert fabrication_authorized'):
        _build(engine, project, root, files)


def test_reviews_need_receipts_bound_to_their_bytes(chain):
    engine, project, root, files = chain
    replay = files.pop('candidate_review_replay')
    with pytest.raises(ChangeDossierError, match='needs its Policy Lab verify receipt'):
        _build(engine, project, root, files)
    receipt = json.loads(replay.read_bytes())
    receipt['review_sha256'] = '0' * 64
    _write(replay, receipt)
    files['candidate_review_replay'] = replay
    with pytest.raises(ChangeDossierError, match='receipt does not bind the review'):
        _build(engine, project, root, files)


def test_base_receipt_must_be_the_one_the_proposal_was_validated_with(chain):
    engine, project, root, files = chain
    receipt = json.loads(files['base_review_replay'].read_bytes())
    receipt['extra'] = 'different receipt'
    _write(files['base_review_replay'], receipt)
    with pytest.raises(ChangeDossierError, match='not validated against the covered Policy Lab replay'):
        _build(engine, project, root, files)


def _candidate_with_target(candidate_chain, **target):
    engine, project, root, files = candidate_chain
    review = json.loads(files['base_review'].read_bytes())
    review['target_results'][0].update(target)
    review_path = _write(files['base_review'], review)
    _write(files['base_review_replay'], json.loads(_receipt(review_path)))
    proposal = json.loads(files['proposal'].read_bytes())
    proposal['policy_review_sha256'] = sha256(review_path.read_bytes()).hexdigest()
    proposal['policy_review_replay_sha256'] = sha256(_receipt(review_path)).hexdigest()
    _write(files['proposal'], proposal)
    return build_change_evidence(engine.projects, project, base_revision=2, candidate_revision=3, root=root, files=files)


def test_strict_operators_are_evaluated_strictly(candidate_chain):
    packet = _candidate_with_target(candidate_chain, operator='>', value=3.75)
    [row] = packet['proposal']['candidate_design_changes']
    assert row['native_outcome']['met'] is False  # 3.75 > 3.75 is false
    assert any(item['kind'] == 'candidate_target_not_met' for item in packet['unresolved'])


def test_unknown_operator_or_fact_prefix_is_refused(candidate_chain):
    with pytest.raises(ChangeDossierError, match='operator'):
        _candidate_with_target(candidate_chain, operator='~=')


def test_fact_without_prefix_is_refused(candidate_chain):
    with pytest.raises(ChangeDossierError, match='metric.\\* or requirement'):
        _candidate_with_target(candidate_chain, fact='runtime_h')


def test_unknown_native_value_is_unresolved(candidate_chain):
    packet = _candidate_with_target(candidate_chain, fact='metric.not_exported')
    kinds = [item['kind'] for item in packet['unresolved']]
    assert 'candidate_target_unknown' in kinds


def test_candidate_targeting_an_unmet_engineering_row_is_refused(candidate_chain):
    engine, project, root, files = candidate_chain
    review = json.loads(files['base_review'].read_bytes())
    review['candidate_design_changes'][0]['target'] = 'engineering.work_runtime'
    _write(files['base_review'], review)
    _write(files['base_review_replay'], json.loads(_receipt(files['base_review'])))
    proposal = json.loads(files['proposal'].read_bytes())
    proposal['applied_candidates'][0]['target'] = 'engineering.work_runtime'
    proposal['policy_review_sha256'] = sha256(files['base_review'].read_bytes()).hexdigest()
    proposal['policy_review_replay_sha256'] = sha256(_receipt(files['base_review'])).hexdigest()
    _write(files['proposal'], proposal)
    with pytest.raises(ChangeDossierError, match='only as an unmet constraint'):
        build_change_evidence(engine.projects, project, base_revision=2, candidate_revision=3, root=root, files=files)
