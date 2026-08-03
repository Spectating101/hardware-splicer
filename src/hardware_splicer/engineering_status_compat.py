"""Compatibility correction for generic status-message deduplication."""

from __future__ import annotations

from typing import Any, Mapping

from . import engineering_status as _target


def install_status_message_compatibility() -> None:
    if getattr(_target, "_containment_deduplication_installed", False):
        return
    original = _target._generic_missing

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
        original(body, rows)

    _target._generic_missing = _generic_missing
    _target._containment_deduplication_installed = True


install_status_message_compatibility()
