"""Static capability audit for the captured Winbond W25Q128JW-Q Verilog model.

This layer deliberately does not execute the model. It binds the exact captured bytes to the
capture manifest, inventories the Verilog source, and asks whether the source contains the
minimum structures expected before a bounded JEDEC-ID execution is even attempted.

Source inspection is only an execution-eligibility input. It is never a passing simulation
result and never promotes modeled evidence into measured or physical authority.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Mapping

from .captured_model_materialization import extract_bound_model_member

SCHEMA_VERSION = "hardware_splicer.spi_winbond_verilog_capability.v1"
_CAPTURE_SCHEMA = "hardware_splicer.vendor_model_capture.v1"
_MODEL_ID = "w25q128jw-q-verilog-da02-aag072"


class WinbondVerilogCapabilityError(ValueError):
    """Raised when the supplied bytes are not the hash-bound Winbond Verilog capture."""


def _sha256(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _recognized_verilog_rows(manifest: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = manifest.get("recognized_model_files")
    if not isinstance(rows, list):
        return []
    return [
        row
        for row in rows
        if isinstance(row, Mapping)
        and row.get("model_kind") == "Verilog"
        and isinstance(row.get("path"), str)
        and row.get("path")
    ]


def _hex_literal_present(source: str, value: str) -> bool:
    token = value.lower().replace("0x", "")
    patterns = [
        rf"(?i)\b(?:\d+)?'h0*{re.escape(token)}\b",
        rf"(?i)\b0x0*{re.escape(token)}\b",
    ]
    return any(re.search(pattern, source) for pattern in patterns)


def audit_winbond_verilog_capabilities(
    outer_payload: bytes,
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    """Inspect hash-bound Winbond Verilog source without executing it.

    ``jedec_id_read_9f_source_candidate`` is intentionally weaker than the capability-gate field
    ``jedec_id_read_9f_supported``. The latter is produced only after an exact-source Icarus
    preflight also succeeds.
    """

    if not isinstance(outer_payload, (bytes, bytearray)) or not outer_payload:
        raise WinbondVerilogCapabilityError("captured model payload is empty")
    payload = bytes(outer_payload)
    if manifest.get("schema_version") != _CAPTURE_SCHEMA:
        raise WinbondVerilogCapabilityError("capture manifest schema mismatch")
    if manifest.get("model_id") != _MODEL_ID:
        raise WinbondVerilogCapabilityError("unexpected model id for Winbond Verilog audit")
    if manifest.get("expected_model_kind") != "Verilog":
        raise WinbondVerilogCapabilityError("Winbond capability audit requires Verilog capture")
    if manifest.get("sha256") != _sha256(payload):
        raise WinbondVerilogCapabilityError("capture manifest outer hash mismatch")

    rows = _recognized_verilog_rows(manifest)
    if not rows:
        raise WinbondVerilogCapabilityError("capture contains no recognized Verilog model file")

    members: list[tuple[str, bytes]] = []
    for row in rows:
        path = str(row["path"])
        member, materialization = extract_bound_model_member(
            payload,
            manifest,
            member_path=path,
        )
        if materialization.get("model_kind") != "Verilog":
            raise WinbondVerilogCapabilityError(f"recognized member kind mismatch: {path}")
        members.append((path, member))

    source = "\n".join(member.decode("latin-1", errors="ignore") for _, member in members)
    lowered = source.lower()
    module_names = sorted(
        {
            match.group(1)
            for match in re.finditer(
                r"(?im)^\s*module\s+([A-Za-z_][A-Za-z0-9_$]*)\b",
                source,
            )
        }
    )
    has_behavioral_logic = bool(
        re.search(r"(?im)^\s*(?:always(?:_ff|_comb|_latch)?|initial)\b", source)
        or re.search(r"(?im)^\s*assign\s+", source)
    )
    has_case_logic = bool(re.search(r"(?i)\bcase[xz]?\s*\(", source))
    command_9f_present = _hex_literal_present(source, "9f") or bool(
        re.search(r"(?i)\b(?:159)\b", source)
    )
    jedec_ef6018_present = bool(re.search(r"(?i)\b(?:24)?'h0*ef[_ ]?60[_ ]?18\b", source)) or (
        _hex_literal_present(source, "ef")
        and _hex_literal_present(source, "60")
        and _hex_literal_present(source, "18")
    )
    likely_spi_terms = sorted(
        term
        for term in ("cs", "clk", "sclk", "mosi", "miso", "di", "do", "io0", "io1")
        if re.search(rf"(?i)\b{re.escape(term)}\b", source)
    )

    source_candidate = bool(
        module_names
        and has_behavioral_logic
        and command_9f_present
        and jedec_ef6018_present
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "model_id": _MODEL_ID,
        "capture_sha256": manifest.get("sha256"),
        "recognized_verilog_member_count": len(members),
        "recognized_verilog_member_paths": [path for path, _ in members],
        "module_names": module_names,
        "module_count": len(module_names),
        "has_behavioral_logic": has_behavioral_logic,
        "has_case_logic": has_case_logic,
        "command_9f_literal_present": command_9f_present,
        "jedec_ef6018_literal_present": jedec_ef6018_present,
        "likely_spi_terms": likely_spi_terms,
        "jedec_id_read_9f_source_candidate": source_candidate,
        # Static text inspection alone is deliberately insufficient for the campaign gate.
        "jedec_id_read_9f_supported": False,
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
            "Literal/source inspection is not a passing JEDEC-ID simulation.",
            "A source candidate still requires exact-source compiler preflight and a bound testbench execution.",
            "Model execution is not measured physical evidence.",
        ],
    }
