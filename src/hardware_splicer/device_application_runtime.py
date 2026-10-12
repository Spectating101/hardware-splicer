"""Opt-in execution of HS-owned templates, never caller-supplied code or hardware."""
from __future__ import annotations

import hashlib
import io
import os
import subprocess
from pathlib import Path
import tempfile
import threading
import zipfile

from .device_application import build_device_application
from .device_application_execution import _run_host, _run_vendor_host
from .bounded_process import BoundedProcessError

_RUN_SLOT = threading.BoundedSemaphore(1)
BOUNDARY = "Modeled software execution only. Not ESP32 silicon, physical sensor readings, bus timing or electrical validation. No flashing or power authorization."
VENDOR_PINS = {
    "Adafruit BME280 Library": "2.3.0", "Adafruit SSD1306": "2.5.17",
    "Adafruit GFX Library": "1.12.6", "Adafruit BusIO": "1.17.4", "Adafruit Unified Sensor": "1.1.15",
}


class DeviceRuntimeError(RuntimeError):
    def __init__(self, message: str, status_code: int = 503):
        super().__init__(message)
        self.status_code = status_code


def _phase(report: dict, log: bytes) -> dict:
    return {**report, "status": "PASSED" if report["pass"] else "FAILED",
            "output_sha256": hashlib.sha256(log).hexdigest()}


def _vendor_manifest(root: Path) -> dict:
    manifest = {}
    for name, version in VENDOR_PINS.items():
        properties = root / name / "library.properties"
        if not properties.is_file() or f"version={version}" not in properties.read_text().splitlines():
            raise DeviceRuntimeError("Vendor libraries do not match the application's pinned versions.")
        members = {}
        for path in sorted((root / name).rglob("*")):
            if path.is_file() and path.suffix in {".cpp", ".h", ".properties"}:
                members[path.relative_to(root / name).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest[name] = {"version": version, "files": members}
    return manifest


def run_device_application(spec: dict) -> dict:
    # Admission and export checks happen before any compiler is launched.
    metadata, package = build_device_application(spec)
    if os.environ.get("HS_DEVICE_RUNTIME_ENABLED") != "1":
        raise DeviceRuntimeError("Modeled execution is disabled on this server; enable HS_DEVICE_RUNTIME_ENABLED=1.")
    if not _RUN_SLOT.acquire(blocking=False):
        raise DeviceRuntimeError("Another modeled run is active. Try again after it finishes.", 429)
    try:
        vendor = {"status": "NOT_RUN", "pass": None, "reason": "Pinned vendor libraries are not configured on this server.", "scenarios": []}
        configured = os.environ.get("HS_DEVICE_RUNTIME_VENDOR_LIBS", "").strip()
        manifest = _vendor_manifest(Path(configured).resolve()) if configured else None
        # Only bytes freshly generated from HS templates enter this temporary directory.
        with tempfile.TemporaryDirectory(prefix="hs-device-modeled-") as temporary:
            project = Path(temporary)
            with zipfile.ZipFile(io.BytesIO(package)) as archive:
                archive.extractall(project)
            host, log = _run_host(project)
            host = _phase(host, log)
            vendor_fixture_supported = any(row["library_id"] == "ssd1306-096-i2c" for row in metadata["declared_devices"])
            if configured and not vendor_fixture_supported:
                vendor["reason"] = "This vendor-host fixture requires the BME280 and SSD1306 combination; the sensor-only adapter was not tested."
            if configured and vendor_fixture_supported and host["pass"] is True:
                report, vendor_log = _run_vendor_host(project, Path(configured).resolve())
                vendor = _phase(report, vendor_log)
                vendor["library_manifest"] = manifest
        state = "FAILED" if host["pass"] is not True or vendor["status"] == "FAILED" else (
            "PASSED" if vendor["status"] == "PASSED" else "PARTIAL")
        return {
            "schema_version": "hardware_splicer.device_application_modeled_run.v1",
            "status": state, "claim_boundary": BOUNDARY,
            "provenance": "generated_template_host_execution",
            "spec_sha256": metadata["spec_sha256"], "plan_sha256": metadata["plan_sha256"],
            "proposal_sha256": hashlib.sha256(package).hexdigest(), "files": metadata["files"],
            "host": host, "vendor_host": vendor,
            "esp32_compilation": "NOT_RUN", "physical_correctness": "UNPROVEN",
            "firmware_authorized": False, "power_on_authorized": False,
        }
    except (OSError, TimeoutError, subprocess.SubprocessError, BoundedProcessError) as exc:
        raise DeviceRuntimeError("The modeled executor could not complete on this server.") from exc
    finally:
        _RUN_SLOT.release()
