#!/usr/bin/env python3
"""Verify manufacturer-backed footprint candidates exist and parse in installed KiCad."""
from __future__ import annotations
import argparse, json, os, shutil, subprocess
from pathlib import Path
from typing import Any, Dict

def _load(path: str | Path) -> Dict[str, Any]:
    body=json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(body,dict): raise ValueError("evidence must be one JSON object")
    return body

def _footprint_location(root: Path, library_id: str) -> tuple[Path,Path,str]:
    lib,name=library_id.split(":",1); library_dir=root/f"{lib}.pretty"
    return library_dir,library_dir/f"{name}.kicad_mod",name

def main()->int:
    p=argparse.ArgumentParser(); p.add_argument("--evidence",default="experiments/electronics/discrete_uart_3v3_1v8_evidence.json"); p.add_argument("--out-dir",default="artifacts/discrete-footprint-presence"); p.add_argument("--kicad-footprint-root",default=os.environ.get("KICAD_FOOTPRINT_ROOT","/usr/share/kicad/footprints")); a=p.parse_args()
    evidence=_load(a.evidence); out=Path(a.out_dir); out.mkdir(parents=True,exist_ok=True); root=Path(a.kicad_footprint_root); cli=shutil.which("kicad-cli")
    selected={"part-tlv75533pdbvr","part-sn74axc2t245rsw"}; rows=[]
    for part in evidence.get("parts") or []:
        if not isinstance(part,dict) or part.get("evidence_id") not in selected: continue
        candidate=str(part.get("verified_kicad_footprint_candidate") or ""); libdir,path,name=_footprint_location(root,candidate) if candidate else (Path(),Path(),""); exists=bool(candidate) and path.is_file(); ok=False; rc=None; stdout=stderr=""
        if exists and cli:
            export_dir=out/str(part["evidence_id"]); export_dir.mkdir(parents=True,exist_ok=True)
            proc=subprocess.run([cli,"fp","export","svg","--output",str(export_dir),"--footprint",name,str(libdir)],text=True,capture_output=True,check=False,timeout=60)
            rc=proc.returncode; stdout=proc.stdout[-4000:]; stderr=proc.stderr[-4000:]; ok=rc==0 and any(export_dir.glob("*.svg"))
        rows.append({"evidence_id":part.get("evidence_id"),"mpn":part.get("mpn"),"package_code":part.get("package_code"),"package_mechanical_code":part.get("package_mechanical_code"),"candidate":candidate,"library_dir":str(libdir),"footprint_name":name,"path":str(path),"file_exists":exists,"kicad_parse_export_ok":ok,"kicad_returncode":rc,"stdout_tail":stdout,"stderr_tail":stderr})
    checks={"kicad_cli_available":bool(cli),"footprint_root_exists":root.is_dir(),"both_selected_ic_candidates_checked":len(rows)==2,"all_candidate_files_exist":len(rows)==2 and all(r["file_exists"] for r in rows),"all_candidate_files_parse_in_kicad":len(rows)==2 and all(r["kicad_parse_export_ok"] for r in rows),"authority_stays_closed":True}; diagnostic=all(checks.values())
    report={"schema_version":"hardware_splicer.discrete_footprint_presence_probe.v1","benchmark":"manufacturer_package_to_installed_kicad_footprint","diagnostic_pass":diagnostic,"kicad_cli":cli,"kicad_footprint_root":str(root),"checks":checks,"parts":rows,"promotion_policy":{"eligible_for_canonical_footprint_promotion":diagnostic,"meaning":"Only exact candidates grounded by manufacturer/package evidence and independently present/parseable in the installed KiCad library may be promoted to kicad_footprint.","fabrication_authorized":False,"authority_effect":"none"},"fabrication_authorized":False,"power_on_authorized":False}
    (out/"DISCRETE_FOOTPRINT_PRESENCE.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    lines=["benchmark=manufacturer_package_to_installed_kicad_footprint",f"diagnostic_pass={diagnostic}"]
    for r in rows: lines += [f"{r['evidence_id']}.candidate={r['candidate']}",f"{r['evidence_id']}.exists={r['file_exists']}",f"{r['evidence_id']}.parse_export_ok={r['kicad_parse_export_ok']}"]
    lines += [f"check.{k}={bool(v)}" for k,v in checks.items()]; (out/"DISCRETE_FOOTPRINT_PRESENCE_SUMMARY.txt").write_text("\n".join(lines)+"\n",encoding="utf-8"); print((out/"DISCRETE_FOOTPRINT_PRESENCE_SUMMARY.txt").read_text(),end="")
    return 0 if diagnostic else 2
if __name__=="__main__": raise SystemExit(main())
