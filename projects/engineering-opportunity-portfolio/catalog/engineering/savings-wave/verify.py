"""Build and compare the internal-use and narrowly scoped farm trials."""

import argparse
import csv
import itertools
import json
import math
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def require(condition, message):
    if not condition:
        raise ValueError(message)


def export(path, fields, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(fields)
        writer.writerows(rows)
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def p116(c, out):
    result = {}
    for label, throat in (("candidate", c["throat_mm"]), ("narrow-control", c["control_throat_mm"])):
        pot = c["pot_width_mm"] + c["pot_overfill_mm"]
        rows = []
        for index in range(c["plugs"]):
            yaw = c["yaw_range_deg"][index % len(c["yaw_range_deg"])]
            rotated = pot * (math.cos(math.radians(yaw)) + abs(math.sin(math.radians(yaw))))
            usable = throat - c["sheet_tol_mm"] - 2 * c["lateral_runout_mm"]
            depth_error = c["static_depth_error_mm"] + c["longitudinal_offset_mm"] * c["local_slope_pct"] / 100
            rows.append((index + 1, round(index * c["pitch_mm"], 3), yaw, round(usable - rotated, 3),
                         c["target_depth_mm"] - depth_error, c["target_depth_mm"] + depth_error))
        table = export(out / f"chain-route-{label}.csv",
                       ("plug", "nominal_station_mm", "yaw_deg", "throat_clearance_mm", "min_depth_mm", "max_depth_mm"), rows)
        snag_candidates = sum(float(r["throat_clearance_mm"]) < c["wanted_clearance_mm"] for r in table)
        depth = max(abs(float(r[col]) - c["target_depth_mm"]) for col in ("min_depth_mm", "max_depth_mm")
                    for r in table)
        require((snag_candidates < 5 and depth <= c["max_depth_error_mm"]) == (label == "candidate"),
                f"P116 throat decision differed for {label}")
        result[label] = dict(plugs_examined=len(table), clearance_gate_misses=snag_candidates,
                             worst_clearance_mm=min(float(r["throat_clearance_mm"]) for r in table),
                             worst_modeled_depth_error_mm=depth)
    return result


def p117(c, out):
    result = {}
    start = (c["bar_length_mm"] - (c["tines"] - 1) * c["tine_centers_mm"]) / 2
    tines = export(out / "tine-spacing.csv", ("tine", "center_mm"),
                   ((n + 1, start + n * c["tine_centers_mm"]) for n in range(c["tines"])))
    require(float(tines[0]["center_mm"]) > 0 and float(tines[-1]["center_mm"]) < c["bar_length_mm"],
            "P117 tine schedule extends past bar")
    for label, tube in (("candidate", c["candidate_tube"]), ("thin-control", c["control_tube"])):
        values = []
        for od_sign, wall_sign in itertools.product((-1, 1), repeat=2):
            diameter = tube[0] + c["od_tol_mm"] * od_sign
            wall = tube[1] + c["wall_tol_mm"] * wall_sign
            interior = diameter - 2 * wall
            inertia = math.pi * (diameter**4 - interior**4) / 64
            stress = c["side_force_n"] * c["lever_mm"] * (diameter / 2) / inertia
            values.append((diameter, wall, round(interior, 3), round(stress, 3)))
        table = export(out / f"socket-{label}.csv", ("outer_mm", "wall_mm", "inner_mm", "model_root_stress_mpa"), values)
        worst = max(float(r["model_root_stress_mpa"]) for r in table)
        require((worst <= c["model_stress_gate_mpa"]) == (label == "candidate"), f"P117 root decision differed for {label}")
        result[label] = dict(tolerance_corners=len(table), worst_model_root_stress_mpa=worst)
    saving = c["catalog_buy_start_ntd"] - c["catalog_first_unit_ntd"]
    result["catalog_cost_sensitivity"] = dict(remaining_first_unit_headroom_ntd=round(saving, 2),
        first_unit_margin_after_scenario_ntd=round(saving - c["catalog_additional_case_ntd"], 2))
    return result


def p129(c, out):
    gain = c["gain"]
    offset = c["offset_adc"]
    uniform = c["uniform_levels"]
    scenarios = [("dark-cal", [0, 0, 0]), ("flat-cal", [c["calibration_light"]] * 3)]
    scenarios += [(f"uniform-{level}", [level] * 3) for level in uniform]
    scenarios.append(("screens", [uniform[-1] * fraction for fraction in c["screen_transmission"]]))
    rows = []
    for index, (scenario, levels) in enumerate(scenarios):
        signals = [round(g * level + z) + ((index + n) % 3 - 1) * c["voltage_noise_codes"]
                   for n, (g, level, z) in enumerate(zip(gain, levels, offset, strict=True))]
        rows.append((scenario, *signals))
    form = export(out / "relative-light-fixture.csv", ("mode", "sensor_a", "sensor_b", "sensor_c"), rows)
    logs = {r["mode"]: [int(r[key]) for key in ("sensor_a", "sensor_b", "sensor_c")] for r in form}
    cal_factor = [(flat - zero) / c["calibration_light"] for flat, zero in zip(logs["flat-cal"], logs["dark-cal"])]
    evaluation = [(mode, samples) for mode, samples in logs.items() if not mode.endswith("-cal")]
    result = {}
    for label, correct in (("calibrated", True), ("raw-control", False)):
        data = []
        for mode, samples in evaluation:
            values = [(value - zero) / scale for value, zero, scale in zip(samples, logs["dark-cal"], cal_factor)
                      ] if correct else samples
            spread = 100 * (max(values) - min(values)) / (sum(values) / len(values))
            data.append((mode, *(round(v, 5) for v in values), round(spread, 4)))
        measured = export(out / f"relative-light-{label}.csv", ("mode", "a", "b", "c", "spread_pct"), data)
        worst = max(float(r["spread_pct"]) for r in measured if r["mode"].startswith("uniform-"))
        screens = measured[-1]
        ranked = float(screens["a"]) > float(screens["b"]) > float(screens["c"])
        require((worst <= c["uniform_error_limit_pct"] and ranked) == correct, f"P129 normalization decision differed for {label}")
        result[label] = dict(uniform_levels=len(uniform), worst_uniform_spread_pct=round(worst, 2),
                             screen_order_preserved=ranked)
    return result


def pulse_logger(edges_ms, lockout_ms):
    """Debounce forward-only contact edges with a lockout relative to the last accepted event."""
    previous = None
    for stamp in edges_ms:
        if previous is None or stamp - previous >= lockout_ms:
            previous = stamp
            yield stamp


def p130(c, out):
    area_mm2 = math.pi * (c["collector_d_mm"] / 2)**2
    tip_ml = area_mm2 * c["mm_per_tip"] / 1000
    input_ml = area_mm2 * c["end_depth_mm"] / 1000
    truth = math.floor(input_ml / tip_ml)
    start = datetime.fromisoformat(c["start_utc"])
    result = {}
    for rate in c["equivalent_rate_mm_per_hour"]:
        gap_ms = c["mm_per_tip"] / rate * 3600000
        targets = [round(n * gap_ms) for n in range(1, truth + 1)]
        rows = export(out / f"contact-edges-{rate}.csv", ("edge_ms",),
                      ((first + bounce,) for first in targets for bounce in c["bounce_after_ms"]))
        edges = [int(r["edge_ms"]) for r in rows]
        rate_summary = {}
        for label, lockout in (("candidate", c["candidate_lockout_ms"]), ("long-control", c["control_lockout_ms"]),
                               ("unfiltered-control", c["overcount_control_ms"])):
            computed = []
            for index, stamp in enumerate(pulse_logger(edges, lockout), start=1):
                date = (start + timedelta(milliseconds=stamp)).isoformat(timespec="milliseconds")
                computed.append((date, stamp, round(index * c["mm_per_tip"], 5)))
            record = export(out / f"rainfall-{rate}-{label}.csv",
                            ("timestamp_utc", "elapsed_ms", "accumulated_mm"), computed)
            last = float(record[-1]["accumulated_mm"])
            err = abs(last - c["end_depth_mm"]) / c["end_depth_mm"] * 100
            duplicates = sum(int(r["elapsed_ms"]) not in targets for r in record)
            passes = err <= c["max_error_pct"] and len(record) == truth and duplicates == 0
            expected = label == "candidate" or (label == "long-control" and lockout <= gap_ms)
            require(passes == expected, f"P130 pulse decision differed for {rate} at {label}")
            rate_summary[label] = dict(accepted_tips=len(record), duplicate_tips=duplicates,
                                       delivered_depth_error_pct=round(err, 2))
        result[str(rate)] = rate_summary
    result["fixture"] = dict(input_volume_ml=round(input_ml, 2), volume_per_tip_ml=round(tip_ml, 3),
                             plotted_true_tips_per_rate=truth)
    return result


def p138(c, out):
    synthetic = []
    for reference in c["reference_m_s"] + c["below_threshold_m_s"]:
        for trial, gain_error in enumerate((-c["gain_tolerance_pct"], 0, c["gain_tolerance_pct"]), 1):
            gain = c["gain_hz_per_m_s"] * (1 + gain_error / 100)
            frequency = gain * (reference - c["slip_intercept_m_s"]) if reference >= c["stall_threshold_m_s"] else 0
            synthetic.append((reference, trial, round(frequency * c["gate_time_s"])))
    source = export(out / "flume-pulse-fixture.csv", ("reference_m_s", "trial", "gate_pulses"), synthetic)
    result = {}
    for label, intercept in (("calibrated", c["slip_intercept_m_s"]), ("zero-offset-control", 0)):
        rows = []
        for trial in source:
            pulses = int(trial["gate_pulses"])
            decoded = intercept + pulses / c["gate_time_s"] / c["gain_hz_per_m_s"] if pulses else None
            rows.append((trial["reference_m_s"], trial["trial"], pulses, decoded, "valid" if pulses else "no_rotation"))
        table = export(out / f"flume-{label}.csv", ("reference_m_s", "trial", "gate_pulses", "decoded_m_s", "state"), rows)
        estimates = {}
        for record in table:
            if record["state"] == "valid":
                estimates.setdefault(float(record["reference_m_s"]), []).append(float(record["decoded_m_s"]))
        worst = max(abs(actual - ref) for ref, trials in estimates.items() for actual in trials)
        repeatability = max(max(trials) - min(trials) for trials in estimates.values())
        stalls = [float(row["reference_m_s"]) for row in table if row["state"] == "no_rotation"]
        require(len(stalls) == 3 * len(c["below_threshold_m_s"]), "P138 stall is being reported as flow")
        require((worst <= c["max_error_m_s"] and repeatability <= c["max_repeatability_range_m_s"])
                == (label == "calibrated"), f"P138 scale decision differed for {label}")
        result[label] = dict(active_speed_points=len(estimates), stalled_replays=len(stalls),
                             max_error_m_s=round(worst, 4), largest_replicate_span_m_s=round(repeatability, 4))
    return result


def p140(c, out):
    result = {}
    for label, maximum_yaw in (("guided", c["candidate_yaw_deg"]), ("unguided-control", c["control_yaw_deg"])):
        report = {}
        for gap, nominal in zip(c["gap_mm"], c["profile_base_mm"], strict=True):
            rows = []
            for specimen in range(c["profile_count"]):
                should_pass = specimen % 2 == 0
                jitter = c["width_jitter_mm"] * ((specimen % 7 - 3) / 3)
                width = nominal + (0 if should_pass else c["profile_pitch_mm"]) + jitter
                yaw = math.radians(maximum_yaw if specimen % 3 == 0 else maximum_yaw / 2)
                projection = math.hypot(width * math.cos(yaw), c["profile_length_mm"] * math.sin(yaw))
                # Apply the unfavorable tolerance for the expected class.
                worst_gap = gap + (-1 if should_pass else 1) * c["gap_tol_mm"]
                rows.append((specimen + 1, round(width, 4), round(math.degrees(yaw), 3),
                             round(projection, 4), worst_gap, int(should_pass), int(projection < worst_gap)))
            table = export(out / f"profiles-{gap:g}-{label}.csv",
                           ("specimen", "width_mm", "yaw_deg", "projected_mm", "gap_mm", "expected_pass", "modeled_pass"), rows)
            pct = 100 * sum(r["expected_pass"] == r["modeled_pass"] for r in table) / len(table)
            require((pct >= c["min_correct_pct"]) == (label == "guided"), f"P140 gap decision differed for {gap} at {label}")
            report[str(gap)] = dict(inert_profiles=len(table), correct_pct=pct)
        result[label] = report
    return result


def p146(c, out):
    coefficients = c["branch_coeff_lpm_per_kpa"]
    thresholds = c["immersed_opening_kpa"]
    step = c["readout_step_lpm"]
    result = {}
    for label, source_resistance in (("regulated", c["source_resistance_kpa_per_lpm"]),
                                     ("droop-control", c["control_resistance_kpa_per_lpm"])):
        rows = []
        for supply, closed in itertools.product(c["test_source_kpa"], (None, *range(4))):
            active = [branch for branch in range(4) if branch != closed]
            conductance = sum(coefficients[branch] for branch in active)
            threshold_flow = sum(coefficients[branch] * thresholds[branch] for branch in active)
            manifold = (supply + source_resistance * threshold_flow) / (1 + source_resistance * conductance)
            require(all(manifold > thresholds[branch] for branch in active), "P146 linear model is outside its envelope")
            for branch in active:
                reference = coefficients[branch] * (manifold - thresholds[branch])
                indicated = round(reference * (1 + c["instrument_scale_error_pct"][branch] / 100) / step) * step
                rows.append((supply, 0 if closed is None else closed + 1, branch + 1,
                             round(manifold, 6), round(reference, 6), round(indicated, 6)))
        table = export(out / f"air-panel-{label}.csv",
                       ("source_kpa", "closed_branch", "read_branch", "manifold_kpa", "reference_lpm", "readout_lpm"), rows)
        baseline = {(r["source_kpa"], r["read_branch"]): float(r["reference_lpm"])
                    for r in table if r["closed_branch"] == "0"}
        worst_read = max(100 * abs(float(r["readout_lpm"]) / float(r["reference_lpm"]) - 1) for r in table)
        worst_shift = max(100 * abs(float(r["reference_lpm"]) / baseline[(r["source_kpa"], r["read_branch"])] - 1)
                          for r in table if r["closed_branch"] != "0")
        require((worst_read <= c["max_error_pct"] and worst_shift <= c["max_outlet_change_pct"])
                == (label == "regulated"), f"P146 distribution decision differed for {label}")
        result[label] = dict(branch_readings=len(table), max_instrument_error_pct=round(worst_read, 2),
                             max_outlet_shift_when_closing_pct=round(worst_shift, 2))
    return result


TRIALS = {"P116": p116, "P117": p117, "P129": p129, "P130": p130, "P138": p138, "P140": p140, "P146": p146}


def generate(output, config, selected):
    for item in selected:
        case = config[item]
        folder = output / item
        folder.mkdir(parents=True, exist_ok=True)
        metrics = TRIALS[item](case, folder)
        report = json.dumps({"pilot": case["pilot"], "metrics": metrics}, indent=2)
        (folder / "results.json").write_text(report + "\n", encoding="utf-8")
        print(item, json.dumps(metrics))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "cases.json")
    parser.add_argument("--out", type=Path, help="write a new export instead of checking the included files")
    parser.add_argument("--trial", choices=TRIALS, action="append")
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    selected = args.trial or list(TRIALS)
    if args.out is not None:
        generate(args.out, config, selected)
        return
    with tempfile.TemporaryDirectory(prefix="hs-savings-") as temp:
        temp = Path(temp)
        generate(temp, config, selected)
        for item in selected:
            expected = {f.name: f.read_bytes() for f in (ROOT / "generated" / item).iterdir()}
            observed = {f.name: f.read_bytes() for f in (temp / item).iterdir()}
            require(observed == expected, f"{item} delivered results differ from replay")


if __name__ == "__main__":
    main()
