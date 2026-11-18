#!/usr/bin/env python3
"""Recover a bounded native DRC on a *copy* of a legacy zone-filled PCB.

KiCad 9 may hang checking old filled zones. Unfill/rebuild in a temporary
copy, independently compare every non-zone copper feature, then run full
native KiCad DRC. Never grant original-PCB or physical/fabrication authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from hardware_splicer.keyboard_splice_zone_drc import (
    verify_original_copper_unchanged,classify_native_drc
)


def call(command:list[str], *, timeout: int) -> str:
    try:
        process=subprocess.run(command,check=False,capture_output=True,
                               text=True,timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise ValueError("native evidence process timed out: "+str(command[:3])) from exc
    if process.returncode:
        raise ValueError("native evidence step failed: "+
                         str(process.returncode)+" "+(process.stderr or process.stdout)[-800:])
    return process.stdout


def run(source:Path, destination:Path, expected_sha:str, system_python:str,
        kicad_cli:str="kicad-cli")->dict:
    if not source.is_file() or len(expected_sha)!=64:
        raise ValueError("missing exact original and SHA256")
    if hashlib.sha256(source.read_bytes()).hexdigest()!=expected_sha:
        raise ValueError("original-source SHA256 mismatch")
    if destination.exists():
        raise ValueError("evidence destination must be new")
    helper=ROOT/"src/hardware_splicer/_pcbnew_helpers/keyboard_splice_legacy_refill.py"
    extract=ROOT/"src/hardware_splicer/_pcbnew_helpers/keyboard_splice_extract.py"
    with tempfile.TemporaryDirectory(prefix="hs-kicad-legacy-refill-") as dirname:
        temp=Path(dirname)
        converted=temp/"converted_refilled_copy.kicad_pcb"
        receipt=temp/"conversion_receipt.json"
        call([system_python,str(helper),"--original",str(source.resolve()),
              "--converted",str(converted),"--receipt",str(receipt),
              "--expected-sha256",expected_sha],timeout=50)
        raw_receipt=json.loads(receipt.read_text(encoding="utf-8"))
        source_data=json.loads(call(
            [system_python,str(extract),"--pcb",str(source.resolve())],
            timeout=55))
        changed_data=json.loads(call(
            [system_python,str(extract),"--pcb",str(converted.resolve())],
            timeout=55))
        preservation=verify_original_copper_unchanged(source_data,changed_data)
        if raw_receipt["original_source_sha256"]!=preservation["original_source_sha256"]:
            raise ValueError("converter changed original board reference")
        if raw_receipt["converted_copy_sha256"]!=preservation["converted_copy_sha256"]:
            raise ValueError("converter changed converted copy after receipt")
        native_report=temp/"native_source_copy_drc.json"
        call([kicad_cli,"pcb","drc","--severity-all","--format","json",
              "--output",str(native_report),str(converted)],timeout=45)
        actual=json.loads(native_report.read_text(encoding="utf-8"))
        classified=classify_native_drc(actual)
        if not classified["drc_completed_with_no_errors_or_opens"]:
            raise ValueError("refilled board copy fails native KiCad error/unconnected requirements")
        source_netless=[name for name in raw_receipt["original_zone_source_net_names"] if not name]
        complete={
            "schema":"hs.legacy-kicad-zone-refilled-source-copy-check.v1",
            "source_original_sha256":expected_sha,
            "native_conversion":raw_receipt,
            "source_geometry_preservation":preservation,
            "native_copy_full_severity_drc":classified,
            "original_netchain_not_changed":True,
            "legacy_filled_zone_regeneration_required":True,
            "original_unconnected_zone_names":len(source_netless),
            "modified_source_file_checked_not_original_bytes":True,
            "upstream_original_copy_available_in_output":False,
            "native_drc_all_warnings_resolved":False,
            "original_firmware_powered":False,
            "physical_keyboard_tested":False,
            "fabrication_approved":False,
            "conclusion":"REFILLED_COPY_ZERO_DRC_ERRORS_BUT_WARNINGS_REMAIN",
        }
        complete["native_refilled_copy_drc_sha256"]=hashlib.sha256(
            native_report.read_bytes()).hexdigest()
        packed=json.dumps(complete,sort_keys=True,ensure_ascii=False,separators=(",",":"))
        complete["payload_sha256"]=hashlib.sha256(packed.encode()).hexdigest()
        destination.mkdir(parents=True)
        (destination/"LEGACY_ZONE_DRC_RECEIPT.json").write_text(
            json.dumps(complete,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
        )
        shutil.copyfile(native_report,destination/"NATIVE_REFILLED_COPY_DRC.json")
    return complete


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--pcb",type=Path,required=True)
    ap.add_argument("--expected-sha256",required=True)
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--system-python",default="/usr/bin/python3")
    args=ap.parse_args()
    result=run(args.pcb,args.out,args.expected_sha256,args.system_python)
    print("SOURCE_SHA256",result["source_original_sha256"])
    print("PRESERVED_PAD_TRACK_VIA_COUNTS",
          result["source_geometry_preservation"]["pad_contacts_preserved"],
          result["source_geometry_preservation"]["copper_tracks_preserved"],
          result["source_geometry_preservation"]["vias_preserved"])
    print("NATIVE_KICAD_ERRORS",
          result["native_copy_full_severity_drc"]["errors"],
          "WARNINGS",result["native_copy_full_severity_drc"]["warnings"],
          "UNCONNECTED",result["native_copy_full_severity_drc"]["unconnected_items"])
    print("PHYSICAL_FABRICATION_AUTHORIZED",False)


if __name__=="__main__":
    main()
