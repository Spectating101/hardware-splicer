"""Canonical diff between two guided engineering plan revisions."""

from __future__ import annotations

from typing import Any, Dict, Mapping

from pydantic import BaseModel, ConfigDict, Field

from .engineering_status import EngineeringStatus, StatusBlocker, build_engineering_status


ENGINEERING_REVISION_DIFF_SCHEMA = "hardware_splicer.engineering_revision_diff.v1"


class DiffBase(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    def __getitem__(self, key: str) -> Any:
        """Retain mapping-style access used by older diff consumers."""

        return getattr(self, key)


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

    @property
    def change(self) -> str:
        """Compatibility alias for the original public diff key."""

        return self.change_type


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
    mechanical_changes: list[Dict[str, Any]] = Field(default_factory=list)
    physical_authorization_changes: list[Dict[str, Any]] = Field(default_factory=list)
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


def _mechanical_map(plan: Mapping[str, Any]) -> dict[str, Dict[str, Any]]:
    result: dict[str, Dict[str, Any]] = {}
    geometry = _mapping(plan.get("mechanical_geometry"))
    for row in _rows(geometry.get("models")):
        model_id = row.get("model_id")
        if model_id:
            result[f"step_model:{model_id}"] = {
                "content_hash": row.get("content_hash"),
                "file_schema": row.get("file_schema"),
                "products": row.get("products") or [],
                "units": row.get("units") or [],
                "bounding_box": row.get("bounding_box"),
                "unresolved": row.get("unresolved") or [],
            }
    for row in _rows(geometry.get("mounts")):
        interface_id = row.get("interface_id")
        if interface_id:
            result[f"mount:{interface_id}"] = row

    fit = _mapping(plan.get("mechanical_fit"))
    for row in _rows(fit.get("checks")):
        check_id = row.get("check_id")
        if check_id:
            result[f"fit_check:{check_id}"] = {
                "category": row.get("category"),
                "status": row.get("status"),
                "message": row.get("message"),
                "target_ids": row.get("target_ids") or [],
                "unresolved_fields": row.get("unresolved_fields") or [],
                "metadata": row.get("metadata") or {},
            }
    for row in _rows(fit.get("clearance_boxes")):
        object_id = row.get("object_id")
        if object_id:
            result[f"clearance_box:{object_id}"] = row
    for row in _rows(fit.get("clearance_requirements")):
        requirement_id = row.get("requirement_id")
        if requirement_id:
            result[f"clearance_requirement:{requirement_id}"] = row
    for row in _rows(fit.get("fastener_stacks")):
        stack_id = row.get("stack_id")
        if stack_id:
            result[f"fastener_stack:{stack_id}"] = row
    return result


def _physical_authorization_map(plan: Mapping[str, Any]) -> dict[str, Dict[str, Any]]:
    result: dict[str, Dict[str, Any]] = {}
    package = _mapping(plan.get("physical_evidence_package"))
    for row in _rows(package.get("calibrations")):
        calibration_id = row.get("calibration_id")
        if calibration_id:
            result[f"calibration:{calibration_id}"] = row
    for row in _rows(package.get("evidence")):
        evidence_id = row.get("evidence_id")
        if evidence_id:
            result[f"physical_evidence:{evidence_id}"] = row
    decision = _mapping(package.get("decision"))
    if decision:
        authorization_id = decision.get("authorization_id") or "decision"
        result[f"authorization:{authorization_id}"] = decision
    assessment = _mapping(package.get("assessment"))
    if assessment:
        result["physical_assessment"] = assessment
    scoped = _mapping(plan.get("scoped_release_assessment"))
    if scoped:
        result["scoped_release_assessment"] = scoped
    return result


def _map_changes(
    base: Mapping[str, Dict[str, Any]],
    candidate: Mapping[str, Dict[str, Any]],
    *,
    id_field: str,
) -> list[Dict[str, Any]]:
    changes: list[Dict[str, Any]] = []
    for record_id in sorted(set(base) | set(candidate)):
        before = base.get(record_id)
        after = candidate.get(record_id)
        if before == after:
            continue
        changes.append(
            {
                id_field: record_id,
                "change_type": (
                    "added" if before is None else "removed" if after is None else "changed"
                ),
                "base": before,
                "candidate": after,
            }
        )
    return changes


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
    """Compare blockers, identities, artifacts, execution, mechanics, and authority."""

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

    execution_changes = _map_changes(
        _execution_map(base_plan),
        _execution_map(candidate_plan),
        id_field="execution_id",
    )
    mechanical_changes = _map_changes(
        _mechanical_map(base_plan),
        _mechanical_map(candidate_plan),
        id_field="mechanical_id",
    )
    physical_authorization_changes = _map_changes(
        _physical_authorization_map(base_plan),
        _physical_authorization_map(candidate_plan),
        id_field="physical_record_id",
    )
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
        mechanical_changes=mechanical_changes,
        physical_authorization_changes=physical_authorization_changes,
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
            "mechanical_change_count": len(mechanical_changes),
            "physical_authorization_change_count": len(physical_authorization_changes),
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
