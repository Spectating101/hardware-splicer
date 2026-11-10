"""Freeze the actual native-slicer receipts and sensitivity-based function ranking.

The original G-code is deliberately kept locally and not released for
unknown physical printers. Public reports retain the original executable
SHA256, actual G-code output SHA256 and every source/toolchain setting.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from hardware_splicer.function_print_slicer import audit_slicer_report
from hardware_splicer.function_print_feedback import interpret_feedback,audit_feedback

HERE=Path(__file__).resolve().parent

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--native-gcode-dir",type=Path,required=True)
    p.add_argument("--out",type=Path,default=HERE/"slicer_results")
    args=p.parse_args()
    if args.out.exists():
        raise SystemExit("Refuse overwrite: native slicer receipts are frozen")
    source=json.loads((HERE/"design_request.json").read_text())
    profile=json.loads((HERE/"slicer_profile.json").read_text())
    policy=json.loads((HERE/"feedback_policy.json").read_text())
    cad=json.loads((HERE/"generated/FUNCTION_GEOMETRY_EVALUATION.json").read_text())
    sliced=json.loads((args.native_gcode_dir/"SLICER_COMPARISON.json").read_text())
    sliced_audit=audit_slicer_report(source,profile,cad_dir=HERE/"generated",
                                     out=args.native_gcode_dir,require_gcode=True)
    feedback=interpret_feedback(source,profile,policy,sliced,cad)
    feedback_audit=audit_feedback(source,profile,policy,sliced,cad,feedback)
    args.out.mkdir(parents=True)
    for filename,obj in (
        ("SLICER_COMPARISON.json",sliced),
        ("NATIVE_SLICER_AUDIT.json",sliced_audit),
        ("MASS_FEEDBACK.json",feedback),
        ("FEEDBACK_AUDIT.json",feedback_audit),
    ):
        (args.out/filename).write_text(json.dumps(obj,indent=2,sort_keys=True)+"\n")
    print(json.dumps({
        "native_slicer_calls":sliced_audit["actual_native_slice_count"],
        "slicer_estimated_nominal":feedback_audit["selected_nominal"],
        "slicer_estimated_guarded":feedback_audit["selected_guarded"],
        "physical_printer_release":feedback_audit["physical_authority"],
        "Gcode_files_kept_outside_repository":True,
    },indent=2))
if __name__=="__main__":
    main()
