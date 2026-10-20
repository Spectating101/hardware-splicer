"""Check actual captured slicer output, not toy G-code-success flags."""
from __future__ import annotations
import json,zipfile
from pathlib import Path
from copy import deepcopy
import pytest
from hardware_splicer.realization_gcode_audit import audit_offline_gcode
from hardware_splicer.realization_runbook import verify_agent_realization_guide,render_realization_runbook
from hardware_splicer.realization_printer_dryrun import simulate_staging_and_denied_start

ROOT=Path(__file__).resolve().parents[1]
BUNDLE=ROOT/"examples/realization_pilot/HS_FABRICATOR_END_TO_END_CONDITIONAL_20261020.zip"

@pytest.fixture(scope="module")
def archive():
 with zipfile.ZipFile(BUNDLE) as zip:
  return {name:zip.read(name) for name in (
   "MK4S_CASING_UNAPPROVED.gcode","GCODE_AUDIT.json",
   "PRINTER_STAGE_DRYRUN.json","VIRTUAL_CONTROLLER_ADVERSARIAL_AUDIT.json",
   "AGENT_REALIZATION_GUIDE.json","AGENT_GUIDE_INDEPENDENT_AUDIT.json",
   "REALIZATION_MANIFEST.json","REAL_WORLD_OPERATOR_RUNBOOK.md"
  )}

@pytest.fixture
def real_gcode(tmp_path,archive):
 p=tmp_path/"captured_20261020.gcode"
 p.write_bytes(archive["MK4S_CASING_UNAPPROVED.gcode"])
 return p

def test_actual_gcode_matches_published_provenance(real_gcode,archive):
 report=audit_offline_gcode(real_gcode)
 expected=json.loads(archive["GCODE_AUDIT.json"])
 manifest=json.loads(archive["REALIZATION_MANIFEST.json"])
 assert report==expected
 assert report["sha256"]==manifest["gcode_sha256"]
 assert report["layer_changes"]==175
 assert report["estimated_filament_grams"]==74.1
 assert report["object_bounding_boxes_mm"]["HS_Casing_Base"]==[19,67.5,119,142.5]
 assert report["object_bounding_boxes_mm"]["HS_Casing_Lid"]==[131,67.5,231,142.5]
 assert report["vendor_purge_path_review_required"]
 assert report["real_print_authorized"] is False

def test_actual_print_job_denied_without_human_approval(real_gcode,archive):
 receipt=simulate_staging_and_denied_start(real_gcode)
 logged=json.loads(archive["PRINTER_STAGE_DRYRUN.json"])
 assert receipt["gcode_sha256"]==logged["gcode_sha256"]
 assert receipt["start_without_human_grant_rejected"]
 assert not receipt["real_printer_or_octoprint_contacted"]
 assert len(receipt["transport_receipts"])==1
 assert receipt["transport_receipts"][0]["print"]=="false"

@pytest.mark.parametrize("find,repl,error",[
 ("; printer_model = MK4S","; printer_model = Unknown","printer"),
 ("; nozzle_diameter = 0.4","; nozzle_diameter = 1.0","nozzle"),
 ("; filament_type = PLA","; filament_type = ABS","filament"),
 ("; objects_info = ","; corrupted_objects_info = ","object metadata"),
])
def test_tampering_actual_sliced_job_detected(real_gcode,find,repl,error):
 data=real_gcode.read_text()
 assert find in data
 real_gcode.write_text(data.replace(find,repl,1))
 with pytest.raises(ValueError,match=error):
  audit_offline_gcode(real_gcode)

def test_dangerous_control_command_rejected(real_gcode):
 with real_gcode.open("a") as out:
  out.write("\nM500 ; unauthorized EEPROM write\n")
 with pytest.raises(ValueError,match="disallowed"):
  audit_offline_gcode(real_gcode)

def test_print_at_bed_edge_rejected(real_gcode):
 data=real_gcode.read_text()
 old='"polygon":[[119.000,142.500],[19.000,142.500],[19.000,67.500],[119.000,67.500]]'
 assert old in data
 new='"polygon":[[100.000,142.500],[0.000,142.500],[0.000,67.500],[100.000,67.500]]'
 real_gcode.write_text(data.replace(old,new,1))
 with pytest.raises(ValueError,match="footprint"):
  audit_offline_gcode(real_gcode)

def test_live_model_instructions_independently_checked(archive):
 guide=json.loads(archive["AGENT_REALIZATION_GUIDE.json"])
 audit=verify_agent_realization_guide(
  guide,
  json.loads(archive["GCODE_AUDIT.json"]),
  json.loads(archive["PRINTER_STAGE_DRYRUN.json"]),
  json.loads(archive["VIRTUAL_CONTROLLER_ADVERSARIAL_AUDIT.json"]),
 )
 assert audit["conditional_instructions_accepted"]
 assert audit["steps_checked"]==30
 assert "Original Prusa MK4S" in render_realization_runbook(guide,json.loads(archive["GCODE_AUDIT.json"]),audit)

@pytest.mark.parametrize("corruption",["release","stop_gate","status"])
def test_bad_model_runbook_fails_independent_authority_check(archive,corruption):
 guide=deepcopy(json.loads(archive["AGENT_REALIZATION_GUIDE.json"]))
 if corruption=="release":guide["release_authorized"]=True
 if corruption=="stop_gate":guide["electrical_reality_path"][2]["stop_if"]=""
 if corruption=="status":guide["model_deployment_status"]="READY_TO_PRINT"
 audit=verify_agent_realization_guide(
  guide,json.loads(archive["GCODE_AUDIT.json"]),
  json.loads(archive["PRINTER_STAGE_DRYRUN.json"]),
  json.loads(archive["VIRTUAL_CONTROLLER_ADVERSARIAL_AUDIT.json"]),
 )
 assert not audit["conditional_instructions_accepted"]
 assert audit["violations"]

def test_zip_contains_all_major_handoff_outputs():
 with zipfile.ZipFile(BUNDLE) as z:
  names=set(z.namelist())
  assert {"REAL_WORLD_OPERATOR_RUNBOOK.md",
          "MK4S_CASING_UNAPPROVED.gcode",
          "CASE_ASSEMBLED.solidcraft",
          "CASE_PRINT_LAYOUT.3mf",
          "HS_Casing_Base.stl",
          "HS_Casing_Lid.stl",
          "partcad/PartCAD_Casing_Assembly.step",
          "PRINTER_STAGE_DRYRUN.json",
          "VIRTUAL_CONTROLLER_ADVERSARIAL_AUDIT.json"}.issubset(names)

def test_agent_receives_real_fabrication_receipt_but_never_real_print():
 from hardware_splicer.engineering_reasoning_agent import _tools
 scenario={"intake":{"goal":"Realize the barcode feeder"}}
 a=_tools("inspect_fabrication_package",{},scenario)
 assert a["software_fabrication_package_exists"]
 assert a["slicer"].startswith("PrusaSlicer")
 assert a["layer_count"]==175
 assert a["tested_mock_printer_without_start"]
 assert a["real_donor_parts_owned"] is False
 assert a["physical_printer_present"] is False
 assert a["machine_ready_for_physical_power"] is False

def test_real_live_agent_again_inspected_actual_fabrication_data():
 with zipfile.ZipFile(BUNDLE) as z:
  trace=json.loads(z.read('CODEX_LIVE_FABRICATOR_TOOL_LOOP.json'))
  manifest=json.loads(z.read('REALIZATION_MANIFEST.json'))
  gcode=json.loads(z.read('GCODE_AUDIT.json'))
 assert trace['status']=='MODEL_FINISHED'
 assert not trace['model_is_test_double']
 assert [x['model_action'] for x in trace['steps']]==[
   'inspect_fabrication_package','audit_candidate','finish'
 ]
 seen=trace['steps'][0]['tool_output']
 assert seen['source_gcode_sha256']==gcode['sha256']
 assert seen['layer_count']==175
 assert seen['tested_mock_printer_without_start']
 assert seen['out_of_nominal_bed_purge_moves']>0
 assert seen['physical_printer_present'] is False
 assert trace['steps'][1]['tool_output']['independent_evidence_audit']['passes_independent_evidence_integrity']
 assert trace['independent_engineering_assessment']['unsafe_model_physical_claims']==[]
 assert not trace['physical_release']
 assert manifest['second_live_agent_physical_safety_audit_passed']
