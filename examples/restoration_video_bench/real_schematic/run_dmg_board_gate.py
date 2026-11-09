"""Correct one previous real KiCad model answer that prescribed pin tests
before the actual target board revision was physically confirmed.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from hardware_splicer.restoration_board_action_correction import correct_board_pin_action
from hardware_splicer.restoration_schematic_grounding import (
    build_case_context, build_reference_tool_result
)

HERE=Path(__file__).resolve().parent
FROZEN=HERE/"real_dmg_kicad_model_ab.json"

def run(source_checkout:Path|None=None):
    original=json.loads(FROZEN.read_text())
    model=original["arms"]["hs_real_kicad"]
    reference=build_reference_tool_result(
        reported_board_revision="DMG-CPU-06",
        source_checkout=source_checkout,
    )
    context=build_case_context(reported_board_revision="DMG-CPU-06",tool_reference=reference)
    return correct_board_pin_action(
        context,model,model="gemini-3.8-flash-low",timeout_s=75
    )

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source-checkout",type=Path)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    if args.out.exists():
        raise SystemExit("Refusing silent reroll/overwrite of prior model correction")
    report=run(source_checkout=args.source_checkout)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    receipt=report["correction"]
    print(json.dumps({
        "prior_unverified_pin_actions":[x["pin_reference"] for x in report["original_unverified_pin_tests"]],
        "corrected_status":receipt["status"],
        "corrected_safe_next_check":receipt["plan"]["next_safe_check"] if receipt.get("plan") else None,
        "elapsed_seconds":receipt["elapsed_seconds"],
        "source_unchanged":report["source_evidence_unchanged"],
        "physical_action_authorized":report["physical_test_or_repair_authorized"],
    },indent=2))
if __name__=="__main__":main()
