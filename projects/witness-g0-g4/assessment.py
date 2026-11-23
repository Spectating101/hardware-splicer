#!/usr/bin/env python3
"""Read-only G0–G4 research gates for the unbuilt 5 V HS ↔ Policy Lab witness.

This verifier can establish consistency of declared documents and models only.
It deliberately has NO path that authorizes construction, procurement, energizing
equipment, metrological accuracy, financial issuance, or physical certification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
CAMPAIGN_SCHEMA = "hs.witness_g0_g4_campaign.experimental.v1"
ASSESSMENT_SCHEMA = "hs.witness_g0_g4_assessment.experimental.v1"
REQUIRED_STEPS = ("G0", "G1", "G2", "G3", "G4")


class Hold(ValueError):
    """Source integrity or semantic validation failed; do not claim release."""


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def positive(value, name):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value <= 0:
        raise Hold(f"{name} must be a positive finite number")
    return float(value)


def _distinct_json(p):
    def pairs(items):
        data = {}
        for key, value in items:
            if key in data:
                raise Hold(f"duplicate JSON key {key}")
            data[key] = value
        return data

    def reject_nonfinite(value):
        raise Hold(f"nonfinite JSON value {value}")
    try:
        obj = json.loads(p.read_text(encoding="utf-8"), object_pairs_hook=pairs,
                         parse_constant=reject_nonfinite)
    except (OSError, json.JSONDecodeError) as exc:
        raise Hold(f"failed reading input JSON: {p}") from exc
    if not isinstance(obj, dict):
        raise Hold("root must be JSON object")
    return obj


def validate(doc, repo=REPO):
    if doc.get("schema") != CAMPAIGN_SCHEMA:
        raise Hold("unknown research campaign schema")
    if set(doc) != {"schema", "campaign_id", "source", "criteria", "candidates",
                    "selected_for_digital_screen", "engineering_provenance",
                    "measurement_protocol", "economics"}:
        raise Hold("campaign keys missing or unexpected")
    if not isinstance(doc["campaign_id"], str) or not doc["campaign_id"].strip():
        raise Hold("invalid campaign identifier")
    source = doc["source"]
    if source.get("revision_status") != "ORIGINAL_UNCHANGED":
        raise Hold("original source may not be overwritten by a trial")
    rel = source.get("station_spec")
    if not isinstance(rel, str) or rel.startswith("/") or ".." in Path(rel).parts:
        raise Hold("station source must be a relative path under repository")
    expected = source.get("sha256")
    if not isinstance(expected, str) or len(expected) != 64 or any(x not in "0123456789abcdef" for x in expected):
        raise Hold("station digest not a canonical SHA-256")
    path = repo / rel
    if digest(path.read_bytes()) != expected:
        raise Hold("station design source digest mismatch")
    station = _distinct_json(path)
    if station.get("nominal_voltage_v") != 5 or station.get("maximum_bus_voltage_v") != 5.25 or station.get("maximum_power_w") != 2.5:
        raise Hold("original station voltage or power contract changed")
    c = doc["criteria"]
    if set(c) != {"bus_min_v", "bus_max_v", "load_power_ceiling_w", "design_reserve_fraction",
                   "minimum_load_current_a", "series_resistance_max_ohm", "max_source_current_a_assumption"}:
        raise Hold("criteria keys missing or changed")
    for key in c:
        positive(c[key], key)
    if c["bus_max_v"] != station["maximum_bus_voltage_v"] or c["load_power_ceiling_w"] != station["maximum_power_w"]:
        raise Hold("criteria exceed original station contract")
    if c["bus_min_v"] >= c["bus_max_v"] or not 0 < c["design_reserve_fraction"] < 1:
        raise Hold("invalid voltage range / reserve")
    if c["max_source_current_a_assumption"] > station["monitor_headroom_a"]:
        raise Hold("assumed current limit exceeds monitor headroom")
    candidates = doc["candidates"]
    if not isinstance(candidates, list) or len(candidates) < 3:
        raise Hold("not enough candidate/negative controls")
    names = []
    for item in candidates:
        if set(item) != {"id", "ohms", "tolerance_pct", "qualification", "source_url"}:
            raise Hold("candidate fields invalid")
        if not isinstance(item["id"], str) or not item["id"]:
            raise Hold("candidate ID missing")
        names.append(item["id"])
        positive(item["ohms"], "ohms")
        tol = positive(item["tolerance_pct"], "tolerance_pct")
        if tol >= 100 or item["qualification"] not in {
            "ORIGINAL_CONTROL", "UNSELECTED_HS_360_MODEL", "UNSELECTED_HS_359_MODEL",
            "MANUFACTURER_IDENTIFIED_NOT_PROCURED", "CURRENT_FLOOR_NEGATIVE_CONTROL"
        }:
            raise Hold("invalid tolerance or candidate authority")
        if item["source_url"] is not None and (not isinstance(item["source_url"], str) or
                                                not item["source_url"].startswith("https://")):
            raise Hold("candidate citation must be HTTPS")
    if len(set(names)) != len(names) or doc["selected_for_digital_screen"] not in names:
        raise Hold("duplicate candidate or missing selected digital case")
    e = doc["engineering_provenance"]
    m = doc["measurement_protocol"]
    money = doc["economics"]
    known_false = (
        "load_physical_fit_verified", "load_stock_in_taiwan_verified", "load_thermal_mounting_verified",
        "reference_shunt_calibration_verified", "dmm_serial_and_calibration_verified",
        "reference_two_channel_timing_verified", "supply_selected_or_bench_verified",
        "source_output_ceiling_verified", "independent_overvoltage_protection_verified",
        "source_fault_current_characterized", "fuse_and_holder_mpn_selected",
        "fuse_dc_interruption_coordination_verified", "earth_isolation_and_i2c_verified",
        "wiring_mechanics_thermal_verified", "original_board_fabricated",
        "external_second_operator_verified"
    )
    if not isinstance(e, dict) or any(e.get(key) is not False for key in known_false):
        raise Hold("unauthenticated physical qualification/promotion attempt")
    if (m.get("acquisition_class") != "NO_PHYSICAL_CAPTURE" or any(m.get(key) is not None for key in
            ("operator_identity", "device_serials", "calibration_documents",
             "independent_reference_capture", "utc_offset_calibration"))):
        raise Hold("unauthenticated measurement submission; this experiment is only a build plan")
    if not isinstance(money, dict) or any(value is not False for value in money.values()):
        raise Hold("economic claims require distinct authenticated measurements and transactions")
    positive(m["reference_shunt_ohms_nominal"], "reference_shunt_ohms_nominal")
    positive(m["reference_shunt_tolerance_pct_uncharacterized"], "reference_shunt_tolerance_pct_uncharacterized")
    positive(m["dmm_200mv_range_v"], "dmm_200mv_range_v")
    positive(m["dmm_accuracy_reading_pct"], "dmm_accuracy_reading_pct")
    positive(m["dmm_accuracy_range_pct"], "dmm_accuracy_range_pct")
    positive(m["screen_threshold_pct_synthetic_only"], "screen_threshold_pct_synthetic_only")
    return station


def evaluate(doc, repo=REPO):
    validate(doc, repo)
    c = doc["criteria"]
    rows = []
    for cand in doc["candidates"]:
        ohms = cand["ohms"]
        tol = cand["tolerance_pct"] / 100
        min_r, max_r = ohms * (1 - tol), ohms * (1 + tol)
        pmax = c["bus_max_v"] ** 2 / min_r
        imax = c["bus_max_v"] / min_r
        imin = c["bus_min_v"] / (max_r + c["series_resistance_max_ohm"])
        checks = {
            "under_original_power_ceiling": pmax <= c["load_power_ceiling_w"],
            "has_required_design_reserve": pmax <= c["load_power_ceiling_w"] * (1 - c["design_reserve_fraction"]),
            "above_test_reference_current_floor": imin >= c["minimum_load_current_a"],
            "below_assumed_supply_current_limit": imax < c["max_source_current_a_assumption"],
            "load_rated_power_ge_worst_modeled": (
                pmax <= doc["engineering_provenance"]["load_nominal_w_rating"]
                if cand["id"] == doc["selected_for_digital_screen"] else None)
        }
        rows.append({
            "id": cand["id"], "nominal_ohms": ohms, "tolerance_pct": cand["tolerance_pct"],
            "source": cand["source_url"], "qualification": cand["qualification"],
            "worst_normal_load_power_w": round(pmax, 8),
            "worst_normal_current_a": round(imax, 8),
            "minimum_normal_current_a": round(imin, 8),
            "checks": checks,
            "digital_pass": all(value for value in checks.values() if value is not None),
            "physical_part_qualified": False
        })
    chosen = next(row for row in rows if row["id"] == doc["selected_for_digital_screen"])
    m = doc["measurement_protocol"]
    vmin = chosen["minimum_normal_current_a"] * m["reference_shunt_ohms_nominal"]
    # Datasheet ±(% reading + % of 200 mV range); NOT a calibration certificate or traceable uncertainty.
    dmm_bound_v = (
        vmin * m["dmm_accuracy_reading_pct"] / 100 +
        m["dmm_200mv_range_v"] * m["dmm_accuracy_range_pct"] / 100
    )
    dmm_bound_percent = 100 * dmm_bound_v / vmin
    combined_illustrative_bound = m["reference_shunt_tolerance_pct_uncharacterized"] + dmm_bound_percent
    gates = {
        "G0": {
            "status": "DIGITAL_MODEL_PASS_PHYSICAL_BUILD_HOLD" if chosen["digital_pass"] else "DESIGN_REJECTED",
            "passed_numerical_corner_checks": chosen["digital_pass"],
            "next_evidence": ["exact purchased load model/lot and measured resistance", "thermal mounting and derating",
                              "selected DC-rated fuse+holder and fault-current/time-current coordination",
                              "actual isolated/limited supply and independent overvoltage protection",
                              "earth/I2C isolation, connectors and safety sign-off"]
        },
        "G1": {"status": "HOLD_NO_PHYSICAL_EVIDENCE",
               "next_evidence": ["identified operator and controlled bench", "meter/supply serial numbers",
                                 "reference calibration and original raw capture", "documented UTC alignment",
                                 "signed/source-custody receipt from a distinct authorized operator"]},
        "G2": {"status": "HOLD_UNCALIBRATED_REFERENCE",
               "next_evidence": ["traceable independent reference calibration including shunt resistance",
                                 "measured covariance/timebase/shunt thermal drift and uncertainty",
                                 "pre-registered physical comparison tolerance and negative controls"]},
        "G3": {"status": "SOFTWARE_FIXTURE_ONLY",
               "next_evidence": ["authentic G1/G2 source evidence", "unchanged Policy Lab PLRS-6 original-byte intake",
                                 "independent review, strict decision and reproduction"]},
        "G4": {"status": "NOT_ASSESSED",
               "next_evidence": ["authenticated electrical cost and billing period",
                                 "independently verified useful output and cost allocation",
                                 "actual invoices/contracts/revenues or explicitly state unknown"]}
    }
    ret = {
        "schema": ASSESSMENT_SCHEMA,
        "campaign_id": doc["campaign_id"],
        "source_status": "ORIGINAL_PINNED_UNMODIFIED",
        "original_station_sha256": doc["source"]["sha256"],
        "digital_candidate": chosen["id"],
        "candidates": rows,
        "reference_sensitivity_screen": {
            "minimum_current_a": chosen["minimum_normal_current_a"],
            "nominal_minimum_10mohm_reference_shunt_mv": round(vmin * 1000, 6),
            "manufacturer_dmm_bound_microvolts_illustrative": round(dmm_bound_v * 1e6, 6),
            "manufacturer_dmm_bound_percent_illustrative": round(dmm_bound_percent, 6),
            "uncalibrated_shunt_tolerance_percent": m["reference_shunt_tolerance_pct_uncharacterized"],
            "simple_sum_percent_not_a_traceable_uncertainty": round(combined_illustrative_bound, 6),
            "fixture_only_sensitivity_threshold_pct": m["screen_threshold_pct_synthetic_only"],
            "g2_physical_agreement_verified": False,
            "note": "Not an uncertainty budget. DMM datasheet at 23±5°C / 1 year alone plus nominal shunt tolerance cannot validate a 0.75% physical threshold."
        },
        "gates": gates,
        "build_authorized": False,
        "power_on_authorized": False,
        "physical_measurements_established": False,
        "policy_lab_financial_claim_authorized": False,
        "not_established": ["physical source authenticity", "primary/reference calibration",
                            "safe equipment/protection", "physical source-clock independence",
                            "G3 external verified intake", "G4 economic transactions"]
    }
    return ret


def build(doc, repo=REPO):
    results = evaluate(doc, repo)
    results["campaign_sha256"] = digest(canonical(doc))
    results["decision_sha256"] = digest(canonical(results))
    return results


def verify(doc, outcome, repo=REPO):
    expected = build(doc, repo)
    if canonical(expected) != canonical(outcome):
        raise Hold("assessment does not replay exactly against frozen input")
    return {"verified": True, "physical_authorized": False, "monetary_authorized": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", type=Path, default=HERE / "campaign.json")
    parser.add_argument("--out", type=Path, help="optional new JSON path; never overwrites")
    parser.add_argument("--verify", type=Path, help="existing JSON assessment to verify")
    args = parser.parse_args()
    doc = _distinct_json(args.campaign)
    if args.verify:
        print(json.dumps(verify(doc, _distinct_json(args.verify)), indent=2))
        return
    result = build(doc)
    if args.out:
        if args.out.exists():
            parser.error("Output already exists: cannot overwrite audit evidence")
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"selected_digital_candidate": result["digital_candidate"],
                      "gates": {k: v["status"] for k, v in result["gates"].items()},
                      "build_authorized": False, "physical_power_on": False,
                      "candidate_corners": len(result["candidates"]),
                      "source_sha256": result["original_station_sha256"]}, indent=2))


if __name__ == "__main__":
    main()
