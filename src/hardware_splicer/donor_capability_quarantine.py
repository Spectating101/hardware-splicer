"""Static quarantine policy for donor capabilities outside the current safety envelope.

A quarantine match is policy, not physical evidence. It prevents architecture use
of high-risk capability roles even if a donor contract otherwise appears complete,
until a separately reviewed safety policy exists for that family.
"""
from __future__ import annotations

import re
from typing import Any

from .fabrication_operator import FabricationValidationError

_ROLE_TOKEN = re.compile(r"[^a-z0-9]+")

_POLICIES: tuple[dict[str, Any], ...] = (
    {
        "quarantine_id": "salvage.quarantine.battery_pack",
        "role_aliases": (
            "battery",
            "battery pack",
            "lithium battery",
            "lithium ion battery",
            "li ion battery",
            "liion battery",
            "lipo battery",
            "lipo pack",
            "rechargeable battery pack",
        ),
        "reason": "Battery reuse needs chemistry, protection, state-of-health, charge/discharge and thermal safety policy that C5 does not yet provide.",
        "inspection_allowed": True,
        "energized_testing_allowed": False,
        "architecture_use_allowed": False,
        "release_condition": "separately reviewed battery salvage safety policy plus evidence contract",
    },
    {
        "quarantine_id": "salvage.quarantine.mains_or_high_energy_power",
        "role_aliases": (
            "mains",
            "mains circuit",
            "mains power",
            "mains supply",
            "ac mains",
            "line voltage",
            "high voltage power",
            "high voltage supply",
            "inverter",
            "pfc stage",
            "power factor correction",
            "high energy power module",
        ),
        "reason": "Mains/high-energy reuse is outside the present low-voltage salvage authority and requires a dedicated isolation, discharge, creepage/clearance and energized-test policy.",
        "inspection_allowed": True,
        "energized_testing_allowed": False,
        "architecture_use_allowed": False,
        "release_condition": "separately reviewed mains/high-energy salvage safety policy plus evidence contract",
    },
)


def quarantine_policy_for_role(role: str) -> dict[str, Any] | None:
    normalized = _normalize_role(role)
    for policy in _POLICIES:
        if normalized in policy["role_aliases"]:
            return {
                "quarantine_id": policy["quarantine_id"],
                "reason": policy["reason"],
                "inspection_allowed": policy["inspection_allowed"],
                "energized_testing_allowed": policy["energized_testing_allowed"],
                "architecture_use_allowed": policy["architecture_use_allowed"],
                "release_condition": policy["release_condition"],
                "truth_contract": {
                    "quarantine_policy_is_physical_evidence": False,
                    "contract_verification_overrides_quarantine": False,
                    "agent_can_release_quarantine": False,
                },
            }
    return None


def _normalize_role(value: Any) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 200:
        raise FabricationValidationError("donor quarantine role must be bounded text")
    return " ".join(part for part in _ROLE_TOKEN.sub(" ", value.strip().lower()).split() if part)
