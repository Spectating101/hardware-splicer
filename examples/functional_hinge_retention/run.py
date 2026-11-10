"""Generate or independently audit the grooved pivot and virtual cable sweep.

No physical printer, actual shaft manufacturing, cable sourcing,
electrical signal testing or servo load actuation is performed.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from hardware_splicer.functional_hinge_retention import run,audit

HERE=Path(__file__).resolve().parent
PARENT=HERE.parent/"functional_hinge_cyberdeck"/"reference_spec.json"

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--spec",type=Path,default=HERE/"spec.json")
    ap.add_argument("--parent",type=Path,default=PARENT)
    ap.add_argument("--out",type=Path,default=HERE/"generated")
    ap.add_argument("--audit-only",action="store_true")
    args=ap.parse_args()
    request=json.loads(args.spec.read_text())
    parent=json.loads(args.parent.read_text())
    if not args.audit_only:
        run(request,parent,out=args.out)
    receipt=audit(request,parent,out=args.out)
    target=args.out/"SOURCE_INDEPENDENT_AUDIT.json"
    if not args.audit_only and not target.exists():
        target.write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n")
    print(json.dumps(receipt,indent=2))
if __name__=="__main__":
    main()
