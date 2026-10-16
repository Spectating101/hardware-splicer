"""Deterministic multi-tool scheduling over the fabrication capability registry.

A schedule allocates capabilities/resources and relative time; it is not physical
authority. The planner supports dependency DAGs and parallel work, and refuses
tasks whose capability envelope cannot be satisfied. Plans are content-addressed
so later reservations can be bound to the exact schedule an agent reviewed.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .fabrication_capability_registry import FabricationCapabilityRegistry
from .fabrication_operator import FabricationValidationError


@dataclass(frozen=True)
class FabricationWorkflowTask:
    task_id: str
    required_capabilities: tuple[str, ...]
    duration_seconds: int
    dependencies: tuple[str, ...] = ()
    kind: str | None = None
    numeric_minimums: Mapping[str, float | int] | None = None
    allow_simulated: bool = True
    requires_physical_authority: bool = False

    def normalized(self) -> dict[str, Any]:
        task_id = _id(self.task_id, "task_id")
        capabilities = [_id(value, "required capability") for value in self.required_capabilities]
        if not capabilities or len(capabilities) != len(set(capabilities)):
            raise FabricationValidationError("workflow task requires unique capabilities")
        if type(self.duration_seconds) is not int or not 1 <= self.duration_seconds <= 31 * 24 * 3600:
            raise FabricationValidationError("workflow task duration_seconds must be 1..2678400")
        dependencies = [_id(value, "dependency") for value in self.dependencies]
        if task_id in dependencies or len(dependencies) != len(set(dependencies)):
            raise FabricationValidationError("workflow dependencies must be unique and cannot self-reference")
        minimums: dict[str, float | int] = {}
        for key, value in dict(self.numeric_minimums or {}).items():
            name = _id(key, "numeric minimum key")
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise FabricationValidationError("numeric minimums must be numbers")
            minimums[name] = value
        return {
            "task_id": task_id,
            "required_capabilities": sorted(capabilities),
            "duration_seconds": self.duration_seconds,
            "dependencies": sorted(dependencies),
            "kind": self.kind,
            "numeric_minimums": minimums,
            "allow_simulated": bool(self.allow_simulated),
            "requires_physical_authority": bool(self.requires_physical_authority),
        }


class FabricationWorkflowPlanner:
    def __init__(self, *, capabilities: FabricationCapabilityRegistry) -> None:
        self.capabilities = capabilities

    def plan(
        self,
        *,
        workflow_id: str,
        tasks: Sequence[FabricationWorkflowTask],
    ) -> dict[str, Any]:
        wid = _id(workflow_id, "workflow_id")
        if isinstance(tasks, (str, bytes, bytearray)) or not isinstance(tasks, Sequence):
            raise FabricationValidationError("workflow tasks must be a list")
        if not tasks or len(tasks) > 1000:
            raise FabricationValidationError("workflow requires 1..1000 tasks")
        normalized = [task.normalized() for task in tasks]
        by_id = {task["task_id"]: task for task in normalized}
        if len(by_id) != len(normalized):
            raise FabricationValidationError("workflow task ids must be unique")
        for task in normalized:
            missing = sorted(set(task["dependencies"]).difference(by_id))
            if missing:
                raise FabricationValidationError(
                    f"task {task['task_id']!r} depends on unknown tasks: {', '.join(missing)}"
                )
        order = _topological_order(by_id)
        resource_free: dict[str, int] = {}
        task_end: dict[str, int] = {}
        scheduled: list[dict[str, Any]] = []
        blockers: list[dict[str, Any]] = []
        blocked_tasks: set[str] = set()

        for task_id in order:
            task = by_id[task_id]
            blocked_deps = [dependency for dependency in task["dependencies"] if dependency in blocked_tasks]
            if blocked_deps:
                blocked_tasks.add(task_id)
                blockers.append({
                    "task_id": task_id,
                    "type": "dependency_unallocated",
                    "dependencies": sorted(blocked_deps),
                })
                continue
            matches = self.capabilities.match(
                required_capabilities=task["required_capabilities"],
                kind=task["kind"],
                numeric_minimums=task["numeric_minimums"],
                allow_simulated=task["allow_simulated"],
            )
            if not matches:
                blocked_tasks.add(task_id)
                blockers.append({
                    "task_id": task_id,
                    "type": "no_matching_resource",
                    "required_capabilities": task["required_capabilities"],
                    "kind": task["kind"],
                    "numeric_minimums": task["numeric_minimums"],
                })
                continue
            dependency_end = max((task_end[dependency] for dependency in task["dependencies"]), default=0)
            candidates = []
            for resource in matches:
                resource_id = resource["operator_id"]
                start = max(dependency_end, resource_free.get(resource_id, 0))
                end = start + task["duration_seconds"]
                candidates.append((start, end, bool(resource.get("simulated_only")), resource_id, resource))
            candidates.sort(key=lambda value: (value[0], value[2], value[3]))
            start, end, _simulated, resource_id, resource = candidates[0]
            resource_free[resource_id] = end
            task_end[task_id] = end
            scheduled.append({
                "task_id": task_id,
                "resource_id": resource_id,
                "resource_kind": resource["kind"],
                "simulated_only": bool(resource.get("simulated_only")),
                "start_offset_seconds": start,
                "end_offset_seconds": end,
                "duration_seconds": task["duration_seconds"],
                "dependencies": task["dependencies"],
                "requires_physical_authority": task["requires_physical_authority"],
                "physical_authority_granted": False,
            })

        base = {
            "schema": "hardware_splicer.fabrication_workflow_plan.v1",
            "workflow_id": wid,
            "tasks": scheduled,
            "blockers": blockers,
            "complete": not blockers and len(scheduled) == len(normalized),
            "makespan_seconds": max((row["end_offset_seconds"] for row in scheduled), default=0),
            "resource_allocation_grants_physical_authority": False,
        }
        digest = _sha_json(base)
        return {**base, "plan_sha256": digest, "plan_id": f"wp-{digest[:24]}"}


def _topological_order(tasks: Mapping[str, Mapping[str, Any]]) -> list[str]:
    indegree = {task_id: 0 for task_id in tasks}
    children = {task_id: [] for task_id in tasks}
    for task_id, task in tasks.items():
        for dependency in task["dependencies"]:
            indegree[task_id] += 1
            children[dependency].append(task_id)
    ready = sorted(task_id for task_id, degree in indegree.items() if degree == 0)
    result: list[str] = []
    while ready:
        current = ready.pop(0)
        result.append(current)
        for child in sorted(children[current]):
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)
                ready.sort()
    if len(result) != len(tasks):
        raise FabricationValidationError("workflow dependency graph contains a cycle")
    return result


def _sha_json(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _id(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise FabricationValidationError(f"{field} must be a string")
    cleaned = value.strip()
    if not cleaned or len(cleaned) > 128 or any(not (ch.isalnum() or ch in "._:-") for ch in cleaned):
        raise FabricationValidationError(f"{field} must be a bounded identifier")
    return cleaned
