"""Read-only engineering assurance projections over canonical project state.

The assurance layer does not own evidence and cannot promote authority. It projects the
existing source graph, project plan, blockers, review state, and revision identities into
an inspectable claim-to-output graph. Evidence-delta analysis delegates invalidation to
the existing conservative evidence-impact engine.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Iterable, Mapping, Sequence

from .engineering_source_graph import (
    EngineeringSourceGraph,
    build_engineering_source_graph,
)
from .evidence_impact import evaluate_evidence_impact


ASSURANCE_SCHEMA = "hardware_splicer.engineering_assurance.v1"
ASSURANCE_REVIEW_PACKET_SCHEMA = "hardware_splicer.engineering_claim_review_packet.v1"
ASSURANCE_DELTA_SCHEMA = "hardware_splicer.engineering_assurance_delta.v1"


def _rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [deepcopy(dict(row)) for row in value if isinstance(row, Mapping)]


def _stable_id(prefix: str, value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return f"{prefix}-{hashlib.sha256(encoded.encode('utf-8')).hexdigest()[:12]}"


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _source_rows(snapshot: Mapping[str, Any]) -> list[dict[str, Any]]:
    return _rows(snapshot.get("engineeringSources"))


def _claims_for_source(source: Mapping[str, Any]) -> list[dict[str, Any]]:
    direct = _rows(source.get("claims"))
    metadata = source.get("metadata")
    nested = _rows(metadata.get("claims")) if isinstance(metadata, Mapping) else []
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, claim in enumerate([*direct, *nested]):
        claim_id = str(claim.get("claim_id") or "").strip()
        identity = claim_id or _canonical([index, claim])
        if identity not in seen:
            seen.add(identity)
            result.append(claim)
    return result


def _normalized_source_rows(snapshot: Mapping[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for source in _source_rows(snapshot):
        row = deepcopy(source)
        row["claims"] = _claims_for_source(source)
        result.append(row)
    return result


def _source_graph(snapshot: Mapping[str, Any]) -> EngineeringSourceGraph:
    stored = snapshot.get("engineeringSourceGraph")
    if isinstance(stored, Mapping):
        return EngineeringSourceGraph.model_validate(stored)
    declared_conflicts = snapshot.get("engineeringSourceConflicts")
    if not isinstance(declared_conflicts, Sequence) or isinstance(
        declared_conflicts, (str, bytes, bytearray)
    ):
        declared_conflicts = snapshot.get("sourceConflicts")
    unresolved = snapshot.get("unresolvedSourceIds") or snapshot.get(
        "unresolved_source_ids"
    )
    return build_engineering_source_graph(
        _normalized_source_rows(snapshot),
        declared_conflicts=_rows(declared_conflicts),
        unresolved_source_ids=(
            [str(value) for value in unresolved]
            if isinstance(unresolved, Sequence)
            and not isinstance(unresolved, (str, bytes, bytearray))
            else []
        ),
    )


def _walk_source_refs(value: Any) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []

    def walk(node: Any, *, inside_refs: bool = False) -> None:
        if isinstance(node, Mapping):
            if inside_refs and (node.get("source_id") or node.get("claim_id")):
                refs.append(deepcopy(dict(node)))
            for key, child in node.items():
                walk(child, inside_refs=inside_refs or str(key) == "source_refs")
        elif isinstance(node, Sequence) and not isinstance(
            node, (str, bytes, bytearray)
        ):
            for child in node:
                walk(child, inside_refs=inside_refs)

    walk(value)
    unique: dict[str, dict[str, Any]] = {}
    for ref in refs:
        unique.setdefault(_canonical(ref), ref)
    return list(unique.values())


def _output_summary(kind: str, row: Mapping[str, Any]) -> str:
    keys = {
        "requirement": ("statement", "requirement", "text", "description", "title"),
        "candidate": ("name", "candidate", "title", "reason", "description"),
        "decision": ("decision", "statement", "title", "description", "reason"),
        "action": ("action", "title", "description", "acceptance"),
        "blocker": ("message", "description", "reason", "title"),
    }.get(kind, ("title", "description", "reason"))
    for key in keys:
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return f"{kind} engineering output"


def _output_nodes(snapshot: Mapping[str, Any]) -> list[dict[str, Any]]:
    plan = snapshot.get("preFabricationPlan")
    if not isinstance(plan, Mapping):
        plan = snapshot.get("engineeringPlan")
    plan = dict(plan) if isinstance(plan, Mapping) else {}
    surfaces = (
        ("requirement", "requirements", ("requirement_id", "id")),
        ("candidate", "architecture_candidates", ("candidate_id", "id")),
        ("decision", "decisions", ("decision_id", "id")),
        ("action", "actions", ("action_id", "id")),
    )
    nodes: list[dict[str, Any]] = []
    for kind, key, id_keys in surfaces:
        for index, row in enumerate(_rows(plan.get(key))):
            local_id = next(
                (
                    str(row.get(id_key)).strip()
                    for id_key in id_keys
                    if str(row.get(id_key) or "").strip()
                ),
                f"{index + 1}",
            )
            refs = _walk_source_refs(row)
            source_ids = sorted(
                {
                    str(value).strip()
                    for value in row.get("source_ids") or []
                    if str(value).strip()
                }
                | {
                    str(ref.get("source_id")).strip()
                    for ref in refs
                    if str(ref.get("source_id") or "").strip()
                }
            )
            claim_ids = sorted(
                {
                    str(ref.get("claim_id")).strip()
                    for ref in refs
                    if str(ref.get("claim_id") or "").strip()
                }
            )
            nodes.append(
                {
                    "node_id": f"{kind}:{local_id}",
                    "kind": kind,
                    "surface": f"{('preFabricationPlan' if snapshot.get('preFabricationPlan') is not None else 'engineeringPlan')}.{key}",
                    "local_id": local_id,
                    "summary": _output_summary(kind, row),
                    "status": str(
                        row.get("status") or row.get("disposition") or "unspecified"
                    ),
                    "source_ids": source_ids,
                    "claim_ids": claim_ids,
                    "source_refs": refs,
                    "raw": row,
                }
            )

    for index, value in enumerate(snapshot.get("engineeringBlockers") or []):
        row = dict(value) if isinstance(value, Mapping) else {"message": str(value)}
        message = _output_summary("blocker", row)
        local_id = str(row.get("blocker_id") or row.get("id") or "").strip()
        local_id = local_id or _stable_id("blocker", message)
        refs = _walk_source_refs(row)
        nodes.append(
            {
                "node_id": f"blocker:{local_id}",
                "kind": "blocker",
                "surface": "engineeringBlockers",
                "local_id": local_id,
                "summary": message,
                "status": "blocking",
                "source_ids": sorted(
                    {
                        str(ref.get("source_id")).strip()
                        for ref in refs
                        if str(ref.get("source_id") or "").strip()
                    }
                ),
                "claim_ids": sorted(
                    {
                        str(ref.get("claim_id")).strip()
                        for ref in refs
                        if str(ref.get("claim_id") or "").strip()
                    }
                ),
                "source_refs": refs,
                "raw": row,
            }
        )
    return nodes


def _claim_reviews(snapshot: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    adjudication = snapshot.get("engineeringSourceAdjudication")
    if not isinstance(adjudication, Mapping):
        return {}
    return {
        str(row.get("claim_id")): row
        for row in _rows(adjudication.get("claim_reviews"))
        if str(row.get("claim_id") or "").strip()
    }


def _reference_issues(
    outputs: list[dict[str, Any]],
    sources: dict[str, dict[str, Any]],
    claims: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for output in outputs:
        for ref in output["source_refs"]:
            source_id = str(ref.get("source_id") or "").strip()
            claim_id = str(ref.get("claim_id") or "").strip()
            source = sources.get(source_id) if source_id else None
            claim = claims.get(claim_id) if claim_id else None
            if source_id and source is None:
                issues.append(
                    {"output_id": output["node_id"], "kind": "unknown_source", "source_id": source_id}
                )
                continue
            if claim_id and claim is None:
                issues.append(
                    {"output_id": output["node_id"], "kind": "unknown_claim", "claim_id": claim_id}
                )
                continue
            if source and claim and claim["source_id"] != source_id:
                issues.append(
                    {
                        "output_id": output["node_id"],
                        "kind": "claim_source_mismatch",
                        "source_id": source_id,
                        "claim_id": claim_id,
                        "actual_source_id": claim["source_id"],
                    }
                )
            for key in ("content_hash", "revision"):
                if source and ref.get(key) is not None and ref.get(key) != source.get(key):
                    issues.append(
                        {
                            "output_id": output["node_id"],
                            "kind": f"source_{key}_mismatch",
                            "source_id": source_id,
                            "expected": source.get(key),
                            "referenced": ref.get(key),
                        }
                    )
            if claim:
                locator = claim.get("evidence_locator") or {}
                for key in (
                    "page",
                    "pages",
                    "section",
                    "table",
                    "figure",
                    "paragraph",
                    "line",
                    "path",
                    "sheet",
                    "cell",
                    "test_case",
                    "timestamp_start",
                    "timestamp_end",
                ):
                    if ref.get(key) is not None and ref.get(key) != locator.get(key):
                        issues.append(
                            {
                                "output_id": output["node_id"],
                                "kind": f"claim_locator_{key}_mismatch",
                                "claim_id": claim_id,
                                "expected": locator.get(key),
                                "referenced": ref.get(key),
                            }
                        )
                if (
                    ref.get("paraphrase") is not None
                    and ref.get("paraphrase") != claim.get("value")
                ):
                    issues.append(
                        {
                            "output_id": output["node_id"],
                            "kind": "claim_paraphrase_mismatch",
                            "claim_id": claim_id,
                            "expected": claim.get("value"),
                            "referenced": ref.get("paraphrase"),
                        }
                    )
    return issues


def build_engineering_assurance(
    snapshot: Mapping[str, Any],
    *,
    project_id: str | None = None,
    revision: int | None = None,
) -> dict[str, Any]:
    """Project canonical state into an inspectable assurance graph."""

    graph = _source_graph(snapshot)
    raw_sources = {
        str(row.get("source_id")): row for row in _source_rows(snapshot) if row.get("source_id")
    }
    reviews = _claim_reviews(snapshot)
    adjudication = (
        dict(snapshot.get("engineeringSourceAdjudication"))
        if isinstance(snapshot.get("engineeringSourceAdjudication"), Mapping)
        else {}
    )
    sources: list[dict[str, Any]] = []
    for source in graph.sources:
        raw = raw_sources.get(source.source_id, {})
        metadata = dict(raw.get("metadata") or {})
        sources.append(
            {
                "source_id": source.source_id,
                "source_type": str(raw.get("source_type") or source.source_type.value),
                "normalized_source_type": source.source_type.value,
                "uri": source.uri or metadata.get("source_locator"),
                "revision": source.revision,
                "content_hash": source.content_hash,
                "retrieved_at": source.retrieved_at,
                "authority_ceiling": source.authority_ceiling.value,
                "claim_ids": list(source.claim_ids),
                "extraction_method": metadata.get("claim_extraction"),
                "raw_bytes_model_visible": metadata.get("raw_bytes_model_visible"),
                "limitations": list(metadata.get("limitations") or []),
            }
        )
    source_index = {row["source_id"]: row for row in sources}

    claims: list[dict[str, Any]] = []
    for claim in graph.claims:
        review = reviews.get(claim.claim_id, {})
        source = source_index[claim.source_id]
        claims.append(
            {
                "claim_id": claim.claim_id,
                "source_id": claim.source_id,
                "subject_id": claim.subject_id,
                "predicate": claim.predicate,
                "value": deepcopy(claim.value),
                "units": claim.units,
                "confidence": claim.confidence,
                "authority": claim.authority.value,
                "authority_ceiling": source["authority_ceiling"],
                "evidence_locator": deepcopy(claim.evidence_locator),
                "extraction_method": source.get("extraction_method"),
                "review": {
                    "status": str(review.get("status") or "pending"),
                    "reviewer": review.get("reviewer"),
                    "reviewed_at": review.get("reviewed_at"),
                    "correction": review.get("correction"),
                },
            }
        )
    claim_index = {row["claim_id"]: row for row in claims}
    outputs = _output_nodes(snapshot)
    reference_issues = _reference_issues(outputs, source_index, claim_index)

    edges: list[dict[str, str]] = []
    for claim in claims:
        edges.append(
            {
                "from": f"source:{claim['source_id']}",
                "to": f"claim:{claim['claim_id']}",
                "relationship": "contains_claim",
            }
        )
    for output in outputs:
        dependencies: list[str] = []
        for claim_id in output["claim_ids"]:
            dependencies.append(f"claim:{claim_id}")
            edges.append(
                {
                    "from": f"claim:{claim_id}",
                    "to": f"output:{output['node_id']}",
                    "relationship": "supports",
                }
            )
        claim_source_ids = {
            claim_index[claim_id]["source_id"]
            for claim_id in output["claim_ids"]
            if claim_id in claim_index
        }
        for source_id in output["source_ids"]:
            if source_id in claim_source_ids:
                continue
            dependencies.append(f"source:{source_id}")
            edges.append(
                {
                    "from": f"source:{source_id}",
                    "to": f"output:{output['node_id']}",
                    "relationship": "supports_directly",
                }
            )
        output["dependency_ids"] = sorted(set(dependencies))
        output["dependency_coverage_complete"] = bool(dependencies) and not any(
            issue["output_id"] == output["node_id"] for issue in reference_issues
        )

    conflicts: list[dict[str, Any]] = []
    for conflict in graph.conflicts:
        row = conflict.model_dump(mode="json")
        row["node_id"] = f"conflict:{conflict.conflict_id}"
        row["dependency_ids"] = [f"claim:{claim_id}" for claim_id in conflict.claim_ids]
        conflicts.append(row)
        for claim_id in conflict.claim_ids:
            edges.append(
                {
                    "from": f"claim:{claim_id}",
                    "to": row["node_id"],
                    "relationship": "participates_in_conflict",
                }
            )

    consumers_by_claim = {
        claim["claim_id"]: sorted(
            output["node_id"]
            for output in outputs
            if claim["claim_id"] in output["claim_ids"]
        )
        for claim in claims
    }
    consumers_by_source = {
        source["source_id"]: sorted(
            output["node_id"]
            for output in outputs
            if source["source_id"] in output["source_ids"]
            or any(
                claim_index.get(claim_id, {}).get("source_id") == source["source_id"]
                for claim_id in output["claim_ids"]
            )
        )
        for source in sources
    }
    for claim in claims:
        claim["downstream_output_ids"] = consumers_by_claim[claim["claim_id"]]
    for source in sources:
        source["downstream_output_ids"] = consumers_by_source[source["source_id"]]

    readiness = (
        dict(snapshot.get("engineering_readiness"))
        if isinstance(snapshot.get("engineering_readiness"), Mapping)
        else {}
    )
    return {
        "schema_version": ASSURANCE_SCHEMA,
        "project_id": project_id or snapshot.get("projectId") or snapshot.get("project_id"),
        "revision": revision,
        "status": (
            "blocked"
            if graph.blocking_conflicts
            or graph.unresolved_source_ids
            or reference_issues
            or any(output["kind"] == "blocker" for output in outputs)
            else "bounded"
        ),
        "sources": sources,
        "claims": claims,
        "outputs": outputs,
        "conflicts": conflicts,
        "edges": edges,
        "reference_issues": reference_issues,
        "unresolved_source_ids": list(graph.unresolved_source_ids),
        "review_state": {
            "status": adjudication.get("status", "not_declared"),
            "independent_signoff": adjudication.get("independent_signoff") is True,
            "independent_reviewer": adjudication.get("independent_reviewer"),
            "independent_reviewed_at": adjudication.get("independent_reviewed_at"),
            "reviewed_claim_count": sum(
                claim["review"]["status"] not in {"pending", "unreviewed", ""}
                for claim in claims
            ),
            "claim_count": len(claims),
        },
        "authority_state": {
            "fabrication_ready": readiness.get("fabrication_ready") is True,
            "power_on_ready": readiness.get("power_on_ready") is True,
            "evidence_complete": readiness.get("evidence_complete") is True,
            "physical_authority_granted": False,
            "authority_effect": "none",
        },
        "summary": {
            "source_count": len(sources),
            "claim_count": len(claims),
            "output_count": len(outputs),
            "blocking_conflict_count": len(graph.blocking_conflicts),
            "blocker_count": sum(output["kind"] == "blocker" for output in outputs),
            "reference_issue_count": len(reference_issues),
            "unreviewed_claim_count": sum(
                claim["review"]["status"] in {"pending", "unreviewed", ""}
                for claim in claims
            ),
            "unconsumed_claim_count": sum(
                not claim["downstream_output_ids"] for claim in claims
            ),
        },
        "metadata": {
            "derived_from_canonical_state": True,
            "parallel_evidence_store_created": False,
            "automatic_authorization": False,
            "physical_correctness": "UNPROVEN",
        },
    }


def build_independent_review_packet(assurance: Mapping[str, Any]) -> dict[str, Any]:
    """Return a conclusion-blind packet for independent claim transcription review."""

    sources = {
        str(row["source_id"]): dict(row) for row in assurance.get("sources") or []
    }
    claims = []
    for raw in assurance.get("claims") or []:
        claim = dict(raw)
        source = sources.get(str(claim.get("source_id")), {})
        claims.append(
            {
                "claim_id": claim.get("claim_id"),
                "source_id": claim.get("source_id"),
                "source_type": source.get("source_type"),
                "uri": source.get("uri"),
                "document_revision": source.get("revision"),
                "content_hash": source.get("content_hash"),
                "evidence_locator": deepcopy(claim.get("evidence_locator") or {}),
                "paraphrase": deepcopy(claim.get("value")),
                "predicate": claim.get("predicate"),
                "extraction_method": claim.get("extraction_method"),
                "authority_ceiling": claim.get("authority_ceiling"),
                "review_response": {
                    "status": None,
                    "allowed_statuses": ["SUPPORTED", "PARTIAL", "WRONG", "AMBIGUOUS"],
                    "correction": None,
                    "notes": None,
                },
            }
        )
    return {
        "schema_version": ASSURANCE_REVIEW_PACKET_SCHEMA,
        "project_id": assurance.get("project_id"),
        "revision": assurance.get("revision"),
        "review_scope": "source transcription and locator support only",
        "blind_to_agent_conclusions": True,
        "instructions": (
            "For each claim, inspect only the identified source bytes and locator. Mark "
            "SUPPORTED, PARTIAL, WRONG, or AMBIGUOUS; provide corrections without using "
            "downstream agent conclusions."
        ),
        "reviewer": None,
        "reviewed_at": None,
        "claims": claims,
        "authority_effect": "none",
        "automatic_authorization": False,
    }


def changed_assurance_dependencies(
    base: Mapping[str, Any], candidate: Mapping[str, Any]
) -> dict[str, list[str]]:
    """Compare two assurance projections by stable source and claim identities."""

    def changed_ids(key: str, id_key: str) -> list[str]:
        left = {str(row[id_key]): row for row in base.get(key) or []}
        right = {str(row[id_key]): row for row in candidate.get(key) or []}
        return sorted(
            identity
            for identity in set(left) | set(right)
            if _canonical(left.get(identity)) != _canonical(right.get(identity))
        )

    return {
        "source_ids": changed_ids("sources", "source_id"),
        "claim_ids": changed_ids("claims", "claim_id"),
    }


def evaluate_assurance_delta(
    assurance: Mapping[str, Any],
    *,
    changed_source_ids: Iterable[str] = (),
    changed_claim_ids: Iterable[str] = (),
    unresolved_source_ids: Iterable[str] = (),
    unresolved_claim_ids: Iterable[str] = (),
) -> dict[str, Any]:
    """Propagate explicit evidence changes through the assurance dependency graph."""

    items: list[dict[str, Any]] = []
    for claim in assurance.get("claims") or []:
        items.append(
            {
                "evidence_id": f"claim:{claim['claim_id']}",
                "depends_on": [f"source:{claim['source_id']}"],
                "dependencies_complete": True,
                "metadata": {"kind": "claim", "claim_id": claim["claim_id"]},
            }
        )
    for output in assurance.get("outputs") or []:
        items.append(
            {
                "evidence_id": f"output:{output['node_id']}",
                "depends_on": list(output.get("dependency_ids") or []),
                "dependencies_complete": output.get("dependency_coverage_complete") is True,
                "metadata": {
                    "kind": output.get("kind"),
                    "node_id": output.get("node_id"),
                    "summary": output.get("summary"),
                },
            }
        )
    for conflict in assurance.get("conflicts") or []:
        items.append(
            {
                "evidence_id": conflict["node_id"],
                "depends_on": list(conflict.get("dependency_ids") or []),
                "dependencies_complete": True,
                "metadata": {
                    "kind": "conflict",
                    "conflict_id": conflict.get("conflict_id"),
                },
            }
        )

    changed = sorted(
        {f"source:{value}" for value in changed_source_ids if str(value)}
        | {f"claim:{value}" for value in changed_claim_ids if str(value)}
    )
    unresolved = sorted(
        {f"source:{value}" for value in unresolved_source_ids if str(value)}
        | {f"claim:{value}" for value in unresolved_claim_ids if str(value)}
    )
    impact = evaluate_evidence_impact(
        {
            "evidence_items": items,
            "changed_dependency_ids": changed,
            "unresolved_dependency_ids": unresolved,
        }
    )
    output_results = [
        row
        for row in impact["results"]
        if str(row.get("evidence_id", "")).startswith("output:")
    ]
    return {
        "schema_version": ASSURANCE_DELTA_SCHEMA,
        "status": impact["status"],
        "changed_source_ids": sorted(set(str(value) for value in changed_source_ids)),
        "changed_claim_ids": sorted(set(str(value) for value in changed_claim_ids)),
        "unresolved_source_ids": sorted(set(str(value) for value in unresolved_source_ids)),
        "unresolved_claim_ids": sorted(set(str(value) for value in unresolved_claim_ids)),
        "impact": impact,
        "affected_outputs": [
            row for row in output_results if row.get("status") == "invalidated"
        ],
        "blocked_outputs": [
            row for row in output_results if row.get("status") == "blocked"
        ],
        "retained_outputs": [
            row for row in output_results if row.get("status") == "retained"
        ],
        "authority_effect": "none",
        "automatic_authorization": False,
        "physical_authority_granted": False,
    }
