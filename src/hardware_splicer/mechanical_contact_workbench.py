"""Local operator interface for the HS two-pin bracket investigation.

Creates an evidence JSON, self-contained HTML review and action checklist.
No server route and no fabrication controls. Physical-test metadata can
establish evidence completeness but cannot automatically verify strength.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
from collections import Counter
from pathlib import Path
from statistics import median
from typing import Any, Mapping


TRIAL_FIELDS = (
    "specimen_id", "print_orientation", "material_batch",
    "fixture_protocol_id", "measured_bore_d_mm", "measured_pin_d_mm",
    "maximum_force_n", "displacement_at_maximum_mm", "failure_mode",
)
ALLOWED_FAILURES = {
    "hole_bearing", "net_section_fracture", "delamination", "bending",
    "fastener_failure", "fixture_slip", "no_failure_observed", "other",
}


def read_physical_trials(path: str | Path) -> dict[str, Any]:
    """Validate user-supplied experimental outcomes; never imply certification."""
    file = Path(path).expanduser().resolve(strict=True)
    if not file.is_file() or not 0 < file.stat().st_size <= 1_000_000:
        raise ValueError("physical trials CSV must be a bounded nonempty file")
    with file.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or set(reader.fieldnames) != set(TRIAL_FIELDS):
            raise ValueError("physical trials CSV has invalid or missing field names")
        rows = list(reader)
    if not 1 <= len(rows) <= 200:
        raise ValueError("physical trial count must be in [1,200]")
    ids = set()
    orientations: dict[str, list[dict[str, Any]]] = {}
    fixture_ids = set()
    material_batches = set()
    for row in rows:
        sid = row["specimen_id"].strip()
        orient = row["print_orientation"].strip()
        batch = row["material_batch"].strip()
        fixture = row["fixture_protocol_id"].strip()
        if not all([sid, orient, batch, fixture]) or any(
            len(value) > 100 for value in (sid, orient, batch, fixture)
        ):
            raise ValueError("specimen, orientation, batch, and fixture are mandatory")
        if sid in ids:
            raise ValueError("physical specimen IDs must be unique")
        ids.add(sid)
        if row["failure_mode"] not in ALLOWED_FAILURES:
            raise ValueError("unrecognized failure mode")
        values = {}
        for key in (
            "measured_bore_d_mm", "measured_pin_d_mm",
            "maximum_force_n", "displacement_at_maximum_mm",
        ):
            try:
                number = float(row[key])
            except (ValueError, TypeError) as exc:
                raise ValueError(f"invalid measured value: {key}") from exc
            if not math.isfinite(number):
                raise ValueError("physical readings must be finite")
            values[key] = number
        if not (
            0 < values["measured_bore_d_mm"] < 200
            and 0 < values["measured_pin_d_mm"] < 200
            and 0 < values["maximum_force_n"] < 100_000
            and 0 <= values["displacement_at_maximum_mm"] < 100
        ):
            raise ValueError("physical readings outside reasonable safe data ranges")
        if values["measured_pin_d_mm"] > values["measured_bore_d_mm"]:
            # Interference fits are a different contact model; do not quietly
            # apply the free-clearance frictionless KKT assumptions.
            raise ValueError(
                "measured pin exceeds bore diameter: interference fit needs another model"
            )
        orientations.setdefault(orient, []).append({
            **values, "failure_mode": row["failure_mode"],
            "specimen_id": sid,
        })
        fixture_ids.add(fixture)
        material_batches.add(batch)
    readiness_blockers = []
    if len(orientations) < 2:
        readiness_blockers.append("less_than_two_print_orientations")
    if any(len(items) < 3 for items in orientations.values()):
        readiness_blockers.append("fewer_than_three_specimens_per_orientation")
    if len(fixture_ids) != 1:
        readiness_blockers.append("multiple_incomparable_fixture_protocols")
    results = []
    for orientation, items in sorted(orientations.items()):
        radials = [
            (x["measured_bore_d_mm"] - x["measured_pin_d_mm"]) / 2
            for x in items
        ]
        results.append({
            "print_orientation": orientation,
            "specimen_count": len(items),
            "median_maximum_force_n": median(
                x["maximum_force_n"] for x in items
            ),
            "minimum_observed_maximum_force_n": min(
                x["maximum_force_n"] for x in items
            ),
            "radial_clearance_mm_median": median(radials),
            "radial_clearance_mm_range": [min(radials), max(radials)],
            "failure_modes": dict(sorted(Counter(
                item["failure_mode"] for item in items
            ).items())),
        })
    return {
        "schema_version": "hardware_splicer.physical_trials_inventory.v1",
        "source_csv_sha256": "sha256:" + hashlib.sha256(file.read_bytes()).hexdigest(),
        "specimen_count": len(rows),
        "material_batches": sorted(material_batches),
        "fixture_protocol_ids": sorted(fixture_ids),
        "orientations": results,
        "minimum_trial_evidence_gate_met": not readiness_blockers,
        "evidence_completeness_blockers": readiness_blockers,
        "test_fixtures_similar_to_fem_verified": False,
        "model_vs_physical_predictions_validated": False,
        "actual_material_constitutive_law_calibrated": False,
        "engineering_strength_signoff_present": False,
        "fabrication_authorized": False,
        "release_authorized": False,
        "claim_boundary": (
            "Presence, dimensional plausibility and grouping of supplied test "
            "records only. Measurements are not authenticated; fixture and "
            "material representativeness require an independent reviewer."
        ),
    }


def make_operator_review(
    investigation: Mapping[str, Any],
    physical: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Produce a fixed, fail-closed operator decision contract."""
    required = {"status", "blockers", "mesh_levels", "generated_step_provenance"}
    if not required <= set(investigation):
        raise ValueError("contact evidence is not a complete operator investigation")
    blockers = list(investigation["blockers"])
    if investigation["status"] != "numerically_bounded_two_pin_screening_only":
        blockers.append("numerical_contact_stress_screen_inconclusive")
    blockers.extend([
        "continuous_surface_contact_not_certified",
        "physical_loading_fixture_not_matched_to_model",
        "material_orientation_and_properties_not_calibrated",
        "engineer_signoff_and_real_failure_load_required",
    ])
    if physical is None:
        blockers.append("physical_specimen_measurements_absent")
    else:
        blockers.extend(physical["evidence_completeness_blockers"])
        # A print does not automatically have the nominal CAD fit.
        # Do not claim the assumed clearance when measurements disagree.
        modeled_clearance = investigation["mesh_levels"][0]["clearance_mm"]
        if any(
            abs(row["radial_clearance_mm_median"] - modeled_clearance)
            > max(.001, .25 * modeled_clearance)
            for row in physical["orientations"]
        ):
            blockers.append("measured_clearance_differs_from_fem_assumption")
        blockers.append("experimental_traceability_and_model_agreement_not_verified")
    blockers = sorted(set(blockers))
    return {
        "schema_version": "hardware_splicer.contact_operator_review.v1",
        "disposition": "research_screening_only",
        "numeric_contact_equilibrium_supported": all(
            x["nodal_max_gap_violation_m"] <= 5e-10 and
            x["relative_gauge_reaction"] < .001
            for x in investigation["mesh_levels"]
        ),
        "screening_status": investigation["status"],
        "primary_blockers": blockers,
        "physical_record_inventory_complete": (
            physical is not None and
            physical["minimum_trial_evidence_gate_met"]
        ),
        "ready_to_issue_strength_rating": False,
        "ready_for_load_bearing_fabrication": False,
        "can_export_test_coupon_as_non_load_bearing_prototype": True,
        "next_actions": [
            "Measure actual pin and bore diameters with traceable instruments",
            "Test multiple physical specimens in at least two print orientations",
            "Log force-displacement curves and observed failure locations",
            "Match actual fastening fixture and material properties to the FEM case",
            "Re-evaluate bore-surface contact stresses using refined contact integration",
            "Obtain independent engineering sign-off before any load-bearing release",
        ],
        "fabrication_authorized": False,
        "release_authorized": False,
    }


def render_html_report(report: Mapping[str, Any]) -> str:
    """Offline, no remote assets, no JS execution or externally fetched media."""
    review = report["operator_review"]
    audit = report["contact_audit"]
    specimen = report.get("physical_trials")
    sweep = report.get("simulated_pin_sweep")
    esc = lambda x: html.escape(str(x), quote=True)
    mesh_rows = []
    for level in audit["mesh_levels"]:
        mesh_rows.append(
            "<tr><td>" + esc(level["mesh_target_mm"]) + " mm</td><td>" +
            esc(f'{level["transmitted_force_scale_n"]:.3f}') + " N</td><td>" +
            esc(f'{level["global_peak_sampled_von_mises_pa"]/1e6:.3f}') +
            " MPa</td><td>" + esc(
                ", ".join(
                    f'#{v["hole_index"]}: {v["weighted_rms_von_mises_pa"]/1e6:.3f}'
                    for v in level["per_hole_stress"]
                )
            ) + " MPa</td></tr>"
        )
    sweep_html = ""
    if sweep is not None:
        curve_rows = "".join(
            "<tr><td>"+esc(f'{level["pin_drive_mm"]:.4f}')+
            " mm</td><td>"+esc(f'{level["force_transferred_n"]:.3f}')+
            " N</td><td>"+esc(level["first_pin_contact_nodes"])+
            "</td><td>"+esc(level["second_pin_contact_nodes"])+
            "</td></tr>"
            for level in sweep["levels"]
        )
        sweep_html = (
            "<section><h2>Simulated rigid-pin force/displacement</h2>"
            "<p><strong>Uncalibrated simulation — not measured or verified.</strong></p>"
            "<table><thead><tr><th>Drive</th><th>Reaction</th>"
            "<th>Stationary pin nodes</th><th>Driven pin nodes</th>"
            "</tr></thead><tbody>" + curve_rows + "</tbody></table></section>"
        )
    blocker_html = "".join(
        "<li>" + esc(x) + "</li>" for x in review["primary_blockers"]
    )
    action_html = "".join(
        "<li>" + esc(x) + "</li>" for x in review["next_actions"]
    )
    measurements = (
        "Physical specimen data were provided for inventory checks only. "
        + esc(specimen["specimen_count"]) + " specimens recorded."
        if specimen else "No physical specimen measurements were supplied."
    )
    return """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src 'none'">
<title>Hardware Splicer | Two-pin mechanical evidence</title>
<style>
:root{color-scheme:light;font:15px/1.55 system-ui, sans-serif}
body{max-width:940px;margin:40px auto;padding:0 20px;background:#f6f8fb;color:#17223c}
header{padding:25px 30px;background:#17294b;color:white;border-radius:18px}
section{background:white;padding:23px 30px;border-radius:16px;margin-top:16px;border:1px solid #dce3ee}
h1{font-size:26px;margin:0 0 8px}h2{font-size:18px;margin:0 0 12px}
strong{font-weight:700}.warning{color:#9a310b}
table{width:100%;border-collapse:collapse}td,th{text-align:left;border-bottom:1px solid #e2e7ee;padding:10px 6px}
small{color:#66728a}li{margin-bottom:7px}
</style></head><body>
<header><h1>Hardware Splicer · Two-pin structural investigation</h1>
<p>Experimental numerical screening · NOT a manufacturing approval</p></header>
<section><h2>Operator disposition</h2>
<p><strong class="warning">RESEARCH SCREENING ONLY — LOAD-BEARING RELEASE BLOCKED</strong></p>
<p>Numerical status: """ + esc(audit["status"]) + """</p>
<p>Contact equilibrium supported: """ + esc(review["numeric_contact_equilibrium_supported"]) + """</p></section>
<section><h2>Resolution and force transfer</h2>
<table><thead><tr><th>Mesh</th><th>Force</th><th>Peak stress (not converged)</th>
<th>Per-hole RMS</th></tr></thead><tbody>""" + "".join(mesh_rows) + """</tbody></table>
<small>Do not treat a stress peak or an RMS screening metric as allowable strength.</small></section>
""" + sweep_html + """
<section><h2>Blocking evidence</h2><ul>""" + blocker_html + """</ul></section>
<section><h2>Physical measurements</h2><p>""" + measurements + """</p></section>
<section><h2>Actions before engineering release</h2>
<ol>""" + action_html + """</ol></section>
<section><h2>Audit controls</h2><p>Input-spec SHA-256: """ + esc(
        report["source_spec_sha256"]
    ) + """</p><p>Generated CAD SHA-256: """ + esc(
        audit["source_step_sha256"]
    ) + """</p>
<small>Full numerical and physical-data provenance is preserved in the accompanying JSON.
This report contains no remote assets, links or executable scripts.</small></section></body></html>"""


def run_contact_workbench(
    *,
    spec_file: str | Path,
    outdir: str | Path,
    mesh_sizes_mm: tuple[float, ...] = (8.,6.,5.),
    pin_drive_mm: float = .02,
    clearance_mm: float = .005,
    physical_csv: str | Path | None = None,
    sweep_drives_mm: Sequence[float] = (0., .01, .02, .04),
) -> dict[str, Any]:
    """One-command, local, bounded investigative workbench."""
    from .mechanical_bracket_screening import (
        _check_bracket_spec, generate_bracket_reference_step,
    )
    from .mechanical_contact_validation import audit_two_pin_contact

    source = Path(spec_file).expanduser().resolve(strict=True)
    if not source.is_file() or not 0 < source.stat().st_size <= 100_000:
        raise ValueError("spec JSON must be a bounded regular local file")
    data = json.loads(source.read_text(encoding="utf-8"))
    spec = data.get("bracket", data)
    _check_bracket_spec(spec)
    if not math.isfinite(pin_drive_mm) or not 0 <= pin_drive_mm <= .1:
        raise ValueError("invalid pin drive")
    if not math.isfinite(clearance_mm) or not 0 <= clearance_mm <= .05:
        raise ValueError("invalid radial clearance")
    sizes = tuple(float(s) for s in mesh_sizes_mm)
    if len(sizes) not in (3,4) or not all(
        math.isfinite(s) and 1 <= s <= 15 for s in sizes
    ) or not all(a > b for a,b in zip(sizes,sizes[1:])):
        raise ValueError("mesh sizes must strictly decrease across 3–4 levels")
    sweep_drives = tuple(float(v) for v in sweep_drives_mm)
    if (
        len(sweep_drives) not in (3,4,5,6)
        or not all(math.isfinite(v) and 0 <= v <= .1 for v in sweep_drives)
        or not all(a < b for a,b in zip(sweep_drives,sweep_drives[1:]))
    ):
        raise ValueError("sweep drives must contain 3–6 increasing values [0,0.1] mm")
    trial_report = read_physical_trials(physical_csv) if physical_csv else None
    output = Path(outdir).expanduser().resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("output directory must be empty to protect prior evidence")
    output.mkdir(parents=True, exist_ok=True)
    step = output / "bracket.step"
    geometry = generate_bracket_reference_step(spec, step)
    numeric = audit_two_pin_contact(
        step, mesh_sizes_mm=sizes,
        centers_xy_mm=geometry["cylindrical_through_hole_centers_xy_mm"],
        hole_d_mm=geometry["geometry_dimensions_mm"]["hole_d_mm"],
        thickness_mm=geometry["geometry_dimensions_mm"]["t_mm"],
        right_pin_drive_mm=pin_drive_mm,
        radial_clearance_mm=clearance_mm,
    )
    numeric["generated_step_provenance"] = geometry
    from .mechanical_contact_sweep import run_contact_displacement_sweep
    sweep = run_contact_displacement_sweep(
        step,
        centers_xy_mm=geometry["cylindrical_through_hole_centers_xy_mm"],
        hole_d_mm=geometry["geometry_dimensions_mm"]["hole_d_mm"],
        thickness_mm=geometry["geometry_dimensions_mm"]["t_mm"],
        pin_drives_mm=sweep_drives,
        mesh_target_mm=sizes[0],
        radial_clearance_mm=clearance_mm,
    )
    operator = make_operator_review(numeric, trial_report)
    if sweep["blockers"]:
        operator["primary_blockers"] = sorted(set(
            operator["primary_blockers"] + sweep["blockers"]
        ))
    report = {
        "schema_version": "hardware_splicer.contact_workbench_v1",
        "source_spec_sha256": "sha256:" + hashlib.sha256(
            source.read_bytes()
        ).hexdigest(),
        "contact_audit": numeric,
        "physical_trials": trial_report,
        "simulated_pin_sweep": sweep,
        "operator_review": operator,
        "fabrication_authorized": False,
        "release_authorized": False,
    }
    (output/"evidence.json").write_text(
        json.dumps(report, indent=2, allow_nan=False)+"\n", encoding="utf-8"
    )
    (output/"review.html").write_text(
        render_html_report(report), encoding="utf-8"
    )
    with (output/"predicted_load_curve.csv").open(
        "w",encoding="utf-8",newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=(
            "pin_drive_mm", "force_transferred_n",
            "first_pin_contact_nodes", "second_pin_contact_nodes",
            "global_sampled_peak_stress_pa",
        ))
        writer.writeheader()
        for row in sweep["levels"]:
            writer.writerow({
                field: row[field] for field in writer.fieldnames
            })
    (output/"remaining_actions.txt").write_text(
        "\n".join(
            f"{i}. {item}" for i,item in enumerate(operator["next_actions"],1)
        )+"\n",encoding="utf-8"
    )
    return report


def main(argv: list[str] | None = None) -> int:
    p=argparse.ArgumentParser(
        description="Produce self-contained contact FEM evidence and an offline review"
    )
    p.add_argument("--spec-json",required=True,type=Path)
    p.add_argument("--output-dir",required=True,type=Path)
    p.add_argument("--physical-trials-csv",type=Path)
    p.add_argument("--mesh-study-mm",type=float,nargs="+",default=[8,6,5])
    p.add_argument("--drive-mm",type=float,default=.02)
    p.add_argument("--sweep-mm",type=float,nargs="+",default=[0,.01,.02,.04])
    p.add_argument("--clearance-mm",type=float,default=.005)
    args=p.parse_args(argv)
    result=run_contact_workbench(
        spec_file=args.spec_json, outdir=args.output_dir,
        mesh_sizes_mm=tuple(args.mesh_study_mm),
        pin_drive_mm=args.drive_mm,
        clearance_mm=args.clearance_mm,
        physical_csv=args.physical_trials_csv,
        sweep_drives_mm=args.sweep_mm,
    )
    print(
        "Contact investigation completed; structural release remains blocked. "
        f"View {args.output_dir/'review.html'} or {args.output_dir/'evidence.json'}"
    )
    return 2 if result["operator_review"]["primary_blockers"] else 0


if __name__=="__main__":
    raise SystemExit(main())
