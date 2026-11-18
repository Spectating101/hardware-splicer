#!/usr/bin/env python3
"""Run an actual HS project from a brief, revise it, audit it, and export both states.

Use the application's Python environment. Configure a supported HS text provider
in the process environment. Native CAD runs through HARDWARE_SPLICER_DIGITAL_PYTHON.
No printer connection or physical motion is performed.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[2]
BASELINE_BRIEF = (
    "Use the original classic Ender-3 reference to make an electronics inspection-card pen plotter. "
    "Use a 10 mm cylindrical pen, a 100 by 80 mm drawing viewport, 180 by 180 mm paper, "
    "and a 3 mm pen lift. Draw a clean blank inspection record: one closed outer border; "
    "a header split into two empty fields; four evenly spaced checklist rows on the left, "
    "each with one empty square checkbox and a blank writing line; and one large clear "
    "rectangular board-sketch area on the right. Leave the fields blank for handwriting. "
    "Use only simple single-stroke outlines, no lettering or decorative symbols, with "
    "internal whitespace so lines do not overlap. Generate the actual drawing for this brief."
)
REVISION_BRIEF = (
    "Keep exactly the same inspection-card artwork and the 3 mm pen lift. "
    "Change to a 12 mm diameter cylindrical pen. Use an A5 landscape sheet, "
    "210 mm wide by 148 mm high, with a centered 190 by 128 mm drawing viewport "
    "and at least 10 mm margin on every edge. Preserve the existing drawing, "
    "changing only these numeric settings. Produce the revised digital build."
)

def stamp():
    return datetime.now(timezone.utc).isoformat()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-root", type=Path, required=True,
                        help="New directory for isolated projects, jobs and complete run records.")
    parser.add_argument("--provider", help="Optional existing HS provider mode, e.g. copilot_cli.")
    args = parser.parse_args()
    state = args.state_root.expanduser().resolve()
    state.mkdir(parents=True, exist_ok=False)
    records = state / "records"
    records.mkdir()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO / "src")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["OPENBLAS_NUM_THREADS"] = "1"
    env["OMP_NUM_THREADS"] = "1"
    if args.provider:
        env["HARDWARE_SPLICER_LLM_PROVIDER"] = args.provider
    prefix = [sys.executable, "-B", "-m", "hardware_splicer.digital_engine_cli",
              "--project-root", str(state / "projects"),
              "--jobs-db", str(state / "jobs.sqlite3")]
    ledger = {"started_at_utc": stamp(),
              "repository_commit": subprocess.check_output(
                  ["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True).strip(),
              "baseline_brief": BASELINE_BRIEF, "revision_brief": REVISION_BRIEF,
              "steps": [], "physical_operation_performed": False}
    ledger_path = records / "run-ledger.json"

    def save():
        ledger_path.write_text(json.dumps(ledger, indent=2) + "\n")

    def invoke(label, *command):
        started = time.monotonic()
        proc = subprocess.run(prefix + list(command), cwd=REPO, env=env,
                              capture_output=True, text=True)
        (records / (label + ".stdout.txt")).write_text(proc.stdout)
        (records / (label + ".stderr.txt")).write_text(proc.stderr)
        row = {"step": label, "arguments": list(command), "exit_code": proc.returncode,
               "elapsed_seconds": round(time.monotonic() - started, 3), "finished_at_utc": stamp()}
        ledger["steps"].append(row)
        save()
        try:
            result = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"{label}: CLI returned no JSON; inspect the saved output") from exc
        (records / (label + ".json")).write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps({"step": label, "exit_code": proc.returncode,
                          "elapsed_seconds": row["elapsed_seconds"], "ok": result.get("ok"),
                          "error": result.get("error")}), flush=True)
        if proc.returncode != 0 or not result.get("ok"):
            raise RuntimeError(f"{label}: HS did not complete the requested step")
        return result

    save()
    try:
        invoke("00-cases", "cases")
        first = invoke("01-prompt-baseline", "prompt", BASELINE_BRIEF)
        if first.get("interpretation", {}).get("status") != "build" or not first.get("project"):
            raise RuntimeError("HS did not select an executable baseline; the response is preserved")
        project = first["project"]
        project_id = project["project_id"]
        baseline_revision = project["revision"]
        ledger.update({"project_id": project_id, "baseline_revision": baseline_revision})
        save()
        invoke("02-export-baseline", "export", project_id, str(state / "baseline-study.zip"),
               "--revision", str(baseline_revision))
        changed = invoke("03-prompt-a5-revision", "prompt", REVISION_BRIEF,
                         "--project-id", project_id, "--base-revision", str(baseline_revision))
        if changed.get("interpretation", {}).get("status") != "build" or changed.get("unchanged"):
            raise RuntimeError("HS did not produce the requested A5 revision")
        history = invoke("04-history", "history", project_id)
        latest_revision = max(item["revision"] for item in history["history"])
        if latest_revision <= baseline_revision:
            raise RuntimeError("No new saved revision was produced")
        ledger["final_revision"] = latest_revision
        save()
        invoke("05-compare", "compare", project_id, "--before", str(baseline_revision),
               "--after", str(latest_revision))
        invoke("06-native-audit", "audit", project_id, "--revision", str(latest_revision), "--native")
        final = invoke("07-export-a5", "export", project_id, str(state / "a5-inspection-card-study.zip"),
                       "--revision", str(latest_revision))
        if final.get("requirements_met") is not True:
            raise RuntimeError("Final package did not meet its engineering requirements")
        ledger.update({"finished_at_utc": stamp(), "outcome": "exported_for_independent_delivery_check",
                       "final_package_sha256": final["sha256"]})
        save()
        print(json.dumps({"project_id": project_id, "baseline_revision": baseline_revision,
                          "final_revision": latest_revision, "package": final["path"],
                          "sha256": final["sha256"], "records": str(records)}), flush=True)
    except Exception as exc:
        ledger.update({"finished_at_utc": stamp(), "outcome": "incomplete",
                       "error": f"{type(exc).__name__}: {exc}"})
        save()
        raise

if __name__ == "__main__":
    main()
