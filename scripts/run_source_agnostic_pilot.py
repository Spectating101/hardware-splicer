#!/usr/bin/env python3
"""Reproducible, offline, read-only source-agnostic engineering pilot.

The public-source facts are transcribed into cases; this runner does not
download documents, power hardware, or independently verify physical results.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "eval" / "source_agnostic_pilot"
SCRIPT = ROOT / "scripts" / "benchmark_source_agnostic_engineering.py"

def main() -> int:
    lane = "engineering" if "--engineering-planner" in sys.argv[1:] else "legacy_intake"
    destination_args = [value for value in sys.argv[1:] if value != "--engineering-planner"]
    paths = sorted(CASES.glob("*.json"))
    if not paths:
        raise SystemExit("No pilot cases found")
    env = os.environ.copy()
    env["HARDWARE_SPLICER_SKIP_VISION_LIVE"] = "1"
    env["HARDWARE_SPLICER_OFFLINE_SALVAGE"] = "1"
    env["PYTHONHASHSEED"] = "0"
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), *(["--engineering-planner"] if lane == "engineering" else []), *(str(path) for path in paths)],
        cwd=ROOT, env=env, capture_output=True, text=True, check=False,
    )
    if proc.returncode:
        print(proc.stderr, file=sys.stderr)
        return proc.returncode
    result = json.loads(proc.stdout)
    manifest = {
        "schema_version": "hardware_splicer.source_agnostic_pilot.v1",
        "run_mode": "offline_no_live_vision",
        "planner_lane": lane,
        "physical_validation": False,
        "source_material": "vendor-guide claims transcribed into local cases",
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "case_sha256": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths
        },
        "suite": result,
    }
    destination = Path(destination_args[0]) if destination_args else Path("/tmp/hardware_splicer_pilot_results.json")
    destination.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(destination),
        "case_count": result["scenario_count"],
        "candidate_count": result["bounded_engineering_candidate_count"],
        "rows": [{
            "id": r["scenario_id"], "score": r["score"], "verdict": r["verdict"],
            "source_handoff_count": r["source_handoff_count"],
            "gaps": r["gaps"]
        } for r in result["rows"]],
    }, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
