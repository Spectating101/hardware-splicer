"""Bounded INA228 acquisition with register transcripts and no simulated fallback.

Register layout and conversion rules: TI SLYS021A sections 7.3, 7.6 and 8.1.2.
Triggered operation intentionally does not read the invalid energy accumulator.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import time
import fcntl
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from .dc_measurement_station import StationSpec, design_station, json_bytes


class AcquisitionError(RuntimeError):
    pass


class RegisterBus(Protocol):
    def read(self, register: int, length: int) -> bytes: ...
    def write(self, register: int, data: bytes) -> None: ...


class LinuxI2CBus:
    """Combined pointer-write/read transactions; requires optional smbus2."""
    def __init__(self, bus_number: int, address: int):
        if type(bus_number) is not int or bus_number < 0 or type(address) is not int or not 0x40 <= address <= 0x4F:
            raise ValueError("expected a nonnegative Linux I2C bus and INA228 address 0x40..0x4F")
        try:
            from smbus2 import SMBus, I2cFunc, i2c_msg  # Transport checked with smbus2 0.5.0.
            from smbus2.smbus2 import I2C_RDWR, i2c_rdwr_ioctl_data
        except ImportError as exc:
            raise AcquisitionError("hardware capture requires smbus2; no fallback data is generated") from exc
        self._bus, self._message = SMBus(bus_number), i2c_msg
        self._rdwr_request, self._packet_type = I2C_RDWR, i2c_rdwr_ioctl_data
        try:
            if not self._bus.funcs & I2cFunc.I2C:
                raise AcquisitionError("adapter lacks combined I2C transactions (I2C_FUNC_I2C)")
            # Check address ownership using I2C_SLAVE, never I2C_SLAVE_FORCE.
            # I2C_RDWR itself carries the selected address on each message.
            fcntl.ioctl(self._bus.fd, 0x0703, address)
        except Exception:
            self._bus.close()
            raise
        self.bus_number, self.address = bus_number, address

    def read(self, register: int, length: int) -> bytes:
        pointer = self._message.write(self.address, [register])
        data = self._message.read(self.address, length)
        self._transfer(pointer, data)
        return bytes(data)

    def write(self, register: int, data: bytes) -> None:
        self._transfer(self._message.write(self.address, bytes([register]) + data))

    def _transfer(self, *messages: Any) -> None:
        # smbus2's convenience method discards the ioctl message count. Check it
        # so a partial transfer cannot become a zero-filled measurement buffer.
        count = fcntl.ioctl(self._bus.fd, self._rdwr_request, self._packet_type.create(*messages))
        if count != len(messages):
            raise AcquisitionError(f"incomplete I2C transfer: {count}/{len(messages)} messages")

    def close(self) -> None:
        self._bus.close()


def decode_signed20(raw: bytes) -> int:
    if not isinstance(raw, bytes) or len(raw) != 3:
        raise AcquisitionError("20-bit register requires exactly 3 bytes")
    word = int.from_bytes(raw, "big")
    if word & 0xF:
        raise AcquisitionError("20-bit register has nonzero reserved low bits")
    value = word >> 4
    return value - (1 << 20) if value & (1 << 19) else value


class INA228:
    def __init__(self, bus: RegisterBus, spec: StationSpec = StationSpec(), *, clock: Any = time):
        self.bus, self.spec, self.clock = bus, spec, clock
        self.design = design_station(spec)
        if not self.design["design_checks_passed"]:
            raise AcquisitionError("station's numerical range/dissipation checks fail")
        self.config = self.design["ina228_configuration"]
        self.identity: dict[str, int] | None = None
        self.last_observation: dict[str, Any] = {}

    def _read(self, register: int, length: int = 2) -> bytes:
        try:
            value = self.bus.read(register, length)
        except Exception as exc:
            raise AcquisitionError(f"I2C read failed at 0x{register:02x}: {exc}") from exc
        if not isinstance(value, bytes) or len(value) != length:
            raise AcquisitionError(f"short/invalid read at 0x{register:02x}")
        return value

    def _word(self, register: int) -> int:
        return int.from_bytes(self._read(register), "big")

    def _write(self, register: int, value: int) -> None:
        try:
            self.bus.write(register, value.to_bytes(2, "big"))
        except Exception as exc:
            raise AcquisitionError(f"I2C write failed at 0x{register:02x}: {exc}") from exc

    def _identity(self) -> dict[str, int]:
        manufacturer, device = self._word(0x3E), self._word(0x3F)
        if manufacturer != 0x5449 or device >> 4 != 0x228:
            raise AcquisitionError(f"unexpected manufacturer/device ID: {manufacturer:04x}/{device:04x}")
        return {"manufacturer_id": manufacturer, "device_id": device, "revision": device & 15}

    @staticmethod
    def _check_diagnostic(diag: int) -> None:
        if not diag & 1:
            raise AcquisitionError("INA228 trim-memory checksum error (MEMSTAT=0)")
        if diag & 0x0EFC:
            raise AcquisitionError(f"INA228 diagnostic fault: 0x{diag:04x}")

    def initialize(self) -> dict[str, int]:
        self.identity = self._identity()
        self._write(0x00, 0x8000)  # Explicit device reset; no load switch is controlled.
        self.clock.sleep(0.003)
        self._write(0x01, self.config["adc_config"] & 0x0FFF)  # Shutdown, fixed timing.
        for register, value in ((0x00, 0), (0x02, self.config["shunt_cal"]), (0x03, 0), (0x0B, 0x8000)):
            self._write(register, value)
        self._verify_configuration()
        self._check_diagnostic(self._word(0x0B))
        return dict(self.identity)

    def _verify_configuration(self) -> None:
        if self.identity is None or self._identity() != self.identity:
            raise AcquisitionError("device identity changed or acquisition was not initialized")
        for register, expected in ((0x00, 0), (0x02, self.config["shunt_cal"]), (0x03, 0)):
            if self._word(register) != expected:
                raise AcquisitionError(f"configuration changed at 0x{register:02x}")
        adc = self._word(0x01)
        if adc & 0x0FFF != self.config["adc_config"] & 0x0FFF or adc >> 12 not in (0, 3, 8):
            raise AcquisitionError("ADC mode or conversion timing changed")

    def sample(self) -> dict[str, Any]:
        self.last_observation = {}
        self._verify_configuration()
        started = self.clock.monotonic()
        self._write(0x01, self.config["adc_config"])
        for _ in range(125):  # Both an elapsed deadline and a finite poll budget.
            diag = self._word(0x0B)
            self.last_observation["diagnostic_hex"] = f"{diag:04x}"
            self._check_diagnostic(diag)
            if diag & 2:
                break
            if self.clock.monotonic() - started >= 0.25:
                raise AcquisitionError("INA228 conversion timed out")
            self.clock.sleep(0.002)
        else:
            raise AcquisitionError("INA228 conversion exhausted polling budget")
        raw = {name: self._read(register, 3) for name, register in (("vshunt", 4), ("vbus", 5), ("current", 7))}
        self.last_observation["registers_hex"] = {k: v.hex() for k, v in raw.items()}
        counts = {name: decode_signed20(value) for name, value in raw.items()}
        if any(value in (-(1 << 19), (1 << 19) - 1) for value in counts.values()):
            raise AcquisitionError("ADC/current register saturation")
        voltage = counts["vbus"] * self.config["bus_lsb_v"]
        current = counts["current"] * self.config["current_lsb_a"]
        shunt_v = counts["vshunt"] * self.config["shunt_lsb_v"]
        if min(voltage, current, shunt_v) < 0:
            raise AcquisitionError("negative voltage/current; this station expects a positive load path")
        if voltage > self.spec.maximum_bus_voltage_v or current > self.spec.monitor_headroom_a:
            raise AcquisitionError("sample exceeds station voltage/current envelope")
        power = voltage * current
        if power > self.spec.maximum_power_w:
            raise AcquisitionError("sample exceeds station power envelope")
        quantization = 2 * self.config["shunt_lsb_v"] / self.spec.shunt_ohm + 2 * self.config["current_lsb_a"]
        if abs(current - shunt_v / self.spec.shunt_ohm) > quantization:
            raise AcquisitionError("current register is inconsistent with shunt voltage and calibration")
        self._verify_configuration()
        return {"voltage_v": voltage, "current_a": current, "power_w": power,
                "shunt_voltage_v": shunt_v, "registers_hex": {k: v.hex() for k, v in raw.items()},
                "diagnostic_hex": f"{diag:04x}", "conversion_elapsed_seconds": self.clock.monotonic() - started}


def _utc(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def capture(driver: INA228, out: Path, *, samples: int = 183, period_seconds: float = 1.0,
            clock_source: str, clock: Any = time) -> dict[str, Any]:
    """Acquire a finite run. Partial files and a failed session survive any fault.

    CSV timestamps are actual host read-completion times, never scheduled times.
    Separate reference acquisition is required; this is only the primary stream.
    """
    if type(samples) is not int or not 2 <= samples <= 86401:
        raise ValueError("samples must be an integer from 2 to 86401")
    if isinstance(period_seconds, bool) or not math.isfinite(period_seconds) or not 0.05 <= period_seconds <= 60:
        raise ValueError("period must be finite and between 0.05 and 60 seconds")
    if samples * period_seconds > 86460 or not isinstance(clock_source, str) or not clock_source.strip():
        raise ValueError("capture must be bounded to one day and name its declared clock source")
    out.mkdir(parents=True, exist_ok=False)
    csv_path, raw_path = out / "samples.csv", out / "registers.jsonl"
    record: dict[str, Any] = {
        "schema_version": "hardware_splicer.ina228_capture.v1", "status": "STARTING",
        "source_kind": "linux_i2c" if isinstance(driver.bus, LinuxI2CBus) else "register_fixture",
        "capture_kind": "DECLARED_BENCH_CAPTURE" if isinstance(driver.bus, LinuxI2CBus) else "TEST_FIXTURE",
        "clock_source_declared": clock_source, "clock_synchronization_verified": False,
        "timestamp_basis": "Host UTC after completed triggered conversion and register/config reads",
        "sampling_method": "Discrete bus/shunt sample pairs; integrate V*I separately using actual timestamps",
        "sampling_limit": "Steady or slowly varying bench loads; samples do not continuously observe intersample transients",
        "measurement_boundary": driver.design["measurement_boundary"],
        "runtime_limit_boundary": driver.design["runtime_limit_boundary"],
        "energy_register_used": False, "calibration_status": "User-supplied shunt parameters; not certification",
        "requested_samples": samples, "period_seconds": period_seconds, "completed_samples": 0,
        "configuration": driver.config, "station_spec": driver.design["spec"],
        "started_utc": _utc(clock.time()), "source": driver.design["source"],
        "bus": {"number": getattr(driver.bus, "bus_number", None), "address": getattr(driver.bus, "address", None)},
    }
    (out / "station-design.json").write_bytes(json_bytes(driver.design))
    (out / "session.json").write_bytes(json_bytes(record))
    failure: Exception | None = None
    try:
        record["device_identity"] = driver.initialize()
        start_mono, start_wall = clock.monotonic(), clock.time()
        previous_wall = None
        with csv_path.open("x", newline="", encoding="utf-8") as stream, raw_path.open("x", encoding="utf-8") as raw_stream:
            writer = csv.DictWriter(stream, fieldnames=("timestamp_utc", "voltage_v", "current_a"))
            writer.writeheader()
            for index in range(samples):
                target = start_mono + index * period_seconds
                delay = target - clock.monotonic()
                if delay > 0:
                    clock.sleep(delay)
                if clock.monotonic() - target > period_seconds * 0.25:
                    raise AcquisitionError("capture schedule missed; no samples were invented")
                sample = driver.sample()
                wall, mono = clock.time(), clock.monotonic()
                if abs((wall - start_wall) - (mono - start_mono)) > min(0.1, period_seconds * 0.1):
                    raise AcquisitionError("UTC clock stepped relative to the monotonic clock")
                if previous_wall is not None and not 0 < wall - previous_wall <= period_seconds * 1.5:
                    raise AcquisitionError("sample time is repeated/backward or coverage gap is too large")
                timestamp = _utc(wall)
                raw_stream.write(json.dumps({"index": index, "timestamp_utc": timestamp,
                                             "monotonic_elapsed_seconds": mono - start_mono,
                                             **sample}, sort_keys=True, allow_nan=False) + "\n")
                raw_stream.flush()
                writer.writerow({"timestamp_utc": timestamp, "voltage_v": format(sample["voltage_v"], ".12g"),
                                 "current_a": format(sample["current_a"], ".12g")})
                stream.flush()
                previous_wall = wall
                record["completed_samples"] += 1
                record.setdefault("first_sample_utc", timestamp)
                record["last_sample_utc"] = timestamp
        record["status"] = "COMPLETE"
    except (Exception, KeyboardInterrupt) as exc:
        failure = exc
        record["status"], record["error"] = "FAILED", f"{type(exc).__name__}: {exc}"
        record["last_fault_observation"] = driver.last_observation
    finally:
        record["finished_utc"] = _utc(clock.time())
        record["files"] = {path.name: {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                                     "bytes": path.stat().st_size}
                           for path in (csv_path, raw_path) if path.exists()}
        (out / "session.json").write_bytes(json_bytes(record))
    if failure is not None:
        raise AcquisitionError(f"capture failed; retained session at {out}: {failure}") from failure
    return record
