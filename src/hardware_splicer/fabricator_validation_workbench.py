"""Agent-facing facade for server-owned frozen validation procedures."""
from __future__ import annotations

from typing import Any, Sequence

from .validation_procedure import ValidationProcedureEvaluator, ValidationProcedureRegistry


class FabricatorValidationWorkbench:
    def __init__(
        self,
        *,
        procedures: ValidationProcedureRegistry,
        evaluator: ValidationProcedureEvaluator,
    ) -> None:
        self.procedures = procedures
        self.evaluator = evaluator

    def list_procedures(self, *, project_id: str | None = None) -> list[dict[str, Any]]:
        return self.procedures.list_public(project_id=project_id)

    def evaluate(self, procedure_id: str, *, evidence_ids: Sequence[str]) -> dict[str, Any]:
        return self.evaluator.evaluate(procedure_id, evidence_ids=evidence_ids)
