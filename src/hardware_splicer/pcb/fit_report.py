"""Which modules on a board have a footprint that was never checked against the real part.

Pad geometry that passes ERC and DRC can still be unable to take the real module: the carrier
may have the wrong pitch, row spacing or pin order for it. Each module footprint therefore
records its ``fit`` (``verified_against`` a named source, or ``unverified_variant`` with a
reason). This report lists the unverified ones for a build, and fabrication is withheld while
any are present. It never touches ``build_ready``, which stays the ERC/DRC/connectivity gate.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

from .module_registry import resolve_module_fit

UNVERIFIED_FIT_BLOCKER_PREFIX = "Module footprint fit is unverified"


def module_fit_report(module_ids: Iterable[str]) -> Dict[str, Any]:
    """Fit record for each distinct module id (first-seen order) plus the unverified ones.

    Ids are used exactly as the geometry looks them up: never trimmed or case-folded, and an empty
    id keeps its (unverified) record. Normalising here would certify a real footprint for an id
    the geometry drew as a synthetic placeholder.
    """
    seen: List[str] = []
    for module_id in module_ids:
        text = "" if module_id is None else str(module_id)
        if text not in seen:
            seen.append(text)
    rows: List[Dict[str, Any]] = []
    for module_id in seen:
        fit = resolve_module_fit(module_id)
        row: Dict[str, Any] = {"module_id": module_id, "status": fit["status"]}
        if fit["status"] == "verified_against":
            row["verified_against"] = fit.get("verified_against")
        else:
            row["reason"] = fit.get("reason")
        rows.append(row)
    unverified = sorted(r["module_id"] for r in rows if r["status"] != "verified_against")
    return {
        "module_fit": rows,
        "unverified_fit_modules": unverified,
        "fabrication_blocker": fit_blocker(unverified, len(rows)),
    }


def fit_blocker(unverified: Iterable[str], module_count: int) -> str | None:
    names = sorted(set(unverified))
    if not names:
        return None
    return (
        f"{UNVERIFIED_FIT_BLOCKER_PREFIX} for {len(names)} of {module_count} module(s): "
        f"{', '.join(names)}. The carrier pads may not take the real part; fabrication is "
        "withheld until each footprint is checked against it."
    )
