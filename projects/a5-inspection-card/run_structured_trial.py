#!/usr/bin/env python3
"""Credential-free reproduction through the real HS registered-project backend.

Artwork below is explicitly assistant-authored structured input. This runner never
calls or mocks a text provider, and does not claim that HS interpreted a prompt.
CAD, persisted revisions, simulation, native audit and export are real HS calls.
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
BASELINE = {"drawing_width_mm": 100., "drawing_height_mm": 80.,
            "pen_diameter_mm": 10., "pen_lift_mm": 3.,
            "paper_width_mm": 180., "paper_height_mm": 180.}
FINAL = {"drawing_width_mm": 190., "drawing_height_mm": 128.,
         "pen_diameter_mm": 12., "pen_lift_mm": 3.,
         "paper_width_mm": 210., "paper_height_mm": 148.}
BRIEF = ("Electronics inspection card: closed outer border, two blank header fields, "
         "four left-side checkboxes and writing lines, and a clear board-sketch box at right.")


def rectangle(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]


def authored_drawing():
    # Logical 100 x 80 canvas, origin lower left. Separate outlines avoid crossings.
    strokes = [rectangle(4., 4., 96., 76.),
               rectangle(8., 63., 48., 72.), rectangle(52., 63., 92., 72.)]
    for y in (49., 38., 27., 16.):
        strokes.append(rectangle(8., y, 13., y + 5.))
        strokes.append([[18., y + 2.5], [44., y + 2.5]])
    strokes.append(rectangle(52., 10., 92., 56.))
    return strokes


def stamp():
    return datetime.now(timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-root", type=Path, required=True,
                        help="New isolated directory; no existing run is overwritten.")
    args = parser.parse_args()
    state = args.state_root.expanduser().resolve()
    state.mkdir(parents=True, exist_ok=False)
    records = state / "records"
    records.mkdir()
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    os.environ["OPENBLAS_NUM_THREADS"] = "1"
    os.environ["OMP_NUM_THREADS"] = "1"
    sys.path.insert(0, str(REPO / "src"))
    from hardware_splicer.digital_engine import DigitalStudyEngine
    from hardware_splicer.digital_brief import BriefInterpretation
    from hardware_splicer.digital_cases import registered

    # Validate the authored data against the production schema without invoking an LLM.
    shaped = BriefInterpretation.model_validate_json(json.dumps({
        "status": "build", "case_id": "ender3-penplotter", "requirements": BASELINE,
        "explanation": "Explicit author-supplied requirements and vector strokes; no prompt interpretation.",
        "drawing": authored_drawing(),
    })).model_dump(mode="json")
    registered("ender3-penplotter").validate(BASELINE)
    registered("ender3-penplotter").validate(FINAL)
    plan = {**shaped, "brief": BRIEF, "provider": None, "model": None,
            "input_origin": "assistant_authored_structured_input",
            "live_model_invocation": False}
    ledger = {"started_at_utc": stamp(), "creation_method": "structured_registered_api",
              "repository_commit": subprocess.check_output(
                  ["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True).strip(),
              "artwork_provenance": "Assistant-authored vector strokes supplied directly to HS; no provider call or mock.",
              "live_model_invocation": False, "physical_operation_performed": False,
              "baseline_requirements": BASELINE, "final_requirements": FINAL,
              "note": "The legacy artifact name sources/prompt-drawing.json does not imply LLM provenance. "
                      "The registered engine fits artwork uniformly and centers it in the viewport. "
                      "The source canvas is 160 x 128 mm in the final 190 x 128 mm viewport; "
                      "logical square checkboxes are 5 x 5 mm at baseline and 8 x 8 mm in the final build.",
              "steps": []}
    ledger_path = records / "run-ledger.json"
    (records / "00-authored-input.json").write_text(json.dumps(plan, indent=2) + "\n")

    def save():
        ledger_path.write_text(json.dumps(ledger, indent=2) + "\n")

    def invoke(label, operation, fn):
        started = time.monotonic()
        try:
            result = fn()
        except Exception as exc:
            ledger["steps"].append({"step": label, "operation": operation,
                "elapsed_seconds": round(time.monotonic() - started, 3), "finished_at_utc": stamp(),
                "ok": False, "error": f"{type(exc).__name__}: {exc}"})
            save()
            raise
        (records / (label + ".json")).write_text(json.dumps(result, indent=2) + "\n")
        row = {"step": label, "operation": operation, "ok": result.get("ok"),
               "elapsed_seconds": round(time.monotonic() - started, 3), "finished_at_utc": stamp()}
        ledger["steps"].append(row)
        save()
        print(json.dumps(row), flush=True)
        if not result.get("ok"):
            raise RuntimeError(f"{label}: HS did not complete the requested step: {result.get('error')}")
        return result

    save()
    try:
        with DigitalStudyEngine(project_root=state / "projects", job_db=state / "jobs.sqlite3") as engine:
            invoke("00-cases", "cases", engine.cases)
            created = invoke("01-structured-baseline", "create", lambda: engine.create(
                name="Electronics inspection card", case_id="ender3-penplotter", brief_plan=plan))
            project = created["project"]
            project_id, baseline_revision = project["project_id"], project["revision"]
            baseline = engine.study(project_id, baseline_revision)
            if baseline["summary"]["requirements"] != BASELINE or not baseline["summary"]["requirements_met"]:
                raise RuntimeError("HS baseline differs from the explicit requirements or misses a target")
            ledger.update(project_id=project_id, baseline_revision=baseline_revision)
            save()
            invoke("02-export-baseline", "export", lambda: engine.export(
                project_id, state / "baseline-study.zip", baseline_revision))
            revised = invoke("03-structured-a5-revision", "run_revision", lambda: engine.run_revision(
                project_id, base_revision=baseline_revision, requirements=FINAL,
                change_request="Preserve authored inspection artwork; adapt to a 12 mm pen and 190 x 128 mm viewport on A5 paper."))
            final_study = revised["study"]
            final_revision = final_study["revision"]
            if final_revision <= baseline_revision or final_study["summary"]["requirements"] != FINAL:
                raise RuntimeError("HS did not save the requested A5 revision")
            artwork = "sources/prompt-drawing.json"
            before_hash = baseline["artifact_manifest"][artwork]["sha256"]
            after_hash = final_study["artifact_manifest"][artwork]["sha256"]
            if before_hash != after_hash:
                raise RuntimeError("The numeric revision changed the authored artwork bytes")
            ledger.update(final_revision=final_revision, artwork_sha256=before_hash,
                          artwork_preserved_between_revisions=True)
            save()
            invoke("04-history", "history", lambda: {"ok": True, "history": engine.history(project_id)})
            invoke("05-compare", "compare", lambda: {"ok": True, "comparison": engine.compare(
                project_id, before_revision=baseline_revision, after_revision=final_revision)})
            audit = invoke("06-native-audit", "audit(native=True)", lambda: engine.audit(
                project_id, final_revision, native=True))
            if audit.get("native_verification", {}).get("engineering_acceptance") is not True:
                raise RuntimeError("The final native audit did not accept the stated requirements")
            exported = invoke("07-export-a5", "export", lambda: engine.export(
                project_id, state / "a5-inspection-card-study.zip", final_revision))
            if exported.get("requirements_met") is not True:
                raise RuntimeError("Final package did not meet its engineering requirements")
            ledger.update(finished_at_utc=stamp(), outcome="exported_for_independent_delivery_check",
                          final_package_sha256=exported["sha256"])
            save()
            print(json.dumps({"project_id": project_id, "baseline_revision": baseline_revision,
                "final_revision": final_revision, "package": exported["path"], "sha256": exported["sha256"],
                "records": str(records), "creation_method": "structured_registered_api",
                "live_model_invocation": False}), flush=True)
    except Exception as exc:
        ledger.update(finished_at_utc=stamp(), outcome="incomplete", error=f"{type(exc).__name__}: {exc}")
        save()
        raise


if __name__ == "__main__":
    main()
