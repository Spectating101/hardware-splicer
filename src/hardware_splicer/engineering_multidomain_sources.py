"""Real mechanical and repair source readers for project-scoped engineering actions."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any

from bs4 import BeautifulSoup


_SOURCE_MAX = 32 * 1024 * 1024
_SUPPORTED_CAD_PYTHON = Path(os.environ.get(
    'HARDWARE_SPLICER_CAD_PYTHON',
    str(Path.home() / '.local/share/hardware-splicer/cad-venv/bin/python')
))
_WORKER = Path(__file__).resolve().parent / 'tool_workers' / 'step_geometry_worker.py'


def inspect_step_brep(content: bytes, *, timeout_s: int = 100) -> dict[str, Any]:
    """Validate a source STEP through OCCT; never infer mounting from its bbox."""
    if len(content) > _SOURCE_MAX or not content[:1024].lstrip().startswith(b'ISO-10303-21;'):
        return {'status': 'rejected', 'reason': 'STEP format or source size unsupported',
                'mounting_interfaces_verified': False}
    if not _SUPPORTED_CAD_PYTHON.is_file():
        return {'status': 'tool_unavailable', 'reason': 'isolated CadQuery CAD kernel not installed',
                'mounting_interfaces_verified': False}
    with tempfile.TemporaryDirectory(prefix='hs-occt-model-') as temp:
        source = Path(temp) / 'registered.step'
        source.write_bytes(content)
        try:
            cp = subprocess.run([str(_SUPPORTED_CAD_PYTHON), str(_WORKER), str(source)],
                                cwd=temp, capture_output=True, text=True, timeout=max(3,min(timeout_s,120)),
                                check=False)
        except subprocess.TimeoutExpired:
            return {'status': 'timeout', 'mounting_interfaces_verified': False}
        except OSError:
            return {'status': 'tool_error', 'mounting_interfaces_verified': False}
        if cp.returncode != 0:
            return {'status': 'cad_import_failed','diagnostic':cp.stderr[-450:],
                    'mounting_interfaces_verified': False}
        try:
            report = json.loads(cp.stdout)
        except json.JSONDecodeError:
            return {'status': 'invalid_cad_report', 'mounting_interfaces_verified': False}
        expected = 'sha256:' + hashlib.sha256(content).hexdigest()
        if report.get('source_sha256') != expected:
            raise ValueError('CAD worker reported different source digest')
        return report


def inspect_repair_guide_html(content: bytes, *, max_steps: int = 150) -> dict[str,Any]:
    """Index real guide steps and access hazards without copying manual paragraphs."""
    if len(content) > 3*1024*1024 or b'<html' not in content[:1500].lower():
        return {'status':'rejected','reason':'source is not a bounded HTML guide'}
    soup = BeautifulSoup(content, 'html.parser')
    title=(soup.title.get_text(' ',strip=True) if soup.title else '')[:180]
    wrappers=soup.select('.step-wrapper.js-step')
    if not wrappers:
        return {'status':'unsupported_layout','title':title,'source_steps_extracted':0}
    if len(wrappers)>max_steps:
        return {'status':'oversize','source_steps_extracted':0}
    stages=[]
    steps_by_class=Counter()
    terms = {
        'battery_isolation': re.compile(r'\b(battery|power off|unplug)\b',re.I),
        'fasteners': re.compile(r'\b(screws?|unscrew|screwdriver)\b',re.I),
        'ribbon_connector': re.compile(r'\b(ribbon|cable|connector|latch)\b',re.I),
        'display_access': re.compile(r'\b(lcd|display|screen)\b',re.I),
        'drive_access': re.compile(r'\b(umd|drive|laser)\b',re.I),
    }
    for pos,wrapper in enumerate(wrappers,1):
        header=wrapper.select_one('h2')
        head=header.get_text(' ',strip=True) if header else f'Step {pos}'
        lines=[li.get_text(' ',strip=True) for li in wrapper.select('.step-lines li')]
        text=' '.join(lines)
        tags=[k for k,pattern in terms.items() if pattern.search(text+' '+head)]
        for tag in tags: steps_by_class[tag]+=1
        stages.append({'step_number':pos,'source_anchor':wrapper.get('id'),
                       'heading':head[:85],'procedure_classes':tags,
                       'step_text_sha256':'sha256:'+hashlib.sha256(text.encode()).hexdigest(),
                       'step_text_stored':False})
    return {'status':'indexed_real_repair_guide','title':title,
            'source_steps_extracted':len(stages),'step_references':stages,
            'procedural_category_counts':dict(steps_by_class),
            'guide_steps_are_not_fault_confirmation':True,
            'actual_device_inspected':False,'replacement_part_approved':False,
            'physical_disassembly_authorized':False,
            'source_limitation':'HTML labels do not prove particular device revision, part fit or diagnosis'}


def inspect_scad_polyhedron(content: bytes) -> dict[str,Any]:
    """Read explicitly exported mesh vertex positions; do not execute OpenSCAD."""
    if len(content)>16*1024*1024:
        return {'status':'rejected','reason':'OpenSCAD geometry exceeds source budget'}
    try:
        text=content.decode('utf-8')
    except UnicodeDecodeError:
        return {'status':'rejected','reason':'invalid OpenSCAD text'}
    match=re.search(r'\bpolyhedron\s*\(\s*points\s*=\s*(\[.*?\])\s*,\s*faces\s*=',text,re.S)
    if not match:
        return {'status':'unsupported','reason':'no literal polyhedron point array'}
    try:
        pts=json.loads(match.group(1))
    except json.JSONDecodeError:
        return {'status':'unparsed','reason':'invalid literal points array'}
    if not isinstance(pts,list) or not pts or len(pts)>350_000:
        return {'status':'unparsed','reason':'invalid or excessive point list'}
    low=[float('inf')]*3;high=[float('-inf')]*3
    import math
    for pt in pts:
        if not isinstance(pt,list) or len(pt)!=3 or not all(type(x) in (int,float) and math.isfinite(x) for x in pt):
            return {'status':'unparsed','reason':'invalid coordinates'}
        for idx,x in enumerate(pt):
            low[idx]=min(low[idx],x);high[idx]=max(high[idx],x)
    return {'status':'parsed_polyhedron_vertices','point_count':len(pts),
            'axis_min':[round(x,3) for x in low],
            'axis_max':[round(x,3) for x in high],
            'axis_span':[round(b-a,3) for a,b in zip(low,high)],
            'units':'unresolved_OpenSCAD_source_unit_assumption',
            'full_assembly_validated':False,'interface_fit_verified':False}
