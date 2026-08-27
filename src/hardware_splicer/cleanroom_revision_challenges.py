"""Revision/provenance challenges for live cleanroom replay.

Stale evidence is not hidden and is not automatically treated as a contract failure. The
product-visible source inventory may contain historical material, but its revision state
and authority ceiling must remain explicit so an embedded operator cannot silently promote
an older source over the current declared evidence.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Mapping

from .cleanroom_replay import ReplayCase


SCHEMA_VERSION = "hardware_splicer.cleanroom_revision_challenges.v1"


def build_stale_revision_case(
    base_case: ReplayCase,
    *,
    current_source_id: str,
    stale_source_id: str,
    stale_revision: str,
    stale_metadata: Mapping[str, Any],
) -> ReplayCase:
    """Add a distinct superseded source as a non-equivalent provenance challenge.

    The current source remains untouched. The stale source receives a different evidence
    identity, advisory authority, and explicit supersession metadata. This tests revision
    reasoning without asking the evaluator to hide history or prescribe an architecture.
    """

    current_source_id = str(current_source_id or "").strip()
    stale_source_id = str(stale_source_id or "").strip()
    stale_revision = str(stale_revision or "").strip()
    if not current_source_id or not stale_source_id or not stale_revision:
        raise ValueError("current_source_id, stale_source_id and stale_revision are required")
    if current_source_id == stale_source_id:
        raise ValueError("stale source must have a distinct product-visible evidence identity")

    body: Dict[str, Any] = deepcopy(dict(base_case.snapshot))
    sources = list(body.get("engineeringSources") or [])
    current = next(
        (
            row
            for row in sources
            if isinstance(row, Mapping)
            and str(row.get("source_id") or "").strip() == current_source_id
        ),
        None,
    )
    if current is None:
        raise ValueError(f"current source is not registered in baseline evidence: {current_source_id}")
    if any(
        isinstance(row, Mapping)
        and str(row.get("source_id") or "").strip() == stale_source_id
        for row in sources
    ):
        raise ValueError(f"stale source ID already exists: {stale_source_id}")

    sources.append(
        {
            "source_id": stale_source_id,
            "source_type": str(current.get("source_type") or "engineering_source_json"),
            "content_hash": f"sha256:{stale_source_id}:{stale_revision}",
            "revision": stale_revision,
            "authority_ceiling": "advisory",
            "metadata": {
                **deepcopy(dict(stale_metadata)),
                "lifecycle_status": "superseded",
                "superseded_by_source_id": current_source_id,
                "current_source_revision": str(current.get("revision") or ""),
                "current_source_content_hash": str(current.get("content_hash") or ""),
            },
        }
    )
    body["engineeringSources"] = sources

    conflicts = list(body.get("engineeringSourceConflicts") or [])
    conflicts.append(
        {
            "conflict_id": f"revision-precedence:{stale_source_id}",
            "source_ids": [current_source_id, stale_source_id],
            "field": "source_revision_precedence",
            "status": "resolved_by_revision_precedence",
            "resolution_source_id": current_source_id,
            "authority_note": "The historical source is superseded/advisory and cannot override current declared evidence.",
        }
    )
    body["engineeringSourceConflicts"] = conflicts

    advisories = list(body.get("engineeringAdvisories") or [])
    advisories.append(
        f"Historical source {stale_source_id} is retained for traceability but is superseded by {current_source_id}."
    )
    body["engineeringAdvisories"] = advisories

    return ReplayCase(
        case_id=f"{base_case.case_id}:stale-revision",
        project_id=base_case.project_id,
        project_revision=base_case.project_revision + 60,
        snapshot=body,
        equivalence_group=None,
        perturbation_kind="stale_revision_evidence",
        metadata={
            **dict(base_case.metadata or {}),
            "baseline_case_id": base_case.case_id,
            "current_source_id": current_source_id,
            "stale_source_id": stale_source_id,
            "expected_equivalent": False,
        },
    )
