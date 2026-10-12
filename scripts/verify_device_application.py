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
# The diagnostic verifier's toolchain cache, so one download serves both. Set PLATFORMIO_CORE_DIR to use another.
DEFAULT_CORE_DIR = Path(__file__).resolve().parents[1] / ".cache" / "hardware-splicer" / "device-firmware" / "platformio-core"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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
            ran = subprocess.run([str(project / "harness")], cwd=project, capture_output=True, check=False)
            log = log + ran.stdout + ran.stderr
            try:
                scenarios = [json.loads(line) for line in ran.stdout.decode().splitlines() if line.strip()]
            except json.JSONDecodeError:
                reason = "host harness did not print JSON scenario results"
            else:
                passed = ran.returncode == 0 and bool(scenarios) and all(row.get("pass") for row in scenarios)
                if not passed:
                    reason = "one or more host scenarios failed"
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


def verify(spec: dict, *, output_root: Path, platformio: str | None = None, timeout: int = 600) -> tuple[Path, dict, dict | None]:
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
    return run, behaviour, compile_report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument("--example", choices=list(example_specs()), default=None)
    inputs.add_argument("--spec", type=Path)
    parser.add_argument("--output-root", type=Path, default=Path(".cache/hardware-splicer/device-application"))
    parser.add_argument("--platformio", default=None, help="Optional PlatformIO Core 6.1.18 binary")
    args = parser.parse_args()
    if args.spec:
        if args.spec.stat().st_size > 64 * 1024:
            parser.error("the spec may be at most 64 KiB")
        spec = json.loads(args.spec.read_text())
    else:
        spec = example_specs()[args.example or "esp32_oled_bme280_usb"]
    run, behaviour, compile_report = verify(spec, output_root=args.output_root, platformio=args.platformio)
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
    print(json.dumps(summary, indent=2))
    if not behaviour["pass"]:
        return 1
    if compile_report is not None and not compile_report["compile_pass"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
