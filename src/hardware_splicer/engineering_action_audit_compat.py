"""Compatibility extension for audited physical release action packets."""

from __future__ import annotations

from typing import Any, Mapping

from . import engineering_action as _target
from . import engineering_status as _status


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _messages(values: Any) -> list[str]:
    result: list[str] = []
    if isinstance(values, list):
        for value in values:
            if isinstance(value, Mapping):
                text = value.get("message") or value.get("reason") or value.get("code")
            else:
                text = value
            if text not in (None, ""):
                result.append(str(text))
    return result


def install_audited_release_action_compatibility() -> None:
    if getattr(_target, "_audited_release_action_installed", False):
        return
    original = _target._release_payload

    # engineering_action imported build_engineering_status before the status compatibility
    # stack installed candidate-bound physical revalidation. Rebind that module-level name
    # to the final wrapped status builder so every prepared action consumes the same fresh
    # authority view as the status endpoint. This removes import-order-dependent authority.
    _target.build_engineering_status = _status.build_engineering_status

    def _release_payload(plan: Mapping[str, Any]):
        payload, blockers = original(plan)
        payload = dict(payload)
        audited = _mapping(plan.get("audited_physical_evidence"))
        if audited:
            # Cached audited evidence is historical input, not current candidate authority.
            # Re-evaluate applicability against the current candidate before projecting a
            # release action so a stale ``applicable=True`` flag cannot survive a revision
            # change. Keep the input plan immutable and expose the revalidated copy only.
            fresh_status = _status.build_engineering_status(plan)
            fresh_applicable = bool(fresh_status.metadata.get("physical_scope_authorized"))
            audited = dict(audited)
            audited["applicable"] = fresh_applicable

            ledger = _mapping(audited.get("ledger_assessment"))
            audit_metadata = _mapping(audited.get("metadata"))
            payload.update(
                {
                    "audited_physical_evidence": audited,
                    "evidence_envelope_count": len(audited.get("envelopes") or []),
                    "authorization_ledger_entry_count": len(audited.get("ledger_entries") or []),
                    "authorization_ledger_valid": bool(ledger.get("valid")),
                    "audited_authorization_applicable": fresh_applicable,
                    "server_attestation_required": bool(
                        audit_metadata.get("server_attestation_required")
                    ),
                    "server_attestation_valid": audit_metadata.get(
                        "server_attestation_valid"
                    ),
                }
            )
            blockers.extend(_messages(audited.get("blockers")))
            blockers.extend(_messages(ledger.get("blockers")))
            if not fresh_applicable:
                blockers.append(
                    "Tamper-evident physical authorization is not applicable to the current candidate."
                )
        payload.update(
            {
                "raw_evidence_hash_schema_route": "/v1/engineering/physical-evidence/raw-files/schema",
                "raw_evidence_hash_route": "/v1/engineering/physical-evidence/raw-files/hash",
                "attested_raw_evidence_hash_route": "/v1/engineering/physical-evidence/raw-files/hash-attested",
                "physical_envelope_build_route": "/v1/engineering/physical-evidence/envelopes/build",
                "attested_envelope_build_route": "/v1/engineering/physical-evidence/envelopes/build-attested",
                "authorization_ledger_build_route": "/v1/engineering/physical-evidence/ledger/build-entry",
                "audited_physical_assess_route": "/v1/engineering/physical-evidence/audited-assess",
                "audited_release_assess_route": "/v1/engineering/physical-evidence/audited-release-assess",
                "audited_apply_save_route": "/v1/engineering/physical-evidence/audited-apply-save",
                "attested_physical_schema_route": "/v1/engineering/physical-evidence/attested/schema",
                "attested_audited_assess_route": "/v1/engineering/physical-evidence/attested-audited-assess",
                "attested_audited_release_assess_route": "/v1/engineering/physical-evidence/attested-audited-release-assess",
                "attested_audited_apply_save_route": "/v1/engineering/physical-evidence/attested-audited-apply-save",
                "server_computed_raw_hash_recommended": True,
                "strict_server_attestation_available": True,
                "plain_hash_alone_proves_origin": False,
                "tamper_evident_envelopes_required": True,
                "valid_authorization_chain_required": True,
                "automatic_authorization": False,
            }
        )
        return payload, list(dict.fromkeys(blockers))

    _target._release_payload = _release_payload
    _target._audited_release_action_installed = True


install_audited_release_action_compatibility()
