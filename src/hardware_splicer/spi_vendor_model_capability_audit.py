"""Capability audit for captured SPI vendor-model bytes.

The audit answers a narrower question than model capture: what classes of modeled claims can
an acquired file actually support? It never executes model code and never upgrades modeled
results into measured or physical evidence.
"""

from __future__ import annotations

import hashlib
import io
import re
import zipfile
from typing import Any, Mapping

_CAPTURE_SCHEMA = "hardware_splicer.vendor_model_capture.v1"
_SCHEMA_VERSION = "hardware_splicer.spi_vendor_model_capability_audit.v1"


class VendorModelCapabilityAuditError(ValueError):
    """Raised when captured bytes cannot be bound to the supplied manifest."""


def _sha256(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _recognized_ibis_members(manifest: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = manifest.get("recognized_model_files")
    if not isinstance(rows, list):
        return []
    return [
        row
        for row in rows
        if isinstance(row, Mapping) and row.get("model_kind") == "IBIS" and row.get("path")
    ]


def _member_bytes(payload: bytes, manifest: Mapping[str, Any]) -> list[tuple[str, bytes]]:
    if manifest.get("archive_type") == "zip":
        result: list[tuple[str, bytes]] = []
        inventory = {
            str(row.get("path")): row
            for row in manifest.get("archive_members", [])
            if isinstance(row, Mapping)
        }
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            for recognized in _recognized_ibis_members(manifest):
                path = str(recognized["path"])
                member = archive.read(path)
                expected = inventory.get(path, {}).get("sha256")
                if expected != _sha256(member) or recognized.get("sha256") != expected:
                    raise VendorModelCapabilityAuditError(
                        f"recognized IBIS member hash mismatch: {path}"
                    )
                result.append((path, member))
        return result

    members = _recognized_ibis_members(manifest)
    if len(members) != 1:
        raise VendorModelCapabilityAuditError("direct IBIS capture must bind exactly one member")
    if members[0].get("sha256") != _sha256(payload):
        raise VendorModelCapabilityAuditError("direct IBIS payload hash mismatch")
    return [(str(members[0]["path"]), payload)]


def audit_txu0304_ibis_capabilities(
    payload: bytes,
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    """Inspect a hash-bound TXU0304 IBIS capture without treating it as isolation proof.

    Standard IBIS electrical structures can support later signal-integrity execution. They do
    not, by themselves, establish the TXU0304 system-level guarantee that outputs are disabled
    when a supply is disconnected. That guarantee remains a source/specification claim unless
    a separate executable model explicitly implements the relevant power/OE state transition.
    """

    if not isinstance(payload, (bytes, bytearray)) or not payload:
        raise VendorModelCapabilityAuditError("captured model payload is empty")
    data = bytes(payload)
    if manifest.get("schema_version") != _CAPTURE_SCHEMA:
        raise VendorModelCapabilityAuditError("capture manifest schema mismatch")
    if manifest.get("model_id") != "txu0304-ibis-scem787":
        raise VendorModelCapabilityAuditError("unexpected model id for TXU0304 audit")
    if manifest.get("expected_model_kind") != "IBIS":
        raise VendorModelCapabilityAuditError("TXU0304 capability audit requires IBIS capture")
    if manifest.get("sha256") != _sha256(data):
        raise VendorModelCapabilityAuditError("capture manifest outer hash mismatch")

    members = _member_bytes(data, manifest)
    if not members:
        raise VendorModelCapabilityAuditError("capture contains no recognized IBIS member")

    combined = "\n".join(member.decode("latin-1", errors="ignore") for _, member in members)
    lowered = combined.lower()
    model_types = sorted(
        {
            match.group(1).strip()
            for match in re.finditer(r"(?im)^\s*model_type\s+([^\r\n|]+)", combined)
        }
    )
    model_names = sorted(
        {
            match.group(1).strip()
            for match in re.finditer(r"(?im)^\s*\[model\]\s+([^\r\n|]+)", combined)
        }
    )
    components = sorted(
        {
            match.group(1).strip()
            for match in re.finditer(r"(?im)^\s*\[component\]\s+([^\r\n|]+)", combined)
        }
    )

    section_presence = {
        "pin": "[pin]" in lowered,
        "model": "[model]" in lowered,
        "pullup": "[pullup]" in lowered,
        "pulldown": "[pulldown]" in lowered,
        "power_clamp": "[power clamp]" in lowered,
        "gnd_clamp": "[gnd clamp]" in lowered,
        "ramp": "[ramp]" in lowered,
        "rising_waveform": "[rising waveform]" in lowered,
        "falling_waveform": "[falling waveform]" in lowered,
    }
    three_state_model_present = any(
        token in model_type.lower() for model_type in model_types for token in ("3-state", "3_state")
    )
    textual_power_state_markers = sorted(
        marker
        for marker in (
            "partial power",
            "power-off",
            "power off",
            "vcc disconnect",
            "vcc-disconnect",
            "i_off",
            "ioff",
            "output enable",
        )
        if marker in lowered
    )
    signal_integrity_structure_present = bool(
        components
        and model_names
        and section_presence["pin"]
        and (section_presence["pullup"] or section_presence["pulldown"])
    )

    # Fail closed: standard IBIS structures and even a textual power-state mention are not an
    # executable proof of the system-level VCC-disconnect/OE transition required by the frozen
    # rail-absent execution contract.
    rail_absent_isolation_claim_supported = False

    return {
        "schema_version": _SCHEMA_VERSION,
        "model_id": "txu0304-ibis-scem787",
        "capture_sha256": manifest.get("sha256"),
        "recognized_ibis_member_count": len(members),
        "recognized_ibis_member_paths": [path for path, _ in members],
        "component_names": components,
        "model_count": len(model_names),
        "model_types": model_types,
        "section_presence": section_presence,
        "three_state_model_present": three_state_model_present,
        "textual_power_state_markers": textual_power_state_markers,
        "signal_integrity_structure_present": signal_integrity_structure_present,
        "eligible_for_later_signal_integrity_execution": signal_integrity_structure_present,
        "rail_absent_isolation_claim_supported": rail_absent_isolation_claim_supported,
        "rail_absent_isolation_blocker": (
            "Standard IBIS electrical data does not by itself execute the TXU0304 "
            "VCC-disconnect/OE state transition required to prove the rail-absent isolation case."
        ),
        "modeled_evidence_only": True,
        "measured_evidence_present": False,
        "physical_correctness": "UNPROVEN",
        "fabrication_ready": False,
        "power_on_ready": False,
        "physical_authority_granted": False,
        "authority_effect": "none",
    }
