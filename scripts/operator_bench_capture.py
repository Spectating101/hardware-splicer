#!/usr/bin/env python3
"""Operator bench capture — fill / submit real instrument readings (not simulator).

Usage:
  # Show open gates + write template
  PYTHONPATH=src python3 scripts/operator_bench_capture.py --build-dir OUT --status

  # Attach photo draft (does not close gates)
  PYTHONPATH=src python3 scripts/operator_bench_capture.py --build-dir OUT \\
    --vision-photo tests/data/golden/rc_toy_motor_board.jpg

  # Submit a filled bench_topology_capture.v1 JSON (must not be simulated)
  PYTHONPATH=src python3 scripts/operator_bench_capture.py --build-dir OUT \\
    --submit path/to/filled_capture.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hardware_splicer.bench_capture_bridge import load_bench_capture_template, submit_bench_capture, sync_bench_session_template
from hardware_splicer.bench_capture_vision import assist_bench_capture_vision
from hardware_splicer.splice_bench import bench_status


def _load_capture(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("capture must be a JSON object")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Operator bench capture helper")
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--status", action="store_true", help="Print gate status + template path")
    parser.add_argument("--vision-photo", type=Path, help="Run vision-assist draft from photo")
    parser.add_argument("--submit", type=Path, help="Submit filled bench_topology_capture.v1")
    parser.add_argument(
        "--allow-simulated",
        action="store_true",
        help="Allow capture packets with simulated=true (CI only)",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    build_dir = args.build_dir.resolve()
    if not build_dir.is_dir():
        raise SystemExit(f"build_dir not found: {build_dir}")

    report: dict = {"build_dir": str(build_dir)}

    if args.status or (not args.vision_photo and not args.submit):
        sync_bench_session_template(build_dir)
        session = bench_status(build_dir)
        template = load_bench_capture_template(build_dir)
        report["status"] = {
            "open_gate_count": session.get("open_gate_count"),
            "power_on_authorized": session.get("power_on_authorized"),
            "readiness": session.get("readiness"),
            "template_path": template.get("template_path"),
            "open_measurements": [
                {"gate_id": row.get("gate_id"), "kind": row.get("kind"), "target": row.get("target")}
                for row in (template.get("measurements") or [])
                if isinstance(row, dict)
            ],
            "policy": (
                "Fill measurements with instrument readings, set simulated=false, "
                "then --submit. Vision drafts do not close gates."
            ),
        }

    if args.vision_photo:
        photo = args.vision_photo.resolve()
        if not photo.is_file():
            raise SystemExit(f"vision photo not found: {photo}")
        assist = assist_bench_capture_vision(
            build_dir,
            attachments=[{"kind": "image", "path": str(photo)}],
            live=False,
            operator_id="operator_bench_capture",
        )
        report["vision_assist"] = {
            "ok": assist.get("ok"),
            "draft_path": assist.get("draft_path"),
            "gates_unchanged": (assist.get("policy") or {}).get("gates_unchanged"),
        }

    if args.submit:
        capture = _load_capture(args.submit.resolve())
        if capture.get("simulated") and not args.allow_simulated:
            raise SystemExit(
                "refusing simulated capture — fill real instrument readings "
                "or pass --allow-simulated for CI"
            )
        if not capture.get("operator_id"):
            raise SystemExit("capture.operator_id required for operator submit")
        result = submit_bench_capture(str(build_dir), capture)
        session = result.get("bench_session") if isinstance(result.get("bench_session"), dict) else bench_status(build_dir)
        report["submit"] = {
            "ok": result.get("ok"),
            "mapped_count": result.get("mapped_count"),
            "power_on_authorized": session.get("power_on_authorized"),
            "open_gate_count": session.get("open_gate_count"),
        }
        if not result.get("ok"):
            if args.json:
                print(json.dumps(report, indent=2))
            else:
                print(json.dumps(report, indent=2))
            return 1

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        if "status" in report:
            st = report["status"]
            print(f"open_gates={st.get('open_gate_count')} power_on={st.get('power_on_authorized')}")
            print(f"template={st.get('template_path')}")
            for row in st.get("open_measurements") or []:
                print(f"  - {row.get('gate_id')}: {row.get('kind')} — {row.get('target')}")
        if "vision_assist" in report:
            va = report["vision_assist"]
            print(f"vision_draft={va.get('draft_path')} gates_unchanged={va.get('gates_unchanged')}")
        if "submit" in report:
            sub = report["submit"]
            print(
                f"submit_ok={sub.get('ok')} mapped={sub.get('mapped_count')} "
                f"power_on={sub.get('power_on_authorized')}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
