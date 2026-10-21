"""Bounded project-scope adapters to existing mechanics and practical chemistry.

The external AI supplies only an action type. Assessments are computed from the
persisted, revision-pinned project analysis requests, never model-provided
measurements, file paths, safety clearances, or downloaded manufacturer claims.
"""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
from typing import Any, Mapping

from .mechanical_workflow_integration import structural_capability_for_design
from .practical_chemistry import assess_practical_chemistry
from .printed_enclosure_workbench import prepare_printed_enclosure

_CHEMICAL_FIELDS = frozenset({
    'task','primary_material','material_identity','adjacent_materials',
    'electrical_state','battery_status','duty','exposure','rework_required',
    'residue_tolerance','electrical_function_required','interface_geometry',
    'contact_pressure_confirmed','dimensional_stability_required','corrosion_damage',
    'keepouts_confirmed','service_temperature_c','cost_quotes','currency',
})
_CAD_RUNTIME = Path(os.environ.get('HARDWARE_SPLICER_MECHANICAL_PYTHON',
    str(Path.home()/'.local/share/hardware-splicer/cad-venv/bin/python')))
_WORKER = Path(__file__).resolve().parent/'tool_workers'/'structural_workbench_worker.py'


def _request_fingerprint(request: Mapping[str, Any]) -> str:
    return 'sha256:' + sha256(json.dumps(dict(request),sort_keys=True,allow_nan=False).encode()).hexdigest()


def screen_declared_chemistry(request: Mapping[str, Any]) -> dict[str,Any]:
    if not isinstance(request, Mapping) or not request:
        raise ValueError('no persisted chemistry assessment request in pinned project')
    unknown=set(request)-_CHEMICAL_FIELDS
    if unknown:
        raise ValueError('unrecognized chemistry assessment fields: '+','.join(sorted(unknown))[:150])
    req=dict(request)
    req.setdefault('primary_material','unknown')
    req.setdefault('material_identity','unknown')
    req.setdefault('electrical_state','unknown')
    req.setdefault('battery_status','unknown')
    # A saved, declared field is NOT an attested physical measurement. Never
    # convert a model/user "verified" label into physical chemistry certainty.
    identity_downgraded=req['material_identity']=='verified'
    if identity_downgraded:
        req['material_identity']='claimed'
    outcome=assess_practical_chemistry(**req)
    return {
        'schema_version':'hardware_splicer.unified_chemistry_review.v1',
        'status':'evaluated_unverified_chemical_candidate',
        'input_sha256':_request_fingerprint(request),
        'model_provided_values_used':False,
        'material_identity_downgraded':identity_downgraded,
        'source_scope':'catalogued_supplier_claims_not_physical_specimen_tests',
        'evaluation':outcome,
        'independent_material_compatibility_verified':False,
        'battery_isolation_physically_verified':False,
        'chemical_clearance_authorized':False,
        'physical_authority_unchanged':True,
    }


def screen_declared_mechanics(request: Mapping[str, Any], *,
                              run_dir: Path, source_geometry: Mapping[str,Any] | None = None) -> dict[str,Any]:
    if not isinstance(request, Mapping) or not request:
        raise ValueError('no persisted mechanical assessment request in pinned project')
    if set(request)-{'design','mode','analysis_purpose'}:
        raise ValueError('unknown mechanical review request fields')
    design=request.get('design')
    if not isinstance(design, Mapping):
        raise ValueError('mechanical review requires project-stored design')
    if len(json.dumps(design,allow_nan=False))>12000:
        raise ValueError('mechanical design exceeds bounded request size')
    mode=request.get('mode','advisory')
    if mode not in {'advisory','run'}:
        raise ValueError('mechanical review mode must be advisory or run')
    scope=structural_capability_for_design(design)
    outcome={
        'schema_version':'hardware_splicer.unified_mechanical_review.v1',
        'input_sha256':_request_fingerprint(request),
        'source_geometry':dict(source_geometry or {}),
        'reference_geometry_does_not_supply_a_validated_load_case':True,
        'calculated_scope':scope,
        'mode_requested':mode,
        'physical_force_or_material_properties_measured':False,
        'structural_safety_verified':False,
        'fabrication_authorized':False,
        'release_authorized':False,
    }
    if mode=='advisory' or scope.get('status')!='available_not_run':
        outcome['status']='advisory_only' if mode=='advisory' else 'unsupported_for_numerical_contact'
        return outcome
    if not _CAD_RUNTIME.is_file():
        outcome.update({'status':'blocked_missing_optional_CAD_solver',
                        'solver_result':{'status':'unavailable'}})
        return outcome
    run_dir.mkdir(parents=True,exist_ok=True)
    job=run_dir/'pinned_mechanics_request.json'
    job.write_text(json.dumps({'design':dict(design)},sort_keys=True,indent=2,allow_nan=False)+'\n')
    result=run_dir/'pinned_mechanics_result.json'
    try:
        env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[1])}
        completed=subprocess.run([str(_CAD_RUNTIME),str(_WORKER),str(job),str(result),str(run_dir)],
                        capture_output=True,text=True,timeout=165,check=False,
                        cwd=str(run_dir),env=env)
    except subprocess.TimeoutExpired:
        outcome.update({'status':'blocked_solver_timeout','solver_result':{'status':'timeout'}})
        return outcome
    if completed.returncode!=0 or not result.is_file():
        outcome.update({'status':'blocked_solver_error',
                        'solver_result':{'status':'tool_error','diagnostic':completed.stderr[-480:]}})
        return outcome
    parsed=json.loads(result.read_text())
    outcome.update({'status':'numerical_screening_completed_not_physical_release',
                    'solver_result':parsed,'analysis_files_directory':str(run_dir)})
    return outcome


def prepare_declared_enclosure(request: Mapping[str, Any]) -> dict[str,Any]:
    if not isinstance(request,Mapping) or not request:
        raise ValueError('no declared enclosure design request in pinned project')
    plan=prepare_printed_enclosure(request)
    return {
        'schema_version':'hardware_splicer.unified_enclosure_concept.v1',
        'status':'parametric_solidcraft_commands_created',
        'design_request_sha256':_request_fingerprint(request),
        'plan':plan,
        'native_cad_executed':False,
        'physical_donor_fit_verified':False,
        'print_authorized':False,
    }
