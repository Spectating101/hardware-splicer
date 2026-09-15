"""Canonical API for hash-bound PDF reading and anchored claim proposals."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Mapping

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from .document_evidence import (
    DOCUMENT_EVIDENCE_SCHEMA,
    DOCUMENT_EXTRACTION_IMPLEMENTATION,
    MAX_DOCUMENT_PAGES,
    MAX_SUPPORTING_TEXT_CHARACTERS,
    document_index,
    document_page,
    extract_registered_pdf,
    normalize_supporting_text,
    search_document,
    supporting_text_is_present,
    text_sha256,
)
from .project_store import (
    CorruptProject,
    InvalidProjectId,
    ProjectNotFound,
    ProjectStore,
    ProjectStoreError,
    RevisionConflict,
)


DOCUMENT_CLAIM_PROPOSAL_SCHEMA = (
    "hardware_splicer.document_claim_proposal.v1"
)


class DocumentEvidenceApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProposedDocumentClaim(DocumentEvidenceApiModel):
    claim_id: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$",
    )
    subject_id: str = Field(min_length=1, max_length=256)
    predicate: str = Field(min_length=1, max_length=256)
    value: Any
    units: str | None = Field(default=None, max_length=64)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    page_number: int = Field(ge=1, le=MAX_DOCUMENT_PAGES)
    section: str | None = Field(default=None, max_length=256)
    supporting_text: str = Field(
        min_length=1,
        max_length=MAX_SUPPORTING_TEXT_CHARACTERS,
    )


class RegisterDocumentClaimsRequest(DocumentEvidenceApiModel):
    expected_revision: int = Field(ge=1)
    claims: list[ProposedDocumentClaim] = Field(min_length=1, max_length=64)


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, InvalidProjectId):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"type": "invalid_project_id", "message": str(exc)},
        )
    if isinstance(exc, ProjectNotFound):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"type": "project_or_document_not_found", "message": str(exc)},
        )
    if isinstance(exc, RevisionConflict):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"type": "document_claim_revision_conflict", "message": str(exc)},
        )
    if isinstance(exc, CorruptProject):
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"type": "corrupt_project", "message": str(exc)},
        )
    if isinstance(exc, (TypeError, ValueError)):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"type": "invalid_document_evidence_request", "message": str(exc)},
        )
    if isinstance(exc, ProjectStoreError):
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"type": "project_store_error", "message": str(exc)},
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={"type": "document_evidence_error", "message": str(exc)},
    )


def _rows(value: Any) -> list[Dict[str, Any]]:
    return [dict(row) for row in value or [] if isinstance(row, Mapping)]


def _source(snapshot: Mapping[str, Any], source_id: str) -> Dict[str, Any]:
    for row in _rows(snapshot.get("engineeringSources")):
        if str(row.get("source_id") or "") == source_id:
            return row
    raise ProjectNotFound(f"registered document source {source_id!r}")


def _load_document(
    store: ProjectStore,
    project_id: str,
    source_id: str,
    *,
    revision: int | None = None,
):
    envelope = (
        store.load(project_id, revision=revision)
        if revision is not None
        else store.load_latest_with_recovery(project_id)
    )
    source = _source(envelope["snapshot"], source_id)
    document = extract_registered_pdf(
        project_id,
        source,
        project_root=store.root,
    )
    return envelope, source, document


def _claim_payload(
    claim: ProposedDocumentClaim,
    *,
    source_id: str,
    source_content_hash: str,
    page_text: str,
) -> Dict[str, Any]:
    supporting_text = normalize_supporting_text(claim.supporting_text)
    if not supporting_text_is_present(page_text, supporting_text):
        raise ValueError(
            f"claim {claim.claim_id!r} supporting_text is not present on "
            f"extracted page {claim.page_number}"
        )
    locator: Dict[str, Any] = {
        "page": claim.page_number,
        "source_content_hash": source_content_hash,
        "page_text_sha256": text_sha256(page_text),
        "extraction_implementation": DOCUMENT_EXTRACTION_IMPLEMENTATION,
        "supporting_text_sha256": text_sha256(supporting_text),
    }
    if claim.section:
        locator["section"] = claim.section
    return {
        "claim_id": claim.claim_id,
        "source_id": source_id,
        "subject_id": claim.subject_id,
        "predicate": claim.predicate,
        "value": claim.value,
        "units": claim.units,
        "confidence": claim.confidence,
        "authority": "proposed",
        "evidence_locator": locator,
        "metadata": {
            "claim_origin": "model_proposed_from_hash_bound_document_text",
            "supporting_text": supporting_text,
            "independent_review_state": "unreviewed",
            "automatic_authorization": False,
        },
    }


def _claim_identity(row: Mapping[str, Any]) -> tuple[Any, ...]:
    locator = dict(row.get("evidence_locator") or {})
    metadata = dict(row.get("metadata") or {})
    return (
        row.get("source_id"),
        row.get("subject_id"),
        row.get("predicate"),
        row.get("value"),
        row.get("units"),
        locator.get("page"),
        locator.get("source_content_hash"),
        locator.get("page_text_sha256"),
        locator.get("supporting_text_sha256"),
        locator.get("extraction_implementation"),
        row.get("authority"),
        metadata.get("claim_origin"),
        metadata.get("supporting_text"),
        metadata.get("independent_review_state"),
        metadata.get("automatic_authorization"),
    )


def create_document_evidence_router(
    project_store: ProjectStore | None = None,
) -> APIRouter:
    store = project_store or ProjectStore()
    router = APIRouter(tags=["document-evidence"])

    @router.get("/v1/engineering/document-evidence/schema")
    def document_evidence_schema() -> Dict[str, Any]:
        return {
            "ok": True,
            "schema_version": DOCUMENT_EVIDENCE_SCHEMA,
            "claim_proposal_schema_version": DOCUMENT_CLAIM_PROPOSAL_SCHEMA,
            "claim_proposal_request_schema": (
                RegisterDocumentClaimsRequest.model_json_schema()
            ),
            "extraction_implementation": DOCUMENT_EXTRACTION_IMPLEMENTATION,
            "maximum_document_pages": MAX_DOCUMENT_PAGES,
            "source_hash_reverified_per_request": True,
            "raw_bytes_returned": False,
            "read_operations_mutate_project": False,
            "claim_authority": "proposed",
            "independent_review_required": True,
            "automatic_authorization": False,
        }

    @router.get("/v1/projects/{project_id}/sources/{source_id}/document")
    def inspect_document(
        project_id: str,
        source_id: str,
        revision: int | None = Query(default=None, ge=1),
    ) -> Dict[str, Any]:
        try:
            envelope, _registered_source, document = _load_document(
                store,
                project_id,
                source_id,
                revision=revision,
            )
            result = document_index(document)
        except Exception as exc:
            raise _error(exc) from exc
        return {
            "ok": True,
            "project_revision": envelope["revision"],
            "document": result,
        }

    @router.get(
        "/v1/projects/{project_id}/sources/{source_id}/document/pages/{page_number}"
    )
    def read_document_page(
        project_id: str,
        source_id: str,
        page_number: int,
        revision: int | None = Query(default=None, ge=1),
        offset: int = Query(default=0, ge=0),
        max_characters: int = Query(default=20_000, ge=1),
    ) -> Dict[str, Any]:
        try:
            envelope, _registered_source, document = _load_document(
                store,
                project_id,
                source_id,
                revision=revision,
            )
            result = document_page(
                document,
                page_number,
                offset=offset,
                max_characters=max_characters,
            )
        except Exception as exc:
            raise _error(exc) from exc
        return {
            "ok": True,
            "project_revision": envelope["revision"],
            "page": result,
        }

    @router.get("/v1/projects/{project_id}/sources/{source_id}/document/search")
    def search_document_text(
        project_id: str,
        source_id: str,
        q: str = Query(min_length=1, max_length=256),
        revision: int | None = Query(default=None, ge=1),
        limit: int = Query(default=20, ge=1, le=50),
        context_characters: int = Query(default=240, ge=20, le=1_000),
    ) -> Dict[str, Any]:
        try:
            envelope, _registered_source, document = _load_document(
                store,
                project_id,
                source_id,
                revision=revision,
            )
            result = search_document(
                document,
                q,
                limit=limit,
                context_characters=context_characters,
            )
        except Exception as exc:
            raise _error(exc) from exc
        return {
            "ok": True,
            "project_revision": envelope["revision"],
            "search": result,
        }

    @router.post(
        "/v1/projects/{project_id}/sources/{source_id}/document/claims",
        status_code=status.HTTP_201_CREATED,
    )
    def register_document_claims(
        project_id: str,
        source_id: str,
        request: RegisterDocumentClaimsRequest,
    ) -> Dict[str, Any]:
        try:
            envelope, source, document = _load_document(
                store,
                project_id,
                source_id,
            )
            current_revision = int(envelope["revision"])
            if current_revision != request.expected_revision:
                raise RevisionConflict(
                    f"project {project_id!r} is at revision {current_revision}, "
                    f"expected {request.expected_revision}"
                )
            if source.get("authority_ceiling") not in {"proposed", "declared"}:
                raise ValueError(
                    "document source authority ceiling must permit proposed claims"
                )

            proposed_ids = [claim.claim_id for claim in request.claims]
            if len(proposed_ids) != len(set(proposed_ids)):
                raise ValueError("claim proposal contains duplicate claim_id values")
            payloads = [
                _claim_payload(
                    claim,
                    source_id=source_id,
                    source_content_hash=document.content_hash,
                    page_text=document.pages[claim.page_number - 1],
                )
                for claim in request.claims
            ]

            snapshot = deepcopy(envelope["snapshot"])
            sources = _rows(snapshot.get("engineeringSources"))
            all_existing = {
                str(claim.get("claim_id") or ""): claim
                for row in sources
                for claim in _rows(row.get("claims"))
                if str(claim.get("claim_id") or "")
            }
            new_payloads: list[Dict[str, Any]] = []
            for payload in payloads:
                existing = all_existing.get(payload["claim_id"])
                if existing is None:
                    new_payloads.append(payload)
                    continue
                if _claim_identity(existing) != _claim_identity(payload):
                    raise ValueError(
                        f"claim_id {payload['claim_id']!r} already identifies a "
                        "different canonical claim"
                    )

            if not new_payloads:
                return {
                    "ok": True,
                    "registered": False,
                    "project_id": project_id,
                    "revision": current_revision,
                    "source_id": source_id,
                    "claims": payloads,
                    "claim_authority": "proposed",
                    "authority_unchanged": True,
                }

            updated_sources: list[Dict[str, Any]] = []
            for row in sources:
                if str(row.get("source_id") or "") != source_id:
                    updated_sources.append(row)
                    continue
                existing_claims = _rows(row.get("claims"))
                existing_claims.extend(new_payloads)
                updated = {**row, "claims": existing_claims}
                metadata = dict(updated.get("metadata") or {})
                metadata["document_claim_extraction"] = {
                    "schema_version": DOCUMENT_CLAIM_PROPOSAL_SCHEMA,
                    "extraction_implementation": DOCUMENT_EXTRACTION_IMPLEMENTATION,
                    "machine_proposed_claim_count": len(existing_claims),
                    "independent_review_required": True,
                    "automatic_authorization": False,
                }
                updated["metadata"] = metadata
                updated_sources.append(updated)
            snapshot["engineeringSources"] = updated_sources
            saved = store.save(
                project_id,
                snapshot,
                expected_revision=current_revision,
                metadata={
                    "source": "document_claim_proposal",
                    "document_claim_proposal_schema": (
                        DOCUMENT_CLAIM_PROPOSAL_SCHEMA
                    ),
                    "document_source_id": source_id,
                    "document_content_hash": document.content_hash,
                    "registered_claim_ids": [
                        row["claim_id"] for row in new_payloads
                    ],
                    "claim_authority": "proposed",
                    "independent_review_required": True,
                    "automatic_authorization": False,
                    "physical_authority_unchanged": True,
                },
            )
        except IndexError as exc:
            raise _error(
                ValueError("claim page_number exceeds the document page count")
            ) from exc
        except Exception as exc:
            raise _error(exc) from exc

        return {
            "ok": True,
            "registered": True,
            "project_id": project_id,
            "revision": saved["revision"],
            "saved_at": saved["saved_at"],
            "source_id": source_id,
            "claims": payloads,
            "registered_claim_count": len(new_payloads),
            "claim_authority": "proposed",
            "independent_review_required": True,
            "authority_unchanged": True,
        }

    return router
