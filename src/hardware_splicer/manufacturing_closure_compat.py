"""Compatibility correction for duplicate manufacturing input projections.

Guided planning supplies both the raw intake and its normalized copy. The canonical
closure collector therefore needs content-based deduplication before quantities,
connector checks, or artifact revision boundaries are evaluated.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

from . import manufacturing_closure as _target


def _deduplicate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        key = json.dumps(row, sort_keys=True, default=str, separators=(",", ":"))
        if key in seen:
            continue
        seen.add(key)
        result.append(row)
    return result


def install_manufacturing_collection_compatibility() -> None:
    if getattr(_target, "_deduplicated_collection_installed", False):
        return
    original = _target._collect

    def _collect(plan: Mapping[str, Any], intake: Mapping[str, Any]):
        collected = original(plan, intake)
        return {key: _deduplicate(list(rows)) for key, rows in collected.items()}

    _target._collect = _collect
    _target._deduplicated_collection_installed = True


install_manufacturing_collection_compatibility()
