"""Bounded facade for planning and reserving multi-tool fabrication workflows."""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from .fabrication_capability_registry import FabricationCapabilityRegistry
from .fabrication_operator import FabricationValidationError
from .fabrication_resource_leases import ResourceLeaseStore, WorkflowPlanRegistry
from .fabrication_workflow_scheduler import FabricationWorkflowPlanner, FabricationWorkflowTask


class FabricatorLabWorkbench:
    def __init__(
        self,
        *,
        capabilities: FabricationCapabilityRegistry,
        plans: WorkflowPlanRegistry | None = None,
        leases: ResourceLeaseStore | None = None,
    ) -> None:
        self.capabilities = capabilities
        self.planner = FabricationWorkflowPlanner(capabilities=capabilities)
        self.plans = plans or WorkflowPlanRegistry()
        self.leases = leases or ResourceLeaseStore(plans=self.plans)

    def list_resources(self, *, kind: str | None = None) -> list[dict[str, Any]]:
        return self.capabilities.list_public(kind=kind)

    def plan_workflow(self, *, workflow_id: str, tasks: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        if isinstance(tasks, (str, bytes, bytearray)) or not isinstance(tasks, Sequence):
            raise FabricationValidationError("workflow tasks must be a list")
        normalized: list[FabricationWorkflowTask] = []
        for index, raw in enumerate(tasks):
            if not isinstance(raw, Mapping):
                raise FabricationValidationError(f"workflow task {index} must be an object")
            try:
                normalized.append(FabricationWorkflowTask(
                    task_id=raw.get("task_id"),
                    required_capabilities=tuple(raw.get("required_capabilities") or ()),
                    duration_seconds=raw.get("duration_seconds"),
                    dependencies=tuple(raw.get("dependencies") or ()),
                    kind=raw.get("kind"),
                    numeric_minimums=raw.get("numeric_minimums") or {},
                    allow_simulated=bool(raw.get("allow_simulated", True)),
                    requires_physical_authority=bool(raw.get("requires_physical_authority", False)),
                ))
            except (TypeError, ValueError) as exc:
                raise FabricationValidationError(f"workflow task {index} is invalid") from exc
        plan = self.planner.plan(workflow_id=workflow_id, tasks=normalized)
        self.plans.register(plan)
        return plan

    def get_plan(self, plan_id: str) -> dict[str, Any]:
        return self.plans.get(plan_id)

    def acquire_task_lease(
        self,
        *,
        plan_id: str,
        task_id: str,
        holder_id: str,
        ttl_seconds: int = 900,
    ) -> dict[str, Any]:
        return self.leases.acquire(
            plan_id=plan_id,
            task_id=task_id,
            holder_id=holder_id,
            ttl_seconds=ttl_seconds,
        )

    def release_task_lease(self, *, lease_id: str, lease_token: str) -> dict[str, Any]:
        return self.leases.release(lease_id, lease_token=lease_token)

    def list_leases(self) -> list[dict[str, Any]]:
        return self.leases.list_public()
