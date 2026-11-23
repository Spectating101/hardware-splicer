#!/usr/bin/env python3
"""G0 candidate load screening + native INA228/PL TEST_FIXTURE replay.

Independent normal-operation bounds include manufacturing tolerance AND
resistor TCR across the candidate's catalogue temperature limits. The
unmodified KiCad v0 board can connect any properly fitted *external* load;
this experiment generates a new isolated 12-ohm replay without replacing the
original published 10-ohm fixture or permitting fabrication or power-on.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
HS_ROOT = HERE.parents[2]
sys.path.insert(0, str(HS_ROOT / "src"))

from hardware_splicer.dc_measurement_station import StationSpec, json_bytes
from hardware_splicer.ina228_fixture import FixtureClock, FixtureI2C
from hardware_splicer.ina228_logger import INA228, capture
from measurement_screen import screen

DEFAULT_MATRIX = HERE / "load-candidate-matrix-v1.json"
SOURCE_TOTAL_R_OHMS = .075  # Unmeasured v0 SPICE assumption, not an approval input
EXPECTED_PARTS = {
    "economy_12r_sqp10ajb_12r": ("YAGEO", "SQP10AJB-12R", 12, 5, 300, -55, 155, 10),
    "precision_12r_re65g12r0c02": ("Vishay Dale", "RE65G12R0C02", 12, 1, 20, -55, 250, 10),
}
EXPECTED_CANDIDATES = set(EXPECTED_PARTS)


def digest(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def positive(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be positive finite")
    return float(value)


def load_bound(row: dict, envelope: dict) -> dict:
    v = positive(envelope["maximum_j2_voltage_v"], "maximum_j2_voltage_v")
    w_limit = positive(envelope["maximum_load_power_w"], "maximum_load_power_w")
    ref_temp = envelope["reference_temperature_c"]
    if not isinstance(ref_temp, (float, int)) or not math.isfinite(ref_temp):
        raise ValueError("reference temperature invalid")
    r0 = positive(row["value_ohms"], "value_ohms")
    rating = positive(row["power_rating_w"], "power_rating_w")
    tolerance = positive(row["tolerance_percent"], "tolerance_percent") / 100
    tcr = positive(row["tcr_absolute_ppm_per_c"], "tcr_absolute_ppm_per_c") / 1e6
    temp = row["operating_temperature_c"]
    a, b = float(temp["min"]), float(temp["max"])
    if not (math.isfinite(a) and math.isfinite(b) and a < ref_temp < b and 0 < tolerance < 1):
        raise ValueError("temperature range/tolerance invalid")
    dtemp = max(abs(a-ref_temp), abs(b-ref_temp))
    thermal_fraction = tcr * dtemp
    if not 0 <= thermal_fraction < 1:
        raise ValueError("TCR bound would produce zero or negative resistance")
    min_ohms = r0 * (1-tolerance) * (1-thermal_fraction)
    power = v*v / min_ohms
    return {
        "part_id": row["id"],
        "mpn": row["mpn"],
        "nominal_ohms": r0,
        "min_resistance_ohms_conservative": min_ohms,
        "assumed_tolerance_pct": tolerance*100,
        "assumed_tcr_abs_ppm_per_c": tcr*1e6,
        "max_delta_temperature_from_reference_c": dtemp,
        "maximum_normal_load_power_w": power,
        "maximum_normal_load_current_a": v / min_ohms,
        "claimed_load_power_ceiling_w": w_limit,
        "power_ceiling_math_satisfied": power <= w_limit,
        "rated_load_watts_catalog": rating,
        "physical_derating_thermal_mount_verified": False,
        "safety_approval": False,
        "protection_coordination_verified": False,
    }


def parse_spice_value(text: str, name: str) -> float:
    m = re.search(r"(?m)^"+re.escape(name)+r"\s*=\s*([-+0-9.eE]+)", text)
    if not m:
        raise RuntimeError("ngspice missing field "+name)
    return float(m.group(1))


def run_spice(volts: float, load_ohms: float, series_ohms: float) -> dict:
    for name, v in (("volts",volts),("load",load_ohms)):
        positive(v,name)
    if not math.isfinite(series_ohms) or series_ohms < 0:
        raise ValueError("series resistance invalid")
    # 0-ohm series is implemented as a conductor, not a zero-ohm resistor.
    src = "V_SRC supply 0 DC %.12g\n" % volts
    if series_ohms:
        src += "R_SERIES supply load %.12g\n" % series_ohms
    else:
        src += "R_LOAD supply 0 %.12g\n" % load_ohms
    if series_ohms:
        src += "R_LOAD load 0 %.12g\n" % load_ohms
    src += ".control\nset noaskquit\nop\nprint i(v_src)\n"
    if series_ohms:
        src += "print v(load)\n"
    else:
        src += "print v(supply)\n"
    src += "quit\n.endc\n.end\n"
    # A fixed source title is required by ngspice and deliberately unphysical.
    run = subprocess.run(["ngspice","-b"], input="Load revision G0, simulation only\n"+src,
                         text=True, capture_output=True, timeout=20)
    if run.returncode:
        raise RuntimeError("ngspice execution failed: "+run.stderr[-350:])
    amps = -parse_spice_value(run.stdout,"i(v_src)")
    v_load = parse_spice_value(run.stdout,"v(load)" if series_ohms else "v(supply)")
    p = amps*v_load
    oracle_i = volts/(series_ohms+load_ohms)
    oracle_p = oracle_i**2*load_ohms
    if not math.isclose(amps,oracle_i,rel_tol=3e-6) or not math.isclose(p,oracle_p,rel_tol=3e-6):
        raise AssertionError("SPICE and independent series-network calculation disagree")
    return {"source_v":volts, "load_ohms":load_ohms,
            "assumed_series_ohms":series_ohms,
            "load_v":v_load, "load_current_a":amps, "load_power_w":p,
            "spice_matched_independent_arithmetic":True,
            "simulation_only":True}


def make_fixture(dest: Path, station: StationSpec, model: dict) -> dict:
    clock = FixtureClock("2026-11-19T23:59:59Z")
    bus = FixtureI2C(clock, shunt_ohm=station.shunt_ohm,
                     voltage_v=model["load_v"], current_a=model["load_current_a"])
    capture(INA228(bus,station,clock=clock),dest/"primary",samples=183,
            period_seconds=1,clock=clock,
            clock_source="Synthetic G0 test fixture clock; NOT a physical instrument")
    first = datetime(2026,11,19,23,59,59,tzinfo=timezone.utc)
    with (dest/"reference-fixture.csv").open("x",newline="",encoding="utf-8") as out:
        writer=csv.writer(out)
        writer.writerow(("timestamp_utc","voltage_v","shunt_voltage_v"))
        for i in range(183):
            t=first+timedelta(seconds=i,microseconds=173000)
            writer.writerow((t.isoformat(timespec="microseconds").replace("+00:00","Z"),
                             "%.9f" % model["load_v"],
                             "%.11f" % (model["load_current_a"]*station.reference_shunt_ohm)))
    cfg={"schema":"policylab.dc_bench_capture_config.v1",
         "capture_kind":"TEST_FIXTURE","channel":"source_dc",
         "window":{"start_utc":"2026-11-20T00:00:00Z",
                   "end_utc":"2026-11-20T00:03:00Z"},
         "maximum_sample_gap_seconds":1.5,
         "primary":{"device_id":"simulated_witness_12r_ina228",
                    "logger_id":"simulated_witness_12r_logger"},
         "reference":{"device_id":"simulated_witness_12r_ref",
                      "logger_id":"simulated_nonindependent_reference",
                      "shunt_resistance_ohms":station.reference_shunt_ohm,
                      "voltage_current_pairing":"Derived from same synthetic model, not independent acquisition"},
         "environment":{"solar_panel_installed":False,"battery_installed":False,
                        "utility_grid_connected":False}}
    (dest/"capture-config.json").write_bytes(json_bytes(cfg))
    primary=dest/"primary"
    strict=screen(primary/"samples.csv",dest/"reference-fixture.csv",
                  primary/"session.json",primary/"registers.jsonl")
    if strict["decision"]!="PASS_FIXTURE_DISCRIMINATION_ONLY" or strict["physical_ready"]:
        raise AssertionError("New 12-ohm register fixture unexpectedly disagrees or promotes physical claims")
    (dest/"strict-screen.json").write_bytes(json_bytes(strict))
    return strict


def run_policy_lab(pl_root: Path, dest: Path) -> dict:
    converter=pl_root/"scripts/equipment/dc_bench_capture.mjs"
    if not converter.exists():
        raise FileNotFoundError("Frozen PL bridge missing: "+str(converter))
    p=dest/"primary"
    command=["node",str(converter),"--primary",str(p/"samples.csv"),
             "--reference",str(dest/"reference-fixture.csv"),
             "--primary-sidecar",str(p/"session.json"),
             "--primary-registers",str(p/"registers.jsonl"),
             "--config",str(dest/"capture-config.json"),
             "--out",str(dest/"policy-lab-intake")]
    done=subprocess.run(command,cwd=pl_root,capture_output=True,text=True,timeout=60)
    if done.returncode:
        raise RuntimeError("Frozen PL bridge rejected synthetic candidate: "+done.stderr[-350:])
    result=json.loads((dest/"policy-lab-intake/intake-receipt.json").read_text())
    if result["decision"] != "TEST_FIXTURE_STRUCTURALLY_INGESTED_NO_PHYSICAL_CLAIMS" or result["physical_ready"] or result["spk_issuance_allowed"]:
        raise AssertionError("Policy Lab silently promoted fixture or changed receiver contract")
    return result


def main(argv=None) -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,required=True,help="Directory must not already exist")
    p.add_argument("--matrix",type=Path,default=DEFAULT_MATRIX)
    p.add_argument("--pl-root",type=Path)
    p.add_argument("--baseline-verification",type=Path,
                   help="Optional original 10R native KiCad + SPICE verification JSON")
    p.add_argument("--fail-if-held",action="store_true",
                   help="Return 2 for unresolved physical G0/G1 gates")
    args=p.parse_args(argv)
    matrix=json.loads(args.matrix.read_text())
    if matrix.get("schema")!="hardware_splicer.witness_load_candidate_matrix.v1":
        raise ValueError("Wrong candidate input schema")
    candidates=matrix["candidates"]
    if len(candidates)!=2 or {x["id"] for x in candidates}!=EXPECTED_CANDIDATES:
        raise ValueError("Expected two independent named part profiles")
    if matrix["maximum_j2_voltage_v"]!=5.25 or matrix["maximum_load_power_w"]!=2.5:
        raise ValueError("Deviation from original power envelope requires engineering review")
    if matrix["series_resistance_ohms_simulated"]!=SOURCE_TOTAL_R_OHMS:
        raise ValueError("Unverified series-resistance model changed without review")
    for row in candidates:
        actual=(row.get("manufacturer"),row.get("mpn"),row.get("value_ohms"),
                row.get("tolerance_percent"),row.get("tcr_absolute_ppm_per_c"),
                row.get("operating_temperature_c",{}).get("min"),
                row.get("operating_temperature_c",{}).get("max"),
                row.get("power_rating_w"))
        if actual != EXPECTED_PARTS[row["id"]]:
            raise ValueError("Part specification changed: independent datasheet review required")
    checks=[]
    for c in candidates:
        bound=load_bound(c,matrix)
        spice=run_spice(matrix["maximum_j2_voltage_v"],
                        bound["min_resistance_ohms_conservative"],0)
        bound["zero_drop_ngspice"]=spice
        if not math.isclose(bound["maximum_normal_load_power_w"],
                            spice["load_power_w"],rel_tol=2e-6):
            raise AssertionError("Part-model max power mismatch against independent SPICE")
        checks.append(bound)
    by_id={c["part_id"]:c for c in checks}
    # The sourced economical part fails the deliberately unrestricted full
    # catalogue temperature bound; the narrower 1% /20ppm option passes math.
    if (by_id["economy_12r_sqp10ajb_12r"]["power_ceiling_math_satisfied"]
        or not by_id["precision_12r_re65g12r0c02"]["power_ceiling_math_satisfied"]):
        raise AssertionError("Candidate acceptance contract changed; independent review required")
    original_check=run_spice(5,10,SOURCE_TOTAL_R_OHMS)
    new_normal=run_spice(5,12,SOURCE_TOTAL_R_OHMS)
    if args.baseline_verification:
        v=json.loads(args.baseline_verification.read_text())
        if v.get("status")!="SOFTWARE_DESIGN_VALIDATED_ONLY" or v.get("native_erc")!="ZERO_VIOLATIONS" or not v.get("native_drc","").startswith("ZERO_VIOLATIONS"):
            raise ValueError("Original KiCad native verification not clean")
        if not math.isclose(v["spice_load_power_w"],original_check["load_power_w"],rel_tol=2e-6):
            raise ValueError("Native original 10-ohm output disagrees with independent SPICE")
    dest=args.out.resolve()
    dest.mkdir(parents=True,exist_ok=False)
    station=StationSpec.from_dict(json.loads((HERE/"station-spec-5v.json").read_text()))
    strict=make_fixture(dest,station,new_normal)
    pl=run_policy_lab(args.pl_root.resolve(),dest) if args.pl_root else None
    ref_drop_v = new_normal["load_current_a"] * station.reference_shunt_ohm
    # An illustrative DMM spec from the earlier audit, NOT a calibrated
    # instrument: +/- (0.015% reading + 0.004% of 200 mV range).
    dmm_absolute_v = .00015 * ref_drop_v + .00004 * .2
    optimistic_reference_uncertainty_pct = (
        station.reference_shunt_tolerance_percent + 100*dmm_absolute_v/ref_drop_v
    )
    report={
        "schema":"hardware_splicer.witness_g0_load_candidate_replay.v1",
        "status":"HOLD_NO_PHYSICAL_SELECTION_OR_QUALIFICATION",
        "fabrication_allowed":False,"physical_ready":False,
        "source_purchased":False,"fuse_coordination_verified":False,
        "reference_independence_verified":False,
        "reference_calibration_verified":False,
        "thermal_mount_verified":False,
        "external_timebase_verified":False,
        "human_operator_signed_off":False,
        "selected_design_for_software_replay":"precision_12r_re65g12r0c02",
        "candidate_screening":checks,
        "original_v0_10ohm_unchanged":original_check,
        "revision_12ohm_nominal_model":new_normal,
        "revision_3min_model_wh":new_normal["load_power_w"]*180/3600,
        "provisional_reference_uncertainty_floor":{
            "nominal_shunt_signal_mv":ref_drop_v*1000,
            "illustrative_dmm_abs_error_uv":dmm_absolute_v*1e6,
            "optimistic_simple_worst_case_pct":optimistic_reference_uncertainty_pct,
            "one_percent_comparison_supported":False,
            "calibration_state":"NOT_CHARACTERIZED; NOT AN ACCEPTANCE BUDGET",
            "missing":"Primary ADC/shunt uncertainty, reference calibration, thermal EMF, clock pairing, drift, voltage channel, covariance"
        },
        "new_fixture":{"primary_samples":183,"strict_screen_decision":strict["decision"],
                       "primary_sha256":digest(dest/"primary/samples.csv"),
                       "reference_sha256":digest(dest/"reference-fixture.csv")},
        "policy_lab_decision":pl["decision"] if pl else "NOT_RUN",
        "provenance":{"matrix_sha256":digest(args.matrix),
                      "original_pcb_sha256":digest(HERE/"low_voltage_witness_fixture_v0.kicad_pcb"),
                      "original_schematic_sha256":digest(HERE/"low_voltage_witness_fixture_v0.kicad_sch"),
                      "original_spec_sha256":digest(HERE/"station-spec-5v.json"),
                      "original_verification_sha256":digest(args.baseline_verification) if args.baseline_verification else None},
        "limitations":[
            "Neither candidate physically procured or mounted.",
            "Resistance/tolerance/TCR arithmetic assumes listed properties for an unverified delivered part.",
            "Manufacturer power rating needs actual mounting/ambient/thermal derating validation.",
            "5.25 V maximum load bus is not protected or independently measured.",
            "Series resistances are unmeasured assumptions; zero series resistance is used for conservative power upper bound.",
            "Source current limit and fuse link coordination are not verified.",
            "Full physically defensible measurement uncertainty is absent.",
            "Reference simulated from same idealized model and is NOT an independent instrument.",
            "The KiCad board is unchanged; native original electrical checks remain separately required.",
            "No approval to fabricate or energize hardware."
        ]
    }
    (dest/"report.json").write_bytes(json_bytes(report))
    print(json.dumps({"status":report["status"],
                      "economy_full_temperature_power_w":by_id["economy_12r_sqp10ajb_12r"]["maximum_normal_load_power_w"],
                      "precision_full_temperature_power_w":by_id["precision_12r_re65g12r0c02"]["maximum_normal_load_power_w"],
                      "precision_full_temperature_within_2_5w":True,
                      "synthetic_3min_wh":report["revision_3min_model_wh"],
                      "PL":report["policy_lab_decision"],
                      "strict_screen":strict["decision"],
                      "out":str(dest)},indent=2))
    return 2 if args.fail_if_held else 0


if __name__=="__main__":
    raise SystemExit(main())
