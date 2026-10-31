#!/usr/bin/env python3
"""Independent native-KiCad re-execution and Atlas capability export.

Executes the *existing* SPI flash adapter verifier on a fresh copy of the
canonical design, checks real KiCad 9 reports and source digests, and publishes
portable software-only evidence. Does not grant fabrication or power authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
DESIGN=ROOT/"hardware/reference_designs/spi_flash_adapter_v1"
RECEIPT_FILES={
  "schematic":"spi_flash_adapter_v1.kicad_sch",
  "pcb":"spi_flash_adapter_v1.kicad_pcb",
  "project_rules":"spi_flash_adapter_v1.kicad_pro",
  "symbol_library":"HardwareSplicer.kicad_sym",
  "symbol_library_table":"sym-lib-table",
  "bom":"BOM.csv",
  "design_manifest":"design_manifest.json",
  "verifier":"verify_design.py",
  "electrical_contract":"design_checks.py",
}

def require(condition:bool, reason:str)->None:
    if not condition:
        raise ValueError("Native SPI acceptance refused: "+reason)

def sha(data:bytes)->str:
    return hashlib.sha256(data).hexdigest()

def as_json(path:Path)->dict[str,Any]:
    obj=json.loads(path.read_text())
    require(isinstance(obj,dict),"non-object JSON "+str(path))
    return obj

def verify_native_reports(
    receipt:dict, manifest:dict, erc:dict, drc:dict,
    source_digests:dict[str,str],
)->None:
    """Reject corrupted native evidence and forged release-readiness assertions."""
    require(receipt.get("schema_version")=="hardware_splicer.reference_design_verification.v2",
            "unknown engineering receipt")
    require(receipt.get("result")=="pass","native verifier did not pass")
    require(receipt.get("design_id")==manifest.get("design_id")=="spi-flash-adapter-v1",
            "wrong design identity")
    require(manifest.get("result_status")=="bounded_pre_fabrication_result",
            "pre-fabrication status drift")
    require(manifest.get("acceptance",{}).get("kicad_erc_required") is True
            and manifest["acceptance"].get("kicad_drc_required") is True
            and manifest["acceptance"].get("schematic_pcb_parity_required") is True,
            "native verification requirements disabled")
    require(receipt.get("artifact_sha256")==source_digests,
            "canonical schematic/board/BOM/source digests do not match native verification")
    claimed=receipt.get("checks",{})
    expected={"erc_errors","erc_warnings","drc_actionable_violations","unconnected_pads",
              "footprint_errors","schematic_parity_issues","required_topology_issues",
              "bom_parity_issues","board_identity_issues","assembly_variant_issues",
              "ground_reference_issues"}
    require(set(claimed)==expected and all(type(v) is int and v==0 for v in claimed.values()),
            "unknown or nonzero engineering checks")
    require(erc.get("$schema")=="https://schemas.kicad.org/erc.v1.json"
            and erc.get("source")=="spi_flash_adapter_v1.kicad_sch",
            "ERC report not from expected native schematic")
    sheets=erc.get("sheets")
    require(isinstance(sheets,list) and len(sheets)==1 and sheets[0].get("violations")==[],
            "native ERC contains violations")
    require(drc.get("$schema")=="https://schemas.kicad.org/drc.v1.json"
            and drc.get("source")=="spi_flash_adapter_v1.kicad_pcb",
            "DRC report not from expected native PCB")
    require(all(isinstance(drc.get(k),list) and not drc[k]
                for k in ("unconnected_items","schematic_parity")),
            "native DRC has unconnected nets or schematic parity issues")
    actual_drc=drc.get("violations")
    require(isinstance(actual_drc,list),"native DRC violations array missing")
    advisories=receipt.get("advisories",{})
    require(isinstance(advisories.get("reviewed_nonpad_library_differences"),list),
            "native footprint advisory record missing")
    require(len(actual_drc)==advisories.get("library_revision_mismatch_warnings"),
            "native DRC finding count diverges from reviewed advisory count")
    require(all(row.get("type")=="lib_footprint_mismatch" and row.get("severity")=="warning"
                for row in actual_drc),"unexpected KiCad DRC warning type")
    require(str(receipt.get("toolchain",{}).get("kicad_cli","")).startswith("9."),
            "native KiCad 9 required for this frozen case")
    authority=receipt.get("authority")
    require(authority==manifest.get("authority")
            and authority.get("modeled_evidence_only") is True
            and authority.get("fabrication_ready") is False
            and authority.get("human_ee_review_complete") is False
            and authority.get("power_on_ready") is False
            and authority.get("physical_correctness")=="UNPROVEN"
            and authority.get("physical_authority_granted") is False,
            "physical authority falsely promoted")
    require(receipt.get("board_inventory",{}).get("footprints_total")==40
            and receipt["board_inventory"].get("mounting_holes")==4
            and receipt["board_inventory"].get("testpoints")==18,
            "board assembly differs from reviewed native reference")

def execute(out:Path)->dict:
    out=out.resolve()
    require(not out.exists() or (out.is_dir() and not any(out.iterdir())),
            "output folder must be empty")
    original=as_json(DESIGN/"verification.json")
    manifest=as_json(DESIGN/"design_manifest.json")
    source_digests={key:sha((DESIGN/name).read_bytes())
                    for key,name in RECEIPT_FILES.items()}
    require(original.get("artifact_sha256")==source_digests,
            "checked-in reference design hashes do not match repository files")
    require(original.get("authority")==manifest.get("authority"),
            "checked-in reference has authority conflict")
    with tempfile.TemporaryDirectory(prefix="hs-spi-native-") as folder:
        design=Path(folder)/"spi_flash_adapter_v1"
        shutil.copytree(DESIGN,design)
        reports=Path(folder)/"real-kicad-reports"
        reports.mkdir()
        run=subprocess.run([sys.executable,str(design/"verify_design.py"),
                            "--report-dir",str(reports)],
                            cwd=design,capture_output=True,text=True,
                            check=False,timeout=240)
        if run.returncode != 0:
            raise ValueError("Native verifier failed (no acceptance): "+
                             (run.stderr+run.stdout)[-4500:])
        native_receipt=as_json(design/"verification.json")
        erc=as_json(reports/"erc.json")
        drc=as_json(reports/"drc.json")
        verify_native_reports(native_receipt,manifest,erc,drc,source_digests)
        require("0 violations" in (reports/"erc.stdout.txt").read_text(),
                "KiCad ERC stdout does not confirm zero violations")
        require("0 unconnected items" in (reports/"drc.stdout.txt").read_text()
                and "0 schematic parity issues" in (reports/"drc.stdout.txt").read_text(),
                "KiCad DRC stdout does not confirm parity")
        out.mkdir(parents=True,exist_ok=True)
        evidence_names=["erc.json","drc.json","erc.stdout.txt","drc.stdout.txt","netlist.xml"]
        for name in evidence_names:
            shutil.copyfile(reports/name,out/name)
        (out/"native-verification.json").write_text(
            json.dumps(native_receipt,sort_keys=True,indent=2)+"\n"
        )
    evidence={
       "schema_version":"hardware_splicer.native_eda_acceptance.v1",
       "capability_id":"hs.spi_flash_adapter_v1.native_kicad_eda",
       "native_eda_executed":True,
       "design_id":"spi-flash-adapter-v1",
       "toolchain":native_receipt["toolchain"],
       "checked_design_sha256":source_digests,
       "verified_native_erc":True,
       "verified_native_drc":True,
       "verified_schematic_pcb_parity":True,
       "verified_bom_identity":True,
       "native_report_sha256":{name:sha((out/name).read_bytes())
                               for name in evidence_names+["native-verification.json"]},
       "simulation_bench_measurement":False,
       "physical_build_tested":False,
       "fabrication_authorized":False,
       "power_on_authorized":False,
       "limitations":manifest["remaining_blockers"],
       "release_level":"MODELED_PRE_FAB_ONLY",
    }
    (out/"NATIVE_EDA_ACCEPTANCE.json").write_text(
        json.dumps(evidence,sort_keys=True,indent=2)+"\n"
    )
    atlas={
      "schema_version":"hardware_splicer.external_capability.v1",
      "capability_id":evidence["capability_id"],
      "input_requirements":{
          "source":"hardware/reference_designs/spi_flash_adapter_v1",
          "baseline_design":"3V3 host to 1V8 SPI flash adapter",
          "design_manifest_sha256":source_digests["design_manifest"],
          "selected_manufacturer_part_numbers":manifest["selected_components"],
      },
      "supported_domains":{
          "electrical":"native_KiCad_9_schematic_ERC_and_netlist",
          "pcb":"native_KiCad_9_routed_board_DRC_and_schematic_parity",
          "bom":"netlist_part_number_assembly_and_footprint_verified",
          "signal_integrity":"modeled_partial_timing_budget_only",
          "mechanical":"board_outline_and_mounting_geometry_only",
          "embedded_firmware":"not_implemented_for_this_design",
          "physical":"UNPROVEN",
      },
      "artifact_types":[
         "kicad_sch","kicad_pcb","kicad_pro","bom_csv",
         "kicad_erc_json","kicad_drc_json","kicad_netlist_xml","sha256_receipt",
      ],
      "verified_native_toolchain":native_receipt["toolchain"],
      "verification":{
         "source_design_sha256":source_digests,
         "native_eda_acceptance_sha256":sha((out/"NATIVE_EDA_ACCEPTANCE.json").read_bytes()),
         "status":"PASS_NATIVE_MODELED_EVIDENCE",
      },
      "reproduction_commands":[
         "sudo apt-get install kicad python3-pcbnew",
         "cd hardware/reference_designs/spi_flash_adapter_v1 && /usr/bin/python3 verify_design.py",
         "/usr/bin/python3 scripts/verify_native_spi_capability.py --out <fresh-artifact-directory>",
      ],
      "limitations":manifest["remaining_blockers"],
      "hardware_authority":{"fabrication":False,"power_on":False,"physical_performance_claim":False},
      "atlas_runtime_required":False,
    }
    (out/"ATLAS_NATIVE_ELECTRONICS_CAPABILITY.json").write_text(
       json.dumps(atlas,sort_keys=True,indent=2)+"\n"
    )
    return evidence

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(execute(args.out),sort_keys=True,indent=2))
