"""Design a bounded editable board-envelope carrier from registered PCB geometry."""
from __future__ import annotations
import hashlib
import os
import json
from pathlib import Path
import subprocess
import tempfile
from typing import Any, Mapping

from .stored_source_parser import read_registered_source_bytes

_CAD_PYTHON=Path(os.environ.get(
    'HARDWARE_SPLICER_CAD_PYTHON',
    str(Path.home() / '.local/share/hardware-splicer/cad-venv/bin/python')
))
_WORKER=Path(__file__).resolve().parent/'tool_workers'/'pcb_carrier_worker.py'


def generate_registered_pcb_carrier(
    project_id: str, sources: list[Mapping[str,Any]], output_dir: str | Path,
    *, project_root: str | Path | None = None,
) -> dict[str, Any]:
    """Generate real STEP + STL candidate with no physical-fit authority."""
    output=Path(output_dir)
    eligible=[src for src in sources if str((src.get('metadata') or {}).get('original_filename') or '').endswith('.kicad_pcb')]
    if len(eligible)!=1:raise ValueError('exactly one registered KiCad board required')
    board=eligible[0]
    filename=str(board['metadata']['original_filename'])
    companion_stem=filename[:-10]
    pro=[src for src in sources if str((src.get('metadata') or {}).get('original_filename') or '')==companion_stem+'.kicad_pro']
    if len(pro)!=1:raise ValueError('matching project configuration required')
    board_raw=read_registered_source_bytes(project_id,board,project_root=project_root)
    pro_raw=read_registered_source_bytes(project_id,pro[0],project_root=project_root)
    if not board_raw.lstrip().startswith(b'(kicad_pcb') or not pro_raw.lstrip().startswith(b'{'):
        raise ValueError('registered board/project signatures invalid')
    if not _CAD_PYTHON.is_file():
        raise RuntimeError('CAD kernel not installed: no carrier generation claimed')
    with tempfile.TemporaryDirectory(prefix='hs-source-carrier-') as td:
        scratch=Path(td)
        pcb=scratch/filename;pcb.write_bytes(board_raw)
        (scratch/(companion_stem+'.kicad_pro')).write_bytes(pro_raw)
        base=scratch/'source-board.step'
        export=subprocess.run(['kicad-cli','pcb','export','step','--board-only','--no-components',
                               '--output',str(base),str(pcb)],cwd=scratch,
                              capture_output=True,text=True,timeout=55,check=False)
        if export.returncode!=0 or not base.is_file():
            raise RuntimeError('KiCad board-only STEP export failed: '+(export.stderr or export.stdout)[-380:])
        output.mkdir(parents=True,exist_ok=True)
        result=subprocess.run([str(_CAD_PYTHON),str(_WORKER),str(base),str(output)],
                              cwd=scratch,capture_output=True,text=True,timeout=100,check=False)
        if result.returncode:
            raise RuntimeError('CAD solid generation failed: '+result.stderr[-350:])
        try:report=json.loads(result.stdout)
        except json.JSONDecodeError as e:raise ValueError('invalid CAD worker response') from e
        if report.get('status')!='generated_valid_solid_candidate':
            raise ValueError('CAD candidate not valid')
        report['registered_board_sha256']=str(board.get('content_hash'))
        report['registered_project_sha256']=str(pro[0].get('content_hash'))
        report['manufacturer_footprints_physically_checked']=False
        report['model_created_by']='HS bounded CadQuery board-envelope operation'
        (output/'carrier_candidate_report.json').write_text(json.dumps(report,indent=2)+'\n')
        return report
