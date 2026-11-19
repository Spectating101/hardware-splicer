"""Build and verify each field pilot from cases.json. Uses only the standard library."""

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


def csv_roundtrip(path, headers, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(headers)
        writer.writerows(rows)
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def create_svg(width, height, title):
    svg = ET.Element("svg", xmlns=SVG, width=f"{width}mm", height=f"{height}mm",
                     viewBox=f"0 0 {width} {height}")
    ET.SubElement(svg, "title").text = title
    return svg


def element(node, tag, **attributes):
    return ET.SubElement(node, tag, {key.replace("_", "-"): str(value)
                                     for key, value in attributes.items()})


def export_svg(node, path):
    ET.indent(node)
    ET.ElementTree(node).write(path, encoding="utf-8", xml_declaration=True)
    return ET.parse(path).getroot()


def build_p111(c, out):
    result = {}
    for label, diameter in (("candidate", c["hole_mm"]), ("control", c["control_hole_mm"])):
        holes = [(col + 1, row + 1, col * c["pitch_x_mm"], row * c["pitch_y_mm"], diameter)
                 for row in range(c["rows"]) for col in range(c["cols"])]
        table = csv_roundtrip(out / f"seed-head-{label}.csv",
                              ("column", "row", "x_mm", "y_mm", "hole_diameter_mm"), holes)
        measured = [float(h["hole_diameter_mm"]) for h in table]
        locations = {(float(h["x_mm"]), float(h["y_mm"])) for h in table}
        expected = {(col * c["pitch_x_mm"], row * c["pitch_y_mm"])
                    for row in range(c["rows"]) for col in range(c["cols"])}
        require(len(locations) == len(table) == 72, "72 unique opening locations are required")
        require(locations == expected, "opening coordinates differ from matched tray pitch")
        smallest = min(measured) - c["diameter_tol_mm"]
        largest = max(measured) + c["diameter_tol_mm"]
        require(smallest > 0, "minimum hole diameter must stay positive")
        seal_force_n = c["vacuum_pa"] * math.pi * (smallest / 2000) ** 2
        load_n = c["max_seed_mass_mg"] * 1e-6 * 9.80665 * c["max_hand_load_g"]
        radial_budget = c["max_alignment_mm"] - math.sqrt(2) * c["xy_tol_mm"]
        margin = seal_force_n / load_n
        result[label] = dict(holes=len(table), ideal_sealed_force_ratio=round(margin, 2),
                             seed_width_margin_mm=round(c["min_seed_width_mm"] - largest, 3),
                             residual_location_budget_mm=round(radial_budget, 3))
        require((margin >= 3 and largest < c["min_seed_width_mm"] and radial_budget >= 0)
                == (label == "candidate"), f"P111 unexpected decision for {label}")
    return result


def build_p112(c, out):
    result = {}
    for label, brace in (("candidate", c["brace_mm"]), ("control", c["control_brace_mm"])):
        span = c["support_span_mm"]
        section_i = c["brace_width_mm"] * brace**3 / 12
        tips = []
        for row in range(c["rows"]):
            for col in range(c["cols"]):
                position = span / 2 + (col - (c["cols"] - 1) / 2) * c["pitch_mm"]
                require(0 <= position <= span, "dibble position outside brace supports")
                x = min(position, span - position)
                sag = c["press_force_n"] * x * (3 * span**2 - 4 * x**2) / (48 * c["modulus_mpa"] * section_i)
                stack = c["tip_stack_error_mm"] + c["tray_stack_error_mm"]
                tips.append((col + 1, row + 1, position, row * c["pitch_mm"],
                             round(c["target_depth_mm"] - sag - stack, 4),
                             round(c["target_depth_mm"] - sag + stack, 4), brace))
        table = csv_roundtrip(out / f"dibble-{label}.csv",
                              ("column", "row", "x_mm", "y_mm", "min_depth_mm", "max_depth_mm", "brace_mm"), tips)
        worst = max(abs(float(r[key]) - c["target_depth_mm"]) for key in ("min_depth_mm", "max_depth_mm")
                    for r in table)
        require(len({(r["x_mm"], r["y_mm"]) for r in table}) == 24, "24 individual positions required")
        require((worst <= 2) == (label == "candidate"), f"P112 unexpected decision for {label}")
        result[label] = dict(measured_positions=len(table), worst_modeled_depth_error_mm=round(worst, 3))
    return result


def count_gate(samples, c):
    """Return a drop time after the gate has cleared long enough to re-arm."""
    count = []
    blocked_run = clear_run = 0
    first_blocked = None
    for stamp, amplitude in samples:
        if amplitude <= c["beam_low"]:
            if blocked_run == 0:
                first_blocked = stamp
            blocked_run += 1
            clear_run = 0
        elif amplitude >= c["beam_high"]:
            clear_run += 1
            if clear_run == c["min_clear_samples"]:
                if blocked_run >= c["min_blocked_samples"]:
                    count.append(first_blocked)
                blocked_run = 0
    return count


def build_p119(c, out):
    result = {}
    for label, overlap in (("spaced", False), ("close-pair-control", True)):
        truth = []
        samples = []
        for index in range(c["drops"]):
            if overlap and index % 2:
                onset = truth[-1] + 3 + c["paired_gap_ms"]
            else:
                onset = (index + 1) * c["spacing_ms"]
            truth.append(onset)
        for stamp in range(0, truth[-1] + 20, c["sample_ms"]):
            blocked = any(start <= stamp < start + 3 for start in truth)
            glitch = stamp % c["spacing_ms"] == 15
            samples.append((stamp, 70 if blocked or glitch else 300))
        table = csv_roundtrip(out / f"gate-{label}-adc.csv", ("stamp_ms", "amplitude"), samples)
        events = count_gate([(int(row["stamp_ms"]), int(row["amplitude"])) for row in table], c)
        csv_roundtrip(out / f"gate-{label}-events.csv", ("drop_ms",), ((stamp,) for stamp in events))
        accuracy = len(set(events) & set(truth))
        false_count = len(events) - accuracy
        require((accuracy >= 98 and false_count == 0) == (label == "spaced"), f"P119 unexpected decision for {label}")
        result[label] = dict(truth=len(truth), detected=len(events), true_timestamps=accuracy, false_events=false_count)
    return result


def build_p122(c, out):
    result = {}
    hydrostatic_bar = 1000 * 9.80665 * (c["tap_height_delta_mm"] / 1000) / 100000
    for label, accuracy in (("candidate", c["class_pct"]), ("control", c["control_class_pct"])):
        step = c["display_step_bar"]
        instrument_span_bar = c["full_scale_bar"] * accuracy / 100
        bound_bar = 2 * instrument_span_bar + step + abs(hydrostatic_bar)
        rows = []
        for common in c["common_pressures_bar"]:
            for up_error, down_error in itertools.product((-instrument_span_bar, instrument_span_bar), repeat=2):
                upstream = round((common + hydrostatic_bar / 2 + up_error) / step) * step
                downstream = round((common - hydrostatic_bar / 2 + down_error) / step) * step
                rows.append((common, up_error, down_error, upstream, downstream))
        table = csv_roundtrip(out / f"pressure-{label}.csv",
                              ("reference_bar", "up_offset_bar", "down_offset_bar", "up_bar", "down_bar"), rows)
        delta = max(abs(float(r["up_bar"]) - float(r["down_bar"])) for r in table)
        require(all(0 <= float(r[col]) <= c["full_scale_bar"] for r in table for col in ("up_bar", "down_bar")),
                "simulated readings outside gauge span")
        require((max(delta, bound_bar) <= c["limit_bar"]) == (label == "candidate"),
                f"P122 unexpected decision for {label}")
        require(delta <= bound_bar + 1e-9, "simulated differential exceeds theoretical bound")
        result[label] = dict(corners=len(table), worst_simulated_pair_bar=round(delta, 4),
                             conservative_error_budget_bar=round(bound_bar, 4))
    return result


def divider_resistance(forward, reverse, full_scale, series):
    """Measure a resistor from two reversed-polarity ADC captures."""
    if (forward, reverse) == (0, full_scale):
        return None, "open"
    if (forward, reverse) == (full_scale, 0):
        return None, "short"
    if not (0 < forward < full_scale and 0 < reverse < full_scale):
        return None, "rail"
    return (series * (full_scale - forward) / forward
            + series * reverse / (full_scale - reverse)) / 2, "ok"


def tension_kpa(ohm, celsius):
    kohm = ohm / 1000
    denom = 1 - 0.009733 * kohm - 0.01205 * celsius
    if denom <= 0:
        return None
    tension = (3.213 * kohm + 4.093) / denom
    return tension if 10 <= tension <= 100 else None


def build_p126(c, out):
    max_code = c["adc_max_code"]
    nominal = c["series_ohm"]
    rows = []
    for expected, temperature, tolerance in itertools.product(c["resistors_ohm"], c["temperatures_c"], (-1, 1)):
        real_series = nominal * (1 + tolerance * c["series_tol_pct"] / 100)
        forward = round(real_series / (expected + real_series) * max_code)
        reverse = round(expected / (expected + real_series) * max_code)
        rows.append((expected, temperature, forward, reverse))
    rows.extend((("", 24, 0, max_code), ("", 24, max_code, 0), ("", 24, 0, 0)))
    table = csv_roundtrip(out / "soil-tension-resistor-input.csv",
                          ("elapsed_s", "reference_ohm", "soil_temp_c", "forward_code", "reverse_code"),
                          ((index * 60, *row) for index, row in enumerate(rows)))
    decoded = []
    for sample in table:
        expected = sample["reference_ohm"]
        temp = float(sample["soil_temp_c"])
        ohm, state = divider_resistance(int(sample["forward_code"]), int(sample["reverse_code"]), max_code, nominal)
        kpa = None if ohm is None else tension_kpa(ohm, temp)
        default = None if ohm is None else tension_kpa(ohm, c["fallback_c"])
        calibration = ("within_model" if kpa is not None else
                       "outside_model" if ohm is not None else "unavailable")
        decoded.append((sample["elapsed_s"], expected, temp, ohm, state, calibration, kpa, default))
    export = csv_roundtrip(out / "soil-tension-resistor-results.csv",
                           ("elapsed_s", "reference_ohm", "soil_temp_c", "read_ohm", "state",
                            "calibration", "kpa", "fixed_temp_control_kpa"), decoded)
    valid = [r for r in export if r["state"] == "ok"]
    error_pct = max(abs(float(r["read_ohm"]) / float(r["reference_ohm"]) - 1) for r in valid) * 100
    bias = max(abs(float(r["kpa"]) - float(r["fixed_temp_control_kpa"])) for r in valid
               if r["kpa"] and r["fixed_temp_control_kpa"])
    require(error_pct <= c["max_error_pct"], "P126 resistor tolerance exceeded")
    require({r["state"] for r in export if not r["reference_ohm"]} == {"open", "short", "rail"}, "P126 rail fault missing")
    require(bias > c["max_default_bias_kpa"], "P126 fixed-temperature control unexpectedly passed")
    return dict(resistor_temperature_corners=len(valid), worst_resistance_error_pct=round(error_pct, 3),
                worst_fixed_temperature_control_bias_kpa=round(bias, 3),
                omitted_invalid_electrical_rows=len(export) - len(valid))


def wetness_events(samples, c, confirm):
    """Emit confirmed transition times and explicit unknown intervals on sampling gaps."""
    state = None
    pending = None
    start = previous = None
    count = 0
    events = []
    for stamp, signal in samples:
        if previous is not None and stamp - previous > c["max_gap_s"]:
            events.append((previous + c["cadence_s"], "unknown"))
            state = pending = None
            count = 0
        previous = stamp
        crossing = "wet" if signal >= c["wet_on"] else "dry" if signal <= c["wet_off"] else None
        if crossing is None or crossing == state:
            pending = None
            count = 0
            continue
        if crossing != pending:
            start = stamp
            pending = crossing
            count = 0
        count += 1
        if count == confirm:
            state = crossing
            events.append((start, state))
            pending = None
            count = 0
    return events


def build_p128(c, out):
    period = c["cycle_period_s"]
    cadence = c["cadence_s"]
    delay = 4 * cadence + 5
    seconds = c["cycles"] * period
    true_events = [(start + offset, state) for start in range(0, seconds, period)
                   for offset, state in ((delay, "wet"), (delay + c["wet_duration_s"], "dry"))]
    dropout = seconds - cadence * 2
    samples = []
    for stamp in range(0, seconds + 4 * cadence, cadence):
        if stamp == dropout:
            continue
        phase = stamp % period
        wet = delay <= phase < delay + c["wet_duration_s"] and stamp < seconds
        signal = 820 if wet else 300
        if phase == cadence * 2 and stamp < seconds:
            signal = 850
        if phase == delay + 5 * cadence - 5 and stamp < seconds:
            signal = 420
        samples.append((stamp, signal))
    raw = csv_roundtrip(out / "leaf-wetness-samples.csv", ("stamp_s", "value"), samples)
    samples = [(int(r["stamp_s"]), int(r["value"])) for r in raw]
    result = {}
    for label, confirm in (("confirmed", c["confirm"]), ("one-sample-control", c["control_confirm"])):
        events = wetness_events(samples, c, confirm)
        table = csv_roundtrip(out / f"leaf-wetness-{label}.csv", ("stamp_s", "state"), events)
        events = [(int(r["stamp_s"]), r["state"]) for r in table]
        qualified = [(t, s) for t, s in events if cadence * 2 <= t < dropout]
        same_sequence = [state for _, state in qualified] == [state for _, state in true_events]
        edge_delay = max((abs(t - target) for (t, _), (target, _) in zip(qualified, true_events)),
                         default=0) if same_sequence else None
        recovered = (dropout, "unknown") in events and (dropout + cadence, "dry") in events
        maximum_confirmed_delay = None if edge_delay is None else edge_delay + (confirm - 1) * cadence
        windows = [(start, end, end - start) for (start, first), (end, second) in itertools.pairwise(events)
                   if first == "wet" and second == "dry"]
        durations = csv_roundtrip(out / f"leaf-wetness-{label}-duration.csv",
                                  ("wet_start_s", "dry_start_s", "wet_duration_s"), windows)
        duration_error = max(abs(int(window["wet_duration_s"]) - c["wet_duration_s"]) for window in durations)
        require(((maximum_confirmed_delay is not None and maximum_confirmed_delay <= 120) and recovered)
                == (label == "confirmed"), f"P128 unexpected decision for {label}")
        result[label] = dict(reference_edges=len(true_events), emitted_edges=len(qualified),
                             worst_edge_timestamp_error_s=edge_delay,
                             worst_observed_confirmation_latency_s=maximum_confirmed_delay,
                             complete_wet_windows=len(durations), max_wet_duration_error_s=duration_error,
                             gap_logged_and_recovered=recovered)
    return result


def build_p132(c, out):
    result = {}
    for label, diameter in (("candidate", c["rod_mm"]), ("control", c["control_rod_mm"])):
        specs = (
            ("sleeve_inner_diameter", c["sleeve_id_mm"], c["size_tol_mm"]),
            ("sleeve_length", c["sleeve_length_mm"], c["size_tol_mm"]),
            ("ejector_shoe_diameter", c["shoe_mm"], c["size_tol_mm"]),
            ("ejector_unsupported_span", c["ejector_span_mm"], 0),
            ("ejector_rod_diameter", diameter, c["rod_tol_mm"]),
        )
        table = csv_roundtrip(out / f"core-sampler-{label}.csv", ("feature", "nominal_mm", "tol_mm"), specs)
        size = {r["feature"]: (float(r["nominal_mm"]), float(r["tol_mm"])) for r in table}
        sleeve, sleeve_tol = size["sleeve_inner_diameter"]
        shoe, shoe_tol = size["ejector_shoe_diameter"]
        rod, rod_tol = size["ejector_rod_diameter"]
        clearance = sleeve - sleeve_tol - shoe - shoe_tol
        length = size["ejector_unsupported_span"][0] * c["effective_length_factor"]
        second_moment = math.pi * (rod - rod_tol)**4 / 64
        critical = math.pi**2 * c["modulus_mpa"] * second_moment / length**2
        force_ratio = critical / c["ejection_force_n"]
        require((clearance >= 0.5 and force_ratio >= c["buckling_factor"]) == (label == "candidate"),
                f"P132 unexpected decision for {label}")
        result[label] = dict(min_diametral_ejector_clearance_mm=round(clearance, 3),
                             euler_critical_force_n=round(critical, 1), euler_load_ratio=round(force_ratio, 2))
    return result


def build_p134(c, out):
    radius = c["diameter_mm"] / 2
    disk = create_svg(c["diameter_mm"], c["diameter_mm"], "Secchi disk masking pattern")
    angles = ((1, 0), (0, 1), (-1, 0), (0, -1))
    for quadrant, (start, finish) in enumerate(zip(angles, angles[1:] + angles[:1])):
        x1, y1 = (radius * (1 + axis) for axis in start)
        x2, y2 = (radius * (1 + axis) for axis in finish)
        element(disk, "path", d=f"M {radius} {radius} L {x1} {y1} A {radius} {radius} 0 0 1 {x2} {y2} Z",
                fill="black" if quadrant % 2 == 0 else "white")
    readback = export_svg(disk, out / "secchi-quadrants.svg")
    require(readback.get("width") == "200mm" and readback.get("height") == "200mm",
            "P134 freshwater profile must be 200 mm square")
    require([p.get("fill") for p in readback.findall(f"{{{SVG}}}path")] == ["black", "white", "black", "white"],
            "P134 marking quadrants were not alternating")
    turns = int(c["spool_width_mm"] // c["line_d_mm"])
    layers = int((c["flange_d_mm"] - c["hub_d_mm"]) // (2 * c["line_d_mm"])) - 1
    capacity = turns * sum(math.pi * (c["hub_d_mm"] + (2 * layer + 1) * c["line_d_mm"])
                           for layer in range(max(0, layers)))
    require(capacity > c["length_mm"], "P134 storage spool capacity insufficient")
    result = {"ideal_storage_capacity_mm": round(capacity)}
    for label, strain in (("candidate", c["residual_strain"]), ("control", c["control_residual_strain"])):
        rows = [(mark, mark * (1 - strain) - c["label_tol_mm"], mark * (1 + strain) + c["label_tol_mm"])
                for mark in range(c["mark_pitch_mm"], c["length_mm"] + 1, c["mark_pitch_mm"])]
        table = csv_roundtrip(out / f"secchi-line-{label}.csv", ("nominal_mm", "min_loaded_mm", "max_loaded_mm"), rows)
        shift = max(abs(float(r[key]) - float(r["nominal_mm"]))
                    for r in table for key in ("min_loaded_mm", "max_loaded_mm"))
        require((shift <= c["allowable_error_mm"]) == (label == "candidate"),
                f"P134 unexpected decision for {label}")
        result[label] = dict(marks_checked=len(table), worst_loaded_mark_error_mm=round(shift, 2))
    return result


def build_p135(c, out):
    volume = math.pi * (c["bore_mm"] / 2)**2 * c["effective_length_mm"] / 1000
    require(975 <= volume <= 1025, "P135 nominal chamber is outside litre target")
    result = {"nominal_chamber_ml": round(volume, 2)}
    for label, hold in (("candidate", c["linger_s"]), ("control", c["control_linger_s"])):
        corners = []
        for sign_v, sign_q in itertools.product((-1, 1), repeat=2):
            v = volume * (1 + sign_v * c["volume_deviation_pct"] / 100)
            q = c["effective_exchange_ml_s"] * (1 + sign_q * c["exchange_deviation_pct"] / 100)
            residual_fraction = math.exp(-q * hold / v)
            added_ml = c["carryover_ml"] + c["retrieval_leak_ml"]
            require(0 <= added_ml <= v, "P135 carryover and leakage must fit chamber")
            final = ((v - added_ml) * residual_fraction + added_ml) / v
            corners.append((round(v, 3), q, hold, round(residual_fraction, 6), round(final, 6)))
        table = csv_roundtrip(out / f"purge-{label}.csv",
                              ("chamber_ml", "exchange_ml_s", "hold_s", "fraction_before_closure", "retrieved_bad_fraction"),
                              corners)
        worst = max(float(r["retrieved_bad_fraction"]) for r in table)
        require((worst < c["bad_fraction_limit"]) == (label == "candidate"), f"P135 unexpected decision for {label}")
        result[label] = dict(corners=len(table), max_retrieved_bad_pct=round(worst * 100, 2))
    return result


def build_p139(c, out):
    result = {}
    for label, correction in (("compensated", 1 / c["printer_scale_x"]), ("native-control", 1)):
        strip = create_svg(c["origin_mm"] + c["span_mm"] * max(1, correction) + 12,
                           c["strip_height_mm"], "Fish length board insert")
        element(strip, "rect", x=0, y=0, width="100%", height="100%", fill="white")
        for measured in range(c["span_mm"] + 1):
            x = round(c["origin_mm"] + measured * correction, 5)
            extent = 15 if measured % 10 == 0 else 9 if measured % 5 == 0 else 4
            element(strip, "line", x1=x, x2=x, y1=0, y2=extent,
                    data_graduation_mm=measured, stroke="#111827", stroke_width=0.20)
            if measured % 40 == 0:
                element(strip, "text", x=x, y=24, font_size=5, text_anchor="middle").text = str(measured)
        output = export_svg(strip, out / f"ruler-{label}.svg")
        marks = {int(mark.get("data-graduation-mm")): float(mark.get("x1"))
                 for mark in output.findall(f"{{{SVG}}}line")}
        require(len(marks) == c["span_mm"] + 1 and all(marks[n] > marks[n - 1] for n in range(1, len(marks))),
                "P139 ruler graduations missing or out of order")
        residual = c["residual_scale_pct"] / 100
        stations = [c["span_mm"] * n / 10 for n in range(1, 11)]
        worst = max(abs((marks[station] - marks[0]) * c["printer_scale_x"] * (1 + sign * residual) - station)
                    + c["stop_tol_mm"] for station, sign in itertools.product(stations, (-1, 1)))
        require((worst <= c["reference_limit_mm"]) == (label == "compensated"), f"P139 unexpected decision for {label}")
        result[label] = dict(ticks=len(marks), reference_checks=len(stations), maximum_error_mm=round(worst, 3))
    return result


def build_p150(c, out):
    result = {}
    order = sorted(c["screens_mm"], reverse=True)
    width = (c["cols"] - 1) * c["pitch_mm"] + 2 * c["edge_mm"]
    height = (c["rows"] - 1) * c["pitch_mm"] + 2 * c["edge_mm"]
    for label, compensation in (("candidate", c["kerf_mm"]), ("control", 0)):
        aperture_bounds = []
        plate_rows = []
        for index, target in enumerate(order, 1):
            plate = create_svg(width, height, f"Plate {index} closed circular cut centerlines, mm")
            # Locate perforations only. The uncut border is the plate size in the SVG page.
            for row, col in itertools.product(range(c["rows"]), range(c["cols"])):
                element(plate, "circle", cx=c["edge_mm"] + c["pitch_mm"] * col,
                        cy=c["edge_mm"] + c["pitch_mm"] * row,
                        r=round((target - compensation) / 2, 5), stroke="#111827", stroke_width=0.02, fill="none")
            replay = export_svg(plate, out / f"sieve-{index}-{label}.svg")
            circles = replay.findall(f"{{{SVG}}}circle")
            opening = [2 * float(circle.get("r")) + c["kerf_mm"] for circle in circles]
            centers = {(float(circle.get("cx")), float(circle.get("cy"))) for circle in circles}
            require(len(centers) == len(circles) == c["rows"] * c["cols"], "P150 holes missing")
            min_spacing = min(math.dist(first, second) for first, second in itertools.combinations(centers, 2))
            worst_error = max(abs(size - target) for size in opening)
            lower = min(opening) - c["hole_tol_mm"]
            upper = max(opening) + c["hole_tol_mm"]
            aperture_bounds.append((lower, upper))
            plate_rows.append((index, target, len(centers), lower, upper, worst_error,
                               min_spacing - upper))
        table = csv_roundtrip(out / f"sieve-{label}-measurements.csv",
                              ("plate", "target_mm", "openings", "worst_min_mm", "worst_max_mm",
                               "systematic_error_mm", "min_web_mm"), plate_rows)
        max_error = max(float(r["systematic_error_mm"]) for r in table)
        min_web = min(float(r["min_web_mm"]) for r in table)
        mass_bins = [0, 0, 0]
        ambiguous_g = 0
        for width_mm, grams in c["gauge_mix"]:
            for grade, (lower, upper) in enumerate(aperture_bounds):
                if width_mm > upper:
                    mass_bins[grade] += grams
                    break
                if width_mm >= lower:
                    ambiguous_g += grams
                    break
            else:
                mass_bins[-1] += grams
        require(sum(mass_bins) + ambiguous_g == sum(m for _, m in c["gauge_mix"]), "P150 fixture mass lost")
        require((max_error < c["hole_tol_mm"] and min_web >= c["min_ligament_mm"] and ambiguous_g == 0)
                == (label == "candidate"), f"P150 unexpected decision for {label}")
        result[label] = dict(openings=sum(int(r["openings"]) for r in table), min_web_mm=round(min_web, 2),
                             systematic_error_mm=round(max_error, 3), unambiguous_g=mass_bins, ambiguous_g=ambiguous_g)
    return result


def build_p151(c, out):
    size = c["slot_clear_mm"] + c["separator_mm"]
    total_width = size * c["slots"] - c["separator_mm"]
    table = csv_roundtrip(out / "riffle-chute-schedule.csv", ("slot", "left_mm", "right_mm", "ramp_deg", "tray"),
                          ((n + 1, n * size, n * size + c["slot_clear_mm"], c["slope_deg"], "AB"[n % 2])
                           for n in range(c["slots"])))
    chutes = [(float(r["left_mm"]), float(r["right_mm"]), r["tray"]) for r in table]
    require(len(chutes) % 2 == 0 and chutes[-1][1] == total_width, "P151 chute schedule size incorrect")
    require(all(right - left >= 3 * c["particle_max_mm"] for left, right, _ in chutes),
            "P151 assumed three-particle chute clearance failed")
    require(all(math.tan(math.radians(float(r["ramp_deg"]))) > c["friction_slope_ratio"] for r in table),
            "P151 ramp does not slide under assumed friction")
    results = {}
    for label, biased in (("uniform", False), ("one-chute-control", True)):
        rows = []
        for trial in range(c["trials"]):
            rng = random.Random(5000 + trial)
            mass = [0.0, 0.0]
            colored = [0.0, 0.0]
            for index in range(c["beads"]):
                fraction = rng.random()
                skewed = biased and index < c["beads"] * c["control_feed_fraction"]
                chute = chutes[0 if skewed else int(fraction * len(chutes))]
                tray = "AB".index(chute[2])
                mass[tray] += c["bead_g"]
                colored[tray] += c["bead_g"] if index % 4 == 0 else 0
            rows.append((trial + 1, *mass, colored[0] / mass[0], colored[1] / mass[1]))
        checked = csv_roundtrip(out / f"riffle-{label}.csv", ("trial", "tray_a_g", "tray_b_g", "colored_a", "colored_b"), rows)
        batch_mass = c["bead_g"] * c["beads"]
        target = batch_mass / 2
        require(all(math.isclose(float(r["tray_a_g"]) + float(r["tray_b_g"]), batch_mass) for r in checked),
                "P151 outlet mass does not sum to intake")
        max_half_error = max(abs(float(r[outlet]) - target) / target * 100
                             for r in checked for outlet in ("tray_a_g", "tray_b_g"))
        max_color_gap = max(abs(float(r["colored_a"]) - float(r["colored_b"])) * 100 for r in checked)
        require((max_half_error <= c["max_half_error_pct"]) == (label == "uniform"),
                f"P151 unexpected decision for {label}")
        results[label] = dict(splits=len(checked), max_half_mass_error_pct=round(max_half_error, 2),
                              max_color_gap_percentage_points=round(max_color_gap, 2))
    return results


TRIALS = {
    "P111": build_p111, "P112": build_p112, "P119": build_p119, "P122": build_p122,
    "P126": build_p126, "P128": build_p128, "P132": build_p132, "P134": build_p134,
    "P135": build_p135, "P139": build_p139, "P150": build_p150, "P151": build_p151,
}


def generate(output, case_file, selected):
    cases = json.loads(case_file.read_text(encoding="utf-8"))
    for product_id in selected:
        case = cases[product_id]
        directory = output / product_id
        directory.mkdir(parents=True, exist_ok=True)
        metrics = TRIALS[product_id](case, directory)
        report = json.dumps({"pilot": case["pilot"], "metrics": metrics}, indent=2)
        (directory / "results.json").write_text(report + "\n", encoding="utf-8")
        print(f"{product_id} {json.dumps(metrics)}")


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
    with tempfile.TemporaryDirectory(prefix="hs-field-") as temp:
        fresh = Path(temp)
        generate(fresh, args.config, selected)
        for product_id in selected:
            replay = {path.name: path.read_bytes() for path in (fresh / product_id).iterdir()}
            delivered = {path.name: path.read_bytes() for path in (ROOT / "generated" / product_id).iterdir()}
            require(delivered == replay, f"{product_id} delivered outputs differ from replay")


if __name__ == "__main__":
    main()
