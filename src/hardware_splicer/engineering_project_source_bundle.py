"""Source-backed, read-only checks of a COMPLETE registered KiCad project bundle.

An individual PCB without its KiCad project configuration MUST NOT receive a
project-equivalent DRC claim. Only hash-verified project source blobs are read;
engineering design facts retain declared/proposed authority.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import math
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
from typing import Any, Mapping
import xml.etree.ElementTree as ET

from .stored_source_parser import read_registered_source_bytes
from .engineering_reference_bom_audit import audit_markdown_reference_bom
from .engineering_kicad_interface import inspect_board_interface_bytes
from .engineering_multidomain_sources import inspect_step_brep, inspect_repair_guide_html, inspect_scad_polyhedron
from .engineering_source_ingestion import MAX_ENGINEERING_SOURCE_BYTES


def _digest(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def inspect_stl(data: bytes) -> dict[str, Any]:
    """Extract strictly geometric (unitless) triangle bounds without a CAD kernel."""
    if len(data) < 84:
        return {"status": "unparsed", "reason": "STL data too short"}
    triangles = struct.unpack_from('<I', data, 80)[0]
    if triangles == 0 or triangles > 2_000_000 or len(data) != 84 + 50 * triangles:
        return {"status": "unparsed", "reason": "not a bounded binary STL"}
    low = [math.inf] * 3
    high = [-math.inf] * 3
    for i in range(triangles):
        base = 84 + i * 50 + 12  # Skip surface normal.
        for corner in range(3):
            coords = struct.unpack_from('<fff', data, base + 12 * corner)
            if not all(math.isfinite(c) for c in coords):
                return {"status": "unparsed", "reason": "nonfinite mesh coordinate"}
            for axis, value in enumerate(coords):
                low[axis] = min(low[axis], value)
                high[axis] = max(high[axis], value)
    return {"status": "parsed_raw_bounds", "triangle_count": triangles,
            "axis_min": [round(v, 5) for v in low],
            "axis_max": [round(v, 5) for v in high],
            "axis_span": [round(b - a, 5) for a, b in zip(low, high)],
            "units": "unresolved_STL_has_no_unit_metadata",
            "fit_verified": False, "watertightness_verified": False}


def _source_kind(name: str, data: bytes) -> str | None:
    if name.endswith('.kicad_pro') and data.lstrip().startswith(b'{'):
        return 'kicad_project_config'
    if name.endswith('.kicad_sch') and data.lstrip().startswith(b'(kicad_sch'):
        return 'kicad_schematic'
    if name.endswith('.kicad_pcb') and data.lstrip().startswith(b'(kicad_pcb'):
        return 'kicad_board'
    if name.lower().endswith('.stl') and len(data) >= 84:
        return 'binary_stl_candidate'
    if name.lower().endswith('.md') and b'estimated total by category' in data[:300_000].lower():
        return 'reference_markdown_bom'
    if name.lower().endswith(('.step', '.stp')) and data[:1024].lstrip().startswith(b'ISO-10303-21;'):
        return 'step_cad'
    if name.lower().endswith('.html') and b'<html' in data[:1500].lower():
        return 'repair_guide_html'
    if name.lower().endswith('.scad') and b'polyhedron' in data[:4096]:
        return 'scad_polyhedron'
    return None


def _validate_named_files(named: Mapping[str, bytes]) -> dict[str, str]:
    names = {}
    if not 1 <= len(named) <= 15:
        raise ValueError('project bundle has unsupported source count')
    for name, data in named.items():
        if name != Path(name).name or '/' in name or '\\' in name or name.startswith('.'):
            raise ValueError('source filename must be a safe basename')
        if not isinstance(data, bytes) or len(data) > MAX_ENGINEERING_SOURCE_BYTES:
            raise ValueError('source bytes missing or over limit')
        kind = _source_kind(name, data)
        if kind:
            names[name] = kind
    return names


def _execute_cli(args: list[str], cwd: str, report: Path) -> dict[str, Any]:
    try:
        cp = subprocess.run(args, cwd=cwd, text=True, capture_output=True, timeout=45, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return {"status": "tool_error", "check_executed": False}
    if cp.returncode not in {0, 5} or not report.is_file():
        return {"status": "tool_error", "check_executed": True,
                "exit_code": cp.returncode, "diagnostic": (cp.stderr or cp.stdout)[:500]}
    contents = report.read_bytes()
    findings = Counter(line[1:].split(']', 1)[0] for line in contents.decode('utf-8', 'replace').splitlines()
                       if line.startswith('[') and ']' in line)
    return {"status": "findings_present" if findings else "no_findings_reported",
            "check_executed": True, "exit_code": cp.returncode,
            "rule_finding_count": sum(findings.values()),
            "rule_findings_by_type": dict(sorted(findings.items())),
            "report_sha256": _digest(contents),
            "manufacturer_or_local_library_issues_possible": True,
            "manufacturing_approved": False}


def _netlist_facts(xml_path: Path) -> dict[str, Any]:
    root = ET.parse(xml_path).getroot()
    comps = root.findall('./components/comp')
    nets = root.findall('./nets/net')
    if len(comps) > 1500 or len(nets) > 10000:
        return {"status": "oversize", "fit_verified": False}
    component_rows = []
    for comp in comps:
        lib = comp.find('libsource')
        component_rows.append({"ref": (comp.get('ref') or '')[:32],
                               "value": (comp.findtext('value') or '')[:125],
                               "footprint": (comp.findtext('footprint') or '')[:160],
                               "library": (lib.get('lib') if lib is not None else None)})
    net_rows = []
    for net in nets:
        nodes = [{"ref": (n.get('ref') or '')[:32], "pin": (n.get('pin') or '')[:24]}
                 for n in net.findall('node')[:100]]
        net_rows.append({"name": (net.get('name') or '')[:150], "nodes": nodes,
                         "nodes_truncated": len(net.findall('node')) > 100})
    return {"status": "exported_project_netlist", "component_count": len(comps),
            "net_count": len(nets), "components": component_rows,
            "nets": net_rows, "source_sha256": _digest(xml_path.read_bytes()),
            "component_ratings_validated": False, "pinout_compatibility_verified": False}


def analyze_project_bundle(named: Mapping[str, bytes], *, source_identity: Mapping[str, str] | None = None, budget_cap_usd: float | None = None) -> dict[str, Any]:
    """Run KiCad CLI on companion files and parse a real source netlist."""
    formats = _validate_named_files(named)
    entry = {name: {"sha256": _digest(content), "kind": formats.get(name, 'unsupported')}
             for name, content in sorted(named.items())}
    if source_identity:
        for name, expected in source_identity.items():
            if name not in entry or entry[name]['sha256'] != expected:
                raise ValueError('bundle file hash mismatches registered source identity')
    result: dict[str, Any] = {"schema_version": "hardware_splicer.project_source_bundle.v1",
                              "input_sources": entry, "software_tool": "kicad-cli",
                              "status": "incomplete", "project_context": "unresolved",
                              "software_checks": {}, "geometry": {}, "repair_evidence": {},
                              "release_authorized": False,
                              "manufacturing_approved": False}
    for name, kind in formats.items():
        if kind == 'binary_stl_candidate':
            result['geometry'][name] = inspect_stl(named[name])
        if kind == 'reference_markdown_bom':
            result['alternative_reference_bom_audit'] = audit_markdown_reference_bom(named[name], cap_usd=budget_cap_usd)
        if kind == 'step_cad':
            result['geometry'][name] = inspect_step_brep(named[name])
        if kind == 'repair_guide_html':
            result['repair_evidence'][name] = inspect_repair_guide_html(named[name])
        if kind == 'scad_polyhedron':
            result['geometry'][name] = inspect_scad_polyhedron(named[name])
    source_failures = []
    for name, data in result['geometry'].items():
        if data.get('status') not in {'imported_brep','parsed_raw_bounds','parsed_polyhedron_vertices'}:
            source_failures.append({'source':name,'status':data.get('status')})
    for name, data in result['repair_evidence'].items():
        if data.get('status') != 'indexed_real_repair_guide':
            source_failures.append({'source':name,'status':data.get('status')})
    result['source_analysis_failures'] = source_failures
    if not any(kind == 'kicad_board' for kind in formats.values()):
        result['project_context'] = 'not_applicable'
        result['status'] = ('incomplete' if source_failures or not formats
                            else 'analyzed_non_electrical_sources')
        result['software_tool'] = 'source_type_auto_dispatch'
        result['semantic_limitations'] = [
            'Extracted source facts do not prove physical fit or a finished design.',
            'Unknown physical measurements, safety and procurement remain blocked.',
        ]
        return result
    bases = sorted({name[:-10] for name, kind in formats.items() if kind == 'kicad_board'})
    if not bases:
        result['reason'] = 'no KiCad board in source bundle'
        return result
    if len(bases) != 1:
        raise ValueError('ambiguous KiCad board stems; select one project')
    base = bases[0]
    result['project_stem'] = base
    if formats.get(base + '.kicad_pro') != 'kicad_project_config':
        result['reason'] = 'companion .kicad_pro absent; standalone DRC is not project-comparable'
        result['project_context'] = 'missing'
        return result
    if formats.get(base + '.kicad_sch') != 'kicad_schematic':
        result['reason'] = 'companion .kicad_sch absent; incomplete electrical project'
        result['project_context'] = 'partial'
        return result
    result['project_context'] = 'source_bundle_sibling_files_present'
    result['board_interface_geometry'] = inspect_board_interface_bytes(named[base + '.kicad_pcb'])
    # Report missing project companions before evaluating tool availability;
    # source-context errors must be stable on developer hosts and CI machines.
    if not shutil.which('kicad-cli'):
        result['reason'] = 'kicad-cli unavailable'
        return result
    with tempfile.TemporaryDirectory(prefix='hs-registered-kicad-project-') as scratch:
        for name, content in named.items():
            if name in formats and formats[name].startswith('kicad_'):
                (Path(scratch) / name).write_bytes(content)
        pcb = Path(scratch) / (base + '.kicad_pcb')
        sch = Path(scratch) / (base + '.kicad_sch')
        checks = {
            'erc': _execute_cli(['kicad-cli','sch','erc','--exit-code-violations',
                                 '--output',str(Path(scratch)/'erc.txt'),str(sch)],
                                scratch, Path(scratch)/'erc.txt'),
            'drc': _execute_cli(['kicad-cli','pcb','drc','--exit-code-violations',
                                 '--output',str(Path(scratch)/'drc.txt'),str(pcb)],
                                scratch, Path(scratch)/'drc.txt'),
        }
        result['software_checks'] = checks
        output = Path(scratch) / 'netlist.xml'
        try:
            cp = subprocess.run(['kicad-cli','sch','export','netlist','--format','kicadxml',
                                 '--output',str(output),str(sch)], cwd=scratch,
                                capture_output=True, text=True, timeout=45, check=False)
            if cp.returncode == 0 and output.is_file() and output.stat().st_size <= 8 * 1024 * 1024:
                result['netlist'] = _netlist_facts(output)
            else:
                result['netlist'] = {"status": "export_failed", "exit_code": cp.returncode}
        except (OSError, subprocess.TimeoutExpired, ET.ParseError):
            result['netlist'] = {"status": "export_error"}
    result['status'] = 'analyzed_with_findings' if all(c.get('check_executed') for c in result['software_checks'].values()) else 'incomplete'
    result['semantic_limitations'] = [
        'This reads existing source; it does not design a complete cyberdeck.',
        'Missing libraries may bias KiCad findings; no physical measurements or compatibility approval.',
        'STL coordinate units, wall strength and mating fit remain unverified.',
    ]
    return result


def analyze_registered_project_bundle(project_id: str, sources: list[Mapping[str, Any]], *,
                                      project_root: str | Path | None = None,
                                      budget_cap_usd: float | None = None) -> dict[str, Any]:
    """Operate on same-project, SHA256-verified registered source blobs only."""
    selected: dict[str, bytes] = {}
    identities: dict[str, str] = {}
    for src in sources:
        metadata = src.get('metadata') or {}
        filename = str(metadata.get('original_filename') or '')
        if not filename or Path(filename).name != filename or '/' in filename or '\\' in filename:
            continue
        suffix = Path(filename).suffix.lower()
        if suffix not in {'.kicad_pro','.kicad_sch','.kicad_pcb','.stl','.step','.stp','.html','.scad','.md'}:
            continue
        if filename in selected:
            raise ValueError('ambiguous multiple source identities for '+filename)
        content = read_registered_source_bytes(project_id, src, project_root=project_root)
        selected[filename] = content
        identities[filename] = str(src.get('content_hash') or '')
    if not selected:
        raise ValueError('no eligible registered engineering files')
    out = analyze_project_bundle(selected, source_identity=identities, budget_cap_usd=budget_cap_usd)
    source_pairs = sorted((str(row.get('source_id') or ''), str(row.get('content_hash') or ''))
                          for row in sources)
    import json
    out['source_set_sha256'] = _digest(json.dumps(source_pairs, sort_keys=True).encode())
    return out
