"""Optional, fail-closed REA intake for owned firmware/application artifacts.

REA is not installed by HS, and this adapter never performs agent setup,
executes analyzed binaries, or converts observations into release authority.
"""
from __future__ import annotations
import hashlib
import json
import subprocess
from pathlib import Path


def investigate_artifact(path: str | Path, *, rea_executable: str = 'rea', timeout_s: int = 90) -> dict:
    target = Path(path).expanduser().resolve(strict=True)
    if not target.is_file() or target.is_symlink() or target.stat().st_size > 128 * 1024 * 1024:
        raise ValueError('REA intake requires a bounded regular local artifact')
    if not 1 <= timeout_s <= 300:
        raise ValueError('bounded REA timeout required')
    digest = 'sha256:' + hashlib.sha256(target.read_bytes()).hexdigest()
    result = {'schema':'hardware_splicer.rea_investigation.v1',
              'artifact_sha256':digest,'size_bytes':target.stat().st_size,
              'investigation_engine':'rea-agents',
              'electrical_behavior_verified':False,'physical_fit_verified':False,
              'firmware_flash_authorized':False,'fabrication_authorized':False,
              'release_authorized':False}
    try:
        completed = subprocess.run([rea_executable,'inspect-artifact',str(target),'--format','json'],
                                   capture_output=True,text=True,timeout=timeout_s,check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {**result,'status':'unavailable','error_type':type(exc).__name__}
    try:
        findings=json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {**result,'status':'unavailable','error_type':'invalid_provider_output'}
    if not isinstance(findings,dict):
        return {**result,'status':'unavailable','error_type':'invalid_provider_shape'}
    if completed.returncode != 0 or findings.get('error') or findings.get('code') in ('provider_unavailable','target_unavailable'):
        return {**result,'status':'blocked',
                'provider_code':str(findings.get('code') or 'nonzero_exit')[:100],
                'provider_message':str(findings.get('message') or findings.get('error') or '')[:400]}
    return {**result,'status':'analysis_available_unverified',
            'rea_evidence':findings,'source_scope':'static_observation_not_physical_repair_qualification'}


def investigate_javascript_application(directory: str | Path, *, rea_executable: str = 'rea', timeout_s: int = 90) -> dict:
    """Static application graph intake; does not execute target JavaScript."""
    root=Path(directory).expanduser().resolve(strict=True)
    if not root.is_dir() or not 1 <= timeout_s <= 300:
        raise ValueError('bounded local application directory required')
    files=[f for f in root.rglob('*') if f.is_file()]
    if len(files)>500 or any(f.is_symlink() or f.stat().st_size>8*1024*1024 for f in files):
        raise ValueError('application directory exceeds bounded static-analysis scope')
    if not files:
        raise ValueError('empty application directory')
    digest=hashlib.sha256()
    for f in sorted(files):
        digest.update(str(f.relative_to(root)).encode());digest.update(hashlib.sha256(f.read_bytes()).digest())
    base={'schema':'hardware_splicer.rea_javascript_intake.v1',
          'input_tree_sha256':'sha256:'+digest.hexdigest(),
          'file_count':len(files),'release_authorized':False,'source_executed':False}
    try:
        proc=subprocess.run([rea_executable,'analyze-javascript-application',str(root),'--format','json'],
                            capture_output=True,text=True,timeout=timeout_s,check=False)
        data=json.loads(proc.stdout)
    except (OSError,subprocess.TimeoutExpired,ValueError) as exc:
        return {**base,'status':'unavailable','error_type':type(exc).__name__}
    if not isinstance(data,dict) or proc.returncode or data.get('error') or data.get('code') in ('target_unavailable','provider_unavailable'):
        return {**base,'status':'blocked','provider_code':str(data.get('code','invalid_output')) if isinstance(data,dict) else 'invalid_output'}
    if data.get('predicate_type')!='rea.javascript-application-analysis' or not isinstance(data.get('evidence_id'),str):
        return {**base,'status':'blocked','provider_code':'unexpected_evidence_type'}
    return {**base,'status':'static_analysis_available_unverified',
            'rea_evidence_id':data['evidence_id'],
            'rea_subject_sha256':data.get('subject',{}).get('digest',{}).get('sha256'),
            'source_scope':'static_application_graph_not_firmware_behavior_or_hardware_validation'}
