#!/usr/bin/env python3
"""Record actual exited-zero native PartCAD CLI parsing on source-bound STEP package."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from hardware_splicer.multicad_toolchain import partcad_execution_receipt
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project",type=Path,required=True)
    p.add_argument("--cli-log",type=Path,required=True)
    a=p.parse_args()
    try:
        evidence=partcad_execution_receipt(a.project,a.cli_log)
    except (OSError,ValueError,KeyError,TypeError) as e:
        print("PartCAD native tool evidence refused: "+str(e),file=sys.stderr)
        return 1
    print(json.dumps(evidence,indent=2,sort_keys=True))
    return 0
if __name__=="__main__":
    raise SystemExit(main())
