"""Compatibility corrections for canonical engineering revision diffs."""

from __future__ import annotations

from typing import Any, Mapping

from . import engineering_revision_diff as _target
from .engineering_status import build_engineering_status


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _rows(value: Any) -> list[dict[str, Any]]:
    return [dict(row) for row in value if isinstance(row, Mapping)] if isinstance(value, list) else []


def install_revision_status_compatibility() -> None:
    if getattr(_target, "_canonical_status_rebuild_installed", False):
        return

    original_physical_map = _target._physical_authorization_map

    def _status(plan: Mapping[str, Any]):
        return build_engineering_status(plan)

    def _physical_authorization_map(plan: Mapping[str, Any]):
        result = dict(original_physical_map(plan))
        audited = _mapping(plan.get("audited_physical_evidence"))
        for row in _rows(audited.get("envelopes")):
            envelope_id = row.get("envelope_id")
            if envelope_id:
                result[f"evidence_envelope:{envelope_id}"] = {
                    "envelope_hash": row.get("envelope_hash"),
                    "evidence_id": _mapping(row.get("record")).get("evidence_id"),
                    "raw_files": row.get("raw_files") or [],
                    "created_at": row.get("created_at"),
                    "created_by": row.get("created_by"),
                }
        for row in _rows(audited.get("ledger_entries")):
            entry_id = row.get("entry_id")
            if entry_id:
                decision = _mapping(row.get("decision"))
                result[f"authorization_ledger:{entry_id}"] = {
                    "entry_hash": row.get("entry_hash"),
                    "previous_entry_hash": row.get("previous_entry_hash"),
                    "recorded_at": row.get("recorded_at"),
                    "recorded_by": row.get("recorded_by"),
                    "authorization_id": decision.get("authorization_id"),
                    "status": decision.get("status"),
                    "scope": decision.get("scope") or {},
                }
        ledger = _mapping(audited.get("ledger_assessment"))
        if ledger:
            result["authorization_ledger_assessment"] = ledger
        if audited:
            result["audited_physical_assessment"] = {
                "applicable": audited.get("applicable"),
                "blockers": audited.get("blockers") or [],
                "warnings": audited.get("warnings") or [],
                "metadata": audited.get("metadata") or {},
            }
        return result

    _target._status = _status
    _target._physical_authorization_map = _physical_authorization_map
    _target._canonical_status_rebuild_installed = True


install_revision_status_compatibility()
