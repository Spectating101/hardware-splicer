"""API for server-computed and optionally attested raw evidence hashes."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, status

from .physical_evidence_attestation import (
    AttestedEvidenceFileResult,
    EvidenceAttestationUnavailable,
    attest_raw_evidence_bytes,
    attestation_capability,
)
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
            "attested_result_schema": AttestedEvidenceFileResult.model_json_schema(),
            "maximum_decoded_size_bytes": MAX_RAW_EVIDENCE_BYTES,
            "hash_algorithm": "sha256",
            "attestation_algorithm": "hmac-sha256",
            "transport_encoding": "base64",
            "attestation_capability": attestation_capability(),
            "raw_bytes_persisted": False,
            "plain_hash_proves_server_origin": False,
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
            "server_attested": False,
            "raw_bytes_persisted": False,
            "automatic_authorization": False,
        }

    @router.post("/hash-attested")
    def hash_attested_raw_file(request: RawEvidenceHashRequest) -> Dict[str, Any]:
        try:
            result = attest_raw_evidence_bytes(request)
        except EvidenceAttestationUnavailable as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"type": "evidence_attestation_unavailable", "message": str(exc)},
            ) from exc
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"type": "invalid_raw_physical_evidence", "message": str(exc)},
            ) from exc
        return {
            "ok": True,
            "attested_raw_evidence": result.model_dump(mode="json"),
            "file_ref": result.file_ref.model_dump(mode="json"),
            "server_attested": not bool(result.verification_blockers),
            "raw_bytes_persisted": False,
            "automatic_authorization": False,
        }

    return router
