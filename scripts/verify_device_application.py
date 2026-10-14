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
from hardware_splicer.device_parts import example_spec_for_part
from hardware_splicer.device_plan import example_specs

DEFAULT_CORE_DIR = Path(__file__).resolve().parents[1] / ".cache" / "hardware-splicer" / "device-firmware" / "platformio-core"
from hardware_splicer.device_application_execution import (
    CLAIM_BOUNDARY, VENDOR_HOST_CLAIM_BOUNDARY, VENDOR_LIB_DIRS, VENDOR_LIB_SOURCES,
    HOST_SCENARIOS, VENDOR_SCENARIOS, _scenario_failure, _sha,
    vendor_libs_available, vendor_host_compile_command, _not_run_vendor, _run_host, _run_vendor_host,
)


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
    if not metadata["part"]["vendor_host_supported"]:
        # Not applicable, not a failure: there is no register-level model for this part to run against.
        # The package says which is true: the part has no bus model, or this controller's Arduino core has no shim.
        on_board = "for this controller" in metadata.get("vendor_host_claim_boundary", "")
        vendor_report = {
            "pass": None,
            "reason": (f"no vendor-host lane exists on the {metadata['target']['board']} board: the host shim models the ESP32 "
                       "Arduino core's Wire, so the Arduino adapter was not tested against a modelled bus") if on_board else
                      f"no vendor-host lane exists for the {metadata['part']['chip']}; its Arduino adapter was not tested against a modelled bus",
        }
    elif vendor_libs is not None or platformio:
        vendor_report, vendor_log = _run_vendor_host(project, libs, metadata["part"]["vendor_profile"])
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
    inputs.add_argument("--part", choices=("bme280", "bh1750"), help="the example wired for this supported sensor")
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
    elif args.part:
        spec = example_spec_for_part({"bme280": "adafruit-bme280-stemma-qt", "bh1750": "adafruit-bh1750-stemma-qt"}[args.part])
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
    if vendor_report is not None and vendor_report["pass"] is False:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
