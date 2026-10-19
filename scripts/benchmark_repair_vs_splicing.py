"""Independent task-level evaluation of repair versus heterogeneous splicing.

Runs two existing fixture controls and two new unowned-marketplace stress cases.
This is a SOFT-only benchmark: KiCad output cannot prove physical success.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CASES = {
    "repair_fixture": ("--case", "robot_repair_cafe_s3"),
    "splice_fixture": ("--case", "printer_motion_stage"),
    "repair_unverified": ("--intake", "examples/dual_track/repair_ls2208_unverified.json"),
    "splice_unverified": ("--intake", "examples/dual_track/splice_four_marketplace_donors_unverified.json"),
}
MARKET_SOURCE_IDS = {
    "repair_unverified": ["ls2208"],
    "splice_unverified": ["ls2208", "epson-lq680", "qnap-ts219pii", "apple-a1314"],
}


def evaluate_one(case_id: str, result: dict, salvage: dict) -> dict:
    """Track mission fulfillment separately from existing compile and demo gates."""
    if case_id not in CASES:
        raise ValueError("unknown case")
    metrics = result["metrics"]
    plan = salvage["splice_plan"]
    blocks = plan.get("reusable_blocks") or []
    row = {
        "case_id": case_id,
        "reported_pipeline_pass": result["evaluation"].get("passed") is True,
        "carrier_drc_pass": metrics.get("drc_pass") is True,
        "build_id": metrics.get("build_id"),
        "salvage_verdict": plan.get("verdict"),
        "circuit_backed_donor_blocks": sum(
            b.get("source") == "circuit_functional_salvage" for b in blocks
        ),
        "physical_testing_done": False,
        "physical_assembly_done": False,
        "physical_authority_from_run": False,
        "native_mission_evaluation": metrics.get("engineering_mission_evaluation"),
    }
    if case_id in MARKET_SOURCE_IDS:
        row.update({
            "marketplace_listing_ids": MARKET_SOURCE_IDS[case_id],
            "physical_donors_in_custody": 0,
            "verified_components_from_listings": 0,
            "original_device_restored": False,
            "working_new_multi_donor_product": False,
            "mission_success": False,
            "pipeline_pass_is_not_mission_pass": result["evaluation"].get("passed") is True,
            "reason": (
                ("Original-function repair is appropriately blocked with a diagnostic evidence queue; no unrelated substitute circuit was generated."
                 if metrics.get("build_id") is None
                 else "Generated generic USB/UART adapter, NOT scanner fault isolation, original-function restoration, or verified repair.")
                if case_id == "repair_unverified"
                else "Marketplace-only donor claims have no physical module contracts, tested interfaces or completed functional product."
            ),
        })
    else:
        row["fixture_scope"] = "preconfigured donor/board fixture; no original-function repair or newly assembled multi-source machine"
        row["mission_success"] = None
    return row


def summarize(rows: list[dict]) -> dict:
    if {r["case_id"] for r in rows} != set(CASES) or len(rows) != len(CASES):
        raise ValueError("all four distinct cases are required")
    market = [r for r in rows if r["case_id"] in MARKET_SOURCE_IDS]
    fixture = [r for r in rows if r["case_id"] not in MARKET_SOURCE_IDS]
    return {
        "schema_version": "hardware_splicer.repair_vs_splicing_benchmark.v1",
        "date": "2026-10-20",
        "fixture_compiles_passed": sum(r["carrier_drc_pass"] for r in fixture),
        "market_compiles_passed": sum(r["carrier_drc_pass"] for r in market),
        "market_pipeline_reported_pass": sum(r["reported_pipeline_pass"] for r in market),
        "market_missions_proved": sum(r["mission_success"] for r in market),
        "market_native_mission_verdicts_blocked": sum(
            (r.get("native_mission_evaluation") or {}).get("mission_success") is False
            for r in market
        ),
        "tested_physical_devices": 0,
        "overall": "S2_CARRIER_COMPILER_WORKS; RESTORATIVE_REPAIR_AND_HETEROGENEOUS_SPLICING_NOT_YET_PROVED",
        "limitations": [
            "Fixtures are pre-established examples and are not evidence of field repair or a new assembled device",
            "Market source descriptions were deliberately inserted as hypothetical available_parts to stress the current planner; none is owned, proven functional or authorized for electrical use",
            "No equipment was bought, inspected, powered, flashed, fabricated or tested",
            "KiCad DRC only covers generated carrier boards and not the absent donor electronics",
            "Unmanifested splice_demo --intake evaluation uses result.ok, not acceptance of repair or novel product mission"
        ],
        "cases": rows,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("/tmp/hs-dual-gpt6-20261020"))
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--reuse-existing", action="store_true")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.update({"PYTHONPATH": str(ROOT / "src"), "QWEN_DISABLED":"1",
                "HARDWARE_SPLICER_QWEN_DISABLED":"1",
                "HARDWARE_SPLICER_OFFLINE_MODE":"1"})
    rows=[]
    for case_id, params in CASES.items():
        d=args.out/case_id
        if not args.reuse_existing:
            p = subprocess.run([sys.executable,"-m","scripts.splice_demo",*params,"--out",str(d.resolve())],
                               cwd=ROOT,env=env,capture_output=True,text=True,timeout=120)
            (args.out/f"{case_id}.log").write_text(p.stdout+p.stderr,encoding="utf-8")
            # A scoped mission correctly exits nonzero when the CAD compile
            # passes but original-function repair / new-product proof is absent.
            if p.returncode not in ({0, 1} if case_id in MARKET_SOURCE_IDS else {0}):
                raise RuntimeError(f"{case_id} could not execute; see {case_id}.log")
            if not (d / "SPLICE_DEMO_RESULT.json").is_file():
                raise RuntimeError(f"{case_id} produced no result; see {case_id}.log")
        result=json.loads((d/"SPLICE_DEMO_RESULT.json").read_text(encoding="utf-8"))
        salvage_path = d / "SPLICE_PLAN.json"
        # Repair-mode missions intentionally produce a diagnostic artifact,
        # not a generic fallback circuit or splice plan.
        salvage = (
            json.loads(salvage_path.read_text(encoding="utf-8"))
            if salvage_path.is_file()
            else {"splice_plan": {"verdict": "BLOCKED_REPAIR_DIAGNOSIS", "reusable_blocks": []}}
        )
        rows.append(evaluate_one(case_id,result,salvage))
    output=summarize(rows)
    summary=args.summary or args.out/"DUAL_TRACK_BENCHMARK_RESULT.json"
    summary.parent.mkdir(parents=True,exist_ok=True)
    summary.write_text(json.dumps(output,indent=2,ensure_ascii=False,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in output.items() if k in
        {"overall","fixture_compiles_passed","market_compiles_passed",
         "market_pipeline_reported_pass","market_missions_proved"}},indent=2))
    print("Summary:",summary)


if __name__ == "__main__":
    main()
