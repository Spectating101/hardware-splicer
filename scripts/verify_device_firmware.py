#!/usr/bin/env python3
"""Compile a fresh, recomputed device proposal. Never upload or access hardware."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

# scripts/hardware_splicer.py would otherwise shadow the src package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from hardware_splicer.device_firmware import build_device_firmware
from hardware_splicer.device_plan import example_specs


def verify(spec: dict, *, output_root: Path, platformio: str, timeout: int = 600) -> tuple[Path, dict]:
    _metadata, package = build_device_firmware(spec)
    output_root.mkdir(parents=True, exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix="device-firmware-", dir=output_root))
    (run / "device-diagnostic-proposal.zip").write_bytes(package)
    project = run / "project"
    # Only fixed, freshly generated members; no user-supplied archive or build scripts.
    with zipfile.ZipFile(io.BytesIO(package)) as archive:
        archive.extractall(project)
    command = [platformio, "run", "--project-dir", str(project), "--environment", "diagnostic", "--jobs", "2"]
    env = dict(os.environ)
    env["PLATFORMIO_CORE_DIR"] = env.get("PLATFORMIO_CORE_DIR", str(output_root.resolve() / "platformio-core"))
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
            process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     timeout=timeout, check=False, env=env)
            returncode, log = process.returncode, process.stdout
    except subprocess.TimeoutExpired as exc:
        reason, log = "compiler timed out", exc.stdout or b""
    except OSError as exc:
        reason = f"compiler could not start: {exc}"
    (run / "compile.log").write_bytes(log)
    binaries = {}
    for name in ("firmware.elf", "firmware.bin"):
        path = project / ".pio" / "build" / "diagnostic" / name
        if path.is_file() and path.stat().st_size:
            data = path.read_bytes()
            binaries[name] = {"sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data)}
    passed = not reason and returncode == 0 and len(binaries) == 2
    report = {"schema_version": "hardware_splicer.device_firmware_compile.v1", "compile_pass": passed,
              "reason": reason or ("" if passed else "compiler failed or expected build artifacts are absent"),
              "compiler": version, "command": command, "exit_code": returncode,
              "proposal_sha256": hashlib.sha256(package).hexdigest(),
              "spec_sha256": _metadata["spec_sha256"], "plan_sha256": _metadata["plan_sha256"],
              "source_sha256": _metadata["files"]["src/main.cpp"]["sha256"],
              "compile_log_sha256": hashlib.sha256(log).hexdigest(), "artifacts": binaries,
              "claim_boundary": "Compiler result only; not a runtime, bus, sensor or physical test.",
              "firmware_authorized": False, "power_on_authorized": False, "physical_correctness": "UNPROVEN"}
    (run / "COMPILE_RESULT.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    if passed:
        # A compiler bundle is separate from the immutable, uncompiled source
        # proposal. It is not a release/flash authorization or a physical result.
        members = {"device-diagnostic-proposal.zip": run / "device-diagnostic-proposal.zip",
                   "COMPILE_RESULT.json": run / "COMPILE_RESULT.json", "compile.log": run / "compile.log"}
        members.update({name: project / ".pio/build/diagnostic" / name for name in binaries})
        with zipfile.ZipFile(run / "compiled-diagnostic-proposal.zip", "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, path in sorted(members.items()):
                archive.writestr(name, path.read_bytes())
    return run, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument("--example", choices=list(example_specs()), default=None)
    inputs.add_argument("--spec", type=Path)
    parser.add_argument("--output-root", type=Path, default=Path(".cache/hardware-splicer/device-firmware"))
    parser.add_argument("--platformio", default="pio")
    args = parser.parse_args()
    if args.spec:
        if args.spec.stat().st_size > 64 * 1024:
            parser.error("the spec may be at most 64 KiB")
        spec = json.loads(args.spec.read_text())
    else:
        spec = example_specs()[args.example or "esp32_oled_bme280_usb"]
    run, report = verify(spec, output_root=args.output_root, platformio=args.platformio)
    print(json.dumps({"artifacts": str(run), "compile_pass": report["compile_pass"],
                      "reason": report["reason"], "physical_correctness": "UNPROVEN"}, indent=2))
    return 0 if report["compile_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
