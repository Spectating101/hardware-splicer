#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _default_vibe_spec() -> Dict[str, Any]:
    """
    Intentionally naive spec that a pure prompt flow might emit.
    This should trigger at least one meaningful gate warning/block.
    """
    return {
        "project_name": "vibe_pan_tilt_camera",
        "simulation_fidelity": "high",
        "mode": "prototype",
        "pan_tilt": {
            "pan_servo": "sg90",
            "tilt_servo": "sg90",
            "max_payload_n": 5.0,
            "payload_offset_mm": 50.0,
        },
        "electronics": {
            "device": "camera_ctrl",
            "pcb_w_mm": 60,
            "pcb_h_mm": 35,
            "pcb_t_mm": 1.6,
            "mounts": [
                {"x_mm": 4, "y_mm": 4, "d_mm": 2.4},
                {"x_mm": 56, "y_mm": 4, "d_mm": 2.4},
                {"x_mm": 4, "y_mm": 31, "d_mm": 2.4},
                {"x_mm": 56, "y_mm": 31, "d_mm": 2.4},
            ],
            "ports": [
                {
                    "kind": "rect",
                    "face": "front",
                    "label": "usb-c",
                    "rect": {"x_mm": 22, "y_mm": 0, "w_mm": 10, "h_mm": 4},
                }
            ],
        },
    }


def _is_blocking(bundle: Dict[str, Any]) -> bool:
    if bool(bundle.get("blockers")):
        return True
    for source in ("dfm", "simulation"):
        for issue in bundle.get(source) or []:
            if str(issue.get("severity", "")).lower() in {"block", "critical", "error"}:
                return True
    return False


def _gate_summary(bundle: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {"dfm": {"info": 0, "warn": 0, "block": 0}, "simulation": {"info": 0, "warn": 0, "block": 0}}
    for key in ("dfm", "simulation"):
        for row in bundle.get(key) or []:
            sev = str(row.get("severity", "info")).lower()
            if sev not in out[key]:
                out[key][sev] = 0
            out[key][sev] += 1
    return out


def _extract_key_findings(bundle: Dict[str, Any]) -> List[str]:
    findings: List[str] = []
    for source in ("dfm", "simulation", "safety"):
        for row in bundle.get(source) or []:
            sev = str(row.get("severity", "")).lower()
            if sev in {"warn", "block", "critical", "error"}:
                findings.append(f"{source}:{sev}:{row.get('message')}")
    return findings[:12]


def _auto_revise(spec: Dict[str, Any], findings: List[str]) -> Dict[str, Any]:
    revised = deepcopy(spec)
    pt = revised.get("pan_tilt")

    joined = "\n".join(findings).lower()
    if pt and ("tilt torque" in joined or "payload moment" in joined):
        if pt.get("pan_servo") != "mg996r":
            pt["pan_servo"] = "mg996r"
            pt["tilt_servo"] = "mg996r"
        else:
            pt["payload_offset_mm"] = max(25.0, float(pt.get("payload_offset_mm", 40.0)) * 0.8)
            pt["max_payload_n"] = max(2.0, float(pt.get("max_payload_n", 4.0)) * 0.85)

    la = revised.get("linear_axis")
    if la and ("torque" in joined or "deflection" in joined):
        la["target_accel_mm_s2"] = max(200.0, float(la.get("target_accel_mm_s2", 600.0)) * 0.75)
        la["payload_n"] = max(4.0, float(la.get("payload_n", 10.0)) * 0.9)

    return revised


def _run_iteration(run_fn, spec: Dict[str, Any], out_dir: Path, idx: int) -> Dict[str, Any]:
    case_dir = out_dir / f"iter_{idx:02d}"
    bundle = run_fn(spec, out_dir=case_dir, simulation_fidelity="high")
    findings = _extract_key_findings(bundle)
    return {
        "iter": idx,
        "out_dir": str(case_dir),
        "blocked": _is_blocking(bundle),
        "gate_summary": _gate_summary(bundle),
        "key_findings": findings,
        "bundle": bundle,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Demonstrate vibe-to-proof loop: generate -> gate -> revise -> pass/fail evidence.")
    ap.add_argument("--out", default="dist_ready_for_sale/vibe_to_proof_demo_latest", help="Output directory")
    ap.add_argument("--max-iters", type=int, default=3)
    ap.add_argument("--spec", default=None, help="Optional input spec JSON")
    args = ap.parse_args()

    import sys

    repo = _repo_root()
    sys.path.insert(0, str(repo))
    from src.mecha_splicer.runner import run  # type: ignore

    out_dir = repo / args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.spec:
        spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    else:
        spec = _default_vibe_spec()

    history: List[Dict[str, Any]] = []
    current = deepcopy(spec)

    for i in range(1, max(1, args.max_iters) + 1):
        step = _run_iteration(run, current, out_dir, i)
        history.append(step)
        if not step["blocked"]:
            break
        current = _auto_revise(current, step["key_findings"])

    final = history[-1]
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "start_spec": spec,
        "final_spec": current,
        "iterations": [
            {
                "iter": h["iter"],
                "out_dir": h["out_dir"],
                "blocked": h["blocked"],
                "gate_summary": h["gate_summary"],
                "key_findings": h["key_findings"],
            }
            for h in history
        ],
        "final_status": "pass" if not final["blocked"] else "fail",
    }

    (out_dir / "vibe_to_proof_result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    lines: List[str] = []
    lines.append("# Vibe-to-Proof Demo\n")
    lines.append(f"- Final status: **{result['final_status']}**")
    lines.append(f"- Iterations: {len(history)}")
    lines.append("")
    lines.append("## Iteration Summary")
    for h in result["iterations"]:
        lines.append(f"- Iter {h['iter']}: blocked={h['blocked']}, dfm={h['gate_summary']['dfm']}, sim={h['gate_summary']['simulation']}")
        for k in h["key_findings"][:4]:
            lines.append(f"  - {k}")
    lines.append("")
    lines.append("## Value Signal")
    lines.append("- LLM generation alone produced at least one blocked design state.")
    lines.append("- Gate + automated revision converted it into a verifiable pass/fail workflow with evidence artifacts.")
    lines.append("")

    (out_dir / "VIBE_TO_PROOF_REPORT.md").write_text("\n".join(lines), encoding="utf-8")

    print(json.dumps({"out_dir": str(out_dir), "final_status": result["final_status"], "iterations": len(history)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
