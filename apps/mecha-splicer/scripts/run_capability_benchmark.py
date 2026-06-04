#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Dict, List


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _benchmark_specs() -> List[Dict[str, Any]]:
    specs: List[Dict[str, Any]] = []

    for i in range(1, 7):
        specs.append(
            {
                "id": f"enc_{i:02d}",
                "segment": "enclosure",
                "spec": {
                    "project_name": f"bench_enclosure_{i}",
                    "simulation_fidelity": "high",
                    "electronics": {
                        "device": f"ctrl_box_{i}",
                        "pcb_w_mm": 40 + i * 6,
                        "pcb_h_mm": 28 + i * 4,
                        "pcb_t_mm": 1.6,
                        "mounts": [
                            {"x_mm": 4, "y_mm": 4, "d_mm": 2.4},
                            {"x_mm": 30, "y_mm": 4, "d_mm": 2.4},
                        ],
                        "ports": [
                            {
                                "kind": "rect",
                                "face": "front",
                                "label": "usb",
                                "rect": {"x_mm": 8, "y_mm": 0, "w_mm": 12, "h_mm": 5},
                            }
                        ],
                    },
                },
            }
        )

    for i in range(1, 7):
        specs.append(
            {
                "id": f"axis_{i:02d}",
                "segment": "linear_axis",
                "spec": {
                    "project_name": f"bench_axis_{i}",
                    "simulation_fidelity": "high",
                    "linear_axis": {
                        "travel_mm": 120 + i * 25,
                        "rod_length_mm": 220 + i * 30,
                        "rod_d_mm": 8,
                        "rod_spacing_mm": 40,
                        "payload_n": 6 + i * 2,
                        "target_speed_mm_s": 60 + i * 15,
                        "target_accel_mm_s2": 400 + i * 80,
                        "pulley_teeth": 20,
                    },
                },
            }
        )

    for i in range(1, 7):
        specs.append(
            {
                "id": f"pt_{i:02d}",
                "segment": "pan_tilt",
                "spec": {
                    "project_name": f"bench_pt_{i}",
                    "simulation_fidelity": "high",
                    "pan_tilt": {
                        "pan_servo": "mg996r" if i >= 4 else "sg90",
                        "tilt_servo": "mg996r" if i >= 4 else "sg90",
                        "max_payload_n": 2 + i,
                        "payload_offset_mm": 30 + i * 5,
                    },
                },
            }
        )

    for i in range(1, 7):
        specs.append(
            {
                "id": f"mix_{i:02d}",
                "segment": "mixed_system",
                "spec": {
                    "project_name": f"bench_mix_{i}",
                    "simulation_fidelity": "high",
                    "auto_compose": True,
                    "system_goal": {
                        "application": "quadruped" if i % 2 == 0 else "mobile_robot",
                        "payload_kg": 0.5 + 0.2 * i,
                        "target_speed_m_s": 0.15 + i * 0.03,
                        "environment": "outdoor" if i >= 4 else "indoor",
                    },
                },
            }
        )

    return specs


def _severity_counts(rows: List[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {"info": 0, "warn": 0, "block": 0}
    for row in rows:
        sev = str(row.get("severity", "info")).lower()
        if sev not in counts:
            counts[sev] = 0
        counts[sev] += 1
    return counts


def _extract_reasons(bundle: Dict[str, Any]) -> List[str]:
    reasons: List[str] = []
    for src in ("dfm", "simulation", "safety"):
        for it in bundle.get(src) or []:
            sev = str(it.get("severity", "")).lower()
            if sev in {"block", "warn"}:
                reasons.append(f"{src}:{sev}:{it.get('message')}")
    return reasons[:8]


def main() -> int:
    ap = argparse.ArgumentParser(description="Run Mecha-Splicer capability benchmark pack.")
    ap.add_argument("--out", default="dist_ready_for_sale/capability_benchmark_latest", help="Output directory for benchmark artifacts")
    ap.add_argument("--simulation-fidelity", choices=["starter", "high"], default="high")
    ap.add_argument("--limit", type=int, default=0, help="Optional limit for quick runs")
    args = ap.parse_args()

    import sys

    repo = _repo_root()
    sys.path.insert(0, str(repo))
    from src.mecha_splicer.runner import run  # type: ignore

    out_dir = repo / args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    specs = _benchmark_specs()
    if args.limit and args.limit > 0:
        specs = specs[: args.limit]

    rows: List[Dict[str, Any]] = []
    for idx, item in enumerate(specs, start=1):
        case_id = item["id"]
        case_out = out_dir / "cases" / case_id
        bundle = run(item["spec"], out_dir=case_out, simulation_fidelity=args.simulation_fidelity)

        blockers = bool(bundle.get("blockers"))
        sim_block = any(str(s.get("severity", "")).lower() == "block" for s in (bundle.get("simulation") or []))
        status = "pass" if not blockers and not sim_block else "fail"

        reasons = _extract_reasons(bundle)
        row = {
            "id": case_id,
            "segment": item["segment"],
            "status": status,
            "outputs": len(bundle.get("outputs") or []),
            "dfm_count": len(bundle.get("dfm") or []),
            "sim_count": len(bundle.get("simulation") or []),
            "warn_or_block_reasons": " || ".join(reasons),
        }
        rows.append(row)
        print(f"[{idx}/{len(specs)}] {case_id}: {status}")

    json_path = out_dir / "benchmark_results.json"
    csv_path = out_dir / "benchmark_results.csv"
    md_path = out_dir / "BENCHMARK_REPORT.md"

    json_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["id", "segment", "status", "outputs", "dfm_count", "sim_count", "warn_or_block_reasons"])
        w.writeheader()
        for row in rows:
            w.writerow(row)

    total = len(rows)
    passed = sum(1 for r in rows if r["status"] == "pass")
    failed = total - passed

    sim_all: List[Dict[str, Any]] = []
    for item in specs:
        bundle_path = out_dir / "cases" / item["id"] / "mecha_splicer.bundle.json"
        if bundle_path.exists():
            bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
            sim_all.extend(bundle.get("simulation") or [])

    sev = _severity_counts(sim_all)
    md = []
    md.append("# Capability Benchmark Report\n")
    md.append(f"- Cases: {total}")
    md.append(f"- Passed: {passed}")
    md.append(f"- Failed: {failed}")
    md.append(f"- Pass rate: {(passed / total * 100.0) if total else 0.0:.1f}%")
    md.append(f"- Simulation severities: info={sev.get('info',0)}, warn={sev.get('warn',0)}, block={sev.get('block',0)}")
    md.append("")
    md.append("## Top Fail Reasons")
    fail_rows = [r for r in rows if r["status"] == "fail"]
    if not fail_rows:
        md.append("- No failed cases.")
    else:
        for r in fail_rows[:10]:
            md.append(f"- `{r['id']}`: {r['warn_or_block_reasons'] or 'n/a'}")
    md.append("")
    md_path.write_text("\n".join(md), encoding="utf-8")

    print(f"Benchmark complete: {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
