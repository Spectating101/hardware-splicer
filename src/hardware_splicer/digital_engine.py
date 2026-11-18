"""Headless engineering operations shared by Python, CLI and HTTP clients.

Projects and jobs use the existing stores. Opening this engine never recovers,
starts or cancels another process's workers. Execution is explicitly requested.
The registered drone remains a bounded proving case, not a general CAD solver.
"""
from __future__ import annotations

import os
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from uuid import UUID, uuid4, uuid5, NAMESPACE_URL
import zipfile

from . import digital_project as digital
from . import digital_cases as cases
from .jobs import JobBackend, JobStore, TERMINAL_STATUSES
from .project_review_store import ProjectReviewStore
from .project_store import CorruptProject, ProjectNotFound, ProjectStore, RevisionConflict, validate_project_id


class DigitalRuntimeUnavailable(RuntimeError):
    pass


class DigitalStudyEngine:
    def __init__(self, project_store=None, job_backend=None, *, project_root=None, job_db=None):
        if project_store is not None and project_root is not None:
            raise ValueError('Supply project_store or project_root, not both.')
        self.projects = project_store if project_store is not None else ProjectStore(project_root)
        if job_backend is None:
            state = Path(os.getenv('HARDWARE_SPLICER_STATE_DIR', '/tmp/hardware_splicer_state'))
            path = job_db or os.getenv('HARDWARE_SPLICER_JOB_DB') or state / 'jobs.sqlite3'
            job_backend = JobBackend(JobStore(path), worker_count=0)
            self._owns_backend = True
        else:
            if job_db is not None:
                raise ValueError('Supply job_backend or job_db, not both.')
            self._owns_backend = False
        previous = getattr(job_backend, 'project_store', None)
        if previous is not None and previous.root != self.projects.root:
            raise ValueError('This job backend belongs to another project store.')
        job_backend.project_store = self.projects
        self.backend = job_backend

    def close(self):
        if self._owns_backend:
            self.backend.stop()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def cases(self):
        tools = digital.requirement_tools()
        return {'ok': True, 'default_case_id': cases.DEFAULT_CASE,
                'cases': [{'case_id': cases.DEFAULT_CASE, 'name': 'HS-3G-B digital study',
                           'source_inputs_available': True,
                           'requirements': {name: {'default': default, 'minimum': tools.BOUNDS[name][0],
                                                   'maximum': tools.BOUNDS[name][1]}
                                            for name, default in tools.DEFAULTS.items()},
                           'scope': 'Registered drone model; no physical validation or flight authority.'},
                          *[case.describe() for case in cases.CASES.values()]]}

    def from_prompt(self, brief, *, project_id=None, base_revision=None):
        from .digital_brief import interpret_brief

        current = None
        if project_id is not None:
            envelope, directory, seal = digital.validated_run(self.projects, project_id, base_revision)
            base_revision = envelope['revision']
            case_id = digital.case_id_for(seal)
            if case_id not in cases.CASES:
                raise ValueError('This project has no registered text-brief adapter.')
            current = {'case_id': case_id, 'requirements': seal['summary']['requirements']}
            if previous := envelope['snapshot'].get('designBrief'):
                current['previous_brief'] = previous['brief']
            if cases.DRAWING in seal['artifact_sha256']:
                current['drawing'] = json.loads((directory / cases.DRAWING).read_bytes())
        elif base_revision is not None:
            raise ValueError('A base revision requires a project ID.')
        plan = interpret_brief(brief, current=current)
        if plan['status'] != 'build':
            return {'ok': True, 'interpretation': plan, 'project': None}
        if current is not None:
            if not plan['requirements'] and plan['drawing'] is None:
                return {'ok': True, 'interpretation': plan, 'project_id': project_id,
                        'revision': base_revision, 'unchanged': True}
            result = self.run_revision(project_id, base_revision=base_revision,
                                       change_request=plan['brief'][:200], requirements=plan['requirements'],
                                       brief_plan=plan)
            return {**result, 'interpretation': plan}
        created = self.create(case_id=plan['case_id'], brief_plan=plan)
        project = created['project']
        study = self.study(project['project_id'], project['revision'])
        return {**created, 'study': study, 'interpretation': plan}

    def create(self, *, name=None, case_id=digital.cases.DEFAULT_CASE, brief_plan=None):
        cases.validate_case_id(case_id)
        if name is None:
            name = 'HS-3G-B digital study' if case_id == cases.DEFAULT_CASE else cases.registered(case_id).name
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 100:
            raise ValueError('Project name must contain 1–100 characters.')
        if case_id != cases.DEFAULT_CASE:
            descriptor = cases.registered(case_id).describe()
            if not descriptor['source_inputs_available']:
                raise DigitalRuntimeUnavailable('Registered case inputs are unavailable: ' + ', '.join(descriptor['missing_inputs']))
            available = digital.runtime_for_case(case_id)
            if not available['available']:
                raise DigitalRuntimeUnavailable(available['setup_hint'])
        return {'ok': True, 'project': digital.create_project(self.projects, name=name.strip(), case_id=case_id,
                                                              brief_plan=brief_plan)}

    def study(self, project_id, revision=None):
        envelope, directory, seal = digital.validated_run(self.projects, project_id, revision)
        return {'revision': envelope['revision'], 'saved_at': envelope['saved_at'],
                'attempt_id': seal.get('attempt_id'),
                **{key: seal[key] for key in ('run_id','parent_revision','change_request','job_id','summary')},
                'artifact_manifest': {name: {'sha256': digest, 'bytes': (directory/name).stat().st_size}
                                      for name,digest in seal['artifact_sha256'].items()}}

    def history(self, project_id):
        digital.load_run(self.projects, project_id)
        return [self.study(project_id, row['revision'])
                for row in ProjectReviewStore(self.projects).list_revisions(project_id)]

    def project_state(self, project_id, revision=None):
        study = self.study(project_id, revision)
        case_id = study['summary'].get('case_id', cases.DEFAULT_CASE)
        bounds = {}
        if case_id != cases.DEFAULT_CASE:
            _, _, seal = digital.load_run(self.projects, project_id, study['revision'])
            case = digital.revision_case(seal)
            bounds = {key: {'minimum': low, 'maximum': high} for key, (_, low, high) in case.requirements.items()}
        return {'ok': True, 'study': study, 'history': self.history(project_id), 'requirement_bounds': bounds,
                'runtime': digital.runtime_for_case(study['summary'].get('case_id', cases.DEFAULT_CASE)),
                'jobs': [j.to_dict() for j in self.backend.store.list_digital_jobs(project_id)]}

    def enqueue_revision(self, project_id, *, base_revision, change_request='', requirements=None,
                         request_id=None, brief_plan=None):
        if isinstance(base_revision, bool) or not isinstance(base_revision, int) or base_revision < 1:
            raise ValueError('base_revision must be a positive integer.')
        if not isinstance(change_request, str) or len(change_request) > 200:
            raise ValueError('change_request must be a string of at most 200 characters.')
        envelope, _, seal = digital.validated_run(self.projects, project_id, base_revision)
        try:
            label = '' if brief_plan and brief_plan.get('drawing') is not None else change_request
            resolved = digital.resolve_requirements(seal, label, requirements)
        except OverflowError as exc:
            raise ValueError('Requirement value exceeds the supported bounds.') from exc
        request_id = str(UUID(str(request_id))) if request_id is not None else str(uuid4())
        payload = {'project_id': project_id, 'base_revision': base_revision,
                   'change_request': change_request.strip(), 'requirements': resolved}
        case_id = digital.case_id_for(seal)
        if case_id != cases.DEFAULT_CASE:
            payload['case_id'] = case_id
        if brief_plan is not None:
            payload['design_brief'] = brief_plan
        job_id = uuid5(NAMESPACE_URL, f'hardware-splicer:digital:{project_id}:{request_id}').hex
        existing = self.backend.store.get_job(job_id)
        if existing:
            if existing.options.get('payload') != payload:
                raise RevisionConflict('This request ID already belongs to a different change.')
            return {'ok': True, 'job': existing.to_dict(), 'resolved_requirements': resolved}
        if self.projects.load(project_id)['revision'] != base_revision:
            raise RevisionConflict('A newer project revision exists. Reload before changing requirements.')
        availability = digital.runtime_for_case(case_id)
        if not availability['available']:
            raise DigitalRuntimeUnavailable(availability['setup_hint'])
        job = self.backend.submit_task(job_id=job_id, request_id='digital:' + project_id + ':' + request_id,
                                       project_name=envelope['snapshot'].get('projectName', 'Digital study'),
                                       output_dir=self.projects.root / '.digital-jobs' / job_id,
                                       job_type='digital_study', payload=payload)
        if job.options.get('payload') != payload:
            raise RevisionConflict('This request ID already belongs to a different change.')
        return {'ok': True, 'job': job.to_dict(), 'resolved_requirements': resolved}

    def job(self, project_id, job_id):
        validate_project_id(project_id)
        job = self.backend.store.get_job(job_id)
        if (job is None or job.options.get('job_type') != 'digital_study'
                or job.options.get('payload', {}).get('project_id') != project_id):
            raise ProjectNotFound('Digital job not found in this project.')
        return job

    def run_revision(self, project_id, **request):
        submitted = self.enqueue_revision(project_id, **request)
        return self.run_job(project_id, submitted['job']['job_id'])

    def run_job(self, project_id, job_id):
        job = self.job(project_id, job_id)
        if job.status == 'queued':
            self.backend.run_next(job_type='digital_study', job_id=job_id, project_id=project_id)
            job = self.job(project_id, job_id)
        if job.status not in TERMINAL_STATUSES:
            # Another worker may already own the task. Observing it does not
            # change its attempt identity or recover/cancel its process.
            job = self.backend.wait_for_terminal(job_id, timeout_s=3660)
        result = {'ok': job.status == 'succeeded', 'job': job.to_dict()}
        if job.status == 'succeeded':
            result['study'] = self.study(project_id, job.result['revision'])
        return result

    def work(self, project_id, *, max_jobs=1):
        digital.validated_run(self.projects, project_id)
        if isinstance(max_jobs, bool) or not isinstance(max_jobs, int) or not 1 <= max_jobs <= 100:
            raise ValueError('max_jobs must be between 1 and 100.')
        completed = []
        for _ in range(max_jobs):
            job = self.backend.run_next(job_type='digital_study', project_id=project_id)
            if job is None:
                break
            completed.append(job.to_dict())
        return {'ok': all(j['status'] == 'succeeded' for j in completed), 'jobs': completed}

    def cancel(self, project_id, job_id):
        self.job(project_id, job_id)
        cancelled = self.backend.store.cancel_job(job_id)
        return {'ok': cancelled, 'job': self.job(project_id, job_id).to_dict()}

    def retry(self, project_id, job_id):
        job = self.job(project_id, job_id)
        if job.status not in {'failed', 'cancelled'}:
            raise RevisionConflict('Only a failed or cancelled digital job can be retried.')
        if self.projects.load(project_id)['revision'] != job.options['payload']['base_revision']:
            raise RevisionConflict('The project changed. Submit a new change from its latest revision.')
        if not self.backend.store.retry_job(job_id, allow_succeeded=False):
            raise RevisionConflict('The job state changed before retry.')
        return {'ok': True, 'job': self.job(project_id, job_id).to_dict()}

    def compare(self, project_id, *, before_revision, after_revision):
        before, after = self.study(project_id, before_revision), self.study(project_id, after_revision)
        b, a = before['summary'], after['summary']
        case_id = b.get('case_id', cases.DEFAULT_CASE)
        if a.get('case_id', cases.DEFAULT_CASE) != case_id:
            raise CorruptProject('Cannot compare different registered digital cases.')
        if case_id == cases.DEFAULT_CASE:
            measures = {'mass_g': (b['mass_g'], a['mass_g']), 'mass_margin_g': (b['mass_margin_g'], a['mass_margin_g'])}
            for key in ('tracking_rms_m','gust_recovery_error_m','peak_current_a_est','consumed_mah_est'):
                measures[key] = b['metrics'][key], a['metrics'][key]
        else:
            if set(b['metrics']) != set(a['metrics']):
                raise CorruptProject('Registered case metric contracts differ between revisions.')
            measures = {key: (b['metrics'][key], a['metrics'][key]) for key in a['metrics']}
        metrics = {key: {'before': old, 'after': new, 'delta': new-old}
                   for key, (old,new) in measures.items()}
        if case_id == cases.DEFAULT_CASE:
            for key in ('centre_of_mass_mm','inertia_diagonal_kg_m2'):
                metrics[key] = {'before': b[key], 'after': a[key], 'delta': [new-old for old,new in zip(b[key],a[key])]}
        changes = {key: {'before': b['requirements'][key], 'after': value, 'delta': value-b['requirements'][key]}
                   for key,value in a['requirements'].items() if value != b['requirements'][key]}
        old_checks = {c['id']: c for c in b['constraints']}
        transitions = []
        for check in a['constraints']:
            old = old_checks.get(check['id'])
            transition = ('new' if old is None else 'unchanged' if old['passed'] == check['passed']
                          else 'resolved' if check['passed'] else 'regressed')
            transitions.append({'id': check['id'], 'before': old, 'after': check, 'transition': transition})
        return {'schema': 'hardware_splicer.digital_comparison.v1', 'project_id': project_id,
                'before_revision': before['revision'], 'after_revision': after['revision'],
                'requirements_met': {'before': b['requirements_met'], 'after': a['requirements_met']},
                'same_engine_sources': b['source_sha256'] == a['source_sha256'],
                'requirements_changes': changes, 'metrics': metrics, 'constraints': transitions,
                'physical_work_requested': False, 'physical_authority_granted': False}

    def audit(self, project_id, revision=None, *, native=False):
        checks, failure = {}, None
        try:
            envelope, directory, seal = digital.validated_run(self.projects, project_id, revision)
            checks['verified_claims_and_revision_identity'] = True
            case_id = digital.case_id_for(seal)
            case = digital.case_for_run(seal)
            artifacts = digital.artifact_names(case_id, case=case)
            for name in sorted(artifacts | {'STUDY.zip'}):
                digital.checked_file(directory, name, seal['artifact_sha256'], case_id=case_id, case=case)
                checks[name] = True
            with zipfile.ZipFile(directory / 'STUDY.zip') as archive:
                infos = archive.infolist()
                if len(infos) != len(artifacts) or {i.filename for i in infos} != artifacts:
                    raise CorruptProject('Digital ZIP inventory differs from the verified package.')
                for info in infos:
                    if (info.file_size != (directory / info.filename).stat().st_size
                            or hashlib.sha256(archive.read(info)).hexdigest() != seal['artifact_sha256'][info.filename]):
                        raise CorruptProject('Digital ZIP contents differ from the verified artifacts.')
            checks['zip_contents_match_verified_files'] = True
        except (CorruptProject, OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
            failure = str(exc)
        result = {'schema': 'hardware_splicer.digital_audit.v1', 'project_id': project_id,
                  'revision': revision, 'artifact_integrity': failure is None, 'ok': failure is None,
                  'checks': checks, 'error': failure, 'physical_authority_granted': False,
                  'native_verification': {'requested': native, 'performed': False}}
        if failure is not None:
            return result
        result.update({'revision': envelope['revision'], 'run_id': seal['run_id'],
                       'requirements_met': seal['summary']['requirements_met']})
        if native:
            available = digital.runtime_for_case(case_id)
            if not available['available']:
                result.update(ok=False, error=available['setup_hint'])
                return result
            # Verification writes its receipt to a scratch copy. Published
            # revision bytes and their original evidence are never replaced.
            with tempfile.TemporaryDirectory(prefix='hs-digital-audit-') as scratch:
                copied = Path(scratch) / 'study'
                copied.mkdir()
                for name in artifacts:
                    (copied / name).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(directory / name, copied / name)
                env = dict(os.environ)
                env.pop('PYTHONOPTIMIZE', None)
                env.update({k: '1' for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')})
                if case_id != cases.DEFAULT_CASE:
                    try:
                        completed = subprocess.run([digital.native_python(), '-B', str(copied / case.verifier)],
                                                   capture_output=True, text=True, timeout=600, env=env)
                        fresh = cases.summarize(case, copied) if completed.returncode == 0 else None
                        valid = completed.returncode == 0 and fresh == seal['summary']
                        result['native_verification'] = {
                            'requested': True, 'performed': True, 'passed': valid,
                            'returncode': completed.returncode,
                            'engineering_acceptance': valid and fresh['requirements_met']}
                        result['ok'] = valid
                        if not valid:
                            result['error'] = 'Independent native verification failed: ' + (completed.stdout + completed.stderr)[-2000:]
                    except (OSError, subprocess.SubprocessError, CorruptProject, ValueError, KeyError) as exc:
                        result.update(ok=False, error=str(exc), native_verification={
                            'requested': True, 'performed': True, 'passed': False})
                    return result
                try:
                    completed = subprocess.run([digital.native_python(), '-B', str(digital.CASE / 'verify_digital.py'),
                                                str(copied), '--design', str(digital.DESIGN), '--study'],
                                               capture_output=True, text=True, timeout=120, env=env)
                    receipt = digital.read_json(copied / 'verification.json')
                except (OSError, subprocess.SubprocessError, CorruptProject) as exc:
                    result.update(ok=False, error=str(exc), native_verification={
                        'requested': True, 'performed': True, 'passed': False})
                    return result
                valid = completed.returncode == 0 and receipt.get('artifact_integrity') is True
                result['native_verification'] = {'requested': True, 'performed': True, 'passed': valid,
                                                 'returncode': completed.returncode,
                                                 'failed_checks': receipt.get('failed_checks', []),
                                                 'engineering_acceptance': valid and receipt.get('engineering_acceptance', False)}
                result['ok'] = valid
        return result

    def export(self, project_id, destination, revision=None):
        audit = self.audit(project_id, revision)
        if not audit['ok']:
            raise CorruptProject(audit['error'])
        _, directory, seal = digital.validated_run(self.projects, project_id, audit['revision'])
        destination = Path(destination).expanduser().absolute()
        destination.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix='.digital-export-', dir=destination.parent)
        try:
            with os.fdopen(fd, 'wb') as handle, (directory / 'STUDY.zip').open('rb') as source:
                shutil.copyfileobj(source, handle)
                handle.flush(); os.fsync(handle.fileno())
            if digital.digest(temporary) != seal['artifact_sha256']['STUDY.zip']:
                raise CorruptProject('Digital package changed while exporting.')
            os.link(temporary, destination)
        finally:
            Path(temporary).unlink(missing_ok=True)
        return {'ok': True, 'project_id': project_id, 'revision': audit['revision'],
                'path': str(destination), 'sha256': seal['artifact_sha256']['STUDY.zip'],
                'requirements_met': seal['summary']['requirements_met'], 'physical_authority_granted': False}
