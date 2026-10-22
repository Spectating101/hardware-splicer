"""Verify that native Circuit JSON can enter HS's canonical electrical identity model."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .electrical_interchange import electrical_design_from_interchange
from .integrations.circuit_json_import import circuit_json_to_netlist

MAX_CIRCUIT_JSON_BYTES = 16_000_000


def inspect_native_circuit_json(path: str | Path, *, project_id: str) -> dict:
    source = Path(path)
    if not source.is_file() or source.stat().st_size > MAX_CIRCUIT_JSON_BYTES:
        raise ValueError("Circuit JSON artifact missing or oversized")
    raw = source.read_bytes()
    if not raw:
        raise ValueError("Circuit JSON is empty")
    documents = json.loads(raw)
    if not isinstance(documents, list) or not 1 <= len(documents) <= 50_000:
        raise ValueError("Circuit JSON requires a bounded nonempty document array")
    if any(not isinstance(row, dict) for row in documents):
        raise ValueError("Circuit JSON contains invalid documents")
    netlist = circuit_json_to_netlist(documents, source="external_tscircuit_native")
    if not netlist.components or not netlist.nets:
        raise ValueError("Circuit JSON has no importable electrical components and nets")
    design = electrical_design_from_interchange(
        netlist, documents, project_id=project_id,
    )
    if not design.components or not design.nets:
        raise ValueError("Circuit JSON did not produce canonical electrical identity")
    erc = design.erc_issues()
    identity = design.metadata.get("identity_map") or {}
    return {
        "schema": "hardware_splicer.external_circuit_json_projection.v1",
        "source_sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
        "status": "candidate_imported_requires_electrical_review",
        "source_document_count": len(documents),
        "netlist_component_count": len(netlist.components),
        "netlist_net_count": len(netlist.nets),
        "canonical_component_count": len(design.components),
        "canonical_net_count": len(design.nets),
        "erc_issue_count": len(erc),
        "canonical_identity_keys": sorted(identity.keys()),
        "manufacturer_footprints_authenticated": False,
        "electrical_erc_authority": "review_only",
        "power_on_authorized": False,
        "fabrication_authorized": False,
        "release_authorized": False,
    }
