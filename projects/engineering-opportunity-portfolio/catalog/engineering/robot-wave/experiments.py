"""Deterministic engineering screens. Millimetres, newtons and seconds unless specified."""

import math
import random
from itertools import product


def outcome(values, revised_passes, control_rejected):
    if not revised_passes or not control_rejected:
        raise ValueError(f"Design or adverse control missed its criterion: {values}")
    return values


def conveyor(d):
    def margin(pos, speed):
        braking = speed * d["delay_s"] + speed**2 / (2 * d["brake_mm_s2"])
        return d["length"] - d["edge_buffer"] - pos - braking

    current = [margin(d["sensor_x"], v) for v in d["speeds"]]
    old = margin(d["old_sensor_x"], max(d["speeds"]))
    return outcome(
        {"stop_margin_mm_at_requested_speeds": current, "old_fast_margin_mm": old},
        min(current) >= 0,
        old < 0,
    )


def singulator(d):
    def window(gap):
        return (
            gap - d["gap_error"] - d["max_thick"],
            2 * d["min_thick"] * (1 - d["compression"]) - gap - d["gap_error"],
        )

    single, double = window(d["gate"])
    _, old_double = window(d["old_gate"])
    side_by_side = 2 * d["min_diameter"] * (1 - d["compression"]) - d["chute_width"]
    return outcome(
        {
            "single_clearance_mm": single,
            "side_by_side_rejection_margin_mm": side_by_side,
            "double_rejection_margin_mm": double,
            "old_double_margin_mm": old_double,
            "lateral_clearance_mm": d["chute_width"] - d["max_diameter"],
        },
        min(single, double, side_by_side, d["chute_width"] - d["max_diameter"]) > 0,
        old_double <= 0,
    )


def sorter(d):
    rng = random.Random(183)
    classes = d["classes"]

    def classify(rgb):
        norm = [x / sum(rgb) for x in rgb]
        return min(
            classes,
            key=lambda k: sum(
                (v / sum(classes[k]) - n) ** 2 for v, n in zip(classes[k], norm)
            ),
        )

    scores = []
    for light in d["ambient_levels"]:
        correct = 0
        for _ in range(100):
            label = rng.choice(list(classes))
            gain = rng.uniform(0.7, 1.1)
            dark = [v + light for v in d["ref_dark"]]
            sample = [
                round(v * gain + b + rng.uniform(-d["uncertainty"], d["uncertainty"]))
                for v, b in zip(classes[label], dark)
            ]
            correct += classify([x - b for x, b in zip(sample, dark)]) == label
        scores.append(correct)

    def headroom(gate):
        return (gate - d["read_x"]) / d["speed"] - d["sensing_time"] - d["gate_time"]

    return outcome(
        {
            "synthetic_correct_per_100_by_light": scores,
            "gate_margin_s": headroom(d["gate_x"]),
            "old_gate_margin_s": headroom(d["old_gate_x"]),
        },
        min(scores) >= 95 and headroom(d["gate_x"]) > 0,
        headroom(d["old_gate_x"]) <= 0,
    )


def odometer(d):
    def err(slip, period):
        counts = round(
            d["travel_mm"]
            * (1 - slip)
            / d["assumed_rolling_mm_per_turn"]
            * d["encoder_counts"]
        )
        return 100 * (counts / d["encoder_counts"] * period / d["travel_mm"] - 1)

    calibrated = {
        k: err(v, d["assumed_rolling_mm_per_turn"]) for k, v in d["floors"].items()
    }
    degraded = err(0.035, d["assumed_rolling_mm_per_turn"])
    return outcome(
        {
            "calibrated_error_pct": calibrated,
            "calibration_input": "assumed rolling circumference",
            "geometric_wheel_error_pct": {
                k: err(v, math.pi * d["wheel_diameter"]) for k, v in d["floors"].items()
            },
            "high_slip_error_pct": degraded,
        },
        max(map(abs, calibrated.values())) <= d["error_limit_pct"],
        abs(degraded) > d["error_limit_pct"],
    )


def pusher(d):
    travel = (
        d["latency_s"] * d["speed"]
        + d["speed"] ** 2 / (2 * d["decel_mm_s2"])
        + d["switch_uncertainty"]
    )

    def margin(x):
        return d["guide_travel"] - x - travel - d["hard_stop_margin"]

    return outcome(
        {
            "worst_after_limit_mm": travel,
            "revised_margin_mm": margin(d["limit_x"]),
            "old_margin_mm": margin(d["old_limit_x"]),
            "assumed_speed_mm_s": d["speed"],
        },
        margin(d["limit_x"]) >= 0,
        margin(d["old_limit_x"]) < 0,
    )


def tracker(d):
    sensors = [(i - (d["sensors"] - 1) / 2) * d["pitch"] for i in range(d["sensors"])]
    samples = []
    for gain, offset in product(d["light_factors"], d["offsets"]):
        sig = [
            gain * max(0, 1 - 2 * abs(x - offset) / d["line_width"]) for x in sensors
        ]
        if max(sig) < d["signal_floor"]:
            raise ValueError("Lost line")
        estimate = sum(v * x for x, v in zip(sensors, sig)) / sum(sig)
        samples.append(abs(estimate - offset))

    # A uniform dark crossing has high signal everywhere and no unique steering cue.
    def unique(sig):
        return max(sig) >= d["signal_floor"] and max(sig) - min(sig) > d["signal_floor"]

    return outcome(
        {
            "normal_positions": len(samples),
            "max_centroid_error_mm": max(samples),
            "uniform_crossing_has_unique_cue": unique([0.8] * len(sensors)),
            "all_white_has_line": unique([0] * len(sensors)),
        },
        max(samples) < d["pitch"] / 2,
        not unique([0.8] * len(sensors)) and not unique([0] * len(sensors)),
    )


def cradle(d):
    torque = d["board_mass"] * 9.80665 * d["cg_from_pivot"] / 1000 * d["factor"]

    def hold(n):
        return d["friction"] * n * d["pivot_radius"] / 1000 - torque

    def fit(gap):
        return gap - d["gap_error"] - d["board_max_thick"]

    return outcome(
        {
            "required_torque_Nm_including_factor": torque,
            "torque_margin_Nm": hold(d["clamp_N"]),
            "low_preload_55N_margin_Nm": hold(55),
            "max_board_gap_margin_mm": fit(d["jaw_max_gap"]),
            "old_gap_margin_mm": fit(d["old_gap"]),
        },
        hold(d["clamp_N"]) > 0 and fit(d["jaw_max_gap"]) > 0,
        hold(55) < 0 and fit(d["old_gap"]) < 0,
    )


def tilt(d):
    def clearance(pivot, deg):
        a = math.radians(deg)
        radius = (
            abs(math.cos(a)) * d["pcb_height"] + abs(math.sin(a)) * d["depth"]
        ) / 2
        return pivot - radius - d["harness_loop"] - d["frame_clearance"]

    a = math.degrees(math.atan2(d["depth"], d["pcb_height"]))
    lim = d["tilt_limit_deg"] + d["angle_error_deg"]
    angles = [-lim, -min(lim, a), 0, min(lim, a), lim]

    def worst(pivot):
        return min(clearance(pivot, ang) for ang in angles)

    return outcome(
        {
            "extremum_angle_deg": a,
            "min_sweep_margin_mm": worst(d["pivot_height"]),
            "old_margin_mm": worst(d["old_pivot_height"]),
            "angles_tested_deg": angles,
        },
        worst(d["pivot_height"]) > 0,
        worst(d["old_pivot_height"]) < 0,
    )


def bumper(d):
    # Rigid beam on two identical linear spring supports, nearest support takes more load.
    # Reaction fraction is clamped at one past the support (other switch unloads).
    positions = sorted(
        {i * d["length"] / 9 - d["length"] / 2 for i in range(10)} | {0.0}
    )

    def stroke(x):
        fraction = min(1, 0.5 + abs(x) / d["switch_span"])
        return min(
            d["overtravel_stop_mm"],
            d["contact_force_N"] * fraction / d["spring_N_per_mm"],
        )

    weakest = min(stroke(x) for x in positions)

    def margin(t):
        return weakest - t - d["switch_tolerance_mm"]

    return outcome(
        {
            "contact_positions_mm": positions,
            "minimum_nearer_switch_travel_mm": weakest,
            "trigger_margin_mm": margin(d["trigger_mm"]),
            "old_trigger_margin_mm": margin(d["old_trigger_mm"]),
        },
        margin(d["trigger_mm"]) >= 0,
        margin(d["old_trigger_mm"]) < 0,
    )


def brackets(d):
    def pad_gap(start):
        return (
            start
            - d["pad_position_error"]
            - max(d["hole_pitch_from_corner"])
            - d["washer_diameter"] / 2
        )

    side_gap = (d["rail_mm"] - d["washer_diameter"]) / 2
    return outcome(
        {
            "pad_to_washer_margin_mm": pad_gap(d["pad_start"]),
            "old_margin_mm": pad_gap(d["old_pad_start"]),
            "outer_side_edge_margin_mm": side_gap,
            "corners_in_set": 4,
        },
        min(pad_gap(d["pad_start"]), side_gap) > 0,
        pad_gap(d["old_pad_start"]) < 0,
    )


def pickup(d):
    required = (
        d["coupon_mass_g"] / 1000 * (9.80665 + d["acceleration"]) * d["safety_factor"]
    )

    def lift(diam):
        return (
            math.pi * (diam / 2000) ** 2 * d["vacuum_kpa"] * 1000 * d["seal_efficiency"]
        )

    full = lift(d["cup_mm"])
    release = next(
        i * d["pressure_sample_s"]
        for i in range(1, 100)
        if full * math.exp(-i * d["pressure_sample_s"] / d["vent_tau_s"])
        < d["coupon_mass_g"] / 1000 * 9.80665
    )
    return outcome(
        {
            "required_force_N": required,
            "revised_available_N": full,
            "old_available_N": lift(d["old_cup_mm"]),
            "first_sample_below_weight_s": release,
            "diametral_throat_clearance_mm": d["fixture_throat"] - d["cup_mm"],
        },
        full >= required and d["fixture_throat"] > d["cup_mm"],
        lift(d["old_cup_mm"]) < required,
    )
