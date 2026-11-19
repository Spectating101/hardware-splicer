"""Design calculations and actual register/clock failure behavior, without hardware."""
import csv
import json
from dataclasses import replace

import pytest

from hardware_splicer.dc_measurement_station import StationSpec, design_station, write_design
from hardware_splicer.ina228_fixture import FixtureClock, FixtureI2C, run_fixture
from hardware_splicer.ina228_logger import AcquisitionError, INA228, LinuxI2CBus, capture, decode_signed20


def initialized(**bus_options):
    clock = FixtureClock()
    bus = FixtureI2C(clock, **bus_options)
    driver = INA228(bus, clock=clock)
    driver.initialize()
    return clock, bus, driver


def test_24v_station_has_actual_7_5a_range_and_separate_reference_path(tmp_path):
    design = write_design(tmp_path / "design")
    assert design["design_checks_passed"] is True
    calc = design["calculations"]
    assert calc["nominal_current_a"] == 5
    assert calc["headroom_shunt_dissipation_w"] == pytest.approx(0.28153125)
    assert calc["reference_headroom_shunt_dissipation_w"] == pytest.approx(0.5630625)
    assert calc["combined_nominal_shunt_drop_v"] == pytest.approx(0.075075)
    assert calc["current_positive_range_a"] > 7.5
    assert design["ina228_configuration"]["shunt_cal"] == 1250
    assert design["physical_status"] == "UNBUILT_UNVERIFIED"
    assert design["isolation"]["monitor_is_galvanically_isolated"] is False
    wires = {(w["from"], w["to"]) for w in design["wiring"]}
    assert ("RSH1.power-", "RSH2.power+") in wires
    assert ("RSH2.power-", "J2.load+") in wires
    assert ("J2.load+", "REF.voltage high") in wires
    assert (tmp_path / "design" / "parts.csv").is_file()


@pytest.mark.parametrize("changes,failed", [
    ({"shunt_ohm": 0.03}, "shunt_adc_range"),
    ({"shunt_rated_power_w": 0.25}, "shunt_dissipation"),
    ({"reference_shunt_rated_power_w": 0.5}, "reference_shunt_dissipation"),
    ({"monitor_headroom_a": 5.0}, "monitor_headroom"),
    ({"calibration_full_scale_a": 7.0}, "current_register_range"),
    ({"maximum_bus_voltage_v": 86.0}, "ina228_bus_range"),
])
def test_insufficient_components_or_ranges_are_failed_design_data(changes, failed):
    spec = replace(StationSpec(), **changes)
    design = design_station(spec)
    assert not design["design_checks_passed"]
    assert not next(c for c in design["checks"] if c["id"] == failed)["passed"]
    with pytest.raises(AcquisitionError, match="checks fail"):
        INA228(FixtureI2C(FixtureClock()), spec)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), True, 0, -0.005])
def test_nonfinite_or_nonnumeric_shunt_is_rejected(bad):
    with pytest.raises(ValueError):
        StationSpec(shunt_ohm=bad)


@pytest.mark.parametrize("hex_bytes,expected", [
    ("000000", 0), ("000010", 1), ("fffff0", -1),
    ("800000", -524288), ("7ffff0", 524287), ("400000", 262144),
])
def test_datasheet_20_bit_msb_first_signed_vectors(hex_bytes, expected):
    assert decode_signed20(bytes.fromhex(hex_bytes)) == expected


@pytest.mark.parametrize("raw", [b"\x00\x00", b"\x00\x00\x01"])
def test_partial_register_or_reserved_bits_fail(raw):
    with pytest.raises(AcquisitionError):
        decode_signed20(raw)


def test_real_driver_decodes_triggered_pair_and_exact_config():
    clock, bus, driver = initialized()
    sample = driver.sample()
    assert sample["registers_hex"] == {"vshunt": "138800", "vbus": "1de800", "current": "400000"}
    assert sample["voltage_v"] == pytest.approx(23.925)
    assert sample["current_a"] == 5
    assert sample["power_w"] == pytest.approx(119.625)
    assert 0.033664 <= sample["conversion_elapsed_seconds"] <= 0.036
    assert (2, b"\x04\xe2") in bus.writes  # SHUNT_CAL=1250, MSB first.
    assert (1, b"\x3b\x6a") in bus.writes
    assert driver.config["energy_register_used"] is False


def test_rounded_calibration_changes_effective_lsb():
    spec = StationSpec(shunt_ohm=0.00471239)
    config = design_station(spec)["ina228_configuration"]
    assert config["shunt_cal"] == 1178
    assert config["current_lsb_a"] != spec.calibration_full_scale_a / 2**19


def test_wrong_chip_is_rejected_before_any_configuration_write():
    clock = FixtureClock()
    bus = FixtureI2C(clock)
    bus.registers[0x3F] = 0x2260
    with pytest.raises(AcquisitionError, match="device ID"):
        INA228(bus, clock=clock).initialize()
    assert bus.writes == []


@pytest.mark.parametrize("fault,pattern", [(0x200, "diagnostic fault"), (0x40, "diagnostic fault")])
def test_device_flags_reject_measurements(fault, pattern):
    _, bus, driver = initialized()
    bus.fault_diagnostic = fault
    with pytest.raises(AcquisitionError, match=pattern):
        driver.sample()


def test_trim_memory_and_configuration_changes_are_not_ignored():
    _, bus, driver = initialized()
    bus.registers[0x0B] = 0x8000
    with pytest.raises(AcquisitionError, match="MEMSTAT"):
        driver.sample()
    bus.registers[0x0B] = 0x8001
    bus.registers[2] = 1
    with pytest.raises(AcquisitionError, match="configuration changed"):
        driver.sample()


def test_no_ready_and_short_reads_stop_instead_of_returning_zeros():
    _, bus, driver = initialized()
    bus.suppress_ready = True
    with pytest.raises(AcquisitionError, match="timed out|polling"):
        driver.sample()
    bus.suppress_ready, bus.short_register = False, 5
    with pytest.raises(AcquisitionError, match="short/invalid"):
        driver.sample()


@pytest.mark.parametrize("voltage,current,pattern", [
    (24, -0.1, "negative"), (25, 1, "envelope"), (20, 8, "envelope"), (24, 5.5, "power envelope")])
def test_reversed_or_out_of_envelope_load_stops(voltage, current, pattern):
    _, _, driver = initialized(voltage_v=voltage, current_a=current)
    with pytest.raises(AcquisitionError, match=pattern):
        driver.sample()


def test_fixture_uses_actual_driver_capture_no_wall_wait(tmp_path):
    session = run_fixture(tmp_path / "capture", start_utc="2026-01-01T00:00:00Z", samples=183)
    assert session["capture_kind"] == "TEST_FIXTURE" and session["source_kind"] == "register_fixture"
    assert session["status"] == "COMPLETE" and session["completed_samples"] == 183
    assert session["clock_synchronization_verified"] is False
    rows = list(csv.DictReader((tmp_path / "capture" / "samples.csv").open()))
    assert len(rows) == 183 and float(rows[0]["current_a"]) == 5
    assert rows[0]["timestamp_utc"].endswith("00:00:00.037000Z")
    assert rows[-1]["timestamp_utc"].endswith("00:03:02.037000Z")
    assert session["files"]["samples.csv"]["sha256"]


def test_clock_jump_keeps_partial_run_and_failed_session(tmp_path):
    clock = FixtureClock()
    bus = FixtureI2C(clock)
    original_time = clock.time
    clock.time = lambda: original_time() + (1 if clock.elapsed > 0.5 else 0)
    driver = INA228(bus, clock=clock)
    with pytest.raises(AcquisitionError, match="UTC clock stepped"):
        capture(driver, tmp_path / "bad-clock", samples=3, clock_source="fixture jump", clock=clock)
    session = json.loads((tmp_path / "bad-clock" / "session.json").read_text())
    assert session["status"] == "FAILED" and session["completed_samples"] == 1
    assert len(list(csv.DictReader((tmp_path / "bad-clock" / "samples.csv").open()))) == 1
    assert session["last_fault_observation"]["registers_hex"]


def test_linux_adapter_requires_combined_i2c_and_closes_on_failure(monkeypatch):
    smbus = pytest.importorskip("smbus2")
    class Adapter:
        funcs, fd, closed = 0, 99, False
        def close(self):
            self.closed = True
    adapter = Adapter()
    monkeypatch.setattr(smbus, "SMBus", lambda number: adapter)
    with pytest.raises(AcquisitionError, match="I2C_FUNC_I2C"):
        LinuxI2CBus(1, 0x40)
    assert adapter.closed


def test_busy_address_never_force_binds(monkeypatch):
    smbus = pytest.importorskip("smbus2")
    class Adapter:
        funcs, fd, closed = 1, 99, False
        def close(self):
            self.closed = True
    adapter = Adapter()
    monkeypatch.setattr(smbus, "SMBus", lambda number: adapter)
    def busy(fd, request, address):
        assert request == 0x0703 and address == 0x40
        raise OSError("address busy")
    monkeypatch.setattr("hardware_splicer.ina228_logger.fcntl.ioctl", busy)
    with pytest.raises(OSError, match="busy"):
        LinuxI2CBus(1, 0x40)
    assert adapter.closed


def test_partial_linux_transfer_cannot_turn_into_zero_measurement(monkeypatch):
    smbus = pytest.importorskip("smbus2")
    class Adapter:
        funcs, fd = 1, 99
        def close(self):
            pass
    monkeypatch.setattr(smbus, "SMBus", lambda number: Adapter())
    monkeypatch.setattr("hardware_splicer.ina228_logger.fcntl.ioctl", lambda fd, request, value: 0)
    bus = LinuxI2CBus(1, 0x40)
    with pytest.raises(AcquisitionError, match="incomplete I2C transfer"):
        bus.read(5, 3)
