#!/usr/bin/env python3
"""Compile the exact generated *application* firmware archive with PlatformIO.

Unlike the firmware's host-model harness this tests an embedded target toolchain.
It does not flash a board, exercise real I2C timing or validate any electrical
behavior. A pinned core version and source hashes are required.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath

PLATFORMIO_VERSION = "PlatformIO Core, version 6.1.18"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_source_archive(source: Path, dest: Path) -> dict:
    """Extract only fresh, allowed source members from HS's output ZIP."""
    with zipfile.ZipFile(source) as z:
        entries = z.infolist()
        if not entries:
            raise ValueError("Empty generated source archive")
        for entry in entries:
            member = PurePosixPath(entry.filename)
            if (
                member.is_absolute()
                or ".." in member.parts
                or "\\" in entry.filename
                or member.parts[0] not in {"src", "test", "platformio.ini", "DEVICE_SPEC.json",
                                         "DEVICE_PLAN.json", "FIRMWARE_PROPOSAL.json",
                                         "PART_DESCRIPTOR.json", "README.md"}
            ):
                raise ValueError(f"Unsafe or unexpected firmware archive member: {entry.filename}")
        z.extractall(dest)
    for required in ("platformio.ini", "src/main.cpp", "DEVICE_SPEC.json", "DEVICE_PLAN.json"):
        if not (dest / required).is_file():
            raise ValueError(f"Required firmware member missing: {required}")
    return {"source_main_sha256": _sha((dest / "src/main.cpp").read_bytes()),
            "platformio_ini_sha256": _sha((dest / "platformio.ini").read_bytes())}


def compile_embedded_firmware(project: Path, *, pio: str = "pio", timeout: int = 1050) -> dict:
    project = Path(project).resolve()
    receipt = json.loads((project / "CROSS_DOMAIN_RECEIPT.json").read_text())
    source = project / "FIRMWARE_SOURCE.zip"
    if _sha(source.read_bytes()) != receipt["artifacts"]["FIRMWARE_SOURCE.zip"]["sha256"]:
        raise ValueError("The actual firmware archive differs from the design receipt")
    if receipt["flashing_authorized"] or receipt["power_on_authorized"]:
        raise ValueError("This build must not grant hardware authority")
    extracted = project / "platformio-application"
    if extracted.exists():
        raise ValueError("Refusing to overwrite prior PlatformIO project")
    extracted.mkdir()
    sources = _load_source_archive(source, extracted)
    bundled_spec = json.loads((extracted / "DEVICE_SPEC.json").read_text())
    if _sha((project / "DEVICE_SPEC.json").read_bytes()) != receipt["source_spec_sha256"]:
        raise ValueError("Bound source specification is not the same revision")
    if bundled_spec != json.loads((project / "DEVICE_SPEC.json").read_text()):
        raise ValueError("Firmware ZIP and CAD source reference different specifications")
    if json.loads((extracted / "DEVICE_PLAN.json").read_text()) != json.loads(
        (project / "DEVICE_PLAN.json").read_text()
    ):
        raise ValueError("Firmware ZIP and CAD source reference different plans")
    ini = (extracted / "platformio.ini").read_text()
    if ("platform = espressif32@6.10.0" not in ini or "board = esp32dev" not in ini
            or "framework = arduino" not in ini or "[env:application]" not in ini):
        raise ValueError("Unexpected embedded build target; refuse unpinned configuration")
    env = dict(os.environ)
    env["PLATFORMIO_SETTING_ENABLE_TELEMETRY"] = "No"
    env["PLATFORMIO_SETTING_CHECK_PLATFORMIO_INTERVAL"] = "0"
    env["PLATFORMIO_CORE_DIR"] = env.get(
        "PLATFORMIO_CORE_DIR", str((project / ".platformio-core").resolve())
    )
    tool = subprocess.run([pio, "--version"], capture_output=True, text=True,
                          timeout=30, env=env, check=False)
    version = tool.stdout.strip()
    if tool.returncode != 0 or version != PLATFORMIO_VERSION:
        raise ValueError(f"Pinned PlatformIO {PLATFORMIO_VERSION} required; got {version!r}")
    command = [pio, "run", "--project-dir", str(extracted),
               "--environment", "application", "--jobs", "2"]
    try:
        process = subprocess.run(command, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, timeout=timeout,
                                 env=env, check=False)
        log = process.stdout
        exit_code = process.returncode
    except subprocess.TimeoutExpired as err:
        log = err.stdout or b""
        exit_code = -1
    (project / "PLATFORMIO_COMPILE.log").write_bytes(log)
    output = extracted / ".pio/build/application"
    artifacts = {}
    for name in ("firmware.elf", "firmware.bin"):
        candidate = output / name
        if candidate.is_file() and candidate.stat().st_size:
            artifacts[name] = {
                "sha256": _sha(candidate.read_bytes()),
                "bytes": candidate.stat().st_size,
            }
    passed = exit_code == 0 and len(artifacts) == 2
    return {
        "schema_version": "hardware_splicer.cross_domain_target_compile.v1",
        "source_spec_sha256": receipt["source_spec_sha256"],
        "firmware_source_zip_sha256": _sha(source.read_bytes()),
        **sources,
        "toolchain": version,
        "command": ["pio", "run", "--environment", "application", "--jobs", "2"],
        "exit_code": exit_code,
        "compile_pass": passed,
        "compile_log_sha256": _sha(log),
        "compiled_artifacts": artifacts,
        "real_hardware_flashing": False,
        "physical_behavior_verified": False,
        "firmware_authorized": False,
        "power_on_authorized": False,
        "note": "ESP32 target compiler only; no real circuit behavior or flashing.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--pio", default="pio")
    args = parser.parse_args()
    path = args.project / "FIRMWARE_TARGET_COMPILE_EVIDENCE.json"
    if path.exists():
        parser.error("Evidence file already exists; refusing to overwrite")
    try:
        evidence = compile_embedded_firmware(args.project, pio=args.pio)
        path.write_text(json.dumps(evidence, sort_keys=True, indent=2) + "\n")
        print(json.dumps(evidence, indent=2))
        return 0 if evidence["compile_pass"] else 1
    except (OSError, ValueError, zipfile.BadZipFile, subprocess.SubprocessError) as exc:
        print(f"Embedded firmware compilation refused/failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
