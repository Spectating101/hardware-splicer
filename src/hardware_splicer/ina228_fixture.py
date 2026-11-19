"""Explicit register fixture for testing the real decoder/logger without hardware.

This is a behavioral fake, not an electrical simulation or an instrument trace.
It is deliberately separate from the hardware capture CLI.
"""
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from .dc_measurement_station import CAL_FACTOR, StationSpec, json_bytes
from .ina228_logger import INA228, capture


class FixtureClock:
    def __init__(self, start_utc: str = "2026-01-01T00:00:00Z"):
        parsed = datetime.fromisoformat(start_utc.replace("Z", "+00:00"))
        if parsed.utcoffset() is None or parsed.utcoffset().total_seconds() != 0:
            raise ValueError("fixture start must be UTC with an explicit offset")
        self.epoch, self.elapsed = parsed.timestamp(), 0.0

    def time(self) -> float:
        return self.epoch + self.elapsed

    def monotonic(self) -> float:
        return self.elapsed

    def sleep(self, seconds: float) -> None:
        self.elapsed += max(0, seconds)


def _signed20_bytes(value: int) -> bytes:
    if not -(1 << 19) <= value < (1 << 19):
        raise ValueError("fixture count is outside signed 20-bit range")
    return ((value & 0xFFFFF) << 4).to_bytes(3, "big")


class FixtureI2C:
    """Enough INA228 state to exercise reset/configuration/trigger/read code."""
    def __init__(self, clock: FixtureClock, *, shunt_ohm: float = 0.005,
                 voltage_v: float = 23.925, current_a: float = 5.0):
        self.clock, self.shunt_ohm = clock, shunt_ohm
        self.voltage_v, self.current_a = voltage_v, current_a
        self.address, self.bus_number = 0x40, None
        self.writes: list[tuple[int, bytes]] = []
        self.ready_at: float | None = None
        self.fault_diagnostic, self.suppress_ready, self.short_register = 0, False, None
        self.registers = {0: 0, 1: 0xFB68, 2: 0x1000, 3: 0, 0x0B: 1, 0x3E: 0x5449, 0x3F: 0x2281}

    def write(self, register: int, data: bytes) -> None:
        if len(data) != 2:
            raise ValueError("fixture only accepts two-byte configuration writes")
        self.writes.append((register, data))
        value = int.from_bytes(data, "big")
        if register == 0 and value & 0x8000:
            self.registers.update({0: 0, 1: 0xFB68, 2: 0x1000, 3: 0, 0x0B: 1})
            self.ready_at = None
            return
        self.registers[register] = value | 1 if register == 0x0B else value
        if register == 1 and value >> 12 == 3:
            self.ready_at = self.clock.monotonic() + 0.033664

    def read(self, register: int, length: int) -> bytes:
        if register == self.short_register:
            return bytes(max(0, length - 1))
        if register == 0x0B:
            ready = self.ready_at is not None and self.clock.monotonic() >= self.ready_at and not self.suppress_ready
            value = self.registers[register] | self.fault_diagnostic | (2 if ready else 0)
            if ready:
                self.ready_at = None  # Reading the diagnostic register clears CNVRF.
            return value.to_bytes(2, "big")
        if register in (4, 5, 7):
            if length != 3:
                raise ValueError("fixture measurement registers need a 3-byte read")
            if register == 4:
                count = round(self.current_a * self.shunt_ohm / 312.5e-9)
            elif register == 5:
                count = round(self.voltage_v / 195.3125e-6)
            else:
                effective_lsb = self.registers[2] / (CAL_FACTOR * self.shunt_ohm)
                count = round(self.current_a / effective_lsb)
            return _signed20_bytes(count)
        return self.registers[register].to_bytes(length, "big")


def run_fixture(out: Path, *, start_utc: str = "2026-01-01T00:00:00Z", samples: int = 183) -> dict:
    spec = StationSpec()
    clock = FixtureClock(start_utc)
    bus = FixtureI2C(clock, shunt_ohm=spec.shunt_ohm)
    session = capture(INA228(bus, spec, clock=clock), out, samples=samples,
                      clock_source="Deterministic software fixture clock; not an observed clock", clock=clock)
    (out / "fixture-definition.json").write_bytes(json_bytes({
        "capture_kind": "TEST_FIXTURE", "hardware_used": False,
        "description": "Constant load-boundary signal encoded by a fake I2C register device, decoded by INA228 driver",
        "voltage_v": bus.voltage_v, "current_a": bus.current_a,
        "reference_shunt_ohm_for_separate_fixture": spec.reference_shunt_ohm,
    }))
    return session


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--start-utc", default="2026-01-01T00:00:00Z")
    parser.add_argument("--samples", type=int, default=183)
    args = parser.parse_args()
    result = run_fixture(args.out, start_utc=args.start_utc, samples=args.samples)
    print(f"TEST_FIXTURE: {result['completed_samples']} samples at {args.out}; no hardware used")


if __name__ == "__main__":
    main()
