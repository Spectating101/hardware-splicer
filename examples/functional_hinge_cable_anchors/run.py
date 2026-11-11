"""Execute or independently re-audit the cable-anchor engineering milestone."""
from __future__ import annotations
import argparse,json
from pathlib import Path
from hardware_splicer.functional_hinge_cable_anchors import execute,audit
HERE=Path(__file__).resolve().parent
HINGE=HERE.parent/"functional_hinge_cyberdeck"/"reference_spec.json"
RET=HERE.parent/"functional_hinge_retention"/"spec.json"

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--spec",type=Path,default=HERE/"spec.json")
    parser.add_argument("--hinge",type=Path,default=HINGE)
    parser.add_argument("--retainer",type=Path,default=RET)
    parser.add_argument("--out",type=Path,default=HERE/"generated")
    parser.add_argument("--audit-only",action="store_true")
    a=parser.parse_args()
    src=json.loads(a.spec.read_text());hinge=json.loads(a.hinge.read_text())
    ret=json.loads(a.retainer.read_text())
    if not a.audit_only:
        execute(src,hinge,ret,a.out)
    result=audit(src,hinge,ret,a.out)
    if not a.audit_only:
        (a.out/"SOURCE_AUDIT.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps(result,indent=2))
if __name__=="__main__": main()
