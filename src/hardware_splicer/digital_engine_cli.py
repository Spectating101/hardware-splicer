"""Operate the digital engineering engine without serving HTTP or opening a UI."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .digital_engine import DigitalStudyEngine
from .digital_cases import DEFAULT_CASE
from .part_substitution import PartProfile
from .so102_drives import follower_drive


def parser():
    command = argparse.ArgumentParser(prog='hs-digital', description=__doc__)
    command.add_argument('--project-root', type=Path)
    command.add_argument('--jobs-db', type=Path)
    commands = command.add_subparsers(dest='command', required=True)
    commands.add_parser('cases', help='List bounded registered cases and numeric requirements.')
    brief = commands.add_parser('prompt', help='Describe a device to build a registered digital study.')
    brief.add_argument('brief', help='A plain-language device description.')
    brief.add_argument('--project-id', help='Continue an existing study.')
    brief.add_argument('--base-revision', type=int, help='Revision to edit (defaults to the current revision).')
    drive = commands.add_parser('so102-drive', help='Trace a follower servo from the BOM through its mount, wiring and joint.')
    drive.add_argument('joint', choices=('shoulder', 'elbow'))
    drive.add_argument('--angle-deg', type=float, help='Test a joint angle measured from the URDF zero pose.')
    donors = drive.add_mutually_exclusive_group()
    donors.add_argument('--candidate', type=Path, help='JSON PartProfile describing a proposed replacement.')
    donors.add_argument('--passive-leader', action='store_true', help='Screen the documented passive leader donor.')
    init = commands.add_parser('init', help='Create a project from the verified digital baseline.')
    init.add_argument('--name')
    init.add_argument('--case', dest='case_id', default=DEFAULT_CASE)
    for name in ('inspect','history','revise','work','job','cancel','retry','compare','audit','export'):
        item = commands.add_parser(name)
        item.add_argument('project_id')
        if name in ('inspect','audit','export'):
            item.add_argument('--revision', type=int)
        if name == 'revise':
            item.add_argument('--base-revision', type=int, required=True)
            item.add_argument('--change', default='')
            item.add_argument('--payload-g', type=float)
            item.add_argument('--gust-scale', type=float)
            item.add_argument('--max-mass-g', type=float)
            item.add_argument('--requirements', type=Path, help='JSON object of explicit case-specific numeric overrides.')
            item.add_argument('--request-id')
            item.add_argument('--enqueue', action='store_true', help='Persist the task for a separate headless worker.')
        if name in ('job','cancel','retry'):
            item.add_argument('job_id')
        if name == 'retry':
            item.add_argument('--enqueue', action='store_true')
        if name == 'work':
            item.add_argument('--max-jobs', type=int, default=1)
        if name == 'compare':
            item.add_argument('--before', type=int, required=True)
            item.add_argument('--after', type=int, required=True)
        if name == 'audit':
            item.add_argument('--native', action='store_true', help='Recompute independent native checks on a scratch copy.')
        if name == 'export':
            item.add_argument('destination', type=Path, help='New ZIP path; existing files are never overwritten.')
    return command


def dispatch(engine, args):
    if args.command == 'prompt':
        return engine.from_prompt(args.brief, project_id=args.project_id, base_revision=args.base_revision)
    name = args.command
    if name == 'cases':
        return engine.cases()
    if name == 'init':
        return engine.create(name=args.name, case_id=args.case_id)
    project = args.project_id
    if name == 'inspect':
        return {'ok': True, 'study': engine.study(project, args.revision)}
    if name == 'history':
        return {'ok': True, 'history': engine.history(project)}
    if name == 'revise':
        requirements = {key: value for key,value in (
            ('payload_mass_g',args.payload_g), ('gust_scale',args.gust_scale), ('max_mass_g',args.max_mass_g)) if value is not None}
        if args.requirements:
            supplied = json.loads(args.requirements.read_text())
            if not isinstance(supplied, dict):
                raise ValueError('The requirements file must contain a JSON object.')
            if set(supplied) & set(requirements):
                raise ValueError('Supply each requirement once, through flags or the JSON file.')
            requirements.update(supplied)
        method = engine.enqueue_revision if args.enqueue else engine.run_revision
        return method(project, base_revision=args.base_revision, change_request=args.change,
                      requirements=requirements, request_id=args.request_id)
    if name == 'work':
        return engine.work(project, max_jobs=args.max_jobs)
    if name == 'job':
        return {'ok': True, 'job': engine.job(project, args.job_id).to_dict()}
    if name == 'cancel':
        return engine.cancel(project, args.job_id)
    if name == 'retry':
        result = engine.retry(project, args.job_id)
        return result if args.enqueue else engine.run_job(project, args.job_id)
    if name == 'compare':
        return {'ok': True, 'comparison': engine.compare(project, before_revision=args.before, after_revision=args.after)}
    if name == 'audit':
        return engine.audit(project, args.revision, native=args.native)
    if name == 'export':
        return engine.export(project, args.destination, args.revision)
    raise ValueError('Unsupported digital engine command.')


def exit_code(result):
    if not result.get('ok', False):
        return 1
    if 'interpretation' in result and result.get('study', {}).get('summary', {}).get('requirements_met') is False:
        return 2
    jobs = result.get('jobs', [])
    if 'job' in result:
        jobs = [result['job']]
    if any(job.get('status') == 'succeeded' and job.get('result', {}).get('requirements_met') is False for job in jobs):
        return 2
    return 0


def run(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == 'so102-drive':
            candidate = PartProfile.model_validate_json(args.candidate.read_bytes()) if args.candidate else None
            report = follower_drive(args.joint, candidate=candidate, passive_leader=args.passive_leader,
                                    angle_deg=args.angle_deg)
            result = {'ok': True, 'report': report}
        else:
            with DigitalStudyEngine(project_root=args.project_root, job_db=args.jobs_db) as engine:
                result = dispatch(engine, args)
        code = exit_code(result)
    except KeyboardInterrupt:
        result = {'ok': False, 'error': {'type': 'WorkerInterrupted', 'message': 'Headless execution interrupted.'}}
        code = 130
    except Exception as exc:
        result = {'ok': False, 'error': {'type': type(exc).__name__, 'message': str(exc)}}
        code = 1
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return code


def main():
    raise SystemExit(run())


if __name__ == '__main__':
    main()
