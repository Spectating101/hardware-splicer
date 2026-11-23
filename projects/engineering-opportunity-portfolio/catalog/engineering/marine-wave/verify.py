"""Regenerate and verify the marine bench trials using only the standard library."""

import argparse
import csv
import itertools
import json
import math
import tempfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent
SVG = "http://www.w3.org/2000/svg"


def require(condition, details):
    if not condition:
        raise ValueError(details)


def exchange_csv(path, fields, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(fields)
        writer.writerows(rows)
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def new_svg(width, height, description):
    document = ET.Element("svg", xmlns=SVG, width=f"{width}mm", height=f"{height}mm",
                          viewBox=f"0 0 {width} {height}")
    ET.SubElement(document, "title").text = description
    return document


def draw(document, tag, **kwargs):
    return ET.SubElement(document, tag, {attribute.replace("_", "-"): str(value)
                                         for attribute, value in kwargs.items()})


def export_svg(document, path):
    ET.indent(document)
    ET.ElementTree(document).write(path, encoding="utf-8", xml_declaration=True)
    return ET.parse(path).getroot()


def p032(c, out):
    radius = c["footprint_d_mm"] / 2
    inner_r = radius - c["edge_ring_mm"]
    result = {}
    for label, rib in (("candidate", c["candidate_rib_mm"]), ("control", c["control_rib_mm"])):
        doc = new_svg(2 * radius, 2 * radius, "Guard face geometry for an unpowered survey coupon")
        draw(doc, "circle", cx=radius, cy=radius, r=radius - c["edge_ring_mm"] / 2,
             fill="none", stroke="black", stroke_width=c["edge_ring_mm"])
        pitch = c["rib_pitch_mm"]
        for offset in range(-int(inner_r // pitch), int(inner_r // pitch) + 1):
            joined_radius = inner_r + c["edge_ring_mm"] / 2
            dx = math.sqrt(joined_radius**2 - (abs(offset * pitch) + rib / 2)**2)
            draw(doc, "rect", x=radius - dx, y=radius + offset * pitch - rib / 2,
                 width=2 * dx, height=rib, fill="black")
        written = export_svg(doc, out / f"face-{label}.svg")
        ring, = written.findall(f"{{{SVG}}}circle")
        written_outer = float(ring.get("r")) + float(ring.get("stroke-width")) / 2
        written_inner = float(ring.get("r")) - float(ring.get("stroke-width")) / 2
        ribs = [(float(r.get("x")), float(r.get("y")), float(r.get("width")), float(r.get("height")))
                for r in written.findall(f"{{{SVG}}}rect")]
        rows = []
        for station, (swept, seat) in enumerate(zip(c["swept_radii_mm"], c["seat_radii_mm"], strict=True), 1):
            blade_r = swept + c["radius_tol_mm"]
            radial_gap = written_inner - blade_r - c["radial_alignment_tol_mm"]
            seat_edge = written_outer - seat - c["seat_position_tol_mm"]
            # Station-specific projected open fraction over a 0.25 mm grid across the blade sweep.
            grid = range(math.floor(-blade_r * 4), math.ceil(blade_r * 4) + 1)
            inside = blocked = 0
            for i, j in itertools.product(grid, repeat=2):
                x, y = i / 4 + radius, j / 4 + radius
                if math.hypot(i / 4, j / 4) > blade_r:
                    continue
                inside += 1
                blocked += any(rx <= x <= rx + w and ry <= y < ry + h for rx, ry, w, h in ribs)
            rows.append((station, c["depth_mm"], round(radial_gap, 4), round(seat_edge, 4),
                         round(100 * (1 - blocked / inside), 4)))
        table = exchange_csv(out / f"six-seats-{label}.csv",
                             ("station", "depth_mm", "blade_radial_gap_mm", "seat_edge_remaining_mm", "open_face_pct"), rows)
        gap = min(float(r["blade_radial_gap_mm"]) for r in table)
        seat_edge = min(float(r["seat_edge_remaining_mm"]) for r in table)
        open_pct = min(float(r["open_face_pct"]) for r in table)
        require(len(table) == 6, "P032 requires six separate host stations")
        require((gap >= c["min_shroud_clearance_mm"] and seat_edge >= 0 and open_pct >= c["min_face_open_pct"])
                == (label == "candidate"), f"P032 unexpected geometry decision for {label}")
        result[label] = dict(stations=len(table), min_radial_clearance_mm=round(gap, 3),
                             min_seat_edge_mm=round(seat_edge, 3), min_open_face_pct=round(open_pct, 2))
    return result


def p172(c, out):
    result = {}
    for label, core in (("candidate", c["core_d_mm"]), ("control", c["control_core_d_mm"])):
        cable = c["cable_mm"]
        turns = math.floor(c["width_mm"] / (c["turn_pitch_factor"] * cable))
        pitch_radius = c["radial_spacing_factor"] * cable
        max_r = c["flange_mm"] / 2 - c["flange_margin_mm"]
        layers = []
        # Evaluate both diameter tolerance ends, including the resulting change in layer count.
        for sign in (-1, 1):
            actual_core = core + sign * c["diameter_tol_mm"]
            radius = actual_core / 2 + cable / 2
            layer = 0
            while radius + cable / 2 <= max_r:
                layer += 1
                layers.append((actual_core, layer, round(radius, 3), turns,
                               round(2 * math.pi * radius * turns / 1000, 6)))
                radius += pitch_radius
        table = exchange_csv(out / f"reel-{label}.csv",
                             ("drum_d_mm", "layer", "centerline_radius_mm", "turns", "layer_capacity_m"), layers)
        groups = [(len(entries), sum(float(r["layer_capacity_m"]) for r in entries))
                  for _, members in itertools.groupby(table, key=lambda r: r["drum_d_mm"])
                  if (entries := list(members))]
        count, gross_m = min(groups, key=lambda group: group[1])
        capacity = gross_m - c["connector_reserve_m"]
        min_d = core - c["diameter_tol_mm"]
        brake = c["hand_pull_n"] * max_r / 1000 * c["brake_factor"]
        require((capacity >= c["target_m"] and min_d >= c["min_bend_d_mm"] and brake <= c["brake_rated_nm"])
                == (label == "candidate"), f"P172 unexpected reel decision for {label}")
        result[label] = dict(layers=count, turns_per_layer=turns, net_storage_m=round(capacity, 2),
                             minimum_working_drum_diameter_mm=min_d, minimum_brake_holding_nm=round(brake, 2))
    return result


def p173(c, out):
    result = {}
    kelvin = c["initial_c"] + 273.15
    for label, drift in (("reference-blank", c["small_drift_kpa"]), ("leak-control", c["leak_control_drift_kpa"])):
        rows = []
        step = c["logged_step_kpa"]
        for origin in c["initial_gauge_kpa"]:
            for minute in range(c["hold_minutes"] + 1):
                phase = minute / c["hold_minutes"]
                temp = kelvin + c["thermal_change_c"] * phase
                absolute = (c["atmosphere_kpa"] + origin + drift * phase) * temp / kelvin
                indicated = round((absolute - c["atmosphere_kpa"]) / step) * step
                corrected = (indicated + c["atmosphere_kpa"]) * kelvin / temp - c["atmosphere_kpa"]
                rows.append((origin, minute, round(temp - 273.15, 4), round(indicated, 4), round(corrected, 6)))
        table = exchange_csv(out / f"reference-blank-{label}.csv",
                             ("initial_gauge_kpa", "minute", "temperature_c", "indicated_kpa", "corrected_kpa"), rows)
        final = [row for row in table if int(row["minute"]) == c["hold_minutes"]]
        worst = max(abs(float(r["corrected_kpa"]) - float(r["initial_gauge_kpa"])) for r in final)
        smallest = min(abs(float(r["corrected_kpa"]) - float(r["initial_gauge_kpa"])) for r in final)
        raw = max(abs(float(r["indicated_kpa"]) - float(r["initial_gauge_kpa"])) for r in final)
        bound = 2 * c["indicated_accuracy_kpa"]
        require((worst + bound <= c["max_drift_kpa"]) == (label == "reference-blank"),
                f"P173 unexpected reference blank decision for {label}")
        if label == "leak-control":
            require(smallest - bound > c["max_drift_kpa"], "P173 leak control indistinguishable from noise")
        result[label] = dict(levels=len(final), max_corrected_drift_kpa=round(worst, 3),
                             max_uncorrected_drift_kpa=round(raw, 3), accuracy_allowance_kpa=bound,
                             guaranteed_least_drift_kpa=round(max(0, smallest - bound), 3))
    return result


def p174(c, out):
    result = {}
    for label, oversize in (("candidate", c["pocket_oversize_mm"]), ("control", c["control_oversize_mm"])):
        rows = []
        for spindle, span, torque in c["models"]:
            pocket = span + oversize
            rows.append((spindle, span, pocket, c["engagement_mm"], torque))
        table = exchange_csv(out / f"jaw-set-{label}.csv",
                             ("fitting", "flats_mm", "jaw_gap_mm", "engagement_mm", "nominal_plug_torque_nm"), rows)
        clearances = []
        stresses = []
        for jaw in table:
            span = float(jaw["flats_mm"])
            clearance = float(jaw["jaw_gap_mm"]) - span
            stack = c["flat_tol_mm"] + c["tool_tol_mm"]
            clearances.append((clearance - stack, clearance + stack))
            torque_nmm = 1000 * float(jaw["nominal_plug_torque_nm"]) * c["torque_factor"]
            face_n = torque_nmm / (span - c["flat_tol_mm"])
            stresses.append(face_n / (float(jaw["engagement_mm"]) * c["effective_bearing_width_mm"]))
        low = min(pair[0] for pair in clearances)
        high = max(pair[1] for pair in clearances)
        stress = max(stresses)
        require((c["min_clearance_mm"] <= low and high <= c["max_clearance_mm"] and stress <= c["allow_bearing_mpa"])
                == (label == "candidate"), f"P174 unexpected jaw decision for {label}")
        result[label] = dict(jaws=len(table), min_assembled_clearance_mm=round(low, 3),
                             max_assembled_clearance_mm=round(high, 3), bearing_estimate_mpa=round(stress, 2))
    return result


def p175(c, out):
    result = {}
    for label, depth in (("candidate", c["bar_depth_mm"]), ("control", c["control_bar_depth_mm"])):
        length, breadth = c["bar_length_mm"], c["bar_width_mm"]
        span = c["clamp_span_mm"]
        center = length / 2
        half_x, half_y = (dim / 2 for dim in c["instrument_pattern_mm"])
        # Two bars of the same layout carry the two bolt rows.
        rows = [(bar, center + side * half_x, bar * half_y, c["hole_d_mm"], c["slot_travel_mm"])
                for bar, side in itertools.product((-1, 1), repeat=2)]
        table = exchange_csv(out / f"bridge-{label}-deck.csv",
                             ("bar", "x_mm", "y_mm", "hole_width_mm", "axial_slot_travel_mm"), rows)
        slot_edge = min(min(float(r["x_mm"]), length - float(r["x_mm"])) -
                        (float(r["hole_width_mm"]) + float(r["axial_slot_travel_mm"])) / 2 for r in table)
        require(length <= c["host_width_mm"] and len(table) == 4 and slot_edge > 0, "P175 deck outside surrogate")
        # Place the entire proof load in the middle of one bar.
        load = c["instrument_mass_kg"] * 9.80665 * c["proof_factor"]
        # Penalize the entire span as if its cross section contained a slot.
        moment_i = (breadth - c["hole_d_mm"]) * depth**3 / 12
        stress = (load * span / 4) * (depth / 2) / moment_i
        deflection = load * span**3 / (48 * c["modulus_mpa"] * moment_i)
        require((stress < c["allow_bending_mpa"] and deflection <= c["allow_deflection_mm"])
                == (label == "candidate"), f"P175 unexpected bar decision for {label}")
        result[label] = dict(instrument_slots=len(table), model_proof_load_n=round(load, 2),
                             bar_stress_mpa=round(stress, 2), bar_sag_mm=round(deflection, 3))
    return result


def p176(c, out):
    water = c["water_g_cm3"]
    foam = c["foam_g_cm3"]
    untrimmed = [(water - foam) * volume - wet - hardware
                 for volume, wet, hardware in zip(c["volumes_cm3"], c["wet_added_g"], c["hardware_g"], strict=True)]
    higher = untrimmed.index(max(untrimmed))
    possibilities = range(0, c["max_shim_g"] + 1, c["shim_step_g"])
    optimized = min(possibilities, key=lambda shim: abs(max(untrimmed) - min(untrimmed) - shim))
    result = {}
    for label, trim in (("matched", optimized), ("unshimmed-control", 0)):
        rows = []
        for index, lift in enumerate(untrimmed):
            shim = trim if index == higher else 0
            allowance = (water - foam) * c["volume_tol_cm3"] + c["mass_tol_g"]
            rows.append((index + 1, c["volumes_cm3"][index], shim, lift - shim - allowance, lift - shim + allowance))
        table = exchange_csv(out / f"trim-{label}.csv",
                             ("float", "volume_cm3", "shim_g", "minimum_lift_g_equiv", "maximum_lift_g_equiv"), rows)
        ranges = [(float(r["minimum_lift_g_equiv"]), float(r["maximum_lift_g_equiv"])) for r in table]
        worst = max(200 * abs(first - second) / (first + second)
                    for first, second in itertools.product(*ranges))
        low = min(rng[0] for rng in ranges)
        require((worst <= c["allowed_mismatch_pct"] and low >= c["min_lift_g_equivalent"])
                == (label == "matched"), f"P176 unexpected float decision for {label}")
        result[label] = dict(high_side_shim_g=trim, worst_pair_mismatch_pct=round(worst, 2),
                             minimum_lift_g_equiv=round(low, 1))
    return result


def alarm_trace(samples, c, confirm):
    """Latch each channel after consecutive wet reads and accept reset only when both are dry."""
    latch = [False, False]
    runs = [0, 0]
    for stamp, adc_a, adc_b, reset in samples:
        values = (adc_a, adc_b)
        wet = [c["wet_band"][0] <= value <= c["wet_band"][1] for value in values]
        dry = [c["dry_band"][0] <= value <= c["dry_band"][1] for value in values]
        for pad in range(2):
            runs[pad] = runs[pad] + 1 if wet[pad] else 0
            if runs[pad] >= confirm:
                latch[pad] = True
        if reset and all(dry):
            latch = [False, False]
        faults = sum((not wet[pad] and not dry[pad]) << pad for pad in range(2))
        yield stamp, sum(value << pad for pad, value in enumerate(latch)), faults


def p177(c, out):
    fixture = []
    waveforms = []
    step = c["poll_ms"]
    start, stop = 6 * step, 6 * step + c["wet_ms"]
    for pad, source, case in itertools.product(range(2), ("fresh", "saline"),
                                                range(1, c["wettings_per_pad_and_water"] + 1)):
        unit = f"{pad+1}-{source}-{case:02}"
        code = c[f"{source}_code"] + (case % 5 - 2) * 4
        for stamp in range(0, stop + 8 * step, step):
            values = [795 + case, 810 - case]
            if stamp == 2 * step or start <= stamp < stop:
                values[pad] = code
            elif stamp == step:
                values[1 - pad] = 0
            reset = int(stamp in (start + 4 * step, stop + 5 * step))
            fixture.append((unit, pad, stamp, *values, reset))
    source = exchange_csv(out / "pad-trials-adc.csv", ("trial", "pad", "ms", "adc_a", "adc_b", "reset"), fixture)
    for unit, batch in itertools.groupby(source, key=lambda row: row["trial"]):
        rows = list(batch)
        samples = [tuple(int(r[key]) for key in ("ms", "adc_a", "adc_b", "reset")) for r in rows]
        waveforms.append((unit, 1 << int(rows[0]["pad"]), samples))
    result = {}
    for label, confirm in (("candidate", c["confirm"]), ("one-sample-control", c["control_confirm"])):
        transitions = []
        for unit, expected, samples in waveforms:
            trace = list(alarm_trace(samples, c, confirm))
            prematurely = any(latch for stamp, latch, _ in trace if stamp < start)
            active = [(stamp, latch) for stamp, latch, _ in trace if start <= stamp < stop and latch]
            correct = bool(active) and all(latch == expected for _, latch in active)
            recovery = [(stamp, latch) for stamp, latch, _ in trace if stamp >= stop]
            retained = all(latch == expected for stamp, latch in recovery if stamp < stop + 5 * step)
            cleared = recovery[-1][1] == 0
            fault = next(bits for stamp, _, bits in trace if stamp == step) == (3 - expected)
            latency = (active[0][0] - start) if active else ""
            transitions.append((unit, int(prematurely), int(correct), int(retained), int(cleared), int(fault), latency))
        table = exchange_csv(out / f"pad-trials-{label}.csv",
                             ("trial", "false_early", "correct_pad", "retained", "cleared", "fault_flag", "delay_ms"),
                             transitions)
        false = sum(int(r["false_early"]) for r in table)
        positives = sum(int(r["correct_pad"]) for r in table)
        lifecycle = all(r["retained"] == r["cleared"] == r["fault_flag"] == "1" for r in table)
        require((positives == len(table) and false == 0 and lifecycle) == (label == "candidate"),
                f"P177 unexpected alarm decision for {label}")
        result[label] = dict(wettings=len(table), correct_pad=positives, premature_latches=false,
                             max_wet_latency_ms=max(int(r["delay_ms"]) for r in table if r["delay_ms"]),
                             latch_reset_fault_test=lifecycle)
    return result


def p178(c, out):
    degrees = math.radians(c["horizontal_fov_deg_air"] / 2)
    glass_theta = math.asin(math.sin(degrees) / c["glass_index"])
    water_theta = math.asin(math.sin(degrees) / c["water_index"])
    exit_edge = c["air_gap_mm"] * math.tan(degrees) + c["glass_mm"] * math.tan(glass_theta)
    window_r = (c["window_d_mm"] - c["window_tol_mm"]) / 2
    tangent_corner = math.hypot(math.tan(degrees), math.tan(math.radians(c["vertical_fov_deg_air"] / 2)))
    corner_angle = math.atan(tangent_corner)
    glass_corner = math.asin(math.sin(corner_angle) / c["glass_index"])
    corner_edge = c["air_gap_mm"] * tangent_corner + c["glass_mm"] * math.tan(glass_corner)
    margin = window_r - corner_edge - c["decenter_mm"]
    width = 2 * (exit_edge + c["target_dist_mm"] * math.tan(water_theta))
    pcb = c["pcb_side_mm"]
    offset = (pcb - c["mount_pitch_mm"]) / 2
    doc = new_svg(pcb, pcb, "BR-100126 camera PCB pickup pattern")
    draw(doc, "rect", x=0, y=0, width=pcb, height=pcb, fill="none", stroke="black", stroke_width=0.15)
    for x, y in itertools.product((offset, pcb - offset), repeat=2):
        draw(doc, "circle", cx=x, cy=y, r=1.22, fill="none", stroke="black", stroke_width=0.10)
    readback = export_svg(doc, out / "camera-board-mount.svg")
    centers = {(float(circle.get("cx")), float(circle.get("cy")))
               for circle in readback.findall(f"{{{SVG}}}circle")}
    require(len(centers) == 4 and max(x for x, _ in centers) - min(x for x, _ in centers) == c["mount_pitch_mm"],
            "P178 camera SVG pickup pattern incorrect")
    result = {}
    for label, columns in (("1080p", c["reference_columns_px"]), ("low-resolution-control", c["control_columns_px"])):
        table = exchange_csv(out / f"target-{label}.csv", ("standoff_mm", "columns_px", "span_mm", "feature_mm"),
                             ((c["target_dist_mm"], columns, round(width, 4), c["feature_mm"]),))
        entry = table[0]
        pixels = int(entry["columns_px"]) * float(entry["feature_mm"]) / float(entry["span_mm"])
        require((margin > 0 and pixels >= c["min_pixels_per_feature"]) == (label == "1080p"),
                f"P178 unexpected optical decision for {label}")
        result[label] = dict(clear_aperture_margin_mm=round(margin, 2), span_mm=round(width, 2),
                             average_pixels_per_feature=round(pixels, 2))
    return result


def p179(c, out):
    distance = c["target_plane_mm"] / 1000
    radians = math.radians(c["half_angle_deg"])
    intensity = c["lumens"] / (2 * math.pi * (1 - math.cos(radians)))
    offset = c["lamp_offset_mm"] / 1000
    width = c["target_half_width_mm"] / 1000
    height = c["target_half_height_mm"] / 1000
    illuminance = []
    for x, y in itertools.product((-width, 0, width), (-height, 0, height)):
        lux = 0
        for lamp in (offset, -offset):
            ray = math.sqrt((x - lamp)**2 + y**2 + distance**2)
            incidence = distance / ray
            if incidence >= math.cos(radians):
                lux += intensity / ray**2 * incidence * math.exp(-c["water_loss_per_m"] * ray)
        illuminance.append((x, y, round(lux, 3)))
    table = exchange_csv(out / "target-illuminance.csv", ("x_m", "y_m", "estimated_lux"), illuminance)
    lowest = min(float(r["estimated_lux"]) for r in table)
    result = {}
    for label, theta in (("candidate", c["wet_theta_k_w"]), ("thermal-control", c["control_theta_k_w"])):
        case_temp = c["water_temp_c"] + theta * c["heat_w"]
        require((lowest >= c["min_illuminance_lux"] and case_temp <= c["max_case_c"]) == (label == "candidate"),
                f"P179 unexpected lighting or thermal decision for {label}")
        result[label] = dict(card_checks=len(table), lowest_model_lux=round(lowest, 1),
                             steady_case_temperature_c=round(case_temp, 1))
    return result


def p180(c, out):
    result = {}
    for label, radius in (("candidate", c["guide_r_mm"]), ("control", c["control_guide_r_mm"])):
        narrowest = c["clamp_throat_mm"] - c["jaw_travel_mm"] + c["jaw_tol_mm"]
        widest = c["clamp_throat_mm"] - c["jaw_tol_mm"]
        groove_gap = c["channel_mm"] - c["cable_mm"] - c["cable_tol_mm"]
        worst_diameter = 2 * (radius - c["guide_tol_mm"])
        steps = [(angle, round(radius * math.sin(math.radians(angle)), 4),
                  round(radius * (1 - math.cos(math.radians(angle))), 4), worst_diameter,
                  c["guide_coverage_deg"] - abs(angle) - c["angle_tol_deg"])
                 for angle in c["working_angles_deg"]]
        table = exchange_csv(out / f"sweep-{label}.csv",
                             ("tangent_angle_deg", "x_mm", "rise_mm", "bend_diameter_mm", "angular_reserve_deg"),
                             steps)
        bend = min(float(r["bend_diameter_mm"]) for r in table)
        angle_reserve = min(float(r["angular_reserve_deg"]) for r in table)
        require((narrowest <= c["rim_min_mm"] <= c["rim_max_mm"] <= widest and groove_gap > 0
                 and bend >= c["min_working_bend_d_mm"] and angle_reserve >= 0) == (label == "candidate"),
                f"P180 unexpected guide decision for {label}")
        result[label] = dict(angles=len(table), clamp_fit_mm=[narrowest, widest],
                             min_bend_diameter_mm=bend, min_angle_reserve_deg=angle_reserve,
                             min_groove_clearance_mm=round(groove_gap, 1))
    return result


TRIALS = {
    "P032": p032, "P172": p172, "P173": p173, "P174": p174, "P175": p175,
    "P176": p176, "P177": p177, "P178": p178, "P179": p179, "P180": p180,
}


def generate(output, case_file, selected):
    cases = json.loads(case_file.read_text(encoding="utf-8"))
    for item in selected:
        case = cases[item]
        target = output / item
        target.mkdir(parents=True, exist_ok=True)
        metrics = TRIALS[item](case, target)
        result = json.dumps({"pilot": case["pilot"], "metrics": metrics}, indent=2)
        (target / "results.json").write_text(result + "\n", encoding="utf-8")
        print(item, json.dumps(metrics))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "cases.json")
    parser.add_argument("--out", type=Path, help="write a new export instead of checking the included files")
    parser.add_argument("--trial", choices=TRIALS.keys(), action="append")
    args = parser.parse_args()
    selected = args.trial or list(TRIALS)
    if args.out is not None:
        generate(args.out, args.config, selected)
        return
    with tempfile.TemporaryDirectory(prefix="hs-marine-") as temp:
        fresh = Path(temp)
        generate(fresh, args.config, selected)
        for product_id in selected:
            replay = {path.name: path.read_bytes() for path in (fresh / product_id).iterdir()}
            delivered = {path.name: path.read_bytes() for path in (ROOT / "generated" / product_id).iterdir()}
            require(delivered == replay, f"{product_id} delivered outputs differ from replay")


if __name__ == "__main__":
    main()
