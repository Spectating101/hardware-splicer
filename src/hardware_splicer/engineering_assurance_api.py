"""Product API for derived engineering assurance and evidence-delta analysis."""

from __future__ import annotations

from copy import deepcopy
from enum import Enum
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from .engineering_assurance import (
    build_engineering_assurance,
    build_independent_review_packet,
    changed_assurance_dependencies,
    evaluate_assurance_delta,
)
from .project_store import (
    CorruptProject,
    ProjectNotFound,
    ProjectStore,
    ProjectStoreError,
    RevisionConflict,
)


class AssuranceApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidenceDeltaRequest(AssuranceApiModel):
    base_revision: int | None = Field(default=None, ge=1)
    candidate_revision: int | None = Field(default=None, ge=1)
    changed_source_ids: list[str] = Field(default_factory=list, max_length=512)
    changed_claim_ids: list[str] = Field(default_factory=list, max_length=2048)
    unresolved_source_ids: list[str] = Field(default_factory=list, max_length=512)
    unresolved_claim_ids: list[str] = Field(default_factory=list, max_length=2048)


class ClaimReviewStatus(str, Enum):
    SUPPORTED = "SUPPORTED"
    PARTIAL = "PARTIAL"
    WRONG = "WRONG"
    AMBIGUOUS = "AMBIGUOUS"


class ClaimReviewSubmission(AssuranceApiModel):
    claim_id: str = Field(min_length=1)
    status: ClaimReviewStatus
    correction: str | None = None
    notes: str | None = None


class SubmitClaimReviewsRequest(AssuranceApiModel):
    expected_revision: int = Field(ge=1)
    reviewer: str = Field(min_length=1)
    reviewed_at: str = Field(min_length=1)
    reviews: list[ClaimReviewSubmission] = Field(min_length=1, max_length=2048)


def _load(store: ProjectStore, project_id: str, revision: int | None) -> Dict[str, Any]:
    return (
        store.load_latest_with_recovery(project_id)
        if revision is None
        else store.load(project_id, revision)
    )


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, ProjectNotFound):
        code = status.HTTP_404_NOT_FOUND
        error_type = "project_not_found"
    elif isinstance(exc, RevisionConflict):
        code = status.HTTP_409_CONFLICT
        error_type = "assurance_review_revision_conflict"
    elif isinstance(exc, (TypeError, ValueError)):
        code = status.HTTP_422_UNPROCESSABLE_CONTENT
        error_type = "invalid_engineering_assurance_request"
    elif isinstance(exc, CorruptProject):
        code = status.HTTP_500_INTERNAL_SERVER_ERROR
        error_type = "corrupt_project"
    elif isinstance(exc, ProjectStoreError):
        code = status.HTTP_409_CONFLICT
        error_type = "project_store_error"
    else:
        code = status.HTTP_500_INTERNAL_SERVER_ERROR
        error_type = "engineering_assurance_error"
    return HTTPException(status_code=code, detail={"type": error_type, "message": str(exc)})


def create_engineering_assurance_router(project_store: ProjectStore) -> APIRouter:
    router = APIRouter(tags=["engineering-assurance"])

    @router.get(
        "/v1/projects/{project_id}/engineering/assurance",
        summary="Project canonical evidence, claims, outputs, blockers, and authority as a read-only assurance graph",
    )
    def get_assurance(
        project_id: str,
        revision: int | None = Query(default=None, ge=1),
    ) -> Dict[str, Any]:
        try:
            envelope = _load(project_store, project_id, revision)
            assurance = build_engineering_assurance(
                envelope["snapshot"],
                project_id=project_id,
                revision=int(envelope["revision"]),
            )
        except Exception as exc:
            raise _error(exc) from exc
        return {
            "ok": True,
            "project_id": project_id,
            "revision": envelope["revision"],
            "recovery": envelope.get("recovery"),
            "assurance": assurance,
        }

    @router.get(
        "/v1/projects/{project_id}/engineering/assurance/review-packet",
        summary="Generate a conclusion-blind independent review packet for source claims",
    )
    def get_review_packet(
        project_id: str,
        revision: int | None = Query(default=None, ge=1),
    ) -> Dict[str, Any]:
        try:
            envelope = _load(project_store, project_id, revision)
            assurance = build_engineering_assurance(
                envelope["snapshot"],
                project_id=project_id,
                revision=int(envelope["revision"]),
            )
            packet = build_independent_review_packet(assurance)
        except Exception as exc:
            raise _error(exc) from exc
        return {
            "ok": True,
            "project_id": project_id,
            "revision": envelope["revision"],
            "review_packet": packet,
            "authority_effect": "none",
        }

    @router.post(
        "/v1/projects/{project_id}/engineering/assurance/evidence-delta",
        summary="Identify stale, blocked, and retained engineering outputs after evidence changes",
    )
    def evidence_delta(
        project_id: str, request: EvidenceDeltaRequest
    ) -> Dict[str, Any]:
        try:
            candidate_envelope = _load(
                project_store, project_id, request.candidate_revision
            )
            candidate = build_engineering_assurance(
                candidate_envelope["snapshot"],
                project_id=project_id,
                revision=int(candidate_envelope["revision"]),
            )
            changed_source_ids = set(request.changed_source_ids)
            changed_claim_ids = set(request.changed_claim_ids)
            base_revision = request.base_revision
            if base_revision is not None:
                base_envelope = _load(project_store, project_id, base_revision)
                base = build_engineering_assurance(
                    base_envelope["snapshot"],
                    project_id=project_id,
                    revision=int(base_envelope["revision"]),
                )
                derived = changed_assurance_dependencies(base, candidate)
                changed_source_ids.update(derived["source_ids"])
                changed_claim_ids.update(derived["claim_ids"])
            if not changed_source_ids and not changed_claim_ids and not request.unresolved_source_ids and not request.unresolved_claim_ids:
                raise ValueError(
                    "supply a base_revision or at least one changed/unresolved source or claim id"
                )
            delta = evaluate_assurance_delta(
                candidate,
                changed_source_ids=changed_source_ids,
                changed_claim_ids=changed_claim_ids,
                unresolved_source_ids=request.unresolved_source_ids,
                unresolved_claim_ids=request.unresolved_claim_ids,
            )
        except Exception as exc:
            raise _error(exc) from exc
        return {
            "ok": True,
            "project_id": project_id,
            "base_revision": base_revision,
            "candidate_revision": candidate_envelope["revision"],
            "evidence_delta": delta,
            "authority_effect": "none",
            "physical_authority_granted": False,
        }

    @router.post(
        "/v1/projects/{project_id}/engineering/assurance/reviews",
        summary="Persist independent source-claim review results without promoting authority",
    )
    def submit_claim_reviews(
        project_id: str, request: SubmitClaimReviewsRequest
    ) -> Dict[str, Any]:
        try:
            envelope = project_store.load_latest_with_recovery(project_id)
            current_revision = int(envelope["revision"])
            if current_revision != request.expected_revision:
                raise RevisionConflict(
                    f"project {project_id!r} is at revision {current_revision}, "
                    f"expected {request.expected_revision}"
                )
            snapshot = deepcopy(dict(envelope["snapshot"]))
            assurance = build_engineering_assurance(
                snapshot, project_id=project_id, revision=current_revision
            )
            known_claim_ids = {str(row["claim_id"]) for row in assurance["claims"]}
            submitted_ids = [row.claim_id for row in request.reviews]
            if len(submitted_ids) != len(set(submitted_ids)):
                raise ValueError("claim review submission contains duplicate claim_ids")
            unknown = sorted(set(submitted_ids) - known_claim_ids)
            if unknown:
                raise ValueError("claim review references unknown claim_ids: " + ", ".join(unknown))

            adjudication = (
                deepcopy(dict(snapshot.get("engineeringSourceAdjudication")))
                if isinstance(snapshot.get("engineeringSourceAdjudication"), dict)
                else {}
            )
            existing = {
                str(row.get("claim_id")): dict(row)
                for row in adjudication.get("claim_reviews") or []
                if isinstance(row, dict) and str(row.get("claim_id") or "").strip()
            }
            for review in request.reviews:
                existing[review.claim_id] = {
                    "claim_id": review.claim_id,
                    "status": review.status.value,
                    "correction": review.correction,
                    "notes": review.notes,
                    "reviewer": request.reviewer,
                    "reviewed_at": request.reviewed_at,
                }
            adjudication["claim_reviews"] = [existing[key] for key in sorted(existing)]
            reviewed_claim_ids = known_claim_ids & set(existing)
            review_complete = reviewed_claim_ids == known_claim_ids and bool(known_claim_ids)
            adjudication["status"] = (
                "independent_claim_review_complete_pending_signoff"
                if review_complete
                else "independent_claim_review_in_progress"
            )
            adjudication["independent_signoff"] = False
            adjudication["last_claim_reviewer"] = request.reviewer
            adjudication["last_claim_reviewed_at"] = request.reviewed_at
            snapshot["engineeringSourceAdjudication"] = adjudication
            saved = project_store.save(
                project_id,
                snapshot,
                expected_revision=current_revision,
                metadata={
                    "source": "independent_claim_review",
                    "reviewed_claim_ids": sorted(submitted_ids),
                    "reviewer_declared_identity": request.reviewer,
                    "independent_signoff_unchanged": True,
                    "physical_authority_unchanged": True,
                    "authority_effect": "none",
                },
            )
        except Exception as exc:
            raise _error(exc) from exc
        return {
            "ok": True,
            "project_id": project_id,
            "revision": saved["revision"],
            "reviewed_claim_count": len(reviewed_claim_ids),
            "claim_count": len(known_claim_ids),
            "review_complete": review_complete,
            "independent_signoff": False,
            "authority_effect": "none",
            "physical_authority_granted": False,
        }

    return router
