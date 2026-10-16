"""Dispatch server-created physical plans through registered private handles.

The dispatcher is intentionally boring.  It does not let a model construct raw
machine commands, choose network targets or bypass authority.  It receives a
PhysicalExecutionPlan created against a server-owned descriptor, revalidates
that descriptor, consumes human authority before any actuation, then invokes a
private handle supplied by server configuration.
"""

from __future__ import annotations

import json
from typing import Any, Mapping, Protocol

from .fabrication_operator import FabricationAuthorityError, FabricationValidationError
from .physical_authority import PhysicalPlanGrantStore, execution_plan_sha256
from .physical_operator import PhysicalExecutionPlan, PhysicalOperatorRegistry


class PhysicalOperatorHandle(Protocol):
    def execute(self, plan: PhysicalExecutionPlan) -> Mapping[str, Any]: ...


class PhysicalDispatcher:
    def __init__(self, *, registry: PhysicalOperatorRegistry, grants: PhysicalPlanGrantStore):
        self.registry = registry
        self.grants = grants

    def dispatch(self, plan: PhysicalExecutionPlan, *, grant_id: str | None = None) -> dict[str, Any]:
        if not isinstance(plan, PhysicalExecutionPlan):
            raise FabricationValidationError("dispatch requires a server-created physical execution plan")

        descriptor = self.registry.descriptor(plan.operator_id)
        action = descriptor.action(plan.action)
        if descriptor.kind != plan.operator_kind or action.action_class != plan.action_class:
            raise FabricationValidationError("physical execution plan no longer matches operator registry")

        authority = "not_required"
        grant_record = None
        if plan.requires_human_grant:
            if not isinstance(grant_id, str) or not grant_id:
                raise FabricationAuthorityError("physical actuation requires a human plan grant")
            # Consume before private handle execution.  A timeout after this point
            # is an ambiguous physical result, never grounds for automatic replay.
            grant_record = self.grants.consume(grant_id, plan)
            authority = "human_grant_consumed"
        elif grant_id is not None:
            raise FabricationValidationError("non-actuation operations must not consume physical authority")

        handle = self.registry.private_handle(plan.operator_id)
        execute = getattr(handle, "execute", None)
        if not callable(execute):
            raise FabricationValidationError("registered physical operator handle is not executable")
        response = execute(plan)
        if not isinstance(response, Mapping):
            raise FabricationValidationError("physical operator returned a non-object response")

        return {
            "schema": "hardware_splicer.physical_dispatch_receipt.v1",
            "project_id": plan.project_id,
            "mission_id": plan.mission_id,
            "operator_id": plan.operator_id,
            "operator_kind": plan.operator_kind,
            "action": plan.action,
            "action_class": plan.action_class,
            "execution_plan_sha256": execution_plan_sha256(plan),
            "payload_sha256": plan.payload_sha256,
            "authority": authority,
            "grant_id": grant_record.get("grant_id") if grant_record else None,
            "physical_correctness": "UNPROVEN",
            "result": json.loads(json.dumps(dict(response))),
        }
