"""Rossmann-style standard safety gates injected into splice bench sessions."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Sequence

_MOTOR_TOKENS = (
    "motor",
    "vmotor",
    "h-bridge",
    "hbridge",
    "driver",
    "actuator",
    "gear",
    "spindle",
    "vcm",
)


def _gate_row(
    *,
    gate_id: str,
    prompt: str,
    gate_type: str,
    critical: bool,
    source: str = "standard_safety_profile",
) -> Dict[str, Any]:
    return {
        "gate_id": gate_id,
        "source": source,
        "prompt": prompt,
        "stage": "before_power_on",
        "critical": critical,
        "block_id": "",
        "board_id": "",
        "gate_type": gate_type,
        "status": "open",
        "measurement": None,
        "closed_at": None,
        "notes": [],
    }


def _motor_context(gates: Sequence[Mapping[str, Any]], intake: Mapping[str, Any]) -> bool:
    if bool(intake.get("salvage_mode")):
        return True
    text = " ".join(
        [
            str(intake.get("goal") or ""),
            *(str(row.get("prompt") or "") for row in gates),
            *(str(row.get("gate_type") or "") for row in gates),
        ]
    ).lower()
    return any(token in text for token in _MOTOR_TOKENS)


def inject_standard_safety_gates(
    gates: Sequence[Mapping[str, Any]],
    intake: Mapping[str, Any],
) -> List[Dict[str, Any]]:
    """Append PSU ramp + optional thermal scan gates when motor/splice context is detected."""
    if not _motor_context(gates, intake):
        return [dict(row) for row in gates]

    kept = [dict(row) for row in gates]
    seen = {str(row.get("gate_id") or "") for row in kept}

    if "psu_current_limit_ramp" not in seen:
        kept.append(
            _gate_row(
                gate_id="psu_current_limit_ramp",
                gate_type="psu_ramp",
                critical=True,
                prompt=(
                    "Ramp VMOTOR / donor supply rail with current-limited bench PSU (≤0.5 A); "
                    "confirm idle current normal and no hotspot before raising limit"
                ),
            )
        )

    if "thermal_baseline_scan" not in seen:
        kept.append(
            _gate_row(
                gate_id="thermal_baseline_scan",
                gate_type="thermal",
                critical=False,
                prompt=(
                    "Thermal baseline scan at idle after current-limited ramp "
                    "(FLIR preferred); attach thermal image URI in capture artifacts if available"
                ),
            )
        )

    return kept
