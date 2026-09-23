from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

STATUS_ELIGIBLE = "ELIGIBLE_FOR_HUMAN_DECISION"
STATUS_INCOMPLETE = "INCOMPLETE"
STATUS_DISQUALIFIED = "DISQUALIFIED"

_REQUIRED_CAPABILITIES = (
    "preserve_DNP_and_open_states",
    "cold_measurements",
    "staged_current_limited_power",
    "raw_measurement_return",
    "bounded_spi_0x9f",
    "board_or_lot_traceability",
)

_REQUIRED_COMMERCIAL_FIELDS = (
    "quotation_reference",
    "quantity",
    "unit_or_batch_cost",
    "lead_time",
)

_AUTHORITY_FIELDS = (
    "fabrication_authorized",
    "power_on_authorized",
    "functional_test_authorized",
    "release_authorized",
)


def _value(mapping: Mapping[str, Any] | None, key: str) -> Any:
    return mapping.get(key) if isinstance(mapping, Mapping) else None


def evaluate_provider_review(
    record: Mapping[str, Any],
    campaign: Mapping[str, Any],
) -> dict[str, Any]:
    """Evaluate a provider reply without granting any physical authority.

    The evaluator is intentionally fail-closed. It can only classify whether a
    provider record is complete enough for a human fabrication decision. It
    cannot select a provider or mutate fabrication, power, functional-test, or
    release authority.
    """

    reasons: list[str] = []
    missing: list[str] = []
    disqualifiers: list[str] = []

    canonical = campaign.get("canonical_source", {})
    subject = record.get("subject", {})

    expected_identity = {
        "revision": canonical.get("revision"),
        "package": canonical.get("package"),
        "package_sha256": canonical.get("package_sha256"),
    }
    for key, expected in expected_identity.items():
        observed = _value(subject, key)
        if expected and observed != expected:
            disqualifiers.append(f"subject_{key}_mismatch")

    campaign_id = record.get("campaign_id")
    expected_campaign = campaign.get("campaign_id")
    if expected_campaign and campaign_id != expected_campaign:
        disqualifiers.append("campaign_id_mismatch")

    authority = record.get("authority_effect", {})
    for field in _AUTHORITY_FIELDS:
        if _value(authority, field) is not False:
            disqualifiers.append(f"authority_not_fail_closed:{field}")

    if record.get("contact_state") in (None, "PENDING_SEND"):
        missing.append("provider_contact_not_sent")
    if not record.get("received_at"):
        missing.append("provider_reply_not_received")

    capabilities = record.get("capabilities_confirmed", {})
    for field in _REQUIRED_CAPABILITIES:
        value = _value(capabilities, field)
        if value is False:
            disqualifiers.append(f"required_capability_rejected:{field}")
        elif value is not True:
            missing.append(f"required_capability_unconfirmed:{field}")

    commercial = record.get("commercial", {})
    for field in _REQUIRED_COMMERCIAL_FIELDS:
        value = _value(commercial, field)
        if value is None or value == "":
            missing.append(f"commercial_missing:{field}")

    findings = record.get("findings", [])
    if not isinstance(findings, list):
        disqualifiers.append("findings_not_list")
        findings = []

    for index, finding in enumerate(findings):
        if not isinstance(finding, Mapping):
            disqualifiers.append(f"finding_{index}_invalid")
            continue
        if finding.get("successor_revision_required") is True:
            missing.append(f"finding_{index}_requires_successor_revision_review")
        if any(
            finding.get(flag) is True
            for flag in (
                "design_change_requested",
                "manufacturing_change_requested",
                "assembly_change_requested",
                "test_change_requested",
            )
        ) and finding.get("successor_revision_required") is None:
            missing.append(f"finding_{index}_change_request_needs_revision_disposition")

    if disqualifiers:
        status = STATUS_DISQUALIFIED
        reasons.append("One or more fail-closed provider eligibility requirements were violated.")
    elif missing:
        status = STATUS_INCOMPLETE
        reasons.append("The provider record is not complete enough for a human fabrication decision.")
    else:
        status = STATUS_ELIGIBLE
        reasons.append(
            "The provider record satisfies the minimum evidence and commercial completeness bar for human review."
        )

    return {
        "schema": "hardware_splicer.provider_review_evaluation.v1",
        "campaign_id": campaign_id,
        "provider": deepcopy(record.get("provider", {})),
        "status": status,
        "reasons": reasons,
        "missing": sorted(set(missing)),
        "disqualifiers": sorted(set(disqualifiers)),
        "authority_effect": "NONE",
        "provider_selected": False,
        "fabrication_authorized": False,
        "power_on_authorized": False,
        "functional_test_authorized": False,
        "release_authorized": False,
    }
