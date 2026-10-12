"""Shared host execution for CLI and product modeled runs; no physical authority."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from .bounded_process import BoundedProcessError, run_bounded


def _execute(command: list[str], *, timeout: float, cwd=None, **_ignored):
    """Reuse HS's output cap and process-group cleanup, including forked harness children."""
    result = run_bounded(command, timeout_s=timeout, cwd=cwd, tail_bytes=1024 * 1024)
    return subprocess.CompletedProcess(command, result.returncode, result.stdout_tail, result.stderr_tail)

CLAIM_BOUNDARY = (
    "Host model of the application logic. Does not test the Adafruit libraries, "
    "the Wire driver, timing, electrical behaviour or any real device."
)
VENDOR_HOST_CLAIM_BOUNDARY = (
    "Vendor-host compile of the real Arduino adapter and the pinned Adafruit sources "
    "against a modelled I2C bus. Not silicon, not ESP32 Wire timing, not electrical behaviour."
)
VENDOR_LIB_DIRS = (
    "Adafruit BME280 Library",
    "Adafruit SSD1306",
    "Adafruit GFX Library",
    "Adafruit BusIO",
    "Adafruit Unified Sensor",
)
VENDOR_LIB_SOURCES = (
    ("Adafruit BME280 Library", "Adafruit_BME280.cpp"),
    ("Adafruit SSD1306", "Adafruit_SSD1306.cpp"),
    ("Adafruit GFX Library", "Adafruit_GFX.cpp"),
    ("Adafruit BusIO", "Adafruit_I2CDevice.cpp"),
    ("Adafruit BusIO", "Adafruit_SPIDevice.cpp"),
    ("Adafruit Unified Sensor", "Adafruit_Sensor.cpp"),
)
# The diagnostic verifier's toolchain cache, so one download serves both. Set PLATFORMIO_CORE_DIR to use another.
HOST_SCENARIOS = (
    "boot_ok", "default_address_binding", "sensor_missing_at_boot", "display_missing",
    "display_at_second_address", "transient_read_failure", "read_fault_persistent_recovery",
    "ambiguous_during_read_fault", "second_read_fault_starts_at_one_second", "implausible_values",
    "clock_wrap", "read_period", "two_devices_answer", "first_read_fails", "serial_grammar",
)
VENDOR_SCENARIOS = (
    "sensor_default_address_0x77_with_display_0x3C", "sensor_0x76_only", "display_at_0x3D_only",
    "display_absent", "sensor_absent_then_appears", "unplug_replug_mid_run", "both_addresses_answer",
    "transient_data_nack", "wire_pins_stay_explicit", "blocking_budget", "im_update_never_clears",
)


def _scenario_failure(rows: list, expected: tuple[str, ...], exit_code: int) -> str:
    if exit_code != 0:
        return f"harness exited unsuccessfully ({exit_code})"
    if any(not isinstance(row, dict) for row in rows):
        return "harness scenario records must be objects"
    names = [row.get("scenario") for row in rows]
    if any(not isinstance(name, str) for name in names) or len(names) != len(expected) or set(names) != set(expected):
        return "harness did not report each expected scenario exactly once"
    if any(row.get("pass") is not True or row.get("finding", False) is not False for row in rows):
        return "one or more harness scenarios failed or reported a finding"
    return ""


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def vendor_libs_available(libdeps: Path | None) -> bool:
    if libdeps is None or not libdeps.is_dir():
        return False
    for name in VENDOR_LIB_DIRS:
        if not (libdeps / name).is_dir():
            return False
    for folder, source in VENDOR_LIB_SOURCES:
        if not (libdeps / folder / source).is_file():
            return False
    return True


def vendor_host_compile_command(project: Path, libdeps: Path, output: Path) -> list[str]:
    gxx = shutil.which("g++") or "g++"
    includes = [
        "-I", str(project / "test" / "vendor_host"),
        "-I", str(project / "src"),
    ]
    for name in VENDOR_LIB_DIRS:
        includes += ["-I", str(libdeps / name)]
    sources = [
        str(project / "src" / "main.cpp"),
        str(project / "test" / "vendor_host" / "arduino_core.cpp"),
        str(project / "test" / "vendor_host" / "Wire.cpp"),
        str(project / "test" / "vendor_host" / "models.cpp"),
        str(project / "test" / "vendor_host" / "vendor_harness.cpp"),
    ]
    for folder, source in VENDOR_LIB_SOURCES:
        sources.append(str(libdeps / folder / source))
    return [
        gxx, "-std=c++17", "-Wall", "-Wextra", "-Wno-macro-redefined",
        "-DARDUINO=10812", "-DESP32", "-DARDUINO_ARCH_ESP32",
        *includes, *sources, "-o", str(output),
    ]


def _not_run_vendor(reason: str) -> dict:
    return {
        "schema_version": "hardware_splicer.device_application_vendor_host.v1",
        "pass": False,
        "reason": reason,
        "scenarios": [],
        "findings": [],
        "compiler": "",
        "claim_boundary": VENDOR_HOST_CLAIM_BOUNDARY,
        "firmware_authorized": False,
        "power_on_authorized": False,
        "physical_correctness": "UNPROVEN",
    }


def _run_vendor_host(project: Path, libdeps: Path | None) -> tuple[dict, bytes]:
    if not vendor_libs_available(libdeps):
        return _not_run_vendor("not run: libraries not available"), b""
    gxx = shutil.which("g++")
    if not gxx:
        return _not_run_vendor("not run: libraries not available"), b"g++ is missing\n"
    assert libdeps is not None
    # Compilation runs inside the extracted project, not the caller's cwd.
    libdeps = libdeps.resolve()
    version = _execute([gxx, "--version"], timeout=30)
    compiler = version.stdout.decode(errors="replace").splitlines()[0] if version.stdout else ""
    binary = project / "vendor_harness"
    command = vendor_host_compile_command(project, libdeps, binary)
    compiled = _execute(command, cwd=project, timeout=120)
    log = compiled.stdout + compiled.stderr
    if compiled.returncode != 0:
        report = _not_run_vendor("vendor-host harness did not compile")
        report["compiler"] = compiler
        return report, log
    try:
        ran = _execute([str(binary)], cwd=project, timeout=60)
    except (subprocess.TimeoutExpired, OSError, BoundedProcessError) as exc:
        report = _not_run_vendor(f"vendor-host harness could not complete: {exc}")
        report["compiler"] = compiler
        return report, log + (getattr(exc, "stdout", None) or b"")
    log = log + ran.stdout + ran.stderr
    scenarios: list[dict] = []
    reason = ""
    try:
        scenarios = [json.loads(line) for line in ran.stdout.decode().splitlines() if line.strip()]
    except (json.JSONDecodeError, UnicodeDecodeError):
        reason = "vendor-host harness did not print JSON scenario results"
        report = _not_run_vendor(reason)
        report["compiler"] = compiler
        return report, log
    reason = _scenario_failure(scenarios, VENDOR_SCENARIOS, ran.returncode)
    findings = [row for row in scenarios if isinstance(row, dict) and row.get("finding")]
    passed = not reason
    return {
        "schema_version": "hardware_splicer.device_application_vendor_host.v1",
        "pass": passed,
        "reason": reason,
        "scenarios": scenarios,
        "findings": findings,
        "compiler": compiler,
        "exit_code": ran.returncode,
        "claim_boundary": VENDOR_HOST_CLAIM_BOUNDARY,
        "firmware_authorized": False,
        "power_on_authorized": False,
        "physical_correctness": "UNPROVEN",
    }, log


def _run_host(project: Path) -> tuple[dict, bytes]:
    gxx = shutil.which("g++")
    compiler = ""
    log = b""
    scenarios: list[dict] = []
    reason = ""
    passed = False
    if not gxx:
        reason = "g++ is missing; host behaviour tests were not run"
    else:
        version = _execute([gxx, "--version"], timeout=30)
        compiler = version.stdout.decode(errors="replace").splitlines()[0] if version.stdout else ""
        compiled = _execute(
            [gxx, "-std=c++17", "-Wall", "-Wextra", "-Werror", "-I", "src", "test/host/harness.cpp", "-o", "harness"],
            cwd=project,
            capture_output=True,
            check=False,
            timeout=120,
        )
        log = compiled.stdout + compiled.stderr
        if compiled.returncode != 0:
            reason = "host harness did not compile"
        else:
            try:
                ran = _execute([str(project / "harness")], cwd=project, timeout=60)
            except (subprocess.TimeoutExpired, OSError, BoundedProcessError) as exc:
                return {
                    "schema_version": "hardware_splicer.device_application_behaviour.v1", "pass": False,
                    "reason": f"host harness could not complete: {exc}", "scenarios": [], "compiler": compiler,
                    "claim_boundary": CLAIM_BOUNDARY, "firmware_authorized": False,
                    "power_on_authorized": False, "physical_correctness": "UNPROVEN",
                }, log + (getattr(exc, "stdout", None) or b"")
            log = log + ran.stdout + ran.stderr
            try:
                scenarios = [json.loads(line) for line in ran.stdout.decode().splitlines() if line.strip()]
            except (json.JSONDecodeError, UnicodeDecodeError):
                reason = "host harness did not print JSON scenario results"
            else:
                reason = _scenario_failure(scenarios, HOST_SCENARIOS, ran.returncode)
                passed = not reason
    return {
        "schema_version": "hardware_splicer.device_application_behaviour.v1",
        "pass": passed,
        "reason": reason,
        "scenarios": scenarios,
        "compiler": compiler,
        "claim_boundary": CLAIM_BOUNDARY,
        "firmware_authorized": False,
        "power_on_authorized": False,
        "physical_correctness": "UNPROVEN",
    }, log


