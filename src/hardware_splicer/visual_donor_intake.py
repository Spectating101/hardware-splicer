"""Typed donor-capture drafts derived from retained visual inspection artifacts.

This is a projection/derivation layer, not a new physical-truth store. Model output
may prefill a donor capture, but every extracted fact remains ``model_inference``
until a person explicitly confirms or corrects it. A marking is transcription,
never part identity. Image-derived geometry is never labelled as measured.
"""
from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from .donor_capture import DonorCaptureError, validate_capture
from .engineering_artifact_store import EngineeringArtifactStore
from .fabrication_operator import FabricationValidationError

_DRAFT_SCHEMA = "hardware_splicer.visual_donor_draft.v1"
_CONFIRMED_SCHEMA = "hardware_splicer.confirmed_visual_donor_capture.v1"
_INSPECTION_SCHEMA = "hardware_splicer.visual_inspection_inference.v1"
_FACT_KINDS = frozenset({"board_outline", "package", "marking", "connector", "screw_location"})
_DECISIONS = frozenset({"confirm", "correct", "reject"})


class VisualDonorIntakeService:
    """Create immutable model drafts and human-confirmed donor-capture artifacts."""

    def __init__(self, *, artifacts: EngineeringArtifactStore) -> None:
        if not isinstance(artifacts, EngineeringArtifactStore):
            raise FabricationValidationError("visual donor intake requires an engineering artifact store")
        self.artifacts = artifacts

    def create_draft(
        self,
        *,
        donor_id: str,
        label: str,
        inspection_artifact_ids: Sequence[str],
        facts: Sequence[Mapping[str, Any]],
        output_artifact_id: str,
    ) -> dict[str, Any]:
        donor = _id(donor_id, "donor_id")
        display = _text(label, "label", 200)
        inspections = self._inspections(inspection_artifact_ids)
        by_id = {row["artifact_id"]: row for row in inspections}
        if isinstance(facts, (str, bytes, bytearray)) or not isinstance(facts, Sequence) or len(facts) > 512:
            raise FabricationValidationError("facts must be a bounded list")
        projected = [_fact(value, index=index, inspections=by_id) for index, value in enumerate(facts)]
        ids = [row["fact_id"] for row in projected]
        if len(ids) != len(set(ids)):
            raise FabricationValidationError("visual donor fact ids must be unique")
        capture_prefill = _capture_prefill(display, projected)
        result = {
            "schema": _DRAFT_SCHEMA,
            "donor_id": donor,
            "label": display,
            "inspections": inspections,
            "facts": projected,
            "fact_count": len(projected),
            "capture_prefill": capture_prefill,
            "capture_prefill_ready": False,
            "requires_human_confirmation": True,
            "evidence_class": "model_inference",
            "geometry_measured": False,
            "markings_establish_identity": False,
            "may_auto_promote_donor_contract": False,
            "physical_correctness": "UNPROVEN",
        }
        stored = self._store(
            artifact_id=output_artifact_id,
            producer="visual_donor_intake",
            payload=result,
            metadata={
                "donor_id": donor,
                "inspection_artifact_ids": [row["artifact_id"] for row in inspections],
                "fact_count": len(projected),
                "evidence_class": "model_inference",
            },
        )
        return {"draft": result, "artifact": stored, "physical_correctness": "UNPROVEN"}

    def confirm_capture(
        self,
        *,
        draft_artifact_id: str,
        output_artifact_id: str,
        human_id: str,
        capture: Mapping[str, Any],
        decisions: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        human = _id(human_id, "human_id")
        draft_record, draft = self._load_json_artifact(
            draft_artifact_id,
            producer="visual_donor_intake",
            schema=_DRAFT_SCHEMA,
        )
        if not isinstance(capture, Mapping):
            raise FabricationValidationError("capture must be an object")
        try:
            validate_capture(dict(capture))
        except DonorCaptureError as exc:
            raise FabricationValidationError(str(exc)) from exc
        draft_facts = {row["fact_id"]: row for row in draft.get("facts", []) if isinstance(row, Mapping)}
        reviewed = _review_decisions(decisions, draft_facts)
        result = {
            "schema": _CONFIRMED_SCHEMA,
            "donor_id": draft.get("donor_id"),
            "label": draft.get("label"),
            "source_draft": {
                "artifact_id": draft_record["artifact_id"],
                "sha256": draft_record["sha256"],
            },
            "reviewed_by": {"kind": "human", "id": human},
            "decisions": reviewed,
            "donor_capture": _canonical(dict(capture)),
            "ready_for_donor_capture": True,
            "evidence_class": "human_confirmation",
            "geometry_measured": False,
            "markings_establish_identity": False,
            "measurement_claims_require_separate_physical_evidence": True,
            "may_auto_promote_physical_evidence": False,
            "physical_correctness": "UNPROVEN",
        }
        stored = self._store(
            artifact_id=output_artifact_id,
            producer="visual_donor_confirmation",
            payload=result,
            metadata={
                "donor_id": draft.get("donor_id"),
                "source_draft_artifact_id": draft_record["artifact_id"],
                "source_draft_sha256": draft_record["sha256"],
                "reviewed_by": human,
            },
        )
        return {"confirmed": result, "artifact": stored, "physical_correctness": "UNPROVEN"}

    def _inspections(self, values: Sequence[str]) -> list[dict[str, Any]]:
        if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence) or not 1 <= len(values) <= 16:
            raise FabricationValidationError("inspection_artifact_ids must contain 1..16 artifact ids")
        result = []
        seen: set[str] = set()
        for raw in values:
            ident = _id(raw, "inspection_artifact_id")
            if ident in seen:
                raise FabricationValidationError("inspection artifact ids must be unique")
            seen.add(ident)
            record, payload = self._load_json_artifact(
                ident,
                producer="vision_inspection",
                schema=_INSPECTION_SCHEMA,
            )
            if payload.get("evidence_class") != "model_inference" or payload.get("hypothesis_only") is not True:
                raise FabricationValidationError("visual inspection authority semantics are invalid")
            result.append({
                "artifact_id": record["artifact_id"],
                "artifact_sha256": record["sha256"],
                "observation_id": payload.get("observation_id"),
                "observation_sha256": payload.get("observation_sha256"),
                "task_id": payload.get("task_id"),
                "model_id": payload.get("model_id"),
                "model_version": payload.get("model_version"),
                "claim_count": payload.get("claim_count"),
                "evidence_class": "model_inference",
            })
        return result

    def _load_json_artifact(
        self,
        artifact_id: str,
        *,
        producer: str,
        schema: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        record = self.artifacts.describe(artifact_id)
        if record.kind != "inspection_document" or record.producer != producer or record.media_type != "application/json":
            raise FabricationValidationError("visual donor intake artifact has incompatible kind or producer")
        try:
            payload = json.loads(self.artifacts.bytes(artifact_id).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise FabricationValidationError("visual donor intake artifact payload is invalid JSON") from exc
        if not isinstance(payload, dict) or payload.get("schema") != schema:
            raise FabricationValidationError("visual donor intake artifact has unsupported schema")
        return record.public_dict(), payload

    def _store(
        self,
        *,
        artifact_id: str,
        producer: str,
        payload: Mapping[str, Any],
        metadata: Mapping[str, Any],
    ) -> dict[str, Any]:
        encoded = (json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
        return self.artifacts.put(
            artifact_id=artifact_id,
            kind="inspection_document",
            content=encoded,
            media_type="application/json",
            producer=producer,
            metadata=metadata,
        ).public_dict()


def _fact(value: Mapping[str, Any], *, index: int, inspections: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise FabricationValidationError(f"fact {index} must be an object")
    extra = set(value) - {"fact_id", "kind", "inspection_artifact_id", "value", "confidence"}
    if extra:
        raise FabricationValidationError(f"fact {index} contains unsupported fields")
    fact_id = _id(value.get("fact_id"), f"fact {index} fact_id")
    kind = value.get("kind")
    if kind not in _FACT_KINDS:
        raise FabricationValidationError(f"fact {index} kind is unsupported")
    inspection_id = _id(value.get("inspection_artifact_id"), f"fact {index} inspection_artifact_id")
    source = inspections.get(inspection_id)
    if source is None:
        raise FabricationValidationError(f"fact {index} references an inspection outside this draft")
    raw_value = value.get("value")
    if not isinstance(raw_value, Mapping):
        raise FabricationValidationError(f"fact {index} value must be an object")
    clean_value = _canonical(dict(raw_value))
    encoded = json.dumps(clean_value, ensure_ascii=False, allow_nan=False)
    if len(encoded.encode("utf-8")) > 16 * 1024:
        raise FabricationValidationError(f"fact {index} value is too large")
    confidence = value.get("confidence")
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool) or not 0 <= float(confidence) <= 1:
        raise FabricationValidationError(f"fact {index} confidence must be between 0 and 1")
    _validate_fact_value(kind, clean_value, index=index)
    return {
        "fact_id": fact_id,
        "kind": kind,
        "value": clean_value,
        "confidence": float(confidence),
        "state": "model_inference",
        "source": {
            "inspection_artifact_id": source["artifact_id"],
            "inspection_artifact_sha256": source["artifact_sha256"],
            "observation_id": source["observation_id"],
            "observation_sha256": source["observation_sha256"],
        },
        "measured": False,
        "human_confirmed": False,
        "establishes_part_identity": False,
    }


def _validate_fact_value(kind: str, value: Mapping[str, Any], *, index: int) -> None:
    if kind == "board_outline":
        _optional_positive(value.get("width_mm"), f"fact {index} board width_mm", 5000)
        _optional_positive(value.get("length_mm"), f"fact {index} board length_mm", 5000)
        if value.get("width_mm") is None and value.get("length_mm") is None and not value.get("outline"):
            raise FabricationValidationError("board_outline requires dimensions or an outline")
    elif kind in {"package", "connector"}:
        _optional_text(value.get("ref"), f"fact {index} ref", 32)
        _optional_text(value.get("package"), f"fact {index} package", 120)
        _optional_text(value.get("kind"), f"fact {index} component kind", 120)
        _optional_positive(value.get("x_mm"), f"fact {index} x_mm", 5000, zero=True)
        _optional_positive(value.get("y_mm"), f"fact {index} y_mm", 5000, zero=True)
    elif kind == "marking":
        _text(value.get("text"), f"fact {index} marking text", 200)
        _optional_text(value.get("ref"), f"fact {index} marking ref", 32)
        if any(key in value for key in ("mpn", "manufacturer", "identity")):
            raise FabricationValidationError("marking transcription must not claim part identity")
    elif kind == "screw_location":
        _optional_positive(value.get("x_mm"), f"fact {index} screw x_mm", 5000, zero=True)
        _optional_positive(value.get("y_mm"), f"fact {index} screw y_mm", 5000, zero=True)
        _optional_positive(value.get("diameter_mm"), f"fact {index} screw diameter_mm", 100)


def _capture_prefill(label: str, facts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    board: dict[str, Any] = {}
    parts: list[dict[str, Any]] = []
    markings: dict[str, str] = {}
    for fact in facts:
        value = fact["value"]
        if fact["kind"] == "board_outline":
            for field in ("width_mm", "length_mm", "thickness_mm"):
                if value.get(field) is not None:
                    board[field] = value[field]
        elif fact["kind"] == "marking" and value.get("ref"):
            markings[str(value["ref"])] = str(value["text"])
    for fact in facts:
        if fact["kind"] not in {"package", "connector"}:
            continue
        value = fact["value"]
        row: dict[str, Any] = {}
        if value.get("ref") is not None:
            row["ref"] = value["ref"]
        row["kind"] = "connector" if fact["kind"] == "connector" else value.get("kind")
        for field in ("package", "x_mm", "y_mm", "width_mm", "length_mm", "rotation_deg", "side"):
            if value.get(field) is not None:
                row[field] = value[field]
        if row.get("ref") in markings:
            row["marking"] = markings[row["ref"]]
        parts.append(row)
    return {
        "schema_version": "hardware_splicer.donor_capture.v1",
        "name": label,
        "board": board,
        "parts": parts,
        "_prefill_provenance": {
            "state": "model_inference",
            "requires_human_confirmation": True,
            "geometry_measured": False,
            "markings_establish_identity": False,
        },
    }


def _review_decisions(
    decisions: Sequence[Mapping[str, Any]],
    facts: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    if isinstance(decisions, (str, bytes, bytearray)) or not isinstance(decisions, Sequence) or len(decisions) > len(facts):
        raise FabricationValidationError("decisions must be a bounded list")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(decisions):
        if not isinstance(raw, Mapping):
            raise FabricationValidationError(f"decision {index} must be an object")
        extra = set(raw) - {"fact_id", "decision", "corrected_value", "note"}
        if extra:
            raise FabricationValidationError(f"decision {index} contains unsupported fields")
        fact_id = _id(raw.get("fact_id"), f"decision {index} fact_id")
        if fact_id in seen or fact_id not in facts:
            raise FabricationValidationError("decision fact ids must be unique and refer to the source draft")
        seen.add(fact_id)
        decision = raw.get("decision")
        if decision not in _DECISIONS:
            raise FabricationValidationError("decision must be confirm, correct or reject")
        corrected = raw.get("corrected_value")
        if decision == "correct" and not isinstance(corrected, Mapping):
            raise FabricationValidationError("correct decisions require corrected_value")
        if corrected is not None and decision != "correct":
            raise FabricationValidationError("corrected_value is only valid for a correction")
        if corrected is not None:
            corrected = _canonical(dict(corrected))
            _validate_fact_value(str(facts[fact_id]["kind"]), corrected, index=index)
        result.append({
            "fact_id": fact_id,
            "decision": decision,
            "state": "human_confirmed" if decision in {"confirm", "correct"} else "human_rejected",
            "corrected_value": corrected,
            "note": _optional_text(raw.get("note"), f"decision {index} note", 500),
            "measured": False,
        })
    return result


def _canonical(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise FabricationValidationError("visual donor value must be canonical JSON") from exc


def _id(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise FabricationValidationError(f"{field} must be a string")
    cleaned = value.strip()
    if not cleaned or len(cleaned) > 128 or any(not (ch.isalnum() or ch in "._:-") for ch in cleaned):
        raise FabricationValidationError(f"{field} must be a bounded identifier")
    return cleaned


def _text(value: Any, field: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise FabricationValidationError(f"{field} must be a string")
    cleaned = value.strip()
    if not cleaned or len(cleaned) > maximum or any(ord(ch) < 32 and ch not in "\t\n" for ch in cleaned):
        raise FabricationValidationError(f"{field} must be bounded text")
    return cleaned


def _optional_text(value: Any, field: str, maximum: int) -> str | None:
    if value is None:
        return None
    return _text(value, field, maximum)


def _optional_positive(value: Any, field: str, maximum: float, *, zero: bool = False) -> float | None:
    if value is None:
        return None
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise FabricationValidationError(f"{field} must be numeric")
    number = float(value)
    low = 0.0 if zero else 0.000001
    if not low <= number <= maximum:
        raise FabricationValidationError(f"{field} is out of bounds")
    return number
