"""Shared host execution for CLI and product modeled runs; no physical authority."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from .bounded_process import BoundedProcessError, run_bounded
from .device_vendor_profiles import VENDOR_PROFILES, vendor_profile


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
RP2040_VENDOR_HOST_CLAIM_BOUNDARY = VENDOR_HOST_CLAIM_BOUNDARY.replace("ESP32 Wire timing", "RP2040 Wire timing or the pico-sdk")
# The diagnostic verifier's toolchain cache, so one download serves both. Set PLATFORMIO_CORE_DIR to use another.
HOST_SCENARIOS = (
    "boot_ok", "default_address_binding", "sensor_missing_at_boot", "display_missing",
    "display_at_second_address", "transient_read_failure", "read_fault_persistent_recovery",
    "ambiguous_during_read_fault", "second_read_fault_starts_at_one_second", "implausible_values",
    "clock_wrap", "read_period", "two_devices_answer", "first_read_fails", "serial_grammar",
)
# The BME280 profile's names, kept for callers that predate per-part profiles.
VENDOR_LIB_DIRS = VENDOR_PROFILES["bme280"]["lib_dirs"]
VENDOR_LIB_SOURCES = VENDOR_PROFILES["bme280"]["lib_sources"]
VENDOR_SCENARIOS = VENDOR_PROFILES["bme280"]["scenarios"]


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


def vendor_libs_available(libdeps: Path | None, profile: str = "bme280") -> bool:
    if libdeps is None or not libdeps.is_dir():
        return False
    chosen = vendor_profile(profile)
    for name in chosen["lib_dirs"]:
        if not (libdeps / name).is_dir():
            return False
    for folder, source in chosen["lib_sources"]:
        if not (libdeps / folder / source).is_file():
            return False
    return True


def vendor_host_compile_command(project: Path, libdeps: Path, output: Path, profile: str = "bme280") -> list[str]:
    gxx = shutil.which("g++") or "g++"
    chosen = vendor_profile(profile)
    host = project / "test" / "vendor_host"
    includes = [
        "-I", str(project / "test" / "vendor_host"),
        "-I", str(project / "src"),
    ]
    for name in chosen["lib_dirs"]:
        includes += ["-I", str(libdeps / name)]
    sources = [
        str(project / "src" / "main.cpp"),
        str(host / "arduino_core.cpp"),
        str(host / "Wire.cpp"),
        # Earlier revisions kept the SSD1306 model inside models.cpp; the benchmark can still score those.
        *([str(host / "ssd1306_model.cpp")] if (host / "ssd1306_model.cpp").is_file() else []),
        *(str(host / name) for name in chosen["model_sources"]),
        str(host / chosen["harness"]),
    ]
    for folder, source in chosen["lib_sources"]:
        sources.append(str(libdeps / folder / source))
    # A package for another board carries board_config.h, which the Arduino shim includes to select that board's core
    # macros and Wire model; only an ESP32 package is compiled with the ESP32 macros.
    # As PlatformIO passes them for board = pico; the libraries test these before they include Arduino.h.
    board = (["-DHS_RP2040", "-DARDUINO_ARCH_RP2040", "-DARDUINO_RASPBERRY_PI_PICO"] if (host / "board_config.h").is_file()
             else ["-DESP32", "-DARDUINO_ARCH_ESP32"])
    return [
        gxx, "-std=c++17", "-Wall", "-Wextra", "-Wno-macro-redefined",
        "-DARDUINO=10812", *board,
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


def _run_vendor_host(project: Path, libdeps: Path | None, profile: str = "bme280") -> tuple[dict, bytes]:
    # A Pico package carries board_config.h, the same marker the compile command switches on.
    boundary = (RP2040_VENDOR_HOST_CLAIM_BOUNDARY if (project / "test" / "vendor_host" / "board_config.h").is_file()
                else VENDOR_HOST_CLAIM_BOUNDARY)

    def _not_run(reason: str) -> dict:
        return {**_not_run_vendor(reason), "claim_boundary": boundary}

    if not vendor_libs_available(libdeps, profile):
        return _not_run("not run: libraries not available"), b""
    gxx = shutil.which("g++")
    if not gxx:
        return _not_run("not run: libraries not available"), b"g++ is missing\n"
    assert libdeps is not None
    # Compilation runs inside the extracted project, not the caller's cwd.
    libdeps = libdeps.resolve()
    version = _execute([gxx, "--version"], timeout=30)
    compiler = version.stdout.decode(errors="replace").splitlines()[0] if version.stdout else ""
    binary = project / "vendor_harness"
    command = vendor_host_compile_command(project, libdeps, binary, profile)
    compiled = _execute(command, cwd=project, timeout=120)
    log = compiled.stdout + compiled.stderr
    if compiled.returncode != 0:
        report = _not_run("vendor-host harness did not compile")
        report["compiler"] = compiler
        return report, log
    try:
        ran = _execute([str(binary)], cwd=project, timeout=60)
    except (subprocess.TimeoutExpired, OSError, BoundedProcessError) as exc:
        report = _not_run(f"vendor-host harness could not complete: {exc}")
        report["compiler"] = compiler
        return report, log + (getattr(exc, "stdout", None) or b"")
    log = log + ran.stdout + ran.stderr
    scenarios: list[dict] = []
    reason = ""
    try:
        scenarios = [json.loads(line) for line in ran.stdout.decode().splitlines() if line.strip()]
    except (json.JSONDecodeError, UnicodeDecodeError):
        reason = "vendor-host harness did not print JSON scenario results"
        report = _not_run(reason)
        report["compiler"] = compiler
        return report, log
    reason = _scenario_failure(scenarios, vendor_profile(profile)["scenarios"], ran.returncode)
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
        "claim_boundary": boundary,
        "firmware_authorized": False,
        "power_on_authorized": False,
        "physical_correctness": "UNPROVEN",
    }, log


def _run_donor_host(project: Path) -> tuple[dict, bytes]:
    from .donor_device_application import DONOR_SCENARIOS, BOUNDARY
    report, log = _run_host(project, scenarios_expected=DONOR_SCENARIOS, boundary=BOUNDARY,
                            harness="test/donor_host/harness.cpp", binary_name="donor_harness",
                            includes=["-I", "test/donor_host", "-I", "src"])
    return {**report, "schema_version": "hardware_splicer.donor_input_behaviour.v1"}, log


def _run_host(project: Path, *, scenarios_expected=HOST_SCENARIOS, boundary=CLAIM_BOUNDARY,
              harness="test/host/harness.cpp", binary_name="harness", includes=None) -> tuple[dict, bytes]:
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
            [gxx, "-std=c++17", "-Wall", "-Wextra", "-Werror", *(includes or ["-I", "src"]), harness, "-o", binary_name],
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
                ran = _execute([str(project / binary_name)], cwd=project, timeout=60)
            except (subprocess.TimeoutExpired, OSError, BoundedProcessError) as exc:
                return {
                    "schema_version": "hardware_splicer.device_application_behaviour.v1", "pass": False,
                    "reason": f"host harness could not complete: {exc}", "scenarios": [], "compiler": compiler,
                    "claim_boundary": boundary, "firmware_authorized": False,
                    "power_on_authorized": False, "physical_correctness": "UNPROVEN",
                }, log + (getattr(exc, "stdout", None) or b"")
            log = log + ran.stdout + ran.stderr
            try:
                scenarios = [json.loads(line) for line in ran.stdout.decode().splitlines() if line.strip()]
            except (json.JSONDecodeError, UnicodeDecodeError):
                reason = "host harness did not print JSON scenario results"
            else:
                reason = _scenario_failure(scenarios, scenarios_expected, ran.returncode)
                passed = not reason
    return {
        "schema_version": "hardware_splicer.device_application_behaviour.v1",
        "pass": passed,
        "reason": reason,
        "scenarios": scenarios,
        "compiler": compiler,
        "claim_boundary": boundary,
        "firmware_authorized": False,
        "power_on_authorized": False,
        "physical_correctness": "UNPROVEN",
    }, log


