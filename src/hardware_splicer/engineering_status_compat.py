"""Compatibility corrections for unified engineering status.

Besides message deduplication and the clean-candidate release action, this layer makes
persisted physical-evidence state part of every fresh status rebuild. Cached status is
not trusted: audited envelopes, HMAC attestations, ledger validity, scoped decisions,
and release scope are re-read from the plan and converted into canonical blockers.
"""

from __future__ import annotations

from typing import Any, Mapping

from . import engineering_status as _target
from .physical_evidence_attestation import verify_evidence_file_attestation
from .physical_evidence_ledger import PhysicalEvidenceEnvelope


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _messages(values: Any) -> list[str]:
    rows: list[str] = []
    if isinstance(values, list):
        for value in values:
            if isinstance(value, Mapping):
                text = value.get("message") or value.get("reason") or value.get("code")
            else:
                text = value
            if text not in (None, ""):
                rows.append(str(text))
    return rows


def _attestation_state(audited: Mapping[str, Any]) -> dict[str, Any]:
    metadata = _mapping(audited.get("metadata"))
    required = bool(metadata.get("server_attestation_required"))
    if not required:
        return {
            "required": False,
            "valid": None,
            "raw_file_count": 0,
            "attested_raw_file_count": 0,
            "blockers": [],
        }

    blockers: list[str] = []
    raw_file_count = 0
    attested_raw_file_count = 0
    for raw_envelope in audited.get("envelopes") or []:
        try:
            envelope = PhysicalEvidenceEnvelope.model_validate(raw_envelope)
        except ValueError as exc:
            blockers.append(f"Persisted physical evidence envelope is invalid: {exc}")
            continue
        for file_ref in envelope.raw_files:
            raw_file_count += 1
            file_blockers = verify_evidence_file_attestation(file_ref)
            if file_blockers:
                blockers.extend(
                    f"Envelope {envelope.envelope_id}: {value}"
                    for value in file_blockers
                )
            else:
                attested_raw_file_count += 1
    if raw_file_count == 0:
        blockers.append(
            "Server-attested physical authorization requires at least one retained raw file."
        )
    blockers = list(dict.fromkeys(blockers))
    return {
        "required": True,
        "valid": not blockers,
        "raw_file_count": raw_file_count,
        "attested_raw_file_count": attested_raw_file_count,
        "blockers": blockers,
    }


def _physical_scope(plan: Mapping[str, Any]) -> dict[str, Any] | None:
    audited = _mapping(plan.get("audited_physical_evidence"))
    package = _mapping(plan.get("physical_evidence_package"))
    scoped = _mapping(plan.get("scoped_release_assessment"))
    if not audited and not package and not scoped:
        return None

    assessment = _mapping(
        _mapping(audited.get("physical_package")).get("assessment")
        if audited
        else package.get("assessment")
    )
    ledger = _mapping(audited.get("ledger_assessment"))
    attestation = _attestation_state(audited)
    audited_present = bool(audited)
    applicable = bool(audited.get("applicable")) if audited_present else bool(assessment.get("applicable"))
    ledger_valid = bool(ledger.get("valid")) if audited_present else False
    allowed = bool(scoped.get("allowed"))
    authorized_operations = list(
        scoped.get("allowed_operations")
        or scoped.get("authorized_operations")
        or assessment.get("authorized_operations")
        or []
    )

    blockers = [
        *_messages(audited.get("blockers")),
        *_messages(ledger.get("blockers")),
        *_messages(assessment.get("blockers")),
        *_messages(scoped.get("blockers")),
        *attestation["blockers"],
    ]
    if audited_present and not ledger_valid:
        blockers.append("The authorization ledger is invalid or incomplete.")
    if audited_present and not audited.get("envelopes"):
        blockers.append("Tamper-evident physical evidence envelopes are missing.")
    if attestation["required"] and not attestation["valid"]:
        blockers.append("Required server attestations for raw evidence are invalid or unavailable.")
    if not applicable:
        blockers.append("No physical authorization applies to the current candidate revision and artifact hashes.")
    if not scoped:
        blockers.append("No scoped release assessment has been completed for a requested physical operation.")
    elif not allowed:
        blockers.append("The requested physical operation scope is not allowed.")
    if allowed and not authorized_operations:
        blockers.append("The scoped release assessment names no authorized operations.")

    blockers = list(dict.fromkeys(value for value in blockers if value))
    valid = (
        applicable
        and allowed
        and bool(authorized_operations)
        and (not attestation["required"] or attestation["valid"])
        and not blockers
    )
    return {
        "valid": valid,
        "applicable": applicable,
        "allowed": allowed,
        "authorized_operations": authorized_operations if valid else [],
        "blockers": blockers,
        "audited": audited_present,
        "ledger_valid": ledger_valid,
        "envelope_count": len(audited.get("envelopes") or []),
        "ledger_entry_count": len(audited.get("ledger_entries") or []),
        "server_attestation_required": attestation["required"],
        "server_attestation_valid": attestation["valid"],
        "raw_file_count": attestation["raw_file_count"],
        "attested_raw_file_count": attestation["attested_raw_file_count"],
    }


def _release_action(report):
    spec = _target._ACTIONS["release"]
    return _target.NextAction(
        action_id="next-release",
        priority=_target._CATEGORY_PRIORITY["release"],
        category="release",
        title=spec["title"],
        instruction=spec["instruction"],
        route=spec["route"],
        blocker_ids=[],
        target_ids=[report.project_id],
        required_inputs=[],
        evidence_to_capture=list(spec["evidence"]),
        payload_hint=dict(spec["payload_hint"]),
        physical_action=False,
        automatic_execution=False,
    )


def install_status_message_compatibility() -> None:
    if getattr(_target, "_containment_deduplication_installed", False):
        return
    original_missing = _target._generic_missing
    original_build = _target.build_engineering_status

    def _generic_missing(plan: Mapping[str, Any], rows: list[Any]) -> None:
        existing = [str(row.message).strip().lower() for row in rows if str(row.message).strip()]
        filtered: list[Any] = []
        for value in plan.get("missing_info") or []:
            text = str(value).strip()
            lowered = text.lower()
            if not text:
                continue
            if any(message in lowered or lowered in message for message in existing):
                continue
            filtered.append(value)
        if not filtered:
            return
        body = dict(plan)
        body["missing_info"] = filtered
        original_missing(body, rows)

    def build_engineering_status(plan: Mapping[str, Any]):
        report = original_build(plan)
        physical = _physical_scope(plan)
        if physical is not None:
            summary = dict(report.summary)
            metadata = dict(report.metadata)
            summary.update(
                {
                    "physical_scope_authorized": physical["valid"],
                    "authorized_operation_count": len(physical["authorized_operations"]),
                    "physical_evidence_audited": physical["audited"],
                    "authorization_ledger_valid": physical["ledger_valid"],
                    "physical_evidence_envelope_count": physical["envelope_count"],
                    "authorization_ledger_entry_count": physical["ledger_entry_count"],
                    "server_attestation_required": physical["server_attestation_required"],
                    "server_attestation_valid": physical["server_attestation_valid"],
                    "raw_evidence_file_count": physical["raw_file_count"],
                    "attested_raw_file_count": physical["attested_raw_file_count"],
                }
            )
            metadata.update(
                {
                    "physical_scope_authorized": physical["valid"],
                    "authorized_operations": physical["authorized_operations"],
                    "physical_evidence_audited": physical["audited"],
                    "authorization_ledger_valid": physical["ledger_valid"],
                    "server_attestation_required": physical["server_attestation_required"],
                    "server_attestation_valid": physical["server_attestation_valid"],
                    "global_authority_flags_unchanged": True,
                    "automatic_authorization": False,
                }
            )
            if not physical["valid"]:
                blocker = _target.StatusBlocker(
                    blocker_id="physical-authorization-scope",
                    category="release",
                    severity=_target.StatusSeverity.ERROR,
                    message=(
                        "Physical operation scope is not authorized: "
                        + " ".join(physical["blockers"])
                    ),
                    target_ids=[report.project_id],
                    required_inputs=[
                        "current candidate revision",
                        "artifact hashes",
                        "operating envelope",
                        "calibrated physical evidence",
                        "tamper-evident evidence envelopes",
                        "valid authorization ledger",
                        "server attestation verification keys when required",
                        "scoped human decision",
                    ],
                    required_evidence=[
                        "calibration certificates",
                        "server-attested raw physical evidence hashes",
                        "fixture and interlock state",
                        "authorization ledger chain",
                    ],
                    metadata={
                        "audited": physical["audited"],
                        "ledger_valid": physical["ledger_valid"],
                        "server_attestation_required": physical["server_attestation_required"],
                        "server_attestation_valid": physical["server_attestation_valid"],
                        "automatic_authorization": False,
                    },
                )
                blockers = {row.blocker_id: row for row in report.blockers}
                blockers[blocker.blocker_id] = blocker
                blocker_rows = sorted(
                    blockers.values(),
                    key=lambda row: (
                        _target._CATEGORY_PRIORITY.get(row.category, 90),
                        row.blocker_id,
                    ),
                )
                groups = {
                    key: list(values)
                    for key, values in report.blocker_groups.items()
                }
                release_ids = list(groups.get("release") or [])
                if blocker.blocker_id not in release_ids:
                    release_ids.append(blocker.blocker_id)
                groups["release"] = release_ids
                actions = _target._actions(blocker_rows, report.advisories)
                categories = [row.category for row in blocker_rows]
                current_phase = min(
                    categories,
                    key=lambda value: _target._CATEGORY_PRIORITY.get(value, 90),
                )
                summary.update(
                    {
                        "blocking_count": len(blocker_rows),
                        "category_count": len(groups),
                        "next_action_count": len(actions),
                        "release_issue_count": len(groups.get("release", [])),
                    }
                )
                return report.model_copy(
                    update={
                        "overall_status": "blocked",
                        "current_phase": current_phase,
                        "blockers": blocker_rows,
                        "blocker_groups": groups,
                        "next_actions": actions,
                        "next_action_id": actions[0].action_id if actions else None,
                        "summary": summary,
                        "metadata": metadata,
                    },
                    deep=True,
                )
            report = report.model_copy(
                update={"summary": summary, "metadata": metadata},
                deep=True,
            )

        if report.next_actions:
            return report
        action = _release_action(report)
        summary = dict(report.summary)
        summary["next_action_count"] = 1
        return report.model_copy(
            update={
                "current_phase": "release",
                "next_actions": [action],
                "next_action_id": action.action_id,
                "summary": summary,
            },
            deep=True,
        )

    _target._generic_missing = _generic_missing
    _target.build_engineering_status = build_engineering_status
    _target._containment_deduplication_installed = True


install_status_message_compatibility()
