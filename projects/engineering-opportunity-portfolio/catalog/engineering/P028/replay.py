"""Reference cycle adjudicator for captured or simulated switch-tester samples."""

import argparse
import csv
from dataclasses import dataclass
from itertools import groupby


PHASES = (("home", False, 40), ("press", True, 120), ("release", False, 120))
CHECK_WINDOW_MS = 25
DEBOUNCE_MS = 6
CYCLE_MS = sum(length for _, _, length in PHASES)


@dataclass(frozen=True)
class Sample:
    tick: int
    boot: str
    command: str
    closed: bool


def adjudicate(samples, boot):
    """Classify one commanded cycle, giving sampling integrity precedence."""
    if len(samples) != CYCLE_MS:
        return "inconclusive_length"
    phase_start = 0
    stable = None
    previous_raw = None
    since = 0
    first_fault = None
    for command, expected, length in PHASES:
        for tick in range(phase_start, phase_start + length):
            sample = samples[tick]
            if sample.boot != boot:
                return "inconclusive_reset"
            if sample.tick != tick:
                return "inconclusive_sequence"
            if sample.command != command:
                return "inconclusive_command"
            if sample.closed != previous_raw:
                since = tick
                previous_raw = sample.closed
            if tick - since >= DEBOUNCE_MS:
                stable = previous_raw
            if tick >= phase_start + length - CHECK_WINDOW_MS and stable != expected:
                first_fault = first_fault or {
                    "home": "closed_at_home", "press": "missed_close", "release": "missed_open"
                }[command]
        phase_start += length
    return first_fault or "pass"


def replay(path, expected_cycles):
    """Read contiguous groups; host-assigned cycle numbers start at one."""
    with open(path, newline="", encoding="utf-8") as file:
        rows = csv.DictReader(file)
        if rows.fieldnames != ["cycle", "tick_ms", "boot", "command", "closed"]:
            raise ValueError("Unexpected trace header")
        next_cycle = 1
        for cycle, packets in groupby(rows, lambda row: int(row["cycle"])):
            if not next_cycle <= cycle <= expected_cycles:
                raise ValueError("Out-of-order, repeated or uncommanded cycle ID")
            while next_cycle < cycle:
                yield next_cycle, "inconclusive_length"
                next_cycle += 1
            samples = []
            for packet in packets:
                if packet["closed"] not in ("0", "1") or not packet["boot"]:
                    raise ValueError("Invalid contact bit or boot epoch")
                samples.append(Sample(int(packet["tick_ms"]), packet["boot"], packet["command"],
                                      packet["closed"] == "1"))
            yield cycle, adjudicate(samples, samples[0].boot)
            next_cycle += 1
        while next_cycle <= expected_cycles:
            yield next_cycle, "inconclusive_length"
            next_cycle += 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace")
    parser.add_argument("--expected-cycles", type=int, required=True)
    args = parser.parse_args()
    if args.expected_cycles < 1:
        parser.error("expected cycles must be positive")
    for number, result in replay(args.trace, args.expected_cycles):
        print(f"{number},{result}")
