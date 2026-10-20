"""Package real slicer data and live Codex instructions with independent gates."""
from __future__ import annotations
import argparse,hashlib,json,zipfile
from pathlib import Path
from hardware_splicer.realization_gcode_audit import audit_offline_gcode
from hardware_splicer.realization_runbook import verify_agent_realization_guide,render_realization_runbook

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser()
 ap.add_argument("--bundle",type=Path,required=True)
 ap.add_argument("--zip",type=Path,required=True)
 a=ap.parse_args(); root=a.bundle.resolve(strict=True)
 raw=json.loads((root/"CODEX_LIVE_REALIZATION_RESULT.json").read_text())
 if not raw.get("ok") or raw.get("provider")!="codex_chatgpt":
  raise ValueError("No authenticated live Codex response")
 guide=json.loads(raw["content"])
 gcode=audit_offline_gcode(root/"MK4S_CASING_UNAPPROVED.gcode")
 staging=json.loads((root/"PRINTER_STAGE_DRYRUN.json").read_text())
 controls=json.loads((root/"VIRTUAL_CONTROLLER_ADVERSARIAL_AUDIT.json").read_text())
 audited=verify_agent_realization_guide(guide,gcode,staging,controls)
 (root/"AGENT_GUIDE_INDEPENDENT_AUDIT.json").write_text(json.dumps(audited,indent=2)+"\n")
 if not audited["conditional_instructions_accepted"]:
  raise ValueError("agent guide validation failed: "+str(audited["violations"]))
 (root/"AGENT_REALIZATION_GUIDE.json").write_text(json.dumps(guide,indent=2)+"\n")
 (root/"REAL_WORLD_OPERATOR_RUNBOOK.md").write_text(render_realization_runbook(guide,gcode,audited))
 manifest=json.loads((root/"REALIZATION_MANIFEST.json").read_text())
 if manifest["gcode_sha256"]!=gcode["sha256"] or staging["gcode_sha256"]!=gcode["sha256"]:
  raise ValueError("G-code hash across checks doesn't match")
 if controls["physical_controller_release"]!="BLOCKED" or controls["mutants_detected"]!=controls["mutants_tested"]:
  raise ValueError("virtual controller independent audit not adequate")
 if manifest["physical_fabrication_authorized"] or manifest["printer_connected"]:
  raise ValueError("unverified physical operation in manifest")
 manifest.update({
  "live_agent":"ChatGPT-authenticated Codex","guide_steps_checked":audited["steps_checked"],
  "independent_agent_guide_accepted":True,
  "printer_staging_dryrun_without_physical_start":True,
  "independent_virtual_controller_redteam":True,
  "release_decision":"BLOCKED_FOR_REAL_PRINTER_WIRING_AND_MOTION",
  "physical_fabrication_authorized":False,
  "physical_motion_authorized":False,
 })
 manifest["files_sha256"]={str(f.relative_to(root)):digest(f) for f in sorted(root.rglob("*"))
                          if f.is_file() and f.name!="REALIZATION_MANIFEST.json"}
 (root/"REALIZATION_MANIFEST.json").write_text(json.dumps(manifest,indent=2)+"\n")
 archive=a.zip.resolve()
 if archive.exists():raise FileExistsError("archive already exists")
 with zipfile.ZipFile(archive,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=7) as out:
  for p in sorted(root.rglob("*")):
   if p.is_file():out.write(p,arcname=str(p.relative_to(root)))
 with zipfile.ZipFile(archive) as z:
  names=z.namelist()
  for entry in (
    "MK4S_CASING_UNAPPROVED.gcode","REAL_WORLD_OPERATOR_RUNBOOK.md",
    "GCODE_AUDIT.json","PRINTER_STAGE_DRYRUN.json",
    "VIRTUAL_CONTROLLER_ADVERSARIAL_AUDIT.json",
    "AGENT_GUIDE_INDEPENDENT_AUDIT.json",
    "CASE_ASSEMBLED.solidcraft","HS_Casing_Base.stl","HS_Casing_Lid.stl",
    "partcad/casing_assembled.assy",
  ):
   if entry not in names:raise ValueError("missing in archive: "+entry)
 print(json.dumps({
  "live_agent_model_steps_written":audited["steps_checked"],
  "gcode_bytes":gcode["bytes"],"actual_prusaslicer_profile":"MK4S 0.4 Prusament PLA",
  "real_slicer_executed":True,
  "virtual_controller_mutants_detected":controls["mutants_detected"],
  "physical_start_denied":staging["start_without_human_grant_rejected"],
  "file_count":len(names),
  "archive":str(archive),"archive_size":archive.stat().st_size,
  "real_print_authorized":False,"motor_wiring_authorized":False},indent=2))
 return 0
if __name__=="__main__":raise SystemExit(main())
