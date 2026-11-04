"""Product policy over raw runtime capability discovery.

Runtime discovery answers what is present. Product policy answers what is required
for the supported Hardware Splicer workflow. Optional specialist engines must not
turn an otherwise healthy electrical/review installation red merely because they
are absent.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .capability_runtime import capability_report
from .github_signal_pipeline import registry_row

_OPTIONAL_SPECIALISTS = {
    "cadquery-isolated",
}


def product_capability_report(
    *,
    build_dir: str | Path | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Return capability truth with product-level required/optional policy applied."""

    payload = capability_report(build_dir=build_dir, **kwargs)
    for row in payload.get("capabilities") or []:
        if not isinstance(row, dict) or row.get("id") not in _OPTIONAL_SPECIALISTS:
            continue
        row["required"] = False
        if row.get("readiness") == "missing_required":
            row["readiness"] = "missing_optional"
            row["next_action"] = (
                "Install and configure this specialist only when the current project "
                "requires generated mechanical output."
            )

    # Externally acquired tools are optional until a real, hash-matching
    # sandbox execution artifact proves project use. Merely discovering a
    # repository must never upgrade HS capability status.
    signal = registry_row(build_dir)
    if signal is not None:
        payload["capabilities"].append(signal)
        payload["capabilities"].sort(key=lambda r: str(r.get("id")))

    required_missing = sorted(
        str(row.get("id"))
        for row in payload.get("capabilities") or []
        if isinstance(row, Mapping)
        and row.get("required")
        and row.get("readiness") == "missing_required"
    )
    counts: dict[str, int] = {}
    for row in payload.get("capabilities") or []:
        if not isinstance(row, Mapping):
            continue
        readiness = str(row.get("readiness") or "unknown")
        counts[readiness] = counts.get(readiness, 0) + 1
    payload["required_missing"] = required_missing
    payload["ok"] = not required_missing
    payload["counts"] = dict(sorted(counts.items()))
    payload["policy"] = {
        "schema_version": "hardware_splicer.capability_policy.v1",
        "optional_specialists": sorted(_OPTIONAL_SPECIALISTS),
        "statement": (
            "Optional specialist engines are required only by projects that select "
            "their workflow; their absence does not fail the base product installation."
        ),
    }
    return payload
