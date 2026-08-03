"""Compatibility corrections for unified engineering status."""

from __future__ import annotations

from typing import Any, Mapping

from . import engineering_status as _target


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
        if report.next_actions:
            return report
        spec = _target._ACTIONS["release"]
        action = _target.NextAction(
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
