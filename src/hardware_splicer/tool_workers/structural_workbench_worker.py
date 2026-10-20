"""Out-of-process optional FEM solver for pinned project engineering requests."""
from __future__ import annotations
import json
from pathlib import Path
import sys


def main():
    if len(sys.argv)!=4:
        raise SystemExit('expected pinned job, output report, destination')
    from hardware_splicer.mechanical_workflow_integration import screen_mecha_project
    job=Path(sys.argv[1]);report=Path(sys.argv[2]);destination=Path(sys.argv[3])
    source=json.loads(job.read_text())
    result=screen_mecha_project(source['design'],out_dir=destination,mode='run')
    report.write_text(json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+'\n')


if __name__=='__main__':main()
