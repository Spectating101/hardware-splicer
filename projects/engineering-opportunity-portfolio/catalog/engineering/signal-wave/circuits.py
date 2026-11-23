"""Executable reference behaviors. Each trial records a nominal trace and a rejected control."""

import itertools
import math
import random
import zlib


def logger(p):
    trace = []
    last = None
    for t, v in [
        (-20, None),
        (-10, 110),
        (0, 48),
        (10, 49),
        (20, None),
        (30, None),
        (40, None),
        (50, 110),
        (60, 47),
    ]:
        valid = (
            v is not None and p["valid_range_pct"][0] <= v <= p["valid_range_pct"][1]
        )
        if valid:
            last = (t, v)
        age = t - last[0] if last else None
        quality = (
            "new"
            if valid
            else "unavailable"
            if last is None
            else "stale"
            if age > p["max_age_s"]
            else "cached"
        )
        trace.append(
            (
                t,
                str(v),
                last[1] if quality in {"new", "cached"} else "",
                quality,
                age,
                last[1] if last else "",
            )
        )
    assert [r[3] for r in trace] == [
        "unavailable",
        "unavailable",
        "new",
        "new",
        "cached",
        "cached",
        "stale",
        "stale",
        "new",
    ]
    assert (
        all(r[2] == "" for r in trace if r[3] in {"unavailable", "stale"})
        and trace[-1][2] == 47
    )
    assert trace[-2][-1] == 49
    return (
        [
            "time_s",
            "input_RH",
            "output_RH",
            "quality",
            "age_s",
            "unqualified_hold_control",
        ],
        trace,
        {
            "boot_without_sensor": "unavailable",
            "cached_rows_labelled": 2,
            "expired_rows_suppressed": 2,
        },
    )


def harness(p):
    pins = p["pins"]
    expected = [{v} for v in p["mapping"]]

    def summarize(wiring):
        return "pass" if wiring == expected else "fault"

    def naive(wiring):
        return "pass" if all(wiring) else "fault"

    cases = [("known-good", expected)]
    for i in range(len(pins)):
        opened = [s.copy() for s in expected]
        opened[i].clear()
        cases.append((f"open-{pins[i]}", opened))
    for i, j in itertools.combinations(range(len(pins)), 2):
        swapped = [s.copy() for s in expected]
        swapped[i], swapped[j] = swapped[j], swapped[i]
        cases.append((f"swap-{pins[i]}-{pins[j]}", swapped))
        short = [s.copy() for s in expected]
        short[i] = short[j] = expected[i] | expected[j]
        cases.append((f"bridge-{pins[i]}-{pins[j]}", short))
    trace = [
        (
            name,
            " ".join(",".join(map(str, sorted(x))) or "-" for x in wiring),
            summarize(wiring),
            naive(wiring),
        )
        for name, wiring in cases
    ]
    assert trace[0][2] == "pass" and all(r[2] == "fault" for r in trace[1:])
    missed = sum(r[3] == "pass" for r in trace[1:])
    assert missed == 12
    return (
        ["case", "readback_by_driven_pin", "pin_map_check", "continuity_only_control"],
        trace,
        {"single_faults_detected": len(trace) - 1, "control_missed": missed},
    )


def capture(p):
    def detects(offset, period):
        return (math.ceil(offset / period) * period - offset) < p["pulse_ns"]

    rows = []
    for channel, phase in itertools.product(
        range(p["channels"]), range(0, p["old_sample_ns"], 5)
    ):
        rows.append(
            (
                channel,
                phase,
                detects(phase, p["sample_ns"]),
                detects(phase, p["old_sample_ns"]),
            )
        )
    assert all(r[2] for r in rows) and not all(r[3] for r in rows)
    return (
        ["channel", "phase_ns", "detected", "slow_control_detected"],
        rows,
        {
            "phase_channel_cases": len(rows),
            "slow_misses": sum(not r[3] for r in rows),
            "input_pulse_ns": p["pulse_ns"],
        },
    )


def winding(p):
    pairs = [frozenset(x) for x in p["pairs"]]

    def classify(m):
        edges = [edge for edge, v in m.items() if v is not None]
        if len(edges) != 2 or len(set.union(*[set(x) for x in edges])) != 4:
            return "reject"
        return (
            "pair"
            if abs(m[edges[0]] - m[edges[1]]) <= p["unequal_limit_ohms"]
            else "reject"
        )

    rows = []
    for perm in itertools.permutations(range(4)):
        m = {
            edge: (
                p["winding_ohms"] + p["lead_ohms"]
                if frozenset(perm[i] for i in edge) in pairs
                else None
            )
            for edge in itertools.combinations(range(4), 2)
        }
        live = [k for k, v in m.items() if v is not None]
        dead = next(k for k, v in m.items() if v is None)
        rows.append(
            (
                "".join(map(str, perm)),
                str(live),
                classify(m),
                classify({**m, live[0]: None}),
                classify({**m, dead: 0.4}),
            )
        )
    assert all(r[2:] == ("pair", "reject", "reject") for r in rows)
    return (
        ["lead_order", "identified_pairs", "good", "open_coil", "bridged_coils"],
        rows,
        {"valid_permutations": len(rows), "bad_samples_rejected": 2 * len(rows)},
    )


def decades(p):
    rows = []
    for digits in itertools.product(range(10), repeat=3):
        target = sum(k * n for k, n in zip(p["decades"], digits))
        contacts = len(digits) * p["contact_ohm"] + p["lead_ohm"]
        raw = contacts + target * p["part_tolerance"]
        # 0.02 ohm assumed change per contact since shorting the instrument for its zero.
        zeroed = 0.02 * len(digits) + target * p["part_tolerance"]
        limit = p["abs_limit_ohm"] + target * p["rel_limit"]
        rows.append(
            (
                target,
                round(raw, 4),
                round(zeroed, 4),
                round(limit, 4),
                raw <= limit,
                zeroed <= limit,
            )
        )
    misses = sum(not r[4] for r in rows)
    assert misses > 0 and all(r[5] for r in rows)
    return (
        [
            "nominal_ohm",
            "raw_max_error_ohm",
            "after_zero_error_ohm",
            "limit_ohm",
            "raw_pass",
            "zeroed_pass",
        ],
        rows,
        {
            "settings": len(rows),
            "uncorrected_settings_outside_budget": misses,
            "assumed_contact_change_each_ohm": 0.02,
        },
    )


def kelvin(p):
    rows = []
    for i, rc in enumerate(p["contact_mohm"]):
        ideal = p["force_mA"] * p["shunt_mohm"]  # mA × milliohms = microvolts
        sense = p["sense_bias_uA"] * rc / 1000
        err = 100 * (p["meter_offset_uV"] + 2 * sense) / ideal
        shared = err + 100 * rc / p["shunt_mohm"]
        rows.append((i + 1, rc, round(err, 4), round(shared, 4)))
    assert (
        max(r[2] for r in rows) < p["limit_pct"]
        and min(r[3] for r in rows) > p["limit_pct"]
    )
    return (
        ["remount", "contact_mohm", "four_wire_error_pct", "shared_contact_error_pct"],
        rows,
        {
            "max_four_wire_error_pct": max(r[2] for r in rows),
            "min_shared_error_pct": min(r[3] for r in rows),
        },
    )


def pedal(p):
    edges = {}
    for start, state in [
        (10, True),
        (10 + p["press_ms"], False),
        (95, True),
        (145, False),
        (175, True),
        (220, False),
    ]:
        for i, delay in enumerate(p["bounce_ms"]):
            edges[start + delay] = state if i % 2 == 0 else not state
    raw = stable = False
    prev = False
    armed = True
    last = 0
    rows = []
    for t in range(245):
        if t in edges and raw != edges[t]:
            raw = edges[t]
            last = t
        if t == 115:
            armed = False  # reconnect while down
        event = False
        if t - last >= p["debounce_ms"] and stable != raw:
            stable = raw
            if not stable:
                armed = True
            elif armed:
                event = True
        naive = (raw and not prev) or (t == 115 and raw)
        rows.append((t, int(raw), int(stable), int(event), int(naive)))
        prev = raw
    count = sum(r[3] for r in rows)
    assert count == 3 and not rows[115][3] and sum(r[4] for r in rows) > count
    return (
        ["t_ms", "raw", "filtered", "trigger", "raw_or_reconnect_control"],
        rows,
        {"valid_triggers": count, "control_triggers": sum(r[4] for r in rows)},
    )


def mux(p):
    rows = []
    accumulated = 0

    def read(mask):
        responders = [n for n in range(p["ports"]) if mask & (1 << n)]
        if not responders:
            return None
        value = 255
        for tag in responders:
            value &= tag
        return value

    def guarded(mask):
        if mask.bit_count() != 1:
            return "reject selection"
        return read(mask)

    for port in range(p["ports"]):
        selected = 1 << port
        accumulated |= selected
        rows.append(
            (
                port,
                hex(p["address"]),
                hex(selected),
                guarded(selected),
                hex(accumulated),
                guarded(accumulated),
                read(accumulated),
            )
        )
    assert all(r[3] == r[0] for r in rows) and read(0) is None and guarded(1) == 0
    misses = sum(r[5] == "reject selection" for r in rows)
    assert misses == p["ports"] - 1 and all(r[6] == 0 for r in rows)
    return (
        [
            "port",
            "address",
            "one_hot_mask",
            "tag_read",
            "accumulating_mask",
            "interlock",
            "unguarded_open_drain_data",
        ],
        rows,
        {
            "correct_tags": len(rows),
            "unsafe_selections_rejected": misses,
            "composite_byte_looks_like_valid_port": 0,
        },
    )


def tally(p):
    rows = []
    for transition in range(100):
        program, preview = divmod(transition % 4, 2)
        color = "red" if program else "green" if preview else "off"
        # Input settles after optocoupler delay. Its phase against the scan clock varies.
        t = transition * 19.17 + p["opto_delay_ms"]

        def lag(period):
            return math.ceil(t / period) * period - t + p["opto_delay_ms"]

        rows.append(
            (
                transition,
                program,
                preview,
                color,
                round(lag(p["poll_ms"]), 3),
                round(lag(p["slow_poll_ms"]), 3),
            )
        )
    assert {r[3] for r in rows} == {"red", "green", "off"} and max(
        r[4] for r in rows
    ) <= p["response_ms"] < max(r[5] for r in rows)
    return (
        ["transition", "program", "preview", "lamp", "delay_ms", "slow_control_ms"],
        rows,
        {
            "max_delay_ms": max(r[4] for r in rows),
            "slow_control_max_ms": max(r[5] for r in rows),
            "open_contacts_output": rows[0][3],
        },
    )


def pads(p):
    rng = random.Random(214)
    rows = []
    for pad in range(4):
        for label, limits in zip(["light", "hard"], p["peak_ranges"]):
            for _ in range(p["samples"]):
                peak = rng.randint(*limits)
                levels = [
                    round(peak * p["adjacent_ratio"]) if i != pad else peak
                    for i in range(4)
                ]
                hit = [i for i, n in enumerate(levels) if n >= p["threshold"]]
                old = [i for i, n in enumerate(levels) if n >= p["old_threshold"]]
                assert hit == [pad]
                rows.append(
                    (pad, label, peak, levels[(pad + 1) % 4], len(hit), len(old))
                )
    ghosts = sum(r[5] - 1 for r in rows)
    assert ghosts > 0 and max(r[2] for r in rows if r[1] == "light") < min(
        r[2] for r in rows if r[1] == "hard"
    )
    return (
        [
            "pad",
            "strike",
            "peak_velocity",
            "coupled_peak",
            "notes",
            "low_threshold_notes",
        ],
        rows,
        {"synthetic_strikes": len(rows), "control_extra_notes": ghosts},
    )


def held_keys(p):
    n = p.get("channels", len(p.get("keys", [])))
    keys = p.get("keys", list(range(4, 4 + n)))
    rows = []
    for i in range(p["rounds"]):
        sequence = [1 << j for j in range(n)] + [(1 << n) - 1, 1, 0]
        for mask in sequence:
            report = [keys[j] for j in range(n) if mask & (1 << j)]
            old = report[:1]
            rows.append((i, mask, " ".join(map(str, report)), " ".join(map(str, old))))
            assert len(set(report)) == mask.bit_count()
    misses = sum(r[2] != r[3] for r in rows)
    assert misses == p["rounds"] and rows[-1][2] == ""
    metrics = {"reports": len(rows), "single_key_control_lost_chords": misses}
    if n == 2:
        mapping = keys.copy()
        armed = (1 << n) - 1

        def scan(mask, *, reset=False, remap=None):
            nonlocal armed, mapping
            if reset or remap is not None:
                armed &= ~mask
            if remap is not None:
                mapping = remap
            armed |= ((1 << n) - 1) ^ mask
            return [k for bit, k in enumerate(mapping) if armed & mask & (1 << bit)]

        sequence = [
            ("pressed", 1, {}, [keys[0]]),
            ("disconnect/reconnect held", 1, {"reset": True}, []),
            ("still down", 1, {}, []),
            ("release", 0, {}, []),
            ("press again", 1, {}, [keys[0]]),
            ("change map held", 1, {"remap": keys[::-1]}, []),
            ("release", 0, {}, []),
            ("new mapping", 1, {}, [keys[1]]),
            ("both", 3, {}, keys[::-1]),
            ("release all", 0, {}, []),
        ]
        for name, mask, event, expected in sequence:
            output = scan(mask, **event)
            assert output == expected
            old = " ".join(str(keys[j]) for j in range(n) if mask & (1 << j))
            rows.append((name, mask, " ".join(map(str, output)), old))
        metrics["reset_while_pressed"] = "held input inhibited until release"
        metrics["remap_and_reset_transitions"] = len(sequence)
    return (
        ["round", "held_mask", "key_usages", "single_key_or_stale_control"],
        rows,
        metrics,
    )


def journal(p):
    # Each message has independent A/B pages. Byte 0 is the commit marker, written last.
    capacity = p["max_bytes"] + 8
    previous = b"alpha sample"
    new = b"replacement audio sample"
    alternate = b"bravo sample"

    def body(gen, data):
        core = bytes([gen, len(data)]) + data
        return core + zlib.crc32(core).to_bytes(4, "little")

    def writes(page, gen, data):
        base = page * capacity
        return (
            [(base, 0)]
            + [(base + 1 + i, b) for i, b in enumerate(body(gen, data))]
            + [(base, 0xA5)]
        )

    def decode(memory, slot):
        candidates = []
        for page in [slot * 2, slot * 2 + 1]:
            base = page * capacity
            if memory[base] != 0xA5:
                continue
            length = memory[base + 2]
            if length > p["max_bytes"]:
                continue
            core = memory[base + 1 : base + 3 + length]
            checksum = memory[base + 3 + length : base + 7 + length]
            if zlib.crc32(core).to_bytes(4, "little") == checksum:
                candidates.append((core[0], bytes(core[2:])))
        return max(candidates)[1] if candidates else None

    def after(snapshot, operations):
        memory = bytearray(snapshot)
        for index, value in operations:
            memory[index] = value
        return bytes(memory)

    blank = bytes(capacity * 2 * p["slots"])
    initial = after(blank, writes(0, 1, previous) + writes(2, 1, alternate))
    ops = writes(1, 2, new)
    inplace = writes(0, 2, new)
    rows = []
    for cut in range(len(ops) + 1):
        image = after(initial, ops[:cut])
        recovered = decode(image, 0)
        assert (
            recovered == (new if cut == len(ops) else previous)
            and decode(image, 1) == alternate
        )
        overwritten = decode(after(initial, inplace[:cut]), 0)
        rows.append((cut, recovered.decode(), (overwritten or b"lost").decode()))
    assert any(r[2] == "lost" for r in rows)
    final = after(initial, ops)
    corrupted = bytearray(final)
    corrupted[capacity + 3] ^= 1
    assert decode(corrupted, 0) == previous
    # Alternate page, increment generation and reopen serialized bytes on every modeled cycle.
    for generation in range(3, 3 + p["power_cycles"]):
        data = f"cycle {generation}".encode()
        final = after(final, writes((generation - 1) % 2, generation, data))
        assert (
            decode(bytes(bytearray(final)), 0) == data and decode(final, 1) == alternate
        )
    return (
        ["write_operations_before_cut", "journal_recovery", "in_place_control"],
        rows,
        {
            "interruption_boundaries": len(rows),
            "second_slot_preserved": True,
            "completed_rewrite_and_reopen_cycles": p["power_cycles"],
            "bad_crc_recovered_prior_message": True,
        },
    )


def timer(p):
    rows = []

    def replay(preset, start, mode="ignore"):
        deadline = None
        active = False
        elapsed = None
        for clock in range(start, start + 2 * preset + 2 * p["tick_ms"], p["tick_ms"]):
            # Input edges are sampled on this clock. A second press arrives halfway through.
            pressed = (
                clock == start
                or clock
                == start + math.ceil(preset / (2 * p["tick_ms"])) * p["tick_ms"]
            )
            if pressed and (not active or mode == "restart"):
                deadline = clock + preset
                active = True
            if active and clock >= deadline:
                elapsed = clock - start
                break
        return elapsed

    for preset in p["preset_ms"]:
        for i in range(p["rounds"]):
            start = i % p["tick_ms"]
            normal = replay(preset, start)
            retrigger = replay(preset, start, "restart")
            rows.append((preset, i, normal, retrigger))
    assert all(
        0 <= r[2] - r[0] < p["tick_ms"] and r[3] - r[0] > p["tick_ms"] for r in rows
    )

    def transition(latched, power, edge):
        if not power:
            return False
        return not latched if edge else latched

    latched = False
    for i in range(p["rounds"]):
        latched = transition(latched, True, True)
        assert latched == (i % 2 == 0) and transition(latched, True, False) == latched
    after_loss = transition(True, False, False)
    assert not after_loss and not transition(after_loss, True, False)
    return (
        ["preset_ms", "cycle", "closed_ms", "retrigger_control_ms"],
        rows,
        {
            "timed_cycles": len(rows),
            "toggle_edges": p["rounds"],
            "maximum_late_ms": max(r[2] - r[0] for r in rows),
            "loss_of_power_closes_contact": after_loss,
        },
    )


def servo(p):
    def moment(mass, radius, angle):
        return mass * 9.80665 / 1000 * radius / 1000 * math.cos(math.radians(angle))

    rows = []
    for angle, da, dr, dm in itertools.product(
        p["angles_deg"], [-1, 1], [-1, 1], [-1, 1]
    ):
        nominal = moment(p["weight_g"], p["arm_mm"], angle)
        true = moment(
            p["weight_g"] + dm * p["weight_error_g"],
            p["arm_mm"] + dr * p["radius_error_mm"],
            angle + da * p["angle_error_deg"],
        )
        raw = moment(p["weight_g"], p["arm_mm"], 0)
        rows.append(
            (
                angle,
                da,
                dr,
                dm,
                round(true, 6),
                round(100 * abs(nominal / true - 1), 3),
                round(100 * abs(raw / true - 1), 3),
            )
        )
    good = max(r[-2] for r in rows)
    control = max(r[-1] for r in rows)
    assert good <= p["max_error_pct"] < control
    return (
        [
            "angle_deg",
            "angle_tol_sign",
            "radius_tol_sign",
            "mass_tol_sign",
            "moment_Nm",
            "corrected_error_pct",
            "horizontal_control_error_pct",
        ],
        rows,
        {"max_corrected_pct": good, "max_uncorrected_pct": control},
    )


def uart(p):
    def receive(byte, tx_rate, skew):
        bits = [0] + [(byte >> i) & 1 for i in range(8)] + [1]
        frame = bits + [0, 1]  # next start follows the stop bit immediately
        period = 1e6 / tx_rate
        rx = period * (1 + skew)
        sampled = [
            frame[min(len(frame) - 1, int((1.5 + i) * rx / period))] for i in range(9)
        ]
        value = sum(bit << i for i, bit in enumerate(sampled[:8]))
        return value, sampled[-1]

    rows = []
    for baud, value, sign in itertools.product(p["baud_rates"], p["bytes"], [-1, 1]):
        good, stop = receive(value, baud, sign * p["clock_skew"])
        old, old_stop = receive(value, baud, sign * p["old_skew"])
        rows.append((baud, value, sign, good, stop, old, old_stop))
    assert all(r[1] == r[3] and r[4] == 1 for r in rows)
    failed = sum(r[1] != r[5] or r[6] != 1 for r in rows)
    assert failed > 0
    return (
        [
            "baud",
            "sent",
            "timing_error_sign",
            "received",
            "stop_bit",
            "old_received",
            "old_stop_bit",
        ],
        rows,
        {"frames_accepted": len(rows), "outside_skew_faults": failed},
    )


def attenuator(p):
    def gain(tap):
        total = p["topology_ohm"]
        lower = tap * total
        loaded = lower * p["load_ohm"] / (lower + p["load_ohm"])
        return loaded / (loaded + p["source_ohm"] + total - lower)

    rows = []
    for tap in p["taps"]:

        def imbalance(tolerance):
            return 20 * math.log10(
                gain(min(1, tap * (1 + tolerance))) / gain(tap * (1 - tolerance))
            )

        rows.append(
            (
                tap,
                round(20 * math.log10(gain(tap)), 3),
                round(imbalance(p["tracking_rel"]), 3),
                round(imbalance(p["old_tracking_rel"]), 3),
            )
        )
    worst = max(r[2] for r in rows)
    raw = max(r[3] for r in rows)
    assert worst <= p["limit_db"] < raw
    return (
        ["fraction", "loaded_gain_db", "matched_imbalance_db", "unmatched_control_db"],
        rows,
        {"worst_tracking_db": worst, "control_worst_db": raw},
    )


def headphones(p):
    rows = []
    for left, right in itertools.product(p["load_ohm"], repeat=2):
        # Each load requires the requested rms voltage. Opposing phases could reduce draw;
        # both headphones reproducing the same waveform gives the simultaneous peak.
        peak = p["request_vrms"] * math.sqrt(2)
        current = 1000 * peak * (1 / left + 1 / right)
        voltage = max(peak * (1 + p["source_r_ohm"] / r) for r in (left, right))
        rows.append(
            (
                left,
                right,
                round(current, 3),
                round(voltage, 4),
                current <= p["peak_current_ma"]
                and voltage <= p["voltage_headroom_vpk"],
                current <= p["old_peak_current_ma"],
            )
        )
    assert all(r[4] for r in rows) and not all(r[5] for r in rows)
    return (
        [
            "output_A_ohm",
            "output_B_ohm",
            "per_side_peak_mA",
            "source_peak_V",
            "candidate",
            "limited_current_control",
        ],
        rows,
        {
            "load_pairs": len(rows),
            "worst_per_side_peak_mA": max(r[2] for r in rows),
            "low_current_missed_pairs": sum(not r[5] for r in rows),
        },
    )


def access_button(p):
    radius = p["face_diameter_mm"] / 2
    moment = p["switch_lever_mm"] * p["switch_force_n"] + p["bias_nmm"]
    rows = []
    for point, x, y in [
        ("center", 0, 0),
        ("near edge", -radius, 0),
        ("far edge", radius, 0),
        ("side A", 0, radius),
        ("side B", 0, -radius),
    ]:

        def force(offset):
            return moment / (offset + radius + x)

        rows.append(
            (
                point,
                x,
                y,
                round(force(p["hinge_offset_mm"]), 4),
                round(force(p["old_offset_mm"]), 4),
            )
        )
    high = max(r[3] for r in rows)
    old = max(r[4] for r in rows)
    assert high <= p["force_limit_n"] < old
    return (
        ["contact", "x_mm", "y_mm", "push_N", "old_hinge_push_N"],
        rows,
        {
            "worst_ideal_force_N": high,
            "original_worst_N": old,
            "assumptions": "Rigid face, symmetric mounting and constant bias torque; no flex, friction variation or measured accessibility.",
        },
    )
