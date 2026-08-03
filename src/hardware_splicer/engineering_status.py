"""Compile one coherent engineering status and ranked next-action surface."""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Dict, Iterable, Mapping

from pydantic import BaseModel, ConfigDict, Field


ENGINEERING_STATUS_SCHEMA = "hardware_splicer.engineering_status.v1"


class StatusBase(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class StatusSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class StatusBlocker(StatusBase):
    blocker_id: str = Field(min_length=1)
    category: str = Field(min_length=1)
    severity: StatusSeverity
    message: str = Field(min_length=1)
    target_ids: list[str] = Field(default_factory=list)
    required_inputs: list[str] = Field(default_factory=list)
    required_evidence: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class NextAction(StatusBase):
    action_id: str = Field(min_length=1)
    priority: int = Field(ge=1)
    category: str = Field(min_length=1)
    title: str = Field(min_length=1)
    instruction: str = Field(min_length=1)
    route: str = Field(min_length=1)
    method: str = "POST"
    blocker_ids: list[str] = Field(default_factory=list)
    target_ids: list[str] = Field(default_factory=list)
    required_inputs: list[str] = Field(default_factory=list)
    evidence_to_capture: list[str] = Field(default_factory=list)
    payload_hint: Dict[str, Any] = Field(default_factory=dict)
    physical_action: bool = False
    automatic_execution: bool = False


class EngineeringStatus(StatusBase):
    schema_version: str = ENGINEERING_STATUS_SCHEMA
    project_id: str = Field(min_length=1)
    overall_status: str
    current_phase: str
    blockers: list[StatusBlocker] = Field(default_factory=list)
    advisories: list[StatusBlocker] = Field(default_factory=list)
    blocker_groups: Dict[str, list[str]] = Field(default_factory=dict)
    next_actions: list[NextAction] = Field(default_factory=list)
    next_action_id: str | None = None
    summary: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


_CATEGORY_PRIORITY = {
    "source": 10,
    "topology": 20,
    "requirements": 25,
    "analysis": 30,
    "manufacturing": 40,
    "execution": 50,
    "change": 60,
    "verification": 70,
    "release": 80,
    "other": 90,
}

_ACTIONS: dict[str, dict[str, Any]] = {
    "source": {
        "title": "Resolve the engineering source boundary",
        "instruction": "Select coherent source revisions and disposition every blocking contradiction before deriving or building from them.",
        "route": "/v1/engineering/sources/resolve-conflicts",
        "payload_hint": {"graph": "engineering_source_graph", "decisions": []},
        "evidence": ["reviewer identity", "selected claim or revision", "decision reason"],
    },
    "topology": {
        "title": "Complete robot topology and identity",
        "instruction": "Resolve missing links, joints, limits, frames, actuator channels, sensor poses, and calibration identities.",
        "route": "/v1/engineering/topology",
        "payload_hint": {"intake": "normalized_intake", "hinted_genre": "native_robot_genre"},
        "evidence": ["dimensioned model", "joint/actuator mapping", "frame and calibration record"],
    },
    "requirements": {
        "title": "Complete the engineering intake",
        "instruction": "Provide the missing requirement, constraint, part, environment, or baseline information and regenerate the candidate.",
        "route": "/v1/engineering/plan",
        "payload_hint": {"intake": "updated normalized_intake"},
        "evidence": ["updated requirement or constraint record"],
    },
    "analysis": {
        "title": "Close quantitative engineering findings",
        "instruction": "Provide the missing measured inputs or revise the design until runtime, current, stability, torque, envelope, payload, and thermal checks pass.",
        "route": "/v1/engineering/analysis",
        "payload_hint": {"intake": "updated normalized_intake", "robot_topology": "robot_topology"},
        "evidence": ["calculation inputs", "instrumented measurements", "recomputed margins"],
    },
    "manufacturing": {
        "title": "Reconcile the manufacturing release candidate",
        "instruction": "Align electrical and firmware pins, connectors and harnesses, BOM and instances, fasteners and assembly, CAD mounts, and artifact revisions.",
        "route": "/v1/engineering/manufacturing-closure",
        "payload_hint": {"plan": "current guided engineering plan"},
        "evidence": ["pin/net matrix", "harness schedule", "instance/BOM reconciliation", "pinned fabrication artifacts"],
    },
    "execution": {
        "title": "Prepare and run bounded software checks",
        "instruction": "Materialize local inputs, preview the allowlisted operation, then run it only under host policy and ingest the signed execution manifest.",
        "route": "/v1/engineering/execution/preview",
        "payload_hint": {"execution_id": "selected check", "operation": "allowlisted operation", "execute": False},
        "evidence": ["execution manifest hash", "tool identity", "return code", "output hashes and logs"],
    },
    "change": {
        "title": "Close the candidate change-impact scope",
        "instruction": "Resolve affected interfaces and execute every regression check against the pinned baseline and candidate revisions.",
        "route": "/v1/engineering/change-impact",
        "payload_hint": {"intake": "normalized_intake", "baseline_project": "pinned baseline"},
        "evidence": ["baseline/candidate comparison", "regression result per affected target"],
    },
    "verification": {
        "title": "Resolve failed or blocked verification",
        "instruction": "Inspect the failed method, correct the design or execution input, rerun it, and attach the new evidence manifest without deleting the failed history.",
        "route": "/v1/engineering/execution/evidence",
        "payload_hint": {"machine_project": "current machine_project", "execution": "new execution manifest"},
        "evidence": ["new verification evidence", "failure disposition", "retained prior result"],
    },
    "release": {
        "title": "Complete scoped human release review",
        "instruction": "Review all physical evidence, limitations, hashes, revisions, payload, environment, and operating envelope before any authorization decision.",
        "route": "/v1/engineering/guide",
        "payload_hint": {"intake": "current intake"},
        "evidence": ["human reviewer", "authorized scope", "physical bench evidence", "limitations"],
    },
    "other": {
        "title": "Resolve remaining engineering blockers",
        "instruction": "Review the unresolved item, assign it to a canonical target, and attach the missing input or evidence.",
        "route": "/v1/engineering/plan",
        "payload_hint": {"intake": "updated intake"},
        "evidence": ["resolution record"],
    },
}


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _rows(value: Any) -> list[dict[str, Any]]:
    return [dict(row) for row in value if isinstance(row, Mapping)] if isinstance(value, list) else []


def _strings(values: Iterable[Any]) -> list[str]:
    return list(dict.fromkeys(str(value) for value in values if value not in (None, "")))


def _slug(value: Any, fallback: str) -> str:
    token = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value or "").strip()).strip("-._").lower()
    return token[:120] or fallback


def _add(
    rows: list[StatusBlocker],
    *,
    blocker_id: str,
    category: str,
    severity: StatusSeverity,
    message: str,
    target_ids: Iterable[Any] = (),
    required_inputs: Iterable[Any] = (),
    required_evidence: Iterable[Any] = (),
    source_ids: Iterable[Any] = (),
    metadata: Mapping[str, Any] | None = None,
) -> None:
    message = str(message).strip()
    if not message:
        return
    key = (category, message.lower(), tuple(sorted(_strings(target_ids))))
    existing = {
        (row.category, row.message.lower(), tuple(sorted(row.target_ids)))
        for row in rows
    }
    if key in existing:
        return
    rows.append(
        StatusBlocker(
            blocker_id=_slug(blocker_id, f"{category}-blocker-{len(rows) + 1}"),
            category=category,
            severity=severity,
            message=message,
            target_ids=_strings(target_ids),
            required_inputs=_strings(required_inputs),
            required_evidence=_strings(required_evidence),
            source_ids=_strings(source_ids),
            metadata=dict(metadata or {}),
        )
    )


def _source_status(plan: Mapping[str, Any], rows: list[StatusBlocker]) -> None:
    graph = _mapping(plan.get("engineering_source_graph"))
    for source_id in graph.get("unresolved_source_ids") or []:
        _add(
            rows,
            blocker_id=f"source-unresolved-{source_id}",
            category="source",
            severity=StatusSeverity.ERROR,
            message=f"Engineering source {source_id!r} is unresolved.",
            source_ids=[source_id],
            required_inputs=["resolvable source identity, revision, and content hash"],
        )
    for conflict in _rows(graph.get("conflicts")):
        if conflict.get("blocking"):
            _add(
                rows,
                blocker_id=conflict.get("conflict_id") or "source-conflict",
                category="source",
                severity=StatusSeverity.ERROR,
                message=conflict.get("reason") or "Engineering sources contain a blocking contradiction.",
                target_ids=[conflict.get("subject_id")],
                source_ids=conflict.get("source_ids") or [],
                required_inputs=["conflict disposition", "selected claim or revision boundary"],
                required_evidence=conflict.get("verification_targets") or [],
                metadata=conflict,
            )


def _topology_status(plan: Mapping[str, Any], rows: list[StatusBlocker]) -> None:
    topology = _mapping(plan.get("robot_topology"))
    for index, item in enumerate(_rows(topology.get("unresolved"))):
        object_id = item.get("object_id") or topology.get("topology_id")
        field = item.get("field") or "unknown"
        _add(
            rows,
            blocker_id=f"topology-{object_id}-{field}-{index}",
            category="topology",
            severity=StatusSeverity.ERROR,
            message=item.get("reason") or f"Topology field {object_id}.{field} is unresolved.",
            target_ids=[object_id],
            required_inputs=[field],
            metadata=item,
        )


def _analysis_status(plan: Mapping[str, Any], rows: list[StatusBlocker]) -> None:
    report = _mapping(plan.get("engineering_analysis"))
    for finding in _rows(report.get("findings")):
        status = str(finding.get("status") or "unknown")
        blocking = bool(finding.get("blocking"))
        if not blocking and status == "pass":
            continue
        severity = StatusSeverity.ERROR if blocking or status == "fail" else StatusSeverity.WARNING
        _add(
            rows,
            blocker_id=finding.get("finding_id") or "analysis-finding",
            category="analysis",
            severity=severity,
            message=finding.get("message") or "Engineering analysis requires review.",
            target_ids=finding.get("target_ids") or [],
            required_inputs=finding.get("missing_inputs") or [],
            required_evidence=["updated calculation or measured input"],
            metadata=finding,
        )


def _manufacturing_status(plan: Mapping[str, Any], rows: list[StatusBlocker]) -> None:
    report = _mapping(plan.get("manufacturing_closure"))
    for check in _rows(report.get("checks")):
        if check.get("status") == "pass":
            continue
        severity = (
            StatusSeverity.ERROR
            if check.get("severity") == "error"
            else StatusSeverity.WARNING
        )
        _add(
            rows,
            blocker_id=check.get("check_id") or "manufacturing-check",
            category="manufacturing",
            severity=severity,
            message=check.get("message") or "Manufacturing closure is incomplete.",
            target_ids=check.get("target_ids") or [],
            source_ids=check.get("source_ids") or [],
            required_inputs=check.get("unresolved_fields") or [],
            required_evidence=["manufacturing closure evidence"],
            metadata=check,
        )


def _execution_status(plan: Mapping[str, Any], rows: list[StatusBlocker]) -> None:
    execution_plan = _mapping(plan.get("engineering_execution_plan"))
    for index, item in enumerate(_rows(execution_plan.get("unresolved"))):
        subject = item.get("source_id") or item.get("artifact_id") or "execution-input"
        _add(
            rows,
            blocker_id=f"execution-input-{subject}-{index}",
            category="execution",
            severity=StatusSeverity.WARNING,
            message=item.get("reason") or "Bounded execution input is unresolved.",
            source_ids=[subject],
            required_inputs=["local workspace path or supported build adapter"],
            metadata=item,
        )
    machine = _mapping(plan.get("machine_project"))
    payloads = _mapping(machine.get("discipline_payloads"))
    evidence = _mapping(payloads.get("engineering_execution_evidence"))
    for manifest in _rows(evidence.get("manifests")):
        status = str(manifest.get("status") or "unknown")
        if status == "passed":
            continue
        severity = StatusSeverity.ERROR if status in {"failed", "timeout", "error"} else StatusSeverity.WARNING
        _add(
            rows,
            blocker_id=f"execution-result-{manifest.get('execution_id') or len(rows)}",
            category="execution",
            severity=severity,
            message=f"Execution {manifest.get('execution_id') or 'unknown'} ended as {status}.",
            target_ids=[manifest.get("target")],
            required_inputs=manifest.get("blockers") or [],
            required_evidence=["corrected execution manifest"],
            metadata=manifest,
        )


def _change_status(plan: Mapping[str, Any], rows: list[StatusBlocker]) -> None:
    impact = _mapping(plan.get("change_impact"))
    for item in _rows(impact.get("impacts")):
        if not item.get("blocking"):
            continue
        _add(
            rows,
            blocker_id=item.get("impact_id") or "change-impact",
            category="change",
            severity=StatusSeverity.ERROR,
            message=item.get("reason") or item.get("message") or "A change impact remains blocking.",
            target_ids=item.get("target_ids") or [item.get("target_id")],
            required_inputs=item.get("unresolved_fields") or [],
            required_evidence=item.get("required_evidence") or [],
            metadata=item,
        )
    for item in _rows(impact.get("unresolved")):
        _add(
            rows,
            blocker_id=f"change-unresolved-{item.get('field') or len(rows)}",
            category="change",
            severity=StatusSeverity.ERROR,
            message=item.get("reason") or "Change-impact input is unresolved.",
            required_inputs=[item.get("field")],
            metadata=item,
        )


def _verification_status(plan: Mapping[str, Any], rows: list[StatusBlocker]) -> None:
    machine = _mapping(plan.get("machine_project"))
    for verification in _rows(machine.get("verifications")):
        status = str(verification.get("status") or "planned")
        if status == "passed":
            continue
        if status in {"failed", "blocked"}:
            severity = StatusSeverity.ERROR
        else:
            severity = StatusSeverity.INFO
        _add(
            rows,
            blocker_id=verification.get("verification_id") or "verification",
            category="verification",
            severity=severity,
            message=f"Verification {verification.get('name') or verification.get('verification_id')} is {status}.",
            target_ids=verification.get("target_ids") or [],
            required_evidence=verification.get("evidence_ids") or ["verification evidence"],
            metadata=verification,
        )


def _generic_missing(plan: Mapping[str, Any], rows: list[StatusBlocker]) -> None:
    existing_messages = "\n".join(row.message.lower() for row in rows)
    for index, message in enumerate(plan.get("missing_info") or []):
        text = str(message).strip()
        if not text or text.lower() in existing_messages:
            continue
        category = "requirements"
        lowered = text.lower()
        if "source" in lowered or "conflict" in lowered:
            category = "source"
        elif "topology" in lowered or "joint" in lowered or "sensor pose" in lowered:
            category = "topology"
        elif "analysis" in lowered or "runtime" in lowered or "torque" in lowered or "stability" in lowered:
            category = "analysis"
        elif "manufacturing" in lowered or "harness" in lowered or "bom" in lowered or "fabrication" in lowered:
            category = "manufacturing"
        elif "execution" in lowered or "workspace path" in lowered:
            category = "execution"
        elif "change" in lowered or "baseline" in lowered or "regression" in lowered:
            category = "change"
        _add(
            rows,
            blocker_id=f"missing-{index + 1}",
            category=category,
            severity=StatusSeverity.WARNING,
            message=text,
            required_inputs=[text],
        )


def _actions(blockers: list[StatusBlocker], advisories: list[StatusBlocker]) -> list[NextAction]:
    by_category: dict[str, list[StatusBlocker]] = {}
    for row in [*blockers, *advisories]:
        by_category.setdefault(row.category if row.category in _ACTIONS else "other", []).append(row)
    actions: list[NextAction] = []
    for category in sorted(by_category, key=lambda value: _CATEGORY_PRIORITY.get(value, 90)):
        items = by_category[category]
        spec = _ACTIONS[category]
        actions.append(
            NextAction(
                action_id=f"next-{category}",
                priority=_CATEGORY_PRIORITY.get(category, 90),
                category=category,
                title=spec["title"],
                instruction=spec["instruction"],
                route=spec["route"],
                blocker_ids=[row.blocker_id for row in items],
                target_ids=_strings(value for row in items for value in row.target_ids),
                required_inputs=_strings(value for row in items for value in row.required_inputs),
                evidence_to_capture=_strings([
                    *spec["evidence"],
                    *(value for row in items for value in row.required_evidence),
                ]),
                payload_hint=dict(spec["payload_hint"]),
                physical_action=False,
                automatic_execution=False,
            )
        )
    return actions


def build_engineering_status(plan: Mapping[str, Any]) -> EngineeringStatus:
    """Build a deduplicated, ranked project status from a guided plan."""

    machine = _mapping(plan.get("machine_project"))
    project_id = str(machine.get("project_id") or plan.get("project_name") or "engineering-project")
    rows: list[StatusBlocker] = []
    _source_status(plan, rows)
    _topology_status(plan, rows)
    _analysis_status(plan, rows)
    _manufacturing_status(plan, rows)
    _execution_status(plan, rows)
    _change_status(plan, rows)
    _verification_status(plan, rows)
    _generic_missing(plan, rows)

    blockers = sorted(
        [row for row in rows if row.severity == StatusSeverity.ERROR],
        key=lambda row: (_CATEGORY_PRIORITY.get(row.category, 90), row.blocker_id),
    )
    advisories = sorted(
        [row for row in rows if row.severity != StatusSeverity.ERROR],
        key=lambda row: (_CATEGORY_PRIORITY.get(row.category, 90), row.blocker_id),
    )
    actions = _actions(blockers, advisories)
    active_categories = [row.category for row in blockers] or [row.category for row in advisories]
    current_phase = min(active_categories, key=lambda value: _CATEGORY_PRIORITY.get(value, 90)) if active_categories else "release"
    overall_status = "blocked" if blockers else "review" if advisories else "candidate"
    groups: dict[str, list[str]] = {}
    for row in [*blockers, *advisories]:
        groups.setdefault(row.category, []).append(row.blocker_id)

    readiness = _mapping(plan.get("engineering_readiness"))
    return EngineeringStatus(
        project_id=project_id,
        overall_status=overall_status,
        current_phase=current_phase,
        blockers=blockers,
        advisories=advisories,
        blocker_groups=groups,
        next_actions=actions,
        next_action_id=actions[0].action_id if actions else None,
        summary={
            "blocking_count": len(blockers),
            "advisory_count": len(advisories),
            "category_count": len(groups),
            "next_action_count": len(actions),
            "source_conflict_count": len(groups.get("source", [])),
            "topology_issue_count": len(groups.get("topology", [])),
            "analysis_issue_count": len(groups.get("analysis", [])),
            "manufacturing_issue_count": len(groups.get("manufacturing", [])),
            "execution_issue_count": len(groups.get("execution", [])),
            "change_issue_count": len(groups.get("change", [])),
            "verification_issue_count": len(groups.get("verification", [])),
            "readiness_status": readiness.get("status"),
        },
        metadata={
            "physical_action_suggested": False,
            "automatic_execution": False,
            "fabrication_authorized": False,
            "flash_authorized": False,
            "power_on_authorized": False,
            "motion_authorized": False,
            "release_authorized": False,
        },
    )
