#!/usr/bin/env python3
"""Verify native third-party integrations actually ran, then emit evidence.

No tool substitutes: if the independent builder, HTML, or DeCAD validation
output is absent, this process fails rather than marking capability complete.
"""
from __future__ import annotations
import argparse,hashlib,json,re,subprocess
from pathlib import Path


def sha(blob:bytes)->str:return hashlib.sha256(blob).hexdigest()

def check(v:bool,message:str)->None:
    if not v:raise ValueError("External backend evidence REFUSED: "+message)


def verify(root:Path,blueprint_sha:str,decad_sha:str)->dict:
    root=Path(root)
    src=json.loads((root/"ECOSYSTEM_HANDOFF_RECEIPT.json").read_text())
    for name,meta in src["files"].items():
        b=(root/name).read_bytes()
        check(sha(b)==meta["sha256"] and len(b)==meta["bytes"],
              "external input mutated: "+name)
    spec=json.loads((root/"BLUEPRINT_ASSEMBLY_SPEC.json").read_text())
    odbom=json.loads((root/"DECAD_CONCEPT_ODBOM.json").read_text())
    states=json.loads((root/"BACKEND_READINESS.json").read_text())
    check(states["source_spec_sha256"]==src["source_spec_sha256"]==
          odbom["metadata"]["x-hs-source-spec-sha256"],
          "backends used different design revisions")
    check(spec["meta"]["id"]=="clearbench-s1" and
          "NON-POTABLE" in spec["meta"]["subtitle"] and
          spec["meta"]["researched"] is False,
          "viewer makes unsupported water-quality/manufacturer claim")
    check(len(spec["parts"])>=10 and "explode" in spec,
          "complete-viewing assembly or interactive teardown missing")
    check(odbom["disassembly_execution_plan"]==[] and
          all(len(v)==0 for v in odbom["graph_edges"].values()),
          "unverified disassembly geometry promoted to executable service plan")
    page=root/"interactive"/"index.html"
    check(page.is_file() and page.stat().st_size>20000,
          "real blueprint-3d-sheet self-contained viewer not generated")
    html=page.read_text(errors="replace")
    check("<html" in html.lower() and
          not re.search(r'<(?:script|link|iframe)[^>]+(?:src|href)\s*=\s*["\']https?://',
                        html,re.IGNORECASE),
          "offline product HTML absent or refers to external runtime assets")
    summary=root/"DECAD_VALIDATION.txt"
    check(summary.is_file() and summary.stat().st_size>5,
          "DeCAD native CLI validation not recorded")
    check("OK:" in summary.read_text() and
          "valid OD-BOM" in summary.read_text(),
          "DeCAD CLI did not actually pass validation")
    check(re.fullmatch(r"[0-9a-f]{40}",blueprint_sha) is not None and
          re.fullmatch(r"[0-9a-f]{40}",decad_sha) is not None,
          "third-party source commits not pinned")
    proof={
        "schema_version":"hardware_splicer.external_product_execution.v1",
        "product_id":src["product_id"],
        "source_spec_sha256":src["source_spec_sha256"],
        "executed_integrations":[
            {"name":"blueprint-3d-sheet",
             "source_commit_sha":blueprint_sha,"native_build_executed":True,
             "result":"OFFLINE_INTERACTIVE_PRODUCT_SHEET_CREATED",
             "artifact":"interactive/index.html",
             "sha256":sha(page.read_bytes()),
             "proves_physical_operation":False},
            {"name":"DeCAD",
             "source_commit_sha":decad_sha,"native_validation_executed":True,
             "result":"SCHEMA_VALID_CONCEPT_ONLY_OD_BOM",
             "artifact":"DECAD_CONCEPT_ODBOM.json",
             "sha256":sha((root/"DECAD_CONCEPT_ODBOM.json").read_bytes()),
             "disassembly_sequence_physically_verified":False},
        ],
        "other_backend_executions_performed":False,
        "CADCLAW_STEP_assembly_verified":False,
        "MARB_independent_benchmark_scored":False,
        "actual_machine_kinematics_verified":False,
        "water_filtration_performance_verified":False,
        "actual_product_assembled":False,
        "physical_authority_granted":False,
    }
    out=root/"EXTERNAL_TOOL_EXECUTION_EVIDENCE.json"
    if out.exists():raise FileExistsError("Refuse to replace external evidence")
    out.write_text(json.dumps(proof,indent=2,sort_keys=True)+"\n")
    return proof


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",required=True,type=Path)
    p.add_argument("--blueprint-sha",required=True)
    p.add_argument("--decad-sha",required=True)
    args=p.parse_args()
    print(json.dumps(verify(args.out,args.blueprint_sha,args.decad_sha),
                     indent=2,sort_keys=True))
