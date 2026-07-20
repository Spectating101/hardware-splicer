"""Evidence-backed authority transitions for canonical machine projects.

This is the only general-purpose workflow allowed to assign observed, measured,
verified, or authorized authority to engineering objects. It records the evidence
and verification objects in the same candidate before applying any promotion.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping

from .machine_project import (
    AuthorityState,
    EvidenceRef,
    MachineProject,
    VerificationMethod,
    VerificationStatus,
)


class EvidencePromotionError(ValueError):
    pass


_AUTHORITY_ORDER = {
    AuthorityState.UNKNOWN: 0,
    AuthorityState.PROPOSED: 1,
    AuthorityState.DECLARED: 2,
    AuthorityState.OBSERVED: 3,
    AuthorityState.MEASURED: 4,
    AuthorityState.VERIFIED: 5,
    AuthorityState.AUTHORIZED: 6,
}

_TARGET_COLLECTIONS: dict[str, tuple[str, str]] = {
    "requirements": ("requirements", "requirement_id"),
    "functions": ("functions", "function_id"),
    "subsystems": ("subsystems", "subsystem_id"),
    "components": ("components", "component_id"),
    "interfaces": ("interfaces", "interface_id"),
    "constraints": ("constraints", "constraint_id"),
    "artifacts": ("artifacts", "artifact_id"),
}


def _upsert(rows: list[Dict[str, Any]], id_field: str, payload: Mapping[str, Any]) -> None:
    object_id = str(payload.get(id_field) or "")
    for index, row in enumerate(rows):
        if str(row.get(id_field)) == object_id:
            rows[index] = dict(payload)
            return
    rows.append(dict(payload))


def _target(
    body: Dict[str, Any],
    collection: str,
    object_id: str,
) -> Dict[str, Any]:
    if collection not in _TARGET_COLLECTIONS:
        raise EvidencePromotionError(f"unsupported promotion collection: {collection!r}")
    body_field, id_field = _TARGET_COLLECTIONS[collection]
    row = next(
        (item for item in body.get(body_field, []) if str(item.get(id_field)) == object_id),
        None,
    )
    if row is None:
        raise EvidencePromotionError(f"unknown promotion target {collection}/{object_id}")
    return row


def _authority(value: Any) -> AuthorityState:
    try:
        return AuthorityState(str(value))
    except ValueError as exc:
        raise EvidencePromotionError(f"invalid authority state: {value!r}") from exc


def _verification_supports(
    verification: VerificationMethod | None,
    collection: str,
    object_id: str,
) -> bool:
    if verification is None:
        return False
    if object_id in verification.target_ids:
        return True
    return collection == "requirements" and object_id in verification.requirement_ids


def _validate_promotion(
    *,
    collection: str,
    object_id: str,
    current: AuthorityState,
    requested: AuthorityState,
    evidence: EvidenceRef,
    verification: VerificationMethod | None,
) -> None:
    if requested in {AuthorityState.UNKNOWN, AuthorityState.PROPOSED, AuthorityState.DECLARED}:
        raise EvidencePromotionError(
            "evidence promotion is reserved for observed, measured, verified, or authorized authority"
        )
    if _AUTHORITY_ORDER[requested] < _AUTHORITY_ORDER[current]:
        raise EvidencePromotionError(
            f"evidence workflow cannot regress {collection}/{object_id} from {current.value} to {requested.value}"
        )
    if object_id not in evidence.supports:
        raise EvidencePromotionError(
            f"evidence {evidence.evidence_id!r} does not declare support for {collection}/{object_id}"
        )

    if requested == AuthorityState.OBSERVED:
        if _AUTHORITY_ORDER[evidence.authority] < _AUTHORITY_ORDER[AuthorityState.OBSERVED]:
            raise EvidencePromotionError("observed promotion requires observed-or-stronger evidence")
        return

    if requested == AuthorityState.MEASURED:
        if evidence.simulated:
            raise EvidencePromotionError("measured promotion requires non-simulated physical evidence")
        if _AUTHORITY_ORDER[evidence.authority] < _AUTHORITY_ORDER[AuthorityState.MEASURED]:
            raise EvidencePromotionError("measured promotion requires measured-or-stronger evidence")
        return

    if requested == AuthorityState.VERIFIED:
        if verification is None or verification.status != VerificationStatus.PASSED:
            raise EvidencePromotionError("verified promotion requires a passing verification")
        if evidence.evidence_id not in verification.evidence_ids:
            raise EvidencePromotionError("passing verification must reference the promotion evidence")
        if not _verification_supports(verification, collection, object_id):
            raise EvidencePromotionError(
                f"verification {verification.verification_id!r} does not target {collection}/{object_id}"
            )
        return

    if requested == AuthorityState.AUTHORIZED:
        if evidence.simulated or evidence.authority != AuthorityState.AUTHORIZED:
            raise EvidencePromotionError(
                "authorized promotion requires non-simulated evidence with authorized authority"
            )
        if verification is None or verification.status != VerificationStatus.PASSED:
            raise EvidencePromotionError("authorized promotion requires a passing verification")
        if evidence.evidence_id not in verification.evidence_ids:
            raise EvidencePromotionError("authorization verification must reference the promotion evidence")
        if not _verification_supports(verification, collection, object_id):
            raise EvidencePromotionError(
                f"authorization verification does not target {collection}/{object_id}"
            )


def record_evidence_and_promote(
    project: MachineProject,
    *,
    evidence: Mapping[str, Any],
    verification: Mapping[str, Any] | None = None,
    promotions: Iterable[Mapping[str, Any]] = (),
) -> MachineProject:
    """Record evidence and optional verification, then apply supported promotions."""

    body = project.model_dump(mode="json")
    evidence_model = EvidenceRef.model_validate(evidence)
    verification_model = (
        VerificationMethod.model_validate(verification)
        if verification is not None
        else None
    )

    if verification_model is not None and evidence_model.evidence_id not in verification_model.evidence_ids:
        raise EvidencePromotionError(
            f"verification {verification_model.verification_id!r} must reference evidence "
            f"{evidence_model.evidence_id!r}"
        )

    _upsert(
        body["evidence"],
        "evidence_id",
        evidence_model.model_dump(mode="json"),
    )

    if verification_model is not None:
        _upsert(
            body["verifications"],
            "verification_id",
            verification_model.model_dump(mode="json"),
        )
        for requirement in body["requirements"]:
            if requirement["requirement_id"] in verification_model.requirement_ids:
                values = list(requirement.get("verification_method_ids") or [])
                if verification_model.verification_id not in values:
                    values.append(verification_model.verification_id)
                requirement["verification_method_ids"] = values
        for interface in body["interfaces"]:
            if interface["interface_id"] in verification_model.target_ids:
                values = list(interface.get("verification_method_ids") or [])
                if verification_model.verification_id not in values:
                    values.append(verification_model.verification_id)
                interface["verification_method_ids"] = values

    for raw in promotions:
        collection = str(raw.get("collection") or "")
        object_id = str(raw.get("object_id") or "")
        if not collection or not object_id:
            raise EvidencePromotionError("promotion collection and object_id are required")
        row = _target(body, collection, object_id)
        current = _authority(row.get("authority") or AuthorityState.UNKNOWN.value)
        requested = _authority(raw.get("authority"))
        _validate_promotion(
            collection=collection,
            object_id=object_id,
            current=current,
            requested=requested,
            evidence=evidence_model,
            verification=verification_model,
        )
        row["authority"] = requested.value

    try:
        return MachineProject.model_validate(body)
    except Exception as exc:
        raise EvidencePromotionError(
            f"evidence candidate violates machine-project invariants: {exc}"
        ) from exc
