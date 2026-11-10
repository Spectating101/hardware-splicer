"""Audit and render the frozen Repair Investigator run as offline interactive HTML.

The renderer makes no LLM calls and never accesses video after-repair
outcomes. It audits every receipt and rebuilds all original prompts from
the saved source evidence before generating the report.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from hardware_splicer.repair_investigator import file_sha256,sha
from hardware_splicer.repair_investigator_audit import verify_investigation
from hardware_splicer.repair_investigator_report import make_html

HERE=Path(__file__).resolve().parent
CASE=HERE/"c64_250407/case.json"

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--case",type=Path,default=CASE)
    p.add_argument("--record",type=Path,required=True)
    p.add_argument("--html",type=Path,required=True)
    p.add_argument("--audit",type=Path,required=True)
    args=p.parse_args()
    if args.html.exists() or args.audit.exists():
        raise SystemExit("Refusing overwrite: previous generated forensic artifacts already exist")
    manifest=json.loads(args.case.read_text())
    ref_path=args.case.parent/manifest["source_reference_file"]
    ref=json.loads(ref_path.read_text())
    data=json.loads(args.record.read_text())
    audit=verify_investigation(data,manifest,ref)
    page=make_html(record=data,manifest=manifest,reference=ref,
                   snapshot_sha256=file_sha256(ref_path))
    args.html.parent.mkdir(parents=True,exist_ok=True)
    args.audit.parent.mkdir(parents=True,exist_ok=True)
    args.html.write_text(page,encoding="utf-8")
    args.audit.write_text(json.dumps(audit,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({
        "case":manifest["id"],
        "report_html":str(args.html),"html_kb":round(args.html.stat().st_size/1024,1),
        "attempts":audit["model_attempts"],"valid_by_arm":audit["valid_by_arm"],
        "source_graph_sha256":audit["source_graph_sha256"],
        "offline_only":True,"physical_repair_claimed":False,
    },indent=2))
if __name__=="__main__":
    main()
