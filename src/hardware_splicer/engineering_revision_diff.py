"""Canonical diff between two guided engineering plan revisions."""

from __future__ import annotations

from typing import Any, Dict, Mapping

from pydantic import BaseModel, ConfigDict, Field

from .engineering_status import EngineeringStatus, StatusBlocker, build_engineering_status


ENGINEERING_REVISION_DIFF_SCHEMA = "hardware_splicer.engineering_revision_diff.v1"


class DiffBase(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class IdentityChange(DiffBase):
    category: str
    added_ids: list[str] = Field(default_factory=list)
    removed_ids: list[str] = Field(default_factory=list)
    retained_ids: list[str] = Field(default_factory=list)


class ArtifactChange(DiffBase):
    artifact_id: str
    change_type: str
    base: Dict[str, Any] = Field(default_factory=dict)
    candidate: Dict[str, Any] = Field(default_factory=dict)


class EngineeringRevisionDiff(DiffBase):
    schema_version: str = ENGINEERING_REVISION_DIFF_SCHEMA
    project_id: str
    base_revision: int | str | None = None
    candidate_revision: int | str | None = None
    opened_blockers: list[StatusBlocker] = Field(default_factory=list)
    resolved_blockers: list[StatusBlocker] = Field(default_factory=list)
    persistent_blockers: list[StatusBlocker] = Field(default_factory=list)
    changed_blockers: list[Dict[str, Any]] = Field(default_factory=list)
    identity_changes: list[IdentityChange] = Field(default_factory=list)
    artifact_changes: list[ArtifactChange] = Field(default_factory=list)
    execution_changes: list[Dict[str, Any]] = Field(default_factory=list)
    authority_regressions: list[str] = Field(default_factory=list)
    candidate_status: EngineeringStatus
    summary: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


_AUTHORITY_FLAGS = (
    "fabrication_authorized",
    "flash_authorized",
    "power_on_authorized",
    "motion_authorized",
    "release_authorized",
)


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _rows(value: Any) -> list[dict[str, Any]]:
    return [dict(row) for row in value if isinstance(row, Mapping)] if isinstance(value, list) else []


def _status(plan: Mapping[str, Any]) -> EngineeringStatus:
    existing = plan.get("engineering_status")
    if isinstance(existing, Mapping):
        try:
            return EngineeringStatus.model_validate(existing)
        except ValueError:
            pass
    return build_engineering_status(plan)


def _blocker_map(status: EngineeringStatus) -> dict[str, StatusBlocker]:
    return {row.blocker_id: row for row in [*status.blockers, *status.advisories]}


def _identity_sets(plan: Mapping[str, Any]) -> dict[str, set[str]]:
    machine = _mapping(plan.get("machine_project"))
    topology = _mapping(plan.get("robot_topology"))
    manufacturing = _mapping(plan.get("manufacturing_projection"))
    return {
        "machine_components": {str(row.get("component_id")) for row in _rows(machine.get("components")) if row.get("component_id")},
        "machine_interfaces": {str(row.get("interface_id")) for row in _rows(machine.get("interfaces")) if row.get("interface_id")},
        "machine_artifacts": {str(row.get("artifact_id")) for row in _rows(machine.get("artifacts")) if row.get("artifact_id")},
        "robot_links": {str(row.get("link_id")) for row in _rows(topology.get("links")) if row.get("link_id")},
        "robot_joints": {str(row.get("joint_id")) for row in _rows(topology.get("joints")) if row.get("joint_id")},
        "robot_actuators": {str(row.get("actuator_id")) for row in _rows(topology.get("actuators")) if row.get("actuator_id")},
        "robot_sensors": {str(row.get("sensor_id")) for row in _rows(topology.get("sensors")) if row.get("sensor_id")},
        "manufacturing_components": set(str(value) for value in manufacturing.get("projected_component_ids") or []),
        "manufacturing_interfaces": set(str(value) for value in manufacturing.get("projected_interface_ids") or []),
        "manufacturing_artifacts": set(str(value) for value in manufacturing.get("projected_artifact_ids") or []),
    }


def _artifact_map(plan: Mapping[str, Any]) -> dict[str, Dict[str, Any]]:
    machine = _mapping(plan.get("machine_project"))
    result: dict[str, Dict[str, Any]] = {}
    for row in _rows(machine.get("artifacts")):
        artifact_id = row.get("artifact_id")
        if not artifact_id:
            continue
        metadata = _mapping(row.get("metadata"))
        result[str(artifact_id)] = {
            "kind": row.get("kind"),
            "ref": row.get("ref"),
            "authority": row.get("authority"),
            "revision": metadata.get("revision"),
            "content_hash": metadata.get("content_hash"),
        }
    return result


def _execution_map(plan: Mapping[str, Any]) -> dict[str, Dict[str, Any]]:
    machine = _mapping(plan.get("machine_project"))
    payloads = _mapping(machine.get("discipline_payloads"))
    evidence = _mapping(payloads.get("engineering_execution_evidence"))
    result: dict[str, Dict[str, Any]] = {}
    for row in _rows(evidence.get("manifests")):
        execution_id = row.get("execution_id")
        if execution_id:
            result[str(execution_id)] = {
                "status": row.get("status"),
                "operation": row.get("operation"),
                "manifest_hash": row.get("manifest_hash"),
                "returncode": row.get("returncode"),
                "output_hashes": row.get("output_hashes") or {},
            }
    return result


def _authority_regressions(plan: Mapping[str, Any]) -> list[str]:
    regressions: list[str] = []
    readiness = _mapping(plan.get("engineering_readiness"))
    status = _mapping(plan.get("engineering_status"))
    status_metadata = _mapping(status.get("metadata"))
    scenario = _mapping(plan.get("scenario"))
    compile_spec = _mapping(scenario.get("compile_spec"))
    sources = [readiness, status_metadata, scenario, compile_spec]
    for flag in _AUTHORITY_FLAGS:
        if any(source.get(flag) is True for source in sources):
            regressions.append(f"Candidate sets {flag}=true outside a scoped human authorization record.")
    machine = _mapping(plan.get("machine_project"))
    evidence = _rows(machine.get("evidence"))
    for row in evidence:
        if row.get("simulated") and row.get("authority") in {"measured", "authorized"}:
            regressions.append(
                f"Simulated evidence {row.get('evidence_id')} carries prohibited authority {row.get('authority')}."
            )
    return list(dict.fromkeys(regressions))


def diff_engineering_revisions(
    base_plan: Mapping[str, Any],
    candidate_plan: Mapping[str, Any],
    *,
    base_revision: int | str | None = None,
    candidate_revision: int | str | None = None,
) -> EngineeringRevisionDiff:
    """Compare blockers, identities, artifacts, execution evidence, and authority."""

    base_status = _status(base_plan)
    candidate_status = _status(candidate_plan)
    project_id = candidate_status.project_id or base_status.project_id
    base_blockers = _blocker_map(base_status)
    candidate_blockers = _blocker_map(candidate_status)
    opened_ids = sorted(set(candidate_blockers) - set(base_blockers))
    resolved_ids = sorted(set(base_blockers) - set(candidate_blockers))
    retained_ids = sorted(set(base_blockers) & set(candidate_blockers))
    changed_blockers: list[Dict[str, Any]] = []
    persistent: list[StatusBlocker] = []
    for blocker_id in retained_ids:
        base_row = base_blockers[blocker_id]
        candidate_row = candidate_blockers[blocker_id]
        if base_row.model_dump(mode="json") == candidate_row.model_dump(mode="json"):
            persistent.append(candidate_row)
        else:
            changed_blockers.append(
                {
                    "blocker_id": blocker_id,
                    "base": base_row.model_dump(mode="json"),
                    "candidate": candidate_row.model_dump(mode="json"),
                }
            )

    base_identities = _identity_sets(base_plan)
    candidate_identities = _identity_sets(candidate_plan)
    identity_changes = [
        IdentityChange(
            category=category,
            added_ids=sorted(candidate_identities.get(category, set()) - base_identities.get(category, set())),
            removed_ids=sorted(base_identities.get(category, set()) - candidate_identities.get(category, set())),
            retained_ids=sorted(base_identities.get(category, set()) & candidate_identities.get(category, set())),
        )
        for category in sorted(set(base_identities) | set(candidate_identities))
        if base_identities.get(category, set()) != candidate_identities.get(category, set())
    ]

    base_artifacts = _artifact_map(base_plan)
    candidate_artifacts = _artifact_map(candidate_plan)
    artifact_changes: list[ArtifactChange] = []
    for artifact_id in sorted(set(base_artifacts) | set(candidate_artifacts)):
        before = base_artifacts.get(artifact_id)
        after = candidate_artifacts.get(artifact_id)
        if before == after:
            continue
        change_type = "added" if before is None else "removed" if after is None else "changed"
        artifact_changes.append(
            ArtifactChange(
                artifact_id=artifact_id,
                change_type=change_type,
                base=before or {},
                candidate=after or {},
            )
        )

    base_execution = _execution_map(base_plan)
    candidate_execution = _execution_map(candidate_plan)
    execution_changes = [
        {
            "execution_id": execution_id,
            "change_type": (
                "added"
                if execution_id not in base_execution
                else "removed"
                if execution_id not in candidate_execution
                else "changed"
            ),
            "base": base_execution.get(execution_id),
            "candidate": candidate_execution.get(execution_id),
        }
        for execution_id in sorted(set(base_execution) | set(candidate_execution))
        if base_execution.get(execution_id) != candidate_execution.get(execution_id)
    ]
    authority_regressions = _authority_regressions(candidate_plan)
    return EngineeringRevisionDiff(
        project_id=project_id,
        base_revision=base_revision,
        candidate_revision=candidate_revision,
        opened_blockers=[candidate_blockers[value] for value in opened_ids],
        resolved_blockers=[base_blockers[value] for value in resolved_ids],
        persistent_blockers=persistent,
        changed_blockers=changed_blockers,
        identity_changes=identity_changes,
        artifact_changes=artifact_changes,
        execution_changes=execution_changes,
        authority_regressions=authority_regressions,
        candidate_status=candidate_status,
        summary={
            "opened_blocker_count": len(opened_ids),
            "resolved_blocker_count": len(resolved_ids),
            "persistent_blocker_count": len(persistent),
            "changed_blocker_count": len(changed_blockers),
            "identity_change_category_count": len(identity_changes),
            "artifact_change_count": len(artifact_changes),
            "execution_change_count": len(execution_changes),
            "authority_regression_count": len(authority_regressions),
            "candidate_overall_status": candidate_status.overall_status,
            "candidate_next_action_id": candidate_status.next_action_id,
        },
        metadata={
            "physical_authority_unchanged": not bool(authority_regressions),
            "automatic_merge": False,
            "fabrication_authorized": False,
            "flash_authorized": False,
            "power_on_authorized": False,
            "motion_authorized": False,
            "release_authorized": False,
        },
    )
