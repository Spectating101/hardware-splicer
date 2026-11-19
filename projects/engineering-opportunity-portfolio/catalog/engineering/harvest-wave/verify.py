"""Build and verify the seven harvest trial packages using the Python standard library."""

import argparse
import csv
import itertools
import json
import math
import random
import tempfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent
SVG = "http://www.w3.org/2000/svg"


def require(condition, details):
    if not condition:
        raise ValueError(details)


def export(path, headers, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(headers)
        writer.writerows(rows)
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def svg(path, width, height, title, items):
    doc = ET.Element("svg", xmlns=SVG, width=f"{width}mm", height=f"{height}mm",
                     viewBox=f"0 0 {width} {height}")
    ET.SubElement(doc, "title").text = title
    for name, attrs in items:
        ET.SubElement(doc, name, {key.replace("_", "-"): str(value) for key, value in attrs.items()})
    ET.indent(doc)
    ET.ElementTree(doc).write(path, encoding="utf-8", xml_declaration=True)
    return ET.parse(path).getroot()


def p115(c, out):
    top = c["width_at_top_mm"]
    depth = c["depth_mm"]
    side = math.tan(math.radians(c["draft_deg"])) * depth
    bottom = top + 2 * side
    cells = c["rows"] * c["cols"]
    width = c["cols"] * c["pitch_mm"]
    height = c["rows"] * c["pitch_mm"]
    parts = []
    for row, col in itertools.product(range(c["rows"]), range(c["cols"])):
        x, y = (col + 0.5) * c["pitch_mm"], (row + 0.5) * c["pitch_mm"]
        for tag, span, color in (("upper", top, "#15283b"), ("exit", bottom, "#356493")):
            parts.append(("rect", dict(x=round(x-span/2, 5), y=round(y-span/2, 5), width=span, height=span,
                                       fill="none", stroke=color, stroke_width=0.15, data_side=tag)))
    doc = svg(out / "block-mold-projections.svg", width, height, "Eight cell upper and exit faces", parts)
    measurements = [(elem.get("data-side"), float(elem.get("width"))) for elem in doc.findall(f"{{{SVG}}}rect")]
    tops = [width for side_tag, width in measurements if side_tag == "upper"]
    bottoms = [width for side_tag, width in measurements if side_tag == "exit"]
    require(len(tops) == len(bottoms) == cells == 8, "P115 malformed cell layout")
    worst_clearance = (min(tops) - c["width_tol_mm"] - c["shoe_side_mm"] - c["shoe_tol_mm"]) / 2 - c["guide_runout_mm"]
    slant = math.hypot(depth, side)
    adverse_wall_mm2 = cells * 4 * ((max(tops) + max(bottoms)) / 2 + c["width_tol_mm"]) * slant
    load = adverse_wall_mm2 * c["model_breakaway_kpa"] / 1000
    result = {}
    for label, ratio in (("candidate", c["proposed_lever_ratio"]), ("short-lever-control", c["control_lever_ratio"])):
        table = export(out / f"ejector-{label}.csv", ("cells", "upper_mm", "exit_mm", "depth_mm", "modeled_breakaway_n",
                                                    "mechanical_advantage", "efficiency", "ejector_stroke_mm"),
                       ((cells, min(tops), max(bottoms), depth, round(load, 4), ratio, c["lever_efficiency"],
                         c["ejector_stroke_mm"]),))
        row = table[0]
        force = float(row["modeled_breakaway_n"]) / (float(row["mechanical_advantage"]) * float(row["efficiency"]))
        handle_travel = float(row["mechanical_advantage"]) * float(row["ejector_stroke_mm"])
        require((force <= c["handle_force_budget_n"] and worst_clearance >= c["min_runout_clearance_mm"]
                 and handle_travel <= c["handle_travel_budget_mm"])
                == (label == "candidate"), f"P115 ejector decision differs for {label}")
        result[label] = dict(cells=cells, model_handle_force_n=round(force, 2),
                             worst_shoe_side_clearance_mm=round(worst_clearance, 3),
                             model_handle_travel_mm=round(handle_travel, 2))
    return result


def p123(c, out):
    grav = 9.80665
    lateral_area = math.pi * (c["lateral_id_mm"] / 2000)**2
    lateral_k = [c["lateral_k"] + c["darcy_factor"] * length / (c["lateral_id_mm"] / 1000)
                 for length in c["lateral_lengths_m"]]
    require(len(lateral_k) == 8, "P123 study expects eight laterals")

    def solve(ids, active):
        areas = [math.pi * (size / 2000)**2 for size in ids]
        segment_k = [c["segment_k"] + c["darcy_factor"] * length / (size / 1000)
                     for size, length in zip(ids, c["segment_lengths_m"], strict=True)]

        def pressures(flows):
            header_flow = list(itertools.accumulate(flows))
            losses = [factor * (flow / area)**2 / (2 * grav)
                      for factor, flow, area in zip(segment_k, header_flow, areas, strict=True)]
            manifold = list(reversed(list(itertools.accumulate(reversed(losses)))))
            source = c["strict_supply_head_m"] - c["source_droop_m_per_lpm_squared"] * (sum(flows) * 60000)**2
            return header_flow, manifold, source

        flows = [0.0] * len(ids)
        for _ in range(1500):
            header_flow, manifold, source = pressures(flows)
            target = [lateral_area * math.sqrt(max(0, source - head) * 2 * grav / k) if index in active else 0
                      for index, (head, k) in enumerate(zip(manifold, lateral_k, strict=True))]
            if max(abs(actual - ideal) for actual, ideal in zip(flows, target, strict=True)) <= 1e-11:
                residuals = [abs(source - head - k * (flow / lateral_area)**2 / (2 * grav))
                             for index, (flow, head, k) in enumerate(zip(flows, manifold, lateral_k, strict=True))
                             if index in active]
                require(max(residuals) < 1e-5, "P123 branch head did not balance")
                return [(index + 1, len(active), c["lateral_lengths_m"][index], c["lateral_id_mm"],
                         c["segment_lengths_m"][index], ids[index],
                         round(flow * 60000, 6), round(flow / lateral_area, 6), round(header / area, 6),
                         round(head, 6), round(source, 6))
                        for index, (flow, header, area, head) in enumerate(zip(flows, header_flow, areas, manifold, strict=True))
                        if index in active]
            flows = [0.85 * actual + 0.15 * ideal for actual, ideal in zip(flows, target, strict=True)]
        raise ValueError("P123 network solver did not converge")

    result = {}
    all_rows = set(range(len(lateral_k)))
    for label, ids in (("progressive", c["progressive_id_mm"]), ("uniform-bore-control", c["control_id_mm"])):
        table = export(out / f"flush-{label}.csv", ("row", "open_rows", "lateral_length_m", "lateral_id_mm",
                                                    "header_segment_length_m", "header_segment_id_mm", "row_lpm",
                                                    "lateral_m_s", "downstream_segment_m_s", "local_head_m", "supply_head_m"),
                       (*solve(ids, all_rows), *(record for index in sorted(all_rows) for record in solve(ids, {index}))))
        all_open = [r for r in table if r["open_rows"] == "8"]
        minimum_lateral = min(float(r["lateral_m_s"]) for r in all_open)
        minimum_header = min(float(r["downstream_segment_m_s"]) for r in all_open)
        isolated = min(float(r["lateral_m_s"]) for r in table if r["open_rows"] == "1")
        require((min(minimum_lateral, minimum_header, isolated) >= c["velocity_gate_m_s"])
                == (label == "progressive"), f"P123 network decision differs for {label}")
        result[label] = dict(all_open_rows=len(all_open), min_all_open_lateral_m_s=round(minimum_lateral, 3),
                             min_all_open_header_m_s=round(minimum_header, 3),
                             min_isolated_lateral_m_s=round(isolated, 3),
                             model_all_open_flow_lpm=round(sum(float(r["row_lpm"]) for r in all_open), 2))
    return result


def p136(c, out):
    large_r = c["mouth_mm"] / 2
    small_r = c["cup_mm"] / 2
    slant = math.hypot(c["body_length_mm"], large_r - small_r)
    outer = slant * large_r / (large_r - small_r)
    inner = outer - slant
    theta = 2 * math.pi * large_r / outer
    surface = math.pi * (large_r + small_r) * slant
    cut = export(out / "net-frustum-cut.csv", ("outer_arcradius_mm", "inner_arcradius_mm", "sector_deg", "seam_allowance_mm"),
                 ((round(outer, 4), round(inner, 4), round(math.degrees(theta), 5), "shop-specific"),))[0]
    rad = math.radians(float(cut["sector_deg"]))
    require(abs(rad * float(cut["outer_arcradius_mm"]) - 2 * math.pi * large_r) < 0.01, "P136 lip perimeter changed")
    require(abs(rad * float(cut["inner_arcradius_mm"]) - 2 * math.pi * small_r) < 0.01, "P136 cup perimeter changed")
    result = {}
    for label, opening in (("candidate", c["candidate_mesh_um"]), ("coarse-control", c["control_mesh_um"])):
        minimum = opening - c["aperture_tol_um"]
        maximum = opening + c["aperture_tol_um"]
        fraction = (minimum / (minimum + c["thread_um"]))**2
        area_ratio = surface * fraction / (math.pi * large_r**2)
        rows = []
        for i in range(c["beads"]):
            diameter = c["bead_min_um"] + (c["bead_max_um"] - c["bead_min_um"]) * i / (c["beads"] - 1)
            bypass = (i + 1) % c["seam_bypass_every"] == 0
            retained = diameter > maximum and not bypass
            rows.append((i + 1, round(diameter, 4), maximum, int(bypass), int(retained)))
        table = export(out / f"beads-{label}.csv", ("bead", "diameter_um", "worst_aperture_um", "assumed_bypass", "retained"), rows)
        retention = 100 * sum(int(r["retained"]) for r in table) / len(table)
        require((retention >= c["retention_gate_pct"] and area_ratio >= c["min_clean_open_to_mouth_ratio"])
                == (label == "candidate"), f"P136 mesh decision differs for {label}")
        result[label] = dict(inert_beads=len(table), worst_aperture_um=maximum, model_retained_pct=retention,
                             approximate_clean_open_area_to_mouth_ratio=round(area_ratio, 2))
    return result


def ellipse(cx, cy, rx, ry):
    return {(x, y) for x, y in itertools.product(range(cx-rx, cx+rx+1), range(cy-ry, cy+ry+1))
            if (x-cx)**2 / rx**2 + (y-cy)**2 / ry**2 <= 1}


def connected_components(pixels):
    pending = set(pixels)
    while pending:
        stack = [pending.pop()]
        count = 0
        while stack:
            x, y = stack.pop()
            count += 1
            for point in ((x-1, y), (x+1, y), (x, y-1), (x, y+1)):
                if point in pending:
                    pending.remove(point)
                    stack.append(point)
        yield count


def p141(c, out):
    rng = random.Random(141)
    frame_w, frame_h = c["frame_px"]
    center_x, center_y = frame_w // 2, frame_h // 2
    axes = c["coupon_axes_px"]
    low, high = c["single_area_envelope_px"]
    human_samples = []
    truth = []
    for batch in range(1, c["batches"] + 1):
        events = ["single"] * (c["items_per_batch"] - 2 * c["visible_pairs_per_batch"])
        events += ["visible-pair"] * c["visible_pairs_per_batch"]
        rng.shuffle(events)
        for i, kind in enumerate(events, 1):
            shift = rng.choice((-2, 0, 2))
            rx = axes[0] + rng.choice((-1, 0, 1)) if kind == "single" else axes[0]
            first = ellipse(center_x + shift, center_y, rx, axes[1])
            blob = first
            if kind == "visible-pair":
                blob = first | ellipse(center_x + shift + c["offset_pair_px"], center_y, axes[0], axes[1])
            blob |= {(1, n + 1) for n in range(c["noise_speck_area_px"])}
            require(all(0 <= x < frame_w and 0 <= y < frame_h for x, y in blob), "P141 mask cropped")
            sizes = sorted(size for size in connected_components(blob) if size >= low)
            accepted = sum(low <= size <= high for size in sizes)
            held = sum(size > high for size in sizes)
            naive = len(sizes)
            truth.append((batch, i, kind, 1 if kind == "single" else 2,
                          " ".join(map(str, sizes)), accepted, held, naive))
            if len(human_samples) < 2 and kind not in {prior for prior, _ in human_samples}:
                human_samples.append((kind, blob))
    hidden = ellipse(center_x, center_y, *axes)
    hidden_outcomes = []
    for _ in range(c["coincident_pair_trials"]):
        shift_x, shift_y = rng.randint(-2, 2), rng.randint(-2, 2)
        mask = ellipse(center_x+shift_x, center_y+shift_y, *axes)
        hidden_outcomes.append(sum(low <= size <= high for size in connected_components(mask | mask)))
    require(set(hidden_outcomes) == {1}, "P141 occlusion control no longer shows ambiguity")
    human_samples.append(("coincident-pair", hidden | hidden))
    artwork = []
    for column, (_, mask) in enumerate(human_samples):
        left = column * frame_w
        artwork.append(("rect", dict(x=left, y=0, width=frame_w, height=frame_h, fill="#fafafa",
                                     stroke="#86929c", stroke_width=0.4)))
        artwork.extend(("rect", dict(x=left+x, y=y, width=1, height=1, fill="#253d49")) for x, y in sorted(mask))
        artwork.append(("line", dict(x1=left+center_x, y1=3, x2=left+center_x, y2=frame_h-3,
                                     stroke="#ec912a", stroke_width=0.2)))
    svg(out / "example-camera-masks.svg", frame_w*len(human_samples), frame_h,
        "Synthetic single, visible pair and indistinguishable fully overlaid pair masks in recorded example order", artwork)
    table = export(out / "batch-event-replay.csv", ("batch", "event", "truth_kind", "truth_inert_objects",
                                                     "mask_areas_px", "accepted_singles", "held", "naive_count"), truth)
    groups = (list(group) for _, group in itertools.groupby(table, key=lambda r: r["batch"]))
    summaries = []
    for rows in groups:
        n = sum(int(r["truth_inert_objects"]) for r in rows)
        accepted = sum(int(r["accepted_singles"]) for r in rows)
        holds = sum(int(r["held"]) for r in rows)
        naive = sum(int(r["naive_count"]) for r in rows)
        summaries.append((rows[0]["batch"], n, accepted, holds, n - accepted, naive, n - naive))
    checks = export(out / "batch-summary.csv", ("batch", "truth_objects", "accepted_singles", "held_events",
                                               "truth_objects_needing_recheck", "naive_complete_count", "naive_missed"),
                    summaries)
    expected_singles = c["items_per_batch"] - 2*c["visible_pairs_per_batch"]
    require(all(int(r["truth_objects"]) == c["items_per_batch"] and int(r["accepted_singles"]) == expected_singles
                and int(r["held_events"]) == c["visible_pairs_per_batch"]
                and int(r["naive_missed"]) >= c["visible_pairs_per_batch"] for r in checks),
            "P141 visible-overlap control was not rejected")
    return dict(batches=len(checks), accepted_singles_per_batch=expected_singles,
                visible_overlaps_held_per_batch=c["visible_pairs_per_batch"],
                naive_undercount_per_batch=int(checks[0]["naive_missed"]), fully_coincident_alias_trials=len(hidden_outcomes))


def p147(c, out):
    step = c["sample_s"]
    total_current = c["horn_mA"] + c["logic_mA"]
    result = {}
    for label, capacity, delay in (("candidate", c["battery_mAh"], c["debounce_s"]),
                                   ("small-battery-control", c["control_mAh"], c["debounce_s"]),
                                   ("unfiltered-control", c["battery_mAh"], step)):
        outcomes = []
        example = []
        for i in range(c["trial_count"]):
            hard_drop = 17 + i * step
            external_loss = 4 + i % 3
            available = c["capacity_fraction"] * capacity
            first_alarm = None
            run = 0
            early = 0
            horn_ticks = 0
            for stamp in range(0, int(3600 * capacity / total_current) + hard_drop + 60, step):
                low = 2 <= stamp < 4 or stamp >= hard_drop
                run = run + step if low else 0
                requested_horn = run >= delay
                load = c["logic_mA"] + (c["horn_mA"] if requested_horn else 0)
                battery_current = 0 if stamp < external_loss else load
                consumption = battery_current * step / 3600
                powered = stamp < external_loss or available >= consumption
                horn = powered and requested_horn
                available = max(0, available - consumption)
                if horn:
                    if stamp < hard_drop:
                        early += 1
                    else:
                        first_alarm = stamp if first_alarm is None else first_alarm
                        horn_ticks += 1
                if i == 0 and (stamp < hard_drop + 30 or not powered):
                    example.append((stamp, int(low), int(stamp < external_loss), int(horn), round(available, 6)))
                if not powered:
                    break
            require(first_alarm is not None, "P147 battery failed before the alarm could fire")
            outcomes.append((i + 1, external_loss, hard_drop, first_alarm - hard_drop, horn_ticks * step / 60, early))
        table = export(out / f"fault-trials-{label}.csv", ("trial", "external_loss_s", "pressure_drop_s", "alarm_delay_s",
                                                           "uninterrupted_horn_min", "pre_fault_horn_samples"), outcomes)
        export(out / f"sample-waveform-{label}.csv", ("stamp_s", "switch_low", "external_power", "horn", "charge_left_mAh"),
               example)
        worst_delay = max(float(r["alarm_delay_s"]) for r in table)
        runtime = min(float(r["uninterrupted_horn_min"]) for r in table)
        transients = sum(int(r["pre_fault_horn_samples"]) > 0 for r in table)
        require((worst_delay <= c["max_alarm_delay_s"] and runtime >= c["min_horn_runtime_min"] and transients == 0)
                == (label == "candidate"), f"P147 fault response differs for {label}")
        result[label] = dict(trials=len(table), max_model_delay_s=worst_delay, min_model_horn_minutes=round(runtime, 2),
                             transient_false_alarm_trials=transients)
    return result


def p153(c, out):
    lanes = math.floor((c["width_mm"] - 2*c["side_margin_mm"]) / c["transverse_pitch_mm"])
    mass_per_mm = c["occupation_fraction"] * lanes * c["average_bean_mass_g"] / c["longitudinal_pitch_mm"]
    min_speed = c["batch_g"] / (60*c["max_batch_minutes"]*mass_per_mm)
    max_speed = c["inspection_length_mm"] / c["min_dwell_s"]
    minimum_gap = c["chute_opening_mm"] - c["max_bean_height_mm"] - c["vertical_allowance_mm"]
    result = {"model_speed_window_mm_s": [round(min_speed, 2), round(max_speed, 2)]}
    for label, speed in (("candidate", c["target_speed_mm_s"]), ("fast-control", c["control_speed_mm_s"])):
        flow_g_s = mass_per_mm * speed
        minutes = c["batch_g"] / (60*flow_g_s)
        dwell = c["inspection_length_mm"] / speed
        rows = []
        for i in range(1, c["marked_defects"]+1):
            entered = (i / (c["marked_defects"]+1)) * minutes * 60
            rows.append((i, round(entered, 4), round(entered+dwell, 4)))
        table = export(out / f"inspection-{label}.csv", ("mark", "visible_start_s", "visible_end_s"), rows)
        minimum_dwell = min(float(r["visible_end_s"]) - float(r["visible_start_s"]) for r in table)
        misses = sum(float(r["visible_end_s"]) - float(r["visible_start_s"]) < c["min_dwell_s"] for r in table)
        require((minutes <= c["max_batch_minutes"] and minimum_dwell >= c["min_dwell_s"] and minimum_gap > 0)
                == (label == "candidate"), f"P153 presentation decision differs for {label}")
        result[label] = dict(lanes=lanes, modeled_batch_minutes=round(minutes, 2), min_mark_exposure_s=round(minimum_dwell, 3),
                             exposure_budget_misses=misses, modeled_chute_height_clearance_mm=minimum_gap)
    return result


def p156(c, out):
    code_per_n = c["force_code_per_n"]
    zero_code = c["force_zero_code"]
    span = c["full_load_n"]
    raw_zero = round(zero_code)
    raw_top = round(zero_code + code_per_n*span)
    slope = (raw_top - raw_zero) / span
    inputs = []
    for load, polarity in itertools.product(c["reference_load_n"], (-1, 0, 1)):
        observed = round(code_per_n*load + zero_code + polarity*c["force_noise_codes"])
        forces = (observed - raw_zero) / slope
        inputs.append((load, observed, round(forces, 6)))
    table = export(out / "force-calibration-replay.csv", ("reference_n", "adc_code", "calibrated_n"), inputs)
    max_error = max(abs(float(r["reference_n"]) - float(r["calibrated_n"])) for r in table)
    nominal = c["target_depth_mm"]
    normal_ratio = math.cos(math.radians(c["guide_angle_deg"]))
    result = {"probe_diameter_mm": c["probe_mm"], "force_replay_max_error_n": round(max_error, 4)}
    for label, stiffness in (("candidate", c["frame_n_per_mm"]), ("flexible-control", c["control_frame_n_per_mm"])):
        travel_rows = []
        for force, stop_tol, normal in itertools.product((*c["reference_load_n"], 0),
                (-c["stop_tolerance_mm"], c["stop_tolerance_mm"]), (normal_ratio, 1)):
            travel = (nominal + stop_tol - force/stiffness) * normal
            travel_rows.append((force, stop_tol, round(normal, 6), nominal, round(travel, 6)))
        travels = export(out / f"probe-travel-{label}.csv", ("force_n", "stop_error_mm", "vertical_factor",
                                                         "target_travel_mm", "model_travel_mm"), travel_rows)
        max_depth_error = max(abs(float(r["target_travel_mm"]) - float(r["model_travel_mm"])) for r in travels)
        foam = []
        for repeat in range(1, c["foam_repeats"]+1):
            seating = (-1, 0, 1)[repeat % 3] * c["stop_tolerance_mm"]
            material = c["foam_stiffness_n_mm"]
            force = material*(nominal+seating)/(1 + material/stiffness)
            foam.append((repeat, seating, round(force/stiffness, 6), round(force, 6)))
        foam_table = export(out / f"foam-{label}.csv", ("repeat", "seating_mm", "frame_deflection_mm", "predicted_peak_n"), foam)
        peaks = [float(r["predicted_peak_n"]) for r in foam_table]
        require((max_depth_error <= c["max_depth_error_mm"] and max_error <= c["max_force_error_n"])
                == (label == "candidate"), f"P156 stand decision differs for {label}")
        result[label] = dict(max_travel_error_mm=round(max_depth_error, 4), reference_load_levels=len(c["reference_load_n"]),
                             model_foam_peak_span_n=round(max(peaks)-min(peaks), 3), model_foam_repeats=len(peaks))
    return result


TRIALS = {"P115": p115, "P123": p123, "P136": p136, "P141": p141, "P147": p147, "P153": p153, "P156": p156}


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
    with tempfile.TemporaryDirectory(prefix="hs-harvest-") as directory:
        temporary = Path(directory)
        generate(temporary, config, selected)
        for item in selected:
            expected = {f.name: f.read_bytes() for f in (ROOT/"generated"/item).iterdir()}
            observed = {f.name: f.read_bytes() for f in (temporary/item).iterdir()}
            require(observed == expected, f"{item} delivered results differ from replay")


if __name__ == "__main__":
    main()
