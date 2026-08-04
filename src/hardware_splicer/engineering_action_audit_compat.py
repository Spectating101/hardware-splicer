"""Compatibility extension for audited physical release action packets."""

from __future__ import annotations

from typing import Any, Mapping

from . import engineering_action as _target


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

    def _release_payload(plan: Mapping[str, Any]):
        payload, blockers = original(plan)
        payload = dict(payload)
        audited = _mapping(plan.get("audited_physical_evidence"))
        if audited:
            ledger = _mapping(audited.get("ledger_assessment"))
            payload.update(
                {
                    "audited_physical_evidence": audited,
                    "evidence_envelope_count": len(audited.get("envelopes") or []),
                    "authorization_ledger_entry_count": len(audited.get("ledger_entries") or []),
                    "authorization_ledger_valid": bool(ledger.get("valid")),
                    "audited_authorization_applicable": bool(audited.get("applicable")),
                }
            )
            blockers.extend(_messages(audited.get("blockers")))
            blockers.extend(_messages(ledger.get("blockers")))
            if not audited.get("applicable"):
                blockers.append(
                    "Tamper-evident physical authorization is not applicable to the current candidate."
                )
        payload.update(
            {
                "physical_envelope_build_route": "/v1/engineering/physical-evidence/envelopes/build",
                "authorization_ledger_build_route": "/v1/engineering/physical-evidence/ledger/build-entry",
                "audited_physical_assess_route": "/v1/engineering/physical-evidence/audited-assess",
                "audited_release_assess_route": "/v1/engineering/physical-evidence/audited-release-assess",
                "audited_apply_save_route": "/v1/engineering/physical-evidence/audited-apply-save",
                "tamper_evident_envelopes_required": True,
                "valid_authorization_chain_required": True,
                "automatic_authorization": False,
            }
        )
        return payload, list(dict.fromkeys(blockers))

    _target._release_payload = _release_payload
    _target._audited_release_action_installed = True


install_audited_release_action_compatibility()
