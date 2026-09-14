"""Static capability audit for captured Winbond W25Q128JWSIQ IBIS bytes.

The audit is intentionally limited to whether the exact model contains ordinary IBIS
structures suitable for later signal-integrity execution. It does not execute a simulator and
never promotes modeled evidence to measured or physical authority.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Mapping

from .captured_model_materialization import extract_bound_model_member

SCHEMA_VERSION = "hardware_splicer.spi_winbond_ibis_capability.v1"
_CAPTURE_SCHEMA = "hardware_splicer.vendor_model_capture.v1"
_MODEL_ID = "w25q128jwsiq-ibis-da03-aag072"


class WinbondIbisCapabilityError(ValueError):
    pass


def _sha256(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _recognized_ibis_rows(manifest: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = manifest.get("recognized_model_files")
    if not isinstance(rows, list):
        return []
    return [
        row
        for row in rows
        if isinstance(row, Mapping)
        and row.get("model_kind") == "IBIS"
        and isinstance(row.get("path"), str)
        and row.get("path")
    ]


def audit_winbond_ibis_capabilities(
    outer_payload: bytes,
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(outer_payload, (bytes, bytearray)) or not outer_payload:
        raise WinbondIbisCapabilityError("captured model payload is empty")
    payload = bytes(outer_payload)
    if manifest.get("schema_version") != _CAPTURE_SCHEMA:
        raise WinbondIbisCapabilityError("capture manifest schema mismatch")
    if manifest.get("model_id") != _MODEL_ID:
        raise WinbondIbisCapabilityError("unexpected model id for Winbond IBIS audit")
    if manifest.get("expected_model_kind") != "IBIS":
        raise WinbondIbisCapabilityError("Winbond capability audit requires IBIS capture")
    if manifest.get("sha256") != _sha256(payload):
        raise WinbondIbisCapabilityError("capture manifest outer hash mismatch")

    rows = _recognized_ibis_rows(manifest)
    if not rows:
        raise WinbondIbisCapabilityError("capture contains no recognized IBIS model file")

    members: list[tuple[str, bytes]] = []
    for row in rows:
        path = str(row["path"])
        member, materialization = extract_bound_model_member(payload, manifest, member_path=path)
        if materialization.get("model_kind") != "IBIS":
            raise WinbondIbisCapabilityError(f"recognized member kind mismatch: {path}")
        members.append((path, member))

    source = "\n".join(member.decode("latin-1", errors="ignore") for _, member in members)
    lowered = source.lower()
    components = sorted(
        {
            match.group(1).strip()
            for match in re.finditer(r"(?im)^\s*\[component\]\s+([^\r\n|]+)", source)
        }
    )
    model_names = sorted(
        {
            match.group(1).strip()
            for match in re.finditer(r"(?im)^\s*\[model\]\s+([^\r\n|]+)", source)
        }
    )
    model_types = sorted(
        {
            match.group(1).strip()
            for match in re.finditer(r"(?im)^\s*model_type\s+([^\r\n|]+)", source)
        }
    )
    sections = {
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
    target_family_marker_present = "w25q128jw" in lowered
    ordinary_si_structure = bool(
        components
        and model_names
        and sections["pin"]
        and (
            sections["pullup"]
            or sections["pulldown"]
            or sections["gnd_clamp"]
            or sections["power_clamp"]
            or sections["ramp"]
        )
    )
    eligible = bool(target_family_marker_present and ordinary_si_structure)

    return {
        "schema_version": SCHEMA_VERSION,
        "model_id": _MODEL_ID,
        "capture_sha256": manifest.get("sha256"),
        "recognized_ibis_member_count": len(members),
        "recognized_ibis_member_paths": [path for path, _ in members],
        "component_names": components,
        "model_count": len(model_names),
        "model_types": model_types,
        "section_presence": sections,
        "target_family_marker_present": target_family_marker_present,
        "signal_integrity_structure_present": ordinary_si_structure,
        "eligible_for_later_signal_integrity_execution": eligible,
        "execution_credit_granted": False,
        "model_inference_used": False,
        "modeled_evidence_only": True,
        "measured_evidence_present": False,
        "physical_correctness": "UNPROVEN",
        "fabrication_ready": False,
        "power_on_ready": False,
        "physical_authority_granted": False,
        "authority_effect": "none",
        "nonclaims": [
            "IBIS structure inspection is not a signal-integrity simulation.",
            "Signal-integrity eligibility still requires an exact engine and preregistered conditions.",
            "A passing manufacturer-model simulation would remain modeled-only evidence.",
        ],
    }
