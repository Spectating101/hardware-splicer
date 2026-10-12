#!/usr/bin/env python3
"""Run host behaviour tests, and optionally compile, a fresh application proposal.

Never upload or access hardware. A pass here is not physical proof.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

# scripts/hardware_splicer.py would otherwise shadow the src package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from hardware_splicer.device_application import build_device_application
from hardware_splicer.device_plan import example_specs

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
DEFAULT_CORE_DIR = Path(__file__).resolve().parents[1] / ".cache" / "hardware-splicer" / "device-firmware" / "platformio-core"
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
    version = subprocess.run([gxx, "--version"], capture_output=True, check=False)
    compiler = version.stdout.decode(errors="replace").splitlines()[0] if version.stdout else ""
    binary = project / "vendor_harness"
    command = vendor_host_compile_command(project, libdeps, binary)
    compiled = subprocess.run(command, cwd=project, capture_output=True, check=False)
    log = compiled.stdout + compiled.stderr
    if compiled.returncode != 0:
        report = _not_run_vendor("vendor-host harness did not compile")
        report["compiler"] = compiler
        return report, log
    try:
        ran = subprocess.run([str(binary)], cwd=project, capture_output=True, check=False, timeout=60)
    except (subprocess.TimeoutExpired, OSError) as exc:
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
        version = subprocess.run([gxx, "--version"], capture_output=True, check=False)
        compiler = version.stdout.decode(errors="replace").splitlines()[0] if version.stdout else ""
        compiled = subprocess.run(
            [gxx, "-std=c++17", "-Wall", "-Wextra", "-Werror", "-I", "src", "test/host/harness.cpp", "-o", "harness"],
            cwd=project,
            capture_output=True,
            check=False,
        )
        log = compiled.stdout + compiled.stderr
        if compiled.returncode != 0:
            reason = "host harness did not compile"
        else:
            try:
                ran = subprocess.run([str(project / "harness")], cwd=project, capture_output=True, check=False, timeout=60)
            except (subprocess.TimeoutExpired, OSError) as exc:
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


def _compile_platformio(project: Path, platformio: str, output_root: Path, timeout: int) -> tuple[dict, bytes]:
    command = [platformio, "run", "--project-dir", str(project), "--environment", "application", "--jobs", "2"]
    env = dict(os.environ)
    env["PLATFORMIO_CORE_DIR"] = env.get("PLATFORMIO_CORE_DIR", str(DEFAULT_CORE_DIR if DEFAULT_CORE_DIR.is_dir() else output_root.resolve() / "platformio-core"))
    env["PLATFORMIO_SETTING_ENABLE_TELEMETRY"] = "No"
    version = ""
    log = b""
    returncode = None
    reason = ""
    try:
        tool = subprocess.run([platformio, "--version"], capture_output=True, timeout=30, check=False, env=env)
        version = tool.stdout.decode(errors="replace").strip()
        if tool.returncode != 0 or version != "PlatformIO Core, version 6.1.18":
            reason = "compiler version must be PlatformIO Core 6.1.18"
            log = tool.stdout + tool.stderr
        else:
            process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, check=False, env=env)
            returncode, log = process.returncode, process.stdout
    except subprocess.TimeoutExpired as exc:
        reason, log = "compiler timed out", exc.stdout or b""
    except OSError as exc:
        reason = f"compiler could not start: {exc}"
    binaries = {}
    for name in ("firmware.elf", "firmware.bin"):
        path = project / ".pio" / "build" / "application" / name
        if path.is_file() and path.stat().st_size:
            data = path.read_bytes()
            binaries[name] = {"sha256": _sha(data), "size_bytes": len(data)}
    passed = not reason and returncode == 0 and len(binaries) == 2
    report = {
        "schema_version": "hardware_splicer.device_application_compile.v1",
        "compile_pass": passed,
        "reason": reason or ("" if passed else "compiler failed or expected build artifacts are absent"),
        "compiler": version,
        "command": command,
        "exit_code": returncode,
        "compile_log_sha256": _sha(log),
        "artifacts": binaries,
        "claim_boundary": "Compiler result only; not a runtime, bus, sensor or physical test.",
        "firmware_authorized": False,
        "power_on_authorized": False,
        "physical_correctness": "UNPROVEN",
    }
    return report, log


def verify(
    spec: dict,
    *,
    output_root: Path,
    platformio: str | None = None,
    timeout: int = 600,
    vendor_libs: Path | None = None,
) -> tuple[Path, dict, dict | None, dict | None]:
    metadata, package = build_device_application(spec)
    output_root.mkdir(parents=True, exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix="device-application-", dir=output_root))
    (run / "device-application-proposal.zip").write_bytes(package)
    project = run / "project"
    with zipfile.ZipFile(io.BytesIO(package)) as archive:
        archive.extractall(project)
    behaviour, host_log = _run_host(project)
    behaviour["core_sha256"] = metadata["files"]["src/app_core.h"]["sha256"]
    behaviour["harness_sha256"] = metadata["files"]["test/host/harness.cpp"]["sha256"]
    (run / "host.log").write_bytes(host_log)
    (run / "BEHAVIOUR_RESULT.json").write_text(json.dumps(behaviour, indent=2, sort_keys=True) + "\n")
    compile_report = None
    if platformio:
        compile_report, compile_log = _compile_platformio(project, platformio, output_root, timeout)
        compile_report["proposal_sha256"] = _sha(package)
        compile_report["spec_sha256"] = metadata["spec_sha256"]
        compile_report["plan_sha256"] = metadata["plan_sha256"]
        compile_report["source_sha256"] = metadata["files"]["src/app_core.h"]["sha256"]
        (run / "compile.log").write_bytes(compile_log)
        (run / "COMPILE_RESULT.json").write_text(json.dumps(compile_report, indent=2, sort_keys=True) + "\n")
    vendor_report = None
    libs = vendor_libs
    if libs is None and platformio:
        libs = project / ".pio" / "libdeps" / "application"
    if vendor_libs is not None or platformio:
        vendor_report, vendor_log = _run_vendor_host(project, libs)
        vendor_report["core_sha256"] = metadata["files"]["src/app_core.h"]["sha256"]
        vendor_report["adapter_sha256"] = metadata["files"]["src/main.cpp"]["sha256"]
        (run / "vendor_host.log").write_bytes(vendor_log)
        (run / "VENDOR_HOST_RESULT.json").write_text(json.dumps(vendor_report, indent=2, sort_keys=True) + "\n")
    return run, behaviour, compile_report, vendor_report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument("--example", choices=list(example_specs()), default=None)
    inputs.add_argument("--spec", type=Path)
    parser.add_argument("--output-root", type=Path, default=Path(".cache/hardware-splicer/device-application"))
    parser.add_argument("--platformio", default=None, help="Optional PlatformIO Core 6.1.18 binary")
    parser.add_argument(
        "--vendor-libs",
        type=Path,
        default=None,
        help="Pinned PlatformIO libdeps/application directory for the vendor-host compile",
    )
    args = parser.parse_args()
    if args.spec:
        if args.spec.stat().st_size > 64 * 1024:
            parser.error("the spec may be at most 64 KiB")
        spec = json.loads(args.spec.read_text())
    else:
        spec = example_specs()[args.example or "esp32_oled_bme280_usb"]
    run, behaviour, compile_report, vendor_report = verify(
        spec,
        output_root=args.output_root,
        platformio=args.platformio,
        vendor_libs=args.vendor_libs,
    )
    summary = {
        "artifacts": str(run),
        "behaviour_pass": behaviour["pass"],
        "reason": behaviour.get("reason", ""),
        "physical_correctness": "UNPROVEN",
        "firmware_authorized": False,
        "power_on_authorized": False,
    }
    if compile_report is not None:
        summary["compile_pass"] = compile_report["compile_pass"]
        summary["compile_reason"] = compile_report["reason"]
    if vendor_report is not None:
        summary["vendor_host_pass"] = vendor_report["pass"]
        summary["vendor_host_reason"] = vendor_report["reason"]
    print(json.dumps(summary, indent=2))
    if not behaviour["pass"]:
        return 1
    if compile_report is not None and not compile_report["compile_pass"]:
        return 1
    if vendor_report is not None and not vendor_report["pass"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
