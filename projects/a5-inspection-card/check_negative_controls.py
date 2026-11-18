#!/usr/bin/env python3
"""Three semantic negative controls for the actual A5 study delivery.

    python -B check_negative_controls.py FINAL.zip --baseline BASELINE.zip \
        --output negative-controls.json

Requires the same native CAD environment as check_delivery.py. Mutations live
only in temporary ZIP copies. Their seals are recomputed deliberately so a
rejection must come from the independent geometry/motion checks, not stale hashes.
No authoring script or script inside a study ZIP is executed.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile

CHECKER_PATH = Path(__file__).with_name("check_delivery.py")
spec = importlib.util.spec_from_file_location("independent_a5_checker", CHECKER_PATH)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False)+"\n").encode()


def reseal(data):
    """Deliberately repair byte seals without changing archived success claims."""
    if "reports/export_manifest.json" in data:
        manifest = checker.read_json(data["reports/export_manifest.json"])
        for name in manifest:
            manifest[name] = digest(data[name])
        data["reports/export_manifest.json"] = encode(manifest)
    receipt = checker.read_json(data["study-verification.json"])
    if set(receipt["artifact_sha256"]) != set(data)-{"study-verification.json"}:
        raise ValueError("Original seal does not cover the exact package inventory")
    receipt["artifact_sha256"] = {name: digest(data[name]) for name in receipt["artifact_sha256"]}
    data["study-verification.json"] = encode(receipt)


def consistent_csv(data):
    """Keep the accompanying CSV internally consistent with manipulated motion."""
    moves = checker.decode_gcode(data["simulation/example.gcode"].decode())
    stream = io.StringIO(newline="")
    fields = ("line", "x0", "y0", "z0", "x1", "y1", "z1",
              "feed_mm_min", "duration_s", "drawing")
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    for move in moves:
        row = dict(zip(("x0", "y0", "z0", "x1", "y1", "z1"),
                       (*move["start"], *move["end"])))
        row.update(line=move["line"], feed_mm_min=move["feed"],
                   duration_s=move["duration"], drawing=int(move["drawing"]))
        writer.writerow(row)
    data["simulation/trajectory.csv"] = stream.getvalue().encode()


def baseline_paper(data, baseline):
    # Authentic baseline geometry supplies the 180x180 sheet; final requirements
    # and all archived success flags still say the requested A5 revision passed.
    for name in ("exports/plotter.step", "exports/plotter.glb"):
        data[name] = baseline[name]


def inadequate_pen_lift(data, baseline):
    name = "simulation/example.gcode"
    code = data[name].decode()
    original = "G0 Z3.0000 F300"
    if original not in code:
        raise ValueError("Expected generated initial 3 mm lift is missing")
    data[name] = code.replace(original, "G0 Z1.0000 F300", 1).encode()
    consistent_csv(data)


def anisotropic_artwork(data, baseline):
    # Restore the actual discovered defect: stretch only X from a 1.6 uniform
    # scale to1.9, leaving Y at1.6. It still fits the requested viewport, but
    # each correct8x8mm checkbox becomes9.5x8mm.
    name = "simulation/example.gcode"
    lines, changed = [], 0
    for raw in data[name].decode().splitlines(keepends=True):
        tokens = raw.strip().split()
        if tokens and tokens[0] in {"G0", "G1"}:
            for i, token in enumerate(tokens[1:], 1):
                match = checker.WORD.fullmatch(token)
                if match and match[1] == "X":
                    x = 117.5 + (float(match[2])-117.5)*(1.9/1.6)
                    tokens[i] = f"X{x:.4f}"
                    changed += 1
            lines.append(" ".join(tokens)+"\n")
        else:
            lines.append(raw)
    if changed == 0:
        raise ValueError("No actual X movements were found to distort")
    data[name] = "".join(lines).encode()
    consistent_csv(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("study", type=Path)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    original_sha = digest(args.study.read_bytes())
    baseline_sha = digest(args.baseline.read_bytes())
    final = checker.inspect_archive(args.study, checker.Audit())
    baseline = checker.inspect_archive(args.baseline, checker.Audit())
    controls = [
        ("baseline_paper_in_a5_delivery", baseline_paper,
         {"step_contains_actual_a5_paper", "glb_contains_actual_a5_paper"},
         "Authentic180x180 baseline layout replaces final layout while A5 requirements remain unchanged."),
        ("one_mm_travel_in_three_mm_job", inadequate_pen_lift,
         {"all_xy_travel_pen_up"},
         "First XY travel uses1mm lift; CSV and all byte seals are updated."),
        ("anisotropic_checkbox_distortion", anisotropic_artwork,
         {"svg_to_gcode_directed_segments", "four_checkboxes_remain_square"},
         "X scaling is stretched1.6→1.9 while Y remains1.6;9.5x8mm checkboxes still fit the viewport."),
    ]
    results = []
    with tempfile.TemporaryDirectory(prefix="hs-a5-negative-controls-") as temporary:
        temporary = Path(temporary)
        for name, mutate, expected, description in controls:
            data = dict(final)
            mutate(data, baseline)
            reseal(data)
            candidate, output = temporary/(name+".zip"), temporary/(name+".json")
            with ZipFile(candidate, "w", ZIP_DEFLATED) as archive:
                for path, raw in sorted(data.items()):
                    archive.writestr(path, raw)
            run = subprocess.run(
                [sys.executable, "-B", str(CHECKER_PATH), str(candidate),
                 "--baseline", str(args.baseline), "--output", str(output)],
                capture_output=True, text=True, timeout=300, check=False)
            report = checker.read_json(output.read_bytes()) if output.is_file() else {}
            checks = {c["name"]: c for c in report.get("checks", [])}
            sealing = ("sealed_file_inventory", "sealed_file_hashes", "registered_source_hashes",
                       "baseline_sealed_bytes", "integrity_and_goal_both_pass")
            seals_pass = all(checks.get(key, {}).get("passed") is True for key in sealing)
            targeted_rejection = all(checks.get(key, {}).get("passed") is False for key in expected)
            passed = (run.returncode == 1 and report.get("accepted") is False
                      and seals_pass and targeted_rejection and "audit_exception" not in checks)
            item = {
                "name": name, "description": description, "passed": passed,
                "candidate_sha256": digest(candidate.read_bytes()), "checker_exit_code": run.returncode,
                "recomputed_seals_and_archived_success_claims_pass": seals_pass,
                "required_semantic_rejections": sorted(expected),
                "observed_failures": [c for c in report.get("checks", []) if not c["passed"]],
                "independent_metrics": report.get("metrics", {}),
            }
            if not report:
                item["process_error"] = (run.stderr or run.stdout)[-3000:]
            results.append(item)
            print(name, "PASS" if passed else "FAIL", flush=True)
    originals_unchanged = (digest(args.study.read_bytes()) == original_sha
                           and digest(args.baseline.read_bytes()) == baseline_sha)
    passed = originals_unchanged and len(results) == 3 and all(x["passed"] for x in results)
    report = {
        "schema": "hardware_splicer.a5_semantic_negative_controls.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "passed": passed, "originals_unchanged": originals_unchanged,
        "study_sha256": original_sha, "baseline_sha256": baseline_sha,
        "checker_sha256": digest(CHECKER_PATH.read_bytes()),
        "harness_sha256": digest(Path(__file__).read_bytes()),
        "controls": results, "physical_validation_performed": False,
        "scope": "Three temporary actual-delivery mutations; byte seals deliberately recomputed before independent semantic rejection.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(encode(report))
    print(json.dumps({"passed": passed, "originals_unchanged": originals_unchanged,
                      "output": str(args.output)}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
