"""Opt-in KiCad CLI analysis of hash-verified registered engineering files.

Returns bounded diagnostics and netlist counts; never certifies a design or a
physical operation. This examines real third-party source instead of demos.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from typing import Any


def kicad_source_check_enabled() -> bool:
    return os.getenv("HARDWARE_SPLICER_ENABLE_KICAD_SOURCE_CHECK") == "1"


def registered_kicad_kind(filename: str, content: bytes) -> str | None:
    suffix = Path(filename).suffix.lower()
    if suffix == ".kicad_sch" and content.lstrip().startswith(b"(kicad_sch"):
        return "schematic"
    if suffix == ".kicad_pcb" and content.lstrip().startswith(b"(kicad_pcb"):
        return "pcb"
    return None


def check_kicad_bytes(filename: str, content: bytes, *, timeout_s: int = 35) -> dict[str, Any]:
    kind = registered_kicad_kind(filename, content)
    if kind is None:
        raise ValueError("KiCad source suffix and format signature do not agree")
    binary = shutil.which("kicad-cli")
    if binary is None:
        return {"status": "unavailable", "kind": kind,
                "reason": "kicad-cli unavailable", "check_executed": False,
                "release_authorized": False}
    timeout = max(1, min(int(timeout_s), 60))
    with tempfile.TemporaryDirectory(prefix="hs-kicad-source-") as directory:
        source_file = Path(directory) / ("input" + Path(filename).suffix.lower())
        source_file.write_bytes(content)
        report = Path(directory) / "diagnostic_report.txt"
        command = [binary, "sch" if kind == "schematic" else "pcb",
                   "erc" if kind == "schematic" else "drc",
                   "--exit-code-violations", "--output", str(report), str(source_file)]
        try:
            result = subprocess.run(command, cwd=directory, capture_output=True,
                                    text=True, timeout=timeout, check=False)
        except subprocess.TimeoutExpired:
            return {"status": "timeout", "kind": kind,
                    "check_executed": False, "release_authorized": False}
        except OSError:
            return {"status": "tool_error", "kind": kind,
                    "check_executed": False, "release_authorized": False}
        if not report.is_file() or result.returncode not in {0, 5}:
            return {"status": "tool_error", "kind": kind, "check_executed": True,
                    "tool_exit_code": result.returncode,
                    "tool_output_excerpt": (result.stderr or result.stdout)[:800],
                    "release_authorized": False}
        report_bytes = report.read_bytes()
        lines = report_bytes.decode("utf-8", errors="replace").splitlines()
        codes = Counter(line[1:].split("]", 1)[0] for line in lines
                        if line.startswith("[") and "]" in line)
        summary = {
            "status": "findings_present" if codes or result.returncode == 5 else "no_findings_reported",
            "kind": kind, "check_executed": True,
            "tool_exit_code": result.returncode,
            "rule_finding_count": sum(codes.values()),
            "rule_findings_by_type": dict(sorted(codes.items())),
            "report_sha256": "sha256:" + hashlib.sha256(report_bytes).hexdigest(),
            "report_bytes": len(report_bytes),
            "missing_or_mismatched_libraries_may_affect_checks": True,
            "manufacturing_verified": False, "release_authorized": False,
        }
        if kind == "schematic":
            net = Path(directory) / "source-netlist.xml"
            try:
                exported = subprocess.run(
                    [binary, "sch", "export", "netlist", "--format", "kicadxml",
                     "--output", str(net), str(source_file)],
                    cwd=directory, capture_output=True, text=True, check=False,
                    timeout=timeout)
            except (OSError, subprocess.TimeoutExpired):
                exported = None
            if exported is not None and exported.returncode == 0 and net.is_file() and net.stat().st_size < 8 * 1024 * 1024:
                try:
                    root = ET.parse(net).getroot()
                    summary["netlist_export"] = {
                        "status": "exported_unverified",
                        "component_count": len(root.findall("./components/comp")),
                        "net_count": len(root.findall("./nets/net")),
                        "sha256": "sha256:" + hashlib.sha256(net.read_bytes()).hexdigest(),
                        "pinout_and_compatibility_verified": False,
                    }
                except ET.ParseError:
                    summary["netlist_export"] = {"status": "invalid_xml"}
            else:
                summary["netlist_export"] = {
                    "status": "failed",
                    "tool_exit_code": exported.returncode if exported is not None else None,
                }
        return summary
