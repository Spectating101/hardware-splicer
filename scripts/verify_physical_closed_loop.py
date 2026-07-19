#!/usr/bin/env python3
"""Verify physical closed-loop pack is software-ready for a human bench win."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

os.environ.setdefault("HARDWARE_SPLICER_OFFLINE_LLM", "1")
os.environ.setdefault("HARDWARE_SPLICER_OFFLINE_VISION", "1")
os.environ.setdefault("HARDWARE_SPLICER_OFFLINE_SALVAGE", "1")
os.environ.setdefault("QWEN_DISABLED", "1")
os.environ.setdefault("HARDWARE_SPLICER_SKIP_VISION_LIVE", "1")
os.environ.setdefault("HARDWARE_SPLICER_AUTOROUTE", "0")
os.environ.setdefault("HARDWARE_SPLICER_DRC_FIX_LOOP", "1")


def _verify_pack(out_dir: Path, spec: Dict[str, Any]) -> Dict[str, Any]:
    failures: List[str] = []
    required = [
        "PHYSICAL_BENCH_RUNBOOK.md",
        "PHYSICAL_BENCH_EVIDENCE.json",
        "PHYSICAL_CLOSED_LOOP_PACK.json",
        "BRINGUP_CARD.md",
        "MECHANISM_PACK.json",
        "MECHATRONICS_AUTHORITY.json",
        "firmware/FIRMWARE_SCAFFOLD.json",
        "build_compilation/build_graph.json",
        "PROJECT_PACKAGE.json",
    ]
    for rel in required:
        if not (out_dir / rel).is_file():
            failures.append(f"missing {rel}")

    pack = {}
    pack_path = out_dir / "PHYSICAL_CLOSED_LOOP_PACK.json"
    if pack_path.is_file():
        pack = json.loads(pack_path.read_text(encoding="utf-8"))
        if not pack.get("compile_ok"):
            failures.append("compile_ok false")
        if not pack.get("confidence_passed"):
            failures.append(f"confidence failed: {pack.get('confidence_failures')}")

    for name in spec.get("require_scad") or []:
        if not (out_dir / "mecha_bundle" / name).is_file():
            failures.append(f"missing mecha_bundle/{name}")

    fw_meta = out_dir / "firmware" / "FIRMWARE_SCAFFOLD.json"
    if fw_meta.is_file():
        fw = json.loads(fw_meta.read_text(encoding="utf-8"))
        src = str(fw.get("source") or "")
        for tok in spec.get("require_firmware_tokens") or []:
            if tok not in src:
                failures.append(f"firmware missing {tok}")
        pins = dict(fw.get("pins") or {})
        if pins.get("servo_pan") is None or pins.get("servo_tilt") is None:
            failures.append("dual servo pins missing in firmware meta")
        if pins.get("servo_pan") == pins.get("servo_tilt"):
            failures.append("pan/tilt share GPIO")

    runbook = out_dir / "PHYSICAL_BENCH_RUNBOOK.md"
    if runbook.is_file():
        text = runbook.read_text(encoding="utf-8")
        steps = text.count("## ")
        if steps < int(spec.get("bench_steps_min") or 4):
            failures.append(f"runbook too thin ({steps} sections)")

    evidence = out_dir / "PHYSICAL_BENCH_EVIDENCE.json"
    if evidence.is_file():
        ev = json.loads(evidence.read_text(encoding="utf-8"))
        if ev.get("status") == "closed":
            # Physical close is human-only; software verify must not require it
            pass
        open_checks = [c for c in (ev.get("checks") or []) if c.get("status") == "open"]
        if not open_checks:
            failures.append("evidence template has no open checks (expected pending operator)")

    auth = out_dir / "MECHATRONICS_AUTHORITY.json"
    if auth.is_file():
        body = json.loads(auth.read_text(encoding="utf-8"))
        if body.get("production_authorized") is True:
            failures.append("production_authorized theater on physical pack")

    return {
        "path_id": spec.get("path_id"),
        "passed": not failures,
        "failures": failures,
        "out_dir": str(out_dir),
        "pack": pack,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "examples" / "physical_loop" / "manifest.json",
    )
    parser.add_argument("--out", type=Path, default=Path("/tmp/hs_physical_closed_loop"))
    parser.add_argument("--skip-prepare", action="store_true")
    args = parser.parse_args()

    if not args.skip_prepare:
        import subprocess

        prep = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "prepare_physical_closed_loop.py"),
                "--manifest",
                str(args.manifest),
                "--out",
                str(args.out),
            ],
            cwd=str(ROOT),
            env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        )
        if prep.returncode != 0:
            print("prepare_physical_closed_loop failed", file=sys.stderr)
            return prep.returncode

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    rows = []
    for spec in manifest.get("paths") or []:
        out_dir = args.out.resolve() / str(spec["path_id"])
        rows.append(_verify_pack(out_dir, spec))

    passed = sum(1 for r in rows if r["passed"])
    report = {
        "schema_version": "hardware_splicer.physical_closed_loop_verify.v1",
        "passed_count": passed,
        "path_count": len(rows),
        "all_passed": passed == len(rows) and len(rows) > 0,
        "software_ready": passed == len(rows) and len(rows) > 0,
        "physical_evidence_closed": False,
        "claim_boundary": (
            "Software pack ready for human bench. Physical evidence still open — "
            "do not unpause invites until PHYSICAL_BENCH_EVIDENCE.json is operator-closed."
        ),
        "paths": rows,
    }
    report_path = args.out.resolve() / "PHYSICAL_CLOSED_LOOP_VERIFY.json"
    args.out.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Physical closed loop (software-ready): {passed}/{len(rows)} passed")
    print(f"report: {report_path}")
    for r in rows:
        status = "PASS" if r["passed"] else "FAIL"
        print(f"  [{status}] {r['path_id']} → {r['out_dir']}")
        for f in r.get("failures") or []:
            print(f"         - {f}")
    print(f"\n{report['claim_boundary']}")
    return 0 if report["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
