"""Product API for capability freezing, derivative reuse and measured economics.

These routes expose the same deterministic machinery used by CLI/CI. They never
grant fabrication, power-on or field authority; physical authorization remains on
Hardware-Splicer's existing revision/hash-bound physical evidence path.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .capability_manifest import project_capability_manifest
from .derivative_reuse import adjudicate_derivative_reuse, predict_derivative_reuse
from .machine_project import MachineProject
from .platform_derivative_metrics import evaluate_platform_derivative_evidence


class _Request(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CapabilityFreezeRequest(_Request):
    project: Dict[str, Any]
    project_revision: str = Field(min_length=1)
    capability_id: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    dependency_specs: list[Dict[str, Any]] = Field(min_length=1)


class DerivativePredictionRequest(_Request):
    baseline_manifest: Dict[str, Any]
    candidate_manifest: Dict[str, Any]
    inherited_evidence_items: list[Dict[str, Any]] = Field(default_factory=list)


class DerivativeAdjudicationRequest(_Request):
    prediction: Dict[str, Any]
    expected_invalidated_evidence_ids: list[str] = Field(default_factory=list)
    adjudicated_evidence_ids: list[str] | None = None
    adjudicator: str = Field(min_length=1)
    adjudication_basis: str = Field(min_length=1)


class DerivativeMetricsRequest(_Request):
    record: Dict[str, Any]


def _unprocessable(code: str, exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=422,
        detail={
            "error": {
                "code": code,
                "message": str(exc),
            }
        },
    )


def create_capability_reuse_router() -> APIRouter:
    router = APIRouter(prefix="/v1/capabilities", tags=["capabilities", "reuse"])

    @router.post("/freeze")
    def freeze_capability(request: CapabilityFreezeRequest) -> Dict[str, Any]:
        """Project canonical MachineProject state into a frozen capability manifest."""

        try:
            project = MachineProject.model_validate(request.project)
            return project_capability_manifest(
                project,
                capability_id=request.capability_id,
                revision=request.revision,
                project_revision=request.project_revision,
                dependency_specs=request.dependency_specs,
            )
        except (ValueError, TypeError) as exc:
            raise _unprocessable("invalid_capability_freeze", exc) from exc

    @router.post("/derive")
    def derive_capability(request: DerivativePredictionRequest) -> Dict[str, Any]:
        """Freeze a selective evidence reuse/retest prediction for a derivative."""

        prediction = predict_derivative_reuse(
            request.baseline_manifest,
            request.candidate_manifest,
            request.inherited_evidence_items,
        )
        if prediction.get("status") != "predicted":
            raise HTTPException(
                status_code=422,
                detail={
                    "error": {
                        "code": "invalid_derivative_prediction",
                        "message": "Capability derivative prediction could not be frozen.",
                        "validation_errors": prediction.get("validation_errors") or [],
                    }
                },
            )
        return prediction

    @router.post("/derive/adjudicate")
    def adjudicate_capability(request: DerivativeAdjudicationRequest) -> Dict[str, Any]:
        """Score a previously frozen prediction against an outer adjudication."""

        result = adjudicate_derivative_reuse(
            request.prediction,
            expected_invalidated_evidence_ids=request.expected_invalidated_evidence_ids,
            adjudicated_evidence_ids=request.adjudicated_evidence_ids,
            adjudicator=request.adjudicator,
            adjudication_basis=request.adjudication_basis,
        )
        if result.get("status") != "adjudicated":
            raise HTTPException(
                status_code=422,
                detail={
                    "error": {
                        "code": "invalid_derivative_adjudication",
                        "message": "Derivative adjudication is inconsistent with the frozen prediction/evidence scope.",
                        "validation_errors": result.get("validation_errors") or [],
                    }
                },
            )
        return result

    @router.post("/derivative-metrics")
    def derivative_metrics(request: DerivativeMetricsRequest) -> Dict[str, Any]:
        """Evaluate measured platform reuse/economics without upgrading authority."""

        result = evaluate_platform_derivative_evidence(request.record)
        return {
            **result,
            "metadata": {
                **dict(result.get("metadata") or {}),
                "automatic_authorization": False,
                "physical_authority_granted": False,
            },
        }

    return router
