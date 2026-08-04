"""API for server-computed hashing of bounded raw physical-evidence bytes."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, status

from .physical_evidence_bytes import (
    MAX_RAW_EVIDENCE_BYTES,
    RawEvidenceHashRequest,
    RawEvidenceHashResult,
    hash_raw_evidence_bytes,
)


def create_physical_evidence_hash_router() -> APIRouter:
    router = APIRouter(
        prefix="/v1/engineering/physical-evidence/raw-files",
        tags=["engineering", "physical-evidence", "hashing"],
    )

    @router.get("/schema")
    def raw_file_hash_schema() -> Dict[str, Any]:
        return {
            "ok": True,
            "request_schema": RawEvidenceHashRequest.model_json_schema(),
            "result_schema": RawEvidenceHashResult.model_json_schema(),
            "maximum_decoded_size_bytes": MAX_RAW_EVIDENCE_BYTES,
            "hash_algorithm": "sha256",
            "transport_encoding": "base64",
            "raw_bytes_persisted": False,
            "automatic_authorization": False,
        }

    @router.post("/hash")
    def hash_raw_file(request: RawEvidenceHashRequest) -> Dict[str, Any]:
        try:
            result = hash_raw_evidence_bytes(request)
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"type": "invalid_raw_physical_evidence", "message": str(exc)},
            ) from exc
        return {
            "ok": True,
            "raw_evidence_hash": result.model_dump(mode="json"),
            "file_ref": result.file_ref.model_dump(mode="json"),
            "raw_bytes_persisted": False,
            "automatic_authorization": False,
        }

    return router
