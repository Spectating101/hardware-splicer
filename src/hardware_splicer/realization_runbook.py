"""Validate model-authored build steps independently of model success flags."""
from __future__ import annotations
import json,re
from collections.abc import Mapping
from typing import Any
AREAS=("printer_reality_path","mechanical_reality_path","electrical_reality_path","firmware_reality_path")

def verify_agent_realization_guide(
 response:Mapping[str,Any],gcode:Mapping[str,Any],dryrun:Mapping[str,Any],controller:Mapping[str,Any]
)->dict:
 errors=[]
 if response.get("release_authorized") is not False:errors.append("physical_release_claimed")
 if response.get("model_deployment_status")!="BLOCKED_UNTIL_PHYSICAL_EVIDENCE":errors.append("status_untrue")
 count=0
 for name in AREAS:
  steps=response.get(name)
  if not isinstance(steps,list) or len(steps)<4:
   errors.append("missing_steps:"+name);continue
  count+=len(steps)
  for i,v in enumerate(steps):
   if not isinstance(v,Mapping) or v.get("step")!=i+1:
    errors.append("step_index_invalid:"+name);continue
   for key in ("action","required_evidence","stop_if"):
    if not isinstance(v.get(key),str) or not v[key].strip():
     errors.append("step_gate_missing:"+name)
 if not gcode.get("model_footprints_have_at_least_4mm_bed_margin"):errors.append("print_margin_missing")
 if not gcode.get("vendor_purge_path_review_required"):errors.append("unexpected_unacknowledged_purge")
 if not (dryrun.get("start_without_human_grant_rejected") and not dryrun.get("real_printer_or_octoprint_contacted")):
  errors.append("printer_permission_bypassed")
 if controller.get("physical_controller_release")!="BLOCKED":errors.append("controller_safety_claim")
 blockers=json.dumps(response.get("blocking_missing_parts",[])).lower()
 if not all(token in blockers for token in ("printer","donor","stop")):
  errors.append("missing_hardware_blockers")
 electric=json.dumps(response.get("electrical_reality_path",[])).lower()
 if any(re.search(p,electric) for p in (r'\bgpio\s*\d+',r'\bpin\s*\d+\s*(?:to|->)\s*\bpin\s*\d+')):
  errors.append("unsupported_specific_pinout")
 return {"schema_version":"hs.independent_realization_guide_audit.v1",
         "conditional_instructions_accepted":not errors,
         "violations":errors,"steps_checked":count,
         "real_printer_present":False,"salvaged_parts_measured":False,
         "real_assembly_or_print_authorized":False}

def render_realization_runbook(response:Mapping[str,Any],gcode:Mapping[str,Any],audit:Mapping[str,Any])->str:
 if not audit.get("conditional_instructions_accepted"):raise ValueError("independent guide rejected")
 lines=[
  "# Hardware Splicer: From digital design to reality",
  "",
  "**This is an operator handoff, not a released machine. Physical printer, donor acquisition, electrical connections and tests remain BLOCKED.**",
  "",
  "## Actual tested fabrication profile",
  "",
  "- Test printer choice: Original Prusa MK4S, 0.4 mm nozzle. NOT detected on Optiplex.",
  "- Genuine PrusaSlicer 2.9.2, manufacturer PrusaResearch.ini derived 0.20 mm structural profile and Prusament PLA settings.",
  "- Actual SolidCraft editable case model, separate base/lid STL, 3MF and PartCAD two-part BOM enclosed.",
  "- Offline G-code: MK4S_CASING_UNAPPROVED.gcode. It is not approved for a physical machine.",
  "- Estimated time: "+str(gcode["estimated_print_time"])+", PLA: "+str(gcode["estimated_filament_grams"])+" g, layers: "+str(gcode["layer_changes"])+".",
  "- Real G-code contains start purge near Y = -4 mm, beyond nominal bed rectangle. Explicitly verify this is intended and supported by the chosen actual printer before using the file.",
  "- No observed power supply, motor, scanner harness or independent emergency stop. Do not guess any pinout or wire colors.",
  "",
  "## Agent's engineering feasibility assessment",
  "",str(response["feasibility_summary"]),""
 ]
 labels={
  "printer_reality_path":"Print the actual casing with a verified machine",
  "mechanical_reality_path":"Mechanical assembly and fit validation",
  "electrical_reality_path":"Connect and commission real hardware only after evidence",
  "firmware_reality_path":"Scanner and motion firmware validation",
 }
 for key in AREAS:
  lines+=["## "+labels[key],""]
  for v in response[key]:
   lines+=["### "+str(v["step"])+". "+v["action"],"",
           "REQUIRED EVIDENCE: "+v["required_evidence"],"",
           "STOP IF: "+v["stop_if"],""]
 lines+=["## Unresolved components and safety gates",""]
 for s in response["blocking_missing_parts"]:
  lines+=["- "+str(s)]
 lines+=["","## What passed vs what did not","",
   "Passed: source-linked native CAD; two closed STL meshes; two-part 3MF; actual PartCAD BOM; native PrusaSlicer G-code; independent footprint, printer profile and thermal command scan.",
   "",
   "Passed in fake transport only: stage exact G-code with print=false; unapproved print-start is denied.",
   "",
   "Passed virtually only: motion/barcode simulation adversarial suite. Physical motion, scan identity and independent hardware stop remain unverified.",
   "",
   "NOT DONE: physical printing, test-fitting to real donors, electrical wiring, firmware flash, energized motion, independent stop trial or validation of any actual recycled machine.",
   ""]
 return "\n".join(lines)
