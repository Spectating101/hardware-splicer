"""Bounded agent-facing facade for Hardware Splicer physical operators.

This is intentionally close to the future MCP/API surface.  It exposes safe
operator/artifact discovery, non-actuating work, approval requests for exact
artifact-bound plans, approval polling and execution after a human has approved
that exact request.  It never exposes registration, connection configuration,
credentials or grant minting.
"""

from __future__ import annotations

from typing import Any, Mapping

from .fabrication_operator import FabricationAuthorityError, FabricationValidationError
from .physical_approval import PhysicalApprovalStore
from .physical_artifact import PhysicalArtifactRegistry
from .physical_dispatch import PhysicalDispatcher
from .physical_operator import PhysicalOperatorRegistry


class AgentPhysicalWorkbench:
    def __init__(
        self,
        *,
        operators: PhysicalOperatorRegistry,
        artifacts: PhysicalArtifactRegistry,
        approvals: PhysicalApprovalStore,
        dispatcher: PhysicalDispatcher,
    ):
        self.operators = operators
        self.artifacts = artifacts
        self.approvals = approvals
        self.dispatcher = dispatcher

    def list_operators(self, *, kinds: list[str] | None = None) -> list[dict[str, Any]]:
        return self.operators.public_list(kinds=kinds)

    def list_artifacts(self, *, kind: str | None = None) -> list[dict[str, Any]]:
        return self.artifacts.list_public(kind=kind)

    def perform_non_actuating(
        self,
        *,
        operator_id: str,
        project_id: str,
        mission_id: str,
        action: str,
        payload: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        plan = self.operators.plan(
            operator_id=operator_id,
            project_id=project_id,
            mission_id=mission_id,
            action=action,
            payload=payload or {},
        )
        if plan.requires_human_grant:
            raise FabricationAuthorityError("agent workbench cannot directly dispatch physical actuation")
        return self.dispatcher.dispatch(plan)

    def request_artifact_actuation(
        self,
        *,
        operator_id: str,
        project_id: str,
        mission_id: str,
        action: str,
        artifact_id: str,
        bindings: Mapping[str, Any] | None,
        agent_id: str,
    ) -> dict[str, Any]:
        if not isinstance(agent_id, str) or not agent_id.strip():
            raise FabricationValidationError("agent_id is required")
        plan = self.artifacts.build_actuation_plan(
            operators=self.operators,
            operator_id=operator_id,
            project_id=project_id,
            mission_id=mission_id,
            action=action,
            artifact_id=artifact_id,
            bindings=bindings,
        )
        return self.approvals.request(plan, requested_by={"kind": "agent", "id": agent_id.strip()})

    def approval_status(self, request_id: str) -> dict[str, Any]:
        return self.approvals.get(request_id)

    def execute_approved(self, request_id: str) -> dict[str, Any]:
        record = self.approvals.get(request_id)
        if record.get("status") != "approved" or not record.get("grant_id"):
            raise FabricationAuthorityError("physical approval request is not approved")
        value = record.get("execution_plan")
        if not isinstance(value, Mapping):
            raise FabricationValidationError("approved request has no execution plan")
        plan = self.operators.plan(
            operator_id=value.get("operator_id"),
            project_id=value.get("project_id"),
            mission_id=value.get("mission_id"),
            action=value.get("action"),
            payload=value.get("payload") or {},
        )
        if isinstance(plan.payload, Mapping) and plan.payload.get("artifact_id") is not None:
            self.artifacts.verify_plan_artifact(plan)
        return self.dispatcher.dispatch(plan, grant_id=record["grant_id"])
