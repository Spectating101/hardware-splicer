"""Registered-project KiCad -> source-contour PCB carrier, release fail-closed.

Inputs are restricted to the original project sources read via HS's
hash-verifying source store. The model cannot select arbitrary source paths,
geometry coordinates, fastener types, machine commands or physical authority.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Any,Mapping

from .engineering_kicad_interface import inspect_board_interface_bytes
from .stored_source_parser import read_registered_source_bytes

_CAD_PYTHON=Path(os.environ.get('HARDWARE_SPLICER_CAD_PYTHON',
    str(Path.home()/'.local/share/hardware-splicer/cad-venv/bin/python')))
_WORKER=Path(__file__).resolve().parent/'tool_workers'/'pcb_edge_retention_worker.py'


def generate_registered_pcb_edge_retention_candidate(
    project_id:str,
    sources:list[Mapping[str,Any]],
    output_dir:str|Path,
    *,project_root:str|Path|None=None,
)->dict[str,Any]:
    boards=[s for s in sources if str((s.get('metadata') or {}).get('original_filename') or '').endswith('.kicad_pcb')]
    if len(boards)!=1:raise ValueError('requires exactly one registered KiCad board')
    board=boards[0]
    filename=str(board['metadata']['original_filename'])
    if '/' in filename or '\\' in filename or len(filename)>150:
        raise ValueError('registered board filename must be flat and bounded')
    stem=filename[:-10]
    project=[s for s in sources if str((s.get('metadata') or {}).get('original_filename') or '')==stem+'.kicad_pro']
    if len(project)!=1:raise ValueError('source board needs corresponding registered .kicad_pro')
    board_raw=read_registered_source_bytes(project_id,board,project_root=project_root)
    project_raw=read_registered_source_bytes(project_id,project[0],project_root=project_root)
    if not board_raw.lstrip().startswith(b'(kicad_pcb') or not project_raw.lstrip().startswith(b'{'):
        raise ValueError('registered KiCad source signatures invalid')
    if not _CAD_PYTHON.is_file():
        raise RuntimeError('CadQuery backend unavailable; no CAD result produced')
    extracted=inspect_board_interface_bytes(board_raw)
    if (extracted.get('status')!='extracted_kicad_source_geometry' or
        not extracted.get('edge_cuts_profile_closed') or
        not extracted.get('edge_cuts_profile_mm') or
        extracted.get('explicit_mounting_footprint_refs')):
        raise ValueError('no valid source single-board Edge.Cuts contour for edge-capture candidate')
    if extracted['source_sha256'] != str(board.get('content_hash')):
        raise ValueError('registered board source hash changed during analysis')
    output=Path(output_dir)
    with tempfile.TemporaryDirectory(prefix='hs-source-verified-edge-retention-') as tmp:
        temp=Path(tmp)
        pcb=temp/filename
        pcb.write_bytes(board_raw)
        (temp/(stem+'.kicad_pro')).write_bytes(project_raw)
        step=temp/'source-board-only.step'
        kicad=subprocess.run([
            'kicad-cli','pcb','export','step','--board-only','--no-components',
            '--output',str(step),str(pcb)],cwd=temp,capture_output=True,
            text=True,timeout=65,check=False)
        if kicad.returncode!=0 or not step.is_file():
            raise RuntimeError('KiCad board-only CAD export failed: '+(kicad.stderr or kicad.stdout)[-400:])
        source_json=temp/'source-interface.json'
        source_json.write_text(json.dumps(extracted))
        output.mkdir(parents=True,exist_ok=True)
        generated=subprocess.run([
           str(_CAD_PYTHON),str(_WORKER),str(step),str(source_json),str(output)],
           cwd=temp,capture_output=True,text=True,timeout=130,check=False)
        if generated.returncode:
            raise RuntimeError('KiCad-derived edge retention CAD failed: '+(generated.stderr or generated.stdout)[-430:])
        try:report=json.loads(generated.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError('edge CAD solver did not report valid JSON') from exc
        if report.get('status')!='generated_collision_screened_edge_retention_candidate':
            raise RuntimeError('CAD worker did not validate proposed solids')
        report['source_project_config_sha256']=str(project[0]['content_hash'])
        report['source_board_sha256']=str(board['content_hash'])
        report['source_geometry_trace']={
            'original_board_filename':filename,
            'edge_cuts_profile_vertex_count':len(extracted['edge_cuts_profile_mm']),
            'source_component_count':extracted['footprint_count'],
            'verified_board_mounting_footprints':extracted['explicit_mounting_footprint_refs'],
            'source_npht_feature_references':sorted({r['reference'] for r in extracted['nonplated_drill_features']}),
        }
        report['software_only_proposal']=True
        report['released_for_fabrication']=False
        (output/'source_edge_retention_report.json').write_text(json.dumps(report,indent=2)+'\n')
        return report
