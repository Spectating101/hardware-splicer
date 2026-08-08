"""Controlled perturbation builders for cleanroom replay.

These helpers mutate only declared test inputs. They never encode an expected engineering
answer. Equivalent perturbations preserve evidence identity; challenge perturbations are
kept out of equivalence groups so the evaluator cannot mistake a changed evidence set for
model instability.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from typing import Any, Dict, Mapping, Sequence

from .cleanroom_replay import ReplayCase


SOURCE_COLLECTION_KEYS = (
    "engineeringSources",
    "engineeringParsedSources",
    "engineeringSourceParserRuns",
)

PART_COLLECTION_KEYS = (
    "available_parts",
    "parts",
    "resources",
)


def _clone(snapshot: Mapping[str, Any]) -> Dict[str, Any]:
    return deepcopy(dict(snapshot))


def _source_identity(snapshot: Mapping[str, Any]) -> list[tuple[str, str, str, str]]:
    rows: list[tuple[str, str, str, str]] = []
    for key in SOURCE_COLLECTION_KEYS:
        value = snapshot.get(key)
        if not isinstance(value, list):
            continue
        for row in value:
            if not isinstance(row, Mapping):
                continue
            source_id = str(row.get("source_id") or "").strip()
            if not source_id:
                continue
            rows.append(
                (
                    key,
                    source_id,
                    str(row.get("content_hash") or row.get("sha256") or ""),
                    str(row.get("revision") or ""),
                )
            )
    return sorted(rows)


def _assert_equivalent_evidence(before: Mapping[str, Any], after: Mapping[str, Any]) -> None:
    if _source_identity(before) != _source_identity(after):
        raise ValueError("equivalent perturbation changed evidence identity")


def reverse_source_order(snapshot: Mapping[str, Any]) -> Dict[str, Any]:
    body = _clone(snapshot)
    for key in SOURCE_COLLECTION_KEYS:
        value = body.get(key)
        if isinstance(value, list):
            body[key] = list(reversed(value))
    _assert_equivalent_evidence(snapshot, body)
    return body


def rotate_source_order(snapshot: Mapping[str, Any], *, offset: int = 1) -> Dict[str, Any]:
    body = _clone(snapshot)
    for key in SOURCE_COLLECTION_KEYS:
        value = body.get(key)
        if not isinstance(value, list) or len(value) < 2:
            continue
        shift = offset % len(value)
        body[key] = value[shift:] + value[:shift]
    _assert_equivalent_evidence(snapshot, body)
    return body


def neutralize_display_labels(
    snapshot: Mapping[str, Any],
    *,
    project_label: str = "Neutral Project",
) -> Dict[str, Any]:
    """Rename display-only labels while preserving evidence IDs/content and mission."""
    body = _clone(snapshot)
    for key in ("name", "project_name"):
        if key in body and isinstance(body.get(key), str):
            body[key] = project_label
    counter = 0
    for collection_key in SOURCE_COLLECTION_KEYS:
        collection = body.get(collection_key)
        if not isinstance(collection, list):
            continue
        for row in collection:
            if not isinstance(row, dict):
                continue
            metadata = row.get("metadata")
            if not isinstance(metadata, dict):
                continue
            for label_key in ("label", "display_name"):
                if label_key in metadata and isinstance(metadata.get(label_key), str):
                    counter += 1
                    metadata[label_key] = f"source-{counter}"
    _assert_equivalent_evidence(snapshot, body)
    return body


def neutralize_part_labels(snapshot: Mapping[str, Any]) -> Dict[str, Any]:
    """Replace human-facing component names but preserve structured type/role/IDs.

    This is useful for detecting familiar-name coupling. The outer evaluator is making
    the equivalence claim, so callers should use it only when the structured attributes
    really do describe an equivalent component.
    """
    body = _clone(snapshot)
    index = 0
    for collection_key in PART_COLLECTION_KEYS:
        collection = body.get(collection_key)
        if not isinstance(collection, list):
            continue
        for row in collection:
            if not isinstance(row, dict) or not isinstance(row.get("name"), str):
                continue
            index += 1
            row["name"] = f"equivalent-component-{index}"
    _assert_equivalent_evidence(snapshot, body)
    return body


def mission_paraphrase(snapshot: Mapping[str, Any], paraphrase: str) -> Dict[str, Any]:
    """Replace only the persisted mission with a caller-supplied semantic paraphrase."""
    if not str(paraphrase or "").strip():
        raise ValueError("mission paraphrase must be non-empty")
    body = _clone(snapshot)
    target_key = next(
        (key for key in ("mission", "goal", "intent", "brief") if isinstance(body.get(key), str)),
        None,
    )
    if target_key is None:
        raise ValueError("snapshot has no string mission/goal/intent/brief to paraphrase")
    body[target_key] = str(paraphrase).strip()
    _assert_equivalent_evidence(snapshot, body)
    return body


def build_standard_equivalence_suite(
    base_case: ReplayCase,
    *,
    mission_paraphrase_text: str | None = None,
    include_part_label_neutralization: bool = False,
) -> list[ReplayCase]:
    """Build a reusable no-golden-answer perturbation suite around one baseline case."""
    group_id = base_case.equivalence_group or f"{base_case.case_id}:equivalent"
    baseline = replace(
        base_case,
        equivalence_group=group_id,
        perturbation_kind="baseline",
        metadata={**dict(base_case.metadata or {}), "equivalence_asserted_by": "outer_engineer"},
    )
    variants: list[ReplayCase] = [baseline]

    def add(suffix: str, kind: str, snapshot: Mapping[str, Any]) -> None:
        variants.append(
            ReplayCase(
                case_id=f"{base_case.case_id}:{suffix}",
                project_id=base_case.project_id,
                project_revision=base_case.project_revision,
                snapshot=snapshot,
                equivalence_group=group_id,
                perturbation_kind=kind,
                metadata={
                    **dict(base_case.metadata or {}),
                    "baseline_case_id": base_case.case_id,
                    "equivalence_asserted_by": "outer_engineer",
                },
            )
        )

    add("source-reverse", "source_order_reverse", reverse_source_order(base_case.snapshot))
    add("source-rotate", "source_order_rotate", rotate_source_order(base_case.snapshot))
    add("labels-neutral", "neutralized_labels", neutralize_display_labels(base_case.snapshot))
    if include_part_label_neutralization:
        add(
            "parts-neutral",
            "unfamiliar_equivalent_component",
            neutralize_part_labels(base_case.snapshot),
        )
    if mission_paraphrase_text is not None:
        add(
            "mission-paraphrase",
            "mission_paraphrase",
            mission_paraphrase(base_case.snapshot, mission_paraphrase_text),
        )
    return variants


def build_partial_evidence_case(
    base_case: ReplayCase,
    *,
    remove_source_ids: Sequence[str],
) -> ReplayCase:
    """Create a non-equivalent challenge case with selected evidence removed."""
    removed = {str(value).strip() for value in remove_source_ids if str(value).strip()}
    if not removed:
        raise ValueError("at least one source ID must be removed")
    body = _clone(base_case.snapshot)
    found: set[str] = set()
    for key in SOURCE_COLLECTION_KEYS:
        value = body.get(key)
        if not isinstance(value, list):
            continue
        kept = []
        for row in value:
            if isinstance(row, Mapping) and str(row.get("source_id") or "").strip() in removed:
                found.add(str(row.get("source_id") or "").strip())
                continue
            kept.append(row)
        body[key] = kept
    missing = sorted(removed - found)
    if missing:
        raise ValueError("requested source IDs were not present: " + ", ".join(missing))
    return ReplayCase(
        case_id=f"{base_case.case_id}:partial-evidence",
        project_id=base_case.project_id,
        project_revision=base_case.project_revision,
        snapshot=body,
        equivalence_group=None,
        perturbation_kind="partial_evidence",
        metadata={
            **dict(base_case.metadata or {}),
            "baseline_case_id": base_case.case_id,
            "removed_source_ids": sorted(removed),
            "expected_equivalent": False,
        },
    )


def build_conflicting_evidence_case(
    base_case: ReplayCase,
    *,
    conflict: Mapping[str, Any],
) -> ReplayCase:
    """Create a non-equivalent challenge with an explicit persisted source conflict."""
    if not conflict:
        raise ValueError("conflict declaration is required")
    body = _clone(base_case.snapshot)
    conflicts = body.get("declared_conflicts")
    if not isinstance(conflicts, list):
        conflicts = []
    conflicts = list(conflicts)
    conflicts.append(deepcopy(dict(conflict)))
    body["declared_conflicts"] = conflicts
    return ReplayCase(
        case_id=f"{base_case.case_id}:conflicting-evidence",
        project_id=base_case.project_id,
        project_revision=base_case.project_revision,
        snapshot=body,
        equivalence_group=None,
        perturbation_kind="conflicting_evidence",
        metadata={
            **dict(base_case.metadata or {}),
            "baseline_case_id": base_case.case_id,
            "expected_equivalent": False,
        },
    )
