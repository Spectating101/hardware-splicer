"""Frozen requirement-linked physical validation procedures.

Criteria are server/human-owned and immutable once registered. Agents may select
a procedure and retained evidence ids, but they cannot rewrite thresholds after
seeing a result. The evaluator recomputes bounded criteria from measured values
and checks that the evidence was captured against the exact procedure hash.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence

from .fabrication_operator import FabricationValidationError
from .physical_evidence import PhysicalEvidenceKind, PhysicalEvidenceRecord

_ALLOWED_OPERATORS = frozenset({"numeric_range", "equals", "text_contains", "text_not_contains"})


@dataclass(frozen=True)
class ValidationCriterion:
    operator: str
    value_key: str
    minimum: float | None = None
    maximum: float | None = None
    expected: Any = None

    def normalized(self) -> dict[str, Any]:
        if self.operator not in _ALLOWED_OPERATORS:
            raise FabricationValidationError("unsupported validation criterion operator")
        key = _id(self.value_key, "criterion value_key")
        if self.operator == "numeric_range":
            if self.minimum is None and self.maximum is None:
                raise FabricationValidationError("numeric_range needs minimum and/or maximum")
            low = _finite_or_none(self.minimum, "criterion minimum")
            high = _finite_or_none(self.maximum, "criterion maximum")
            if low is not None and high is not None and low > high:
                raise FabricationValidationError("criterion minimum exceeds maximum")
            return {"operator": self.operator, "value_key": key, "minimum": low, "maximum": high}
        if self.minimum is not None or self.maximum is not None:
            raise FabricationValidationError("non-range criterion must not define numeric bounds")
        if self.operator in {"text_contains", "text_not_contains"}:
            if not isinstance(self.expected, str) or not self.expected:
                raise FabricationValidationError("text criterion expected value must be non-empty text")
            if len(self.expected) > 1000:
                raise FabricationValidationError("text criterion expected value is too long")
            expected = self.expected
        else:
            expected = _canonical(self.expected)
        return {"operator": self.operator, "value_key": key, "expected": expected}


@dataclass(frozen=True)
class ValidationStep:
    step_id: str
    requirement_ids: tuple[str, ...]
    evidence_kind: PhysicalEvidenceKind
    target_ids: tuple[str, ...]
    criteria: tuple[ValidationCriterion, ...]

    def normalized(self) -> dict[str, Any]:
        sid = _id(self.step_id, "validation step_id")
        requirements = tuple(_id(value, "requirement_id") for value in self.requirement_ids)
        targets = tuple(_id(value, "target_id") for value in self.target_ids)
        if not requirements or len(requirements) != len(set(requirements)):
            raise FabricationValidationError("validation step requires unique requirement ids")
        if not targets or len(targets) != len(set(targets)):
            raise FabricationValidationError("validation step requires unique target ids")
        if not self.criteria:
            raise FabricationValidationError("validation step requires at least one criterion")
        return {
            "step_id": sid,
            "requirement_ids": list(requirements),
            "evidence_kind": self.evidence_kind.value,
            "target_ids": list(targets),
            "criteria": [criterion.normalized() for criterion in self.criteria],
        }


@dataclass(frozen=True)
class ValidationProcedure:
    procedure_id: str
    project_id: str
    candidate_revision: str
    steps: tuple[ValidationStep, ...]

    def canonical(self) -> dict[str, Any]:
        steps = [step.normalized() for step in self.steps]
        if not steps:
            raise FabricationValidationError("validation procedure requires steps")
        ids = [step["step_id"] for step in steps]
        if len(ids) != len(set(ids)):
            raise FabricationValidationError("validation procedure step ids must be unique")
        return {
            "schema": "hardware_splicer.validation_procedure.v1",
            "procedure_id": _id(self.procedure_id, "procedure_id"),
            "project_id": _id(self.project_id, "project_id"),
            "candidate_revision": _id(self.candidate_revision, "candidate_revision"),
            "steps": steps,
            "criteria_mutable_after_registration": False,
        }

    @property
    def sha256(self) -> str:
        return _sha_json(self.canonical())

    def public_dict(self) -> dict[str, Any]:
        value = self.canonical()
        value["procedure_sha256"] = self.sha256
        value["grants_physical_authority"] = False
        return value


class ValidationProcedureRegistry:
    def __init__(self) -> None:
        self._procedures: dict[str, ValidationProcedure] = {}

    def register(self, procedure: ValidationProcedure) -> None:
        if not isinstance(procedure, ValidationProcedure):
            raise FabricationValidationError("procedure registry requires ValidationProcedure")
        canonical = procedure.canonical()
        pid = canonical["procedure_id"]
        if pid in self._procedures:
            raise FabricationValidationError("validation procedure id already registered")
        self._procedures[pid] = procedure

    def get(self, procedure_id: str) -> ValidationProcedure:
        key = _id(procedure_id, "procedure_id")
        try:
            return self._procedures[key]
        except KeyError as exc:
            raise FabricationValidationError("unknown validation procedure") from exc

    def list_public(self, *, project_id: str | None = None) -> list[dict[str, Any]]:
        values = self._procedures.values()
        if project_id is not None:
            wanted = _id(project_id, "project_id")
            values = [procedure for procedure in values if procedure.project_id == wanted]
        return [procedure.public_dict() for procedure in sorted(values, key=lambda item: item.procedure_id)]


class ValidationEvidenceResolver(Protocol):
    def resolve(self, evidence_id: str) -> PhysicalEvidenceRecord: ...


class MappingEvidenceResolver:
    def __init__(self, records: Sequence[PhysicalEvidenceRecord]) -> None:
        self._records: dict[str, PhysicalEvidenceRecord] = {}
        for record in records:
            if not isinstance(record, PhysicalEvidenceRecord):
                raise FabricationValidationError("evidence resolver requires PhysicalEvidenceRecord objects")
            if record.evidence_id in self._records:
                raise FabricationValidationError("duplicate physical evidence id")
            self._records[record.evidence_id] = record

    def resolve(self, evidence_id: str) -> PhysicalEvidenceRecord:
        key = _id(evidence_id, "evidence_id")
        try:
            return self._records[key]
        except KeyError as exc:
            raise FabricationValidationError("unknown retained physical evidence id") from exc


class ValidationProcedureEvaluator:
    def __init__(self, *, procedures: ValidationProcedureRegistry, evidence: ValidationEvidenceResolver) -> None:
        self.procedures = procedures
        self.evidence = evidence

    def evaluate(self, procedure_id: str, *, evidence_ids: Sequence[str]) -> dict[str, Any]:
        if isinstance(evidence_ids, (str, bytes, bytearray)) or not isinstance(evidence_ids, Sequence):
            raise FabricationValidationError("evidence_ids must be a list")
        if not evidence_ids or len(evidence_ids) > 1000:
            raise FabricationValidationError("validation evaluation requires 1..1000 evidence ids")
        ids = [_id(value, "evidence_id") for value in evidence_ids]
        if len(ids) != len(set(ids)):
            raise FabricationValidationError("evidence ids must be unique")
        procedure = self.procedures.get(procedure_id)
        canonical = procedure.canonical()
        procedure_hash = procedure.sha256
        records = [self.evidence.resolve(evidence_id) for evidence_id in ids]
        by_step: dict[str, list[PhysicalEvidenceRecord]] = {}
        for record in records:
            if record.project_id != canonical["project_id"]:
                raise FabricationValidationError("physical evidence belongs to a different project")
            if record.candidate_revision != canonical["candidate_revision"]:
                raise FabricationValidationError("physical evidence belongs to a different candidate revision")
            metadata = dict(record.metadata or {})
            step_id = metadata.get("validation_step_id")
            if not isinstance(step_id, str):
                raise FabricationValidationError("physical evidence lacks validation_step_id metadata")
            if metadata.get("validation_procedure_sha256") != procedure_hash:
                raise FabricationValidationError("physical evidence is not bound to the frozen validation procedure")
            by_step.setdefault(step_id, []).append(record)

        results: list[dict[str, Any]] = []
        all_passed = True
        for step in canonical["steps"]:
            matches = by_step.get(step["step_id"], [])
            if len(matches) != 1:
                results.append({
                    "step_id": step["step_id"],
                    "status": "MISSING_OR_AMBIGUOUS_EVIDENCE",
                    "evidence_ids": [record.evidence_id for record in matches],
                    "recomputed_passed": False,
                })
                all_passed = False
                continue
            record = matches[0]
            blockers: list[str] = []
            if record.kind.value != step["evidence_kind"]:
                blockers.append("evidence kind does not match frozen step")
            if set(record.target_ids) != set(step["target_ids"]):
                blockers.append("evidence targets do not match frozen step")
            criterion_results = []
            criteria_pass = True
            for criterion in step["criteria"]:
                outcome = _evaluate_criterion(criterion, record.measured_values)
                criterion_results.append(outcome)
                if not outcome["passed"]:
                    criteria_pass = False
            recomputed = not blockers and criteria_pass
            if bool(record.passed) != recomputed:
                blockers.append("retained evidence passed flag disagrees with frozen-criteria recomputation")
                recomputed = False
            if not recomputed:
                all_passed = False
            results.append({
                "step_id": step["step_id"],
                "requirement_ids": step["requirement_ids"],
                "evidence_id": record.evidence_id,
                "criterion_results": criterion_results,
                "blockers": blockers,
                "recomputed_passed": recomputed,
                "status": "PASS" if recomputed else "FAIL",
            })

        used_steps = {step["step_id"] for step in canonical["steps"]}
        unexpected = sorted(step_id for step_id in by_step if step_id not in used_steps)
        if unexpected:
            all_passed = False
        return {
            "schema": "hardware_splicer.validation_procedure_assessment.v1",
            "procedure_id": canonical["procedure_id"],
            "procedure_sha256": procedure_hash,
            "project_id": canonical["project_id"],
            "candidate_revision": canonical["candidate_revision"],
            "steps": results,
            "unexpected_evidence_steps": unexpected,
            "validation_scope_passed": all_passed,
            "whole_device_physical_correctness": "UNPROVEN",
            "grants_physical_authority": False,
        }


def _evaluate_criterion(criterion: Mapping[str, Any], values: Mapping[str, Any]) -> dict[str, Any]:
    key = criterion["value_key"]
    if key not in values:
        return {"criterion": dict(criterion), "passed": False, "reason": "measured value missing"}
    actual = values[key]
    operator = criterion["operator"]
    if operator == "numeric_range":
        if not isinstance(actual, (int, float)) or isinstance(actual, bool) or not math.isfinite(float(actual)):
            return {"criterion": dict(criterion), "actual": actual, "passed": False, "reason": "measured value is not finite numeric"}
        number = float(actual)
        passed = (criterion.get("minimum") is None or number >= criterion["minimum"]) and (
            criterion.get("maximum") is None or number <= criterion["maximum"]
        )
    elif operator == "equals":
        passed = _canonical(actual) == criterion.get("expected")
    elif operator == "text_contains":
        passed = isinstance(actual, str) and criterion["expected"] in actual
    elif operator == "text_not_contains":
        passed = isinstance(actual, str) and criterion["expected"] not in actual
    else:  # pragma: no cover - registration forbids it
        raise FabricationValidationError("unsupported validation criterion operator")
    return {"criterion": dict(criterion), "actual": _canonical(actual), "passed": bool(passed)}


def _finite_or_none(value: Any, field: str) -> float | None:
    if value is None:
        return None
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(float(value)):
        raise FabricationValidationError(f"{field} must be finite")
    return float(value)


def _canonical(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise FabricationValidationError("validation value must be canonical JSON") from exc


def _sha_json(value: Any) -> str:
    encoded = json.dumps(_canonical(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _id(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise FabricationValidationError(f"{field} must be a string")
    cleaned = value.strip()
    if not cleaned or len(cleaned) > 128 or any(not (ch.isalnum() or ch in "._:-") for ch in cleaned):
        raise FabricationValidationError(f"{field} must be a bounded identifier")
    return cleaned
