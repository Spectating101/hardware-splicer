"""Independent process boundary for extracting KiCad footprint/interface facts."""
from __future__ import annotations
import json,hashlib,subprocess,tempfile
from pathlib import Path
from typing import Any

_WORKER=Path(__file__).resolve().parent/'tool_workers'/'kicad_board_interface_worker.py'
_PYTHON=Path('/usr/bin/python3')

def inspect_board_interface_bytes(raw:bytes)->dict[str,Any]:
    source_hash='sha256:'+hashlib.sha256(raw).hexdigest()
    if len(raw)>16*1024*1024 or not raw.lstrip().startswith(b'(kicad_pcb'):
        return {'status':'invalid_board_source','source_sha256':source_hash,'physical_fit_authorized':False}
    if not _PYTHON.is_file():
        return {'status':'pcbnew_not_available','source_sha256':source_hash,'physical_fit_authorized':False}
    with tempfile.TemporaryDirectory(prefix='hs-kicad-physical-interface-') as t:
        source=Path(t)/'registered.kicad_pcb';source.write_bytes(raw)
        try:
            proc=subprocess.run([str(_PYTHON),str(_WORKER),str(source)],
                 cwd=t,capture_output=True,text=True,timeout=30,check=False)
        except (subprocess.TimeoutExpired,OSError):
            return {'status':'tool_failed_or_timeout','source_sha256':source_hash,
                    'physical_fit_authorized':False}
        if proc.returncode:
            if 'No module named' in proc.stderr and 'pcbnew' in proc.stderr:
                return {'status':'pcbnew_not_available','source_sha256':source_hash,
                        'physical_fit_authorized':False}
            return {'status':'pcbnew_failed','source_sha256':source_hash,
                    'diagnostic':proc.stderr[-350:], 'physical_fit_authorized':False}
        try:result=json.loads(proc.stdout)
        except json.JSONDecodeError:
            return {'status':'invalid_pcbnew_output','source_sha256':source_hash,
                    'physical_fit_authorized':False}
        result['source_sha256']=source_hash
        return result
