"""Bounded STEP-first mechanical identity and declared mount reconciliation.

The parser extracts stable file identity, schema, product names, units, and a coarse
Cartesian-point envelope from ISO-10303-21 text. It does not claim full BREP validity,
collision analysis, mass properties, or manufacturing authority. Mount geometry is
reconciled from explicit declared interfaces and tolerances against the selected STEP
model identity.
"""

from __future__ import annotations

import hashlib
import re
from enum import Enum
from math import isfinite
from typing import Any, Dict, Iterable, Mapping

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .machine_project import AuthorityState


STEP_GEOMETRY_SCHEMA = "hardware_splicer.step_geometry.v1"
MECHANICAL_GEOMETRY_SCHEMA = "hardware_splicer.mechanical_geometry_report.v1"
MAX_STEP_BYTES = 20 * 1024 * 1024


class StepBase(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class MechanicalCheckStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"


class StepBoundingBox(StepBase):
    minimum: list[float] = Field(min_length=3, max_length=3)
    maximum: list[float] = Field(min_length=3, max_length=3)
    size: list[float] = Field(min_length=3, max_length=3)
    point_count: int = Field(ge=1)
    units: str = "unknown"


class StepModelSummary(StepBase):
    schema_version: str = STEP_GEOMETRY_SCHEMA
    source_id: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    byte_count: int = Field(ge=1)
    file_schema: list[str] = Field(default_factory=list)
    products: list[str] = Field(default_factory=list)
    units: str = "unknown"
    entity_count: int = Field(ge=0)
    cartesian_point_count: int = Field(ge=0)
    bounding_box: StepBoundingBox | None = None
    authority: AuthorityState = AuthorityState.DECLARED
    unresolved: list[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class HolePattern(StepBase):
    count: int = Field(ge=1)
    spacing_x_mm: float | None = Field(default=None, ge=0.0)
    spacing_y_mm: float | None = Field(default=None, ge=0.0)
    pitch_circle_diameter_mm: float | None = Field(default=None, ge=0.0)
    hole_diameter_mm: float = Field(gt=0.0)
    positional_tolerance_mm: float = Field(default=0.1, ge=0.0)
    diameter_tolerance_mm: float = Field(default=0.1, ge=0.0)
    pattern_kind: str = "declared"


class DeclaredMountInterface(StepBase):
    interface_id: str = Field(min_length=1)
    part_id: str = Field(min_length=1)
    cad_model_id: str = Field(min_length=1)
    mount_type: str = Field(min_length=1)
    mates_with: str | None = None
    datum_frame: str = Field(min_length=1)
    origin_mm: list[float] | None = Field(default=None, min_length=3, max_length=3)
    normal: list[float] | None = Field(default=None, min_length=3, max_length=3)
    hole_pattern: HolePattern | None = None
    fastener_spec: str | None = None
    material: str | None = None
    thickness_mm: float | None = Field(default=None, gt=0.0)
    authority: AuthorityState = AuthorityState.DECLARED
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def declared_mount_cannot_be_physically_verified_by_import(self) -> "DeclaredMountInterface":
        if self.authority in {AuthorityState.VERIFIED, AuthorityState.AUTHORIZED}:
            raise ValueError("imported mount declarations cannot be verified or authorized")
        return self


class MechanicalGeometryCheck(StepBase):
    check_id: str = Field(min_length=1)
    category: str = Field(min_length=1)
    status: MechanicalCheckStatus
    message: str = Field(min_length=1)
    target_ids: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    unresolved_fields: list[str] = Field(default_factory=list)
    blocking: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MechanicalGeometryReport(StepBase):
    schema_version: str = MECHANICAL_GEOMETRY_SCHEMA
    project_id: str
    models: list[StepModelSummary] = Field(default_factory=list)
    mounts: list[DeclaredMountInterface] = Field(default_factory=list)
    checks: list[MechanicalGeometryCheck] = Field(default_factory=list)
    status: str
    required_evidence: list[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def blocking_checks(self) -> list[MechanicalGeometryCheck]:
        return [row for row in self.checks if row.blocking and row.status != MechanicalCheckStatus.PASS]


_STEP_ENTITY_RE = re.compile(r"(?m)^\s*#\d+\s*=", re.ASCII)
_SCHEMA_RE = re.compile(r"FILE_SCHEMA\s*\(\s*\((.*?)\)\s*\)\s*;", re.IGNORECASE | re.DOTALL)
_PRODUCT_RE = re.compile(
    r"PRODUCT\s*\(\s*'([^']*)'\s*,\s*'([^']*)'",
    re.IGNORECASE,
)
_POINT_RE = re.compile(
    r"CARTESIAN_POINT\s*\(\s*'[^']*'\s*,\s*\(([^()]*)\)\s*\)",
    re.IGNORECASE,
)
_SI_UNIT_RE = re.compile(
    r"SI_UNIT\s*\(\s*\.([A-Z]+)\.\s*,\s*\.([A-Z_]+)\.\s*\)",
    re.IGNORECASE,
)
_CONVERSION_MM_RE = re.compile(r"MILLI\s*METRE|MILLIMETRE|MILLIMETER", re.IGNORECASE)


def _slug(value: str, fallback: str) -> str:
    token = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip()).strip("-._").lower()
    return token[:120] or fallback


def _source_text(content: str | bytes) -> tuple[str, bytes]:
    raw = content.encode("utf-8") if isinstance(content, str) else bytes(content)
    if not raw:
        raise ValueError("STEP source is empty")
    if len(raw) > MAX_STEP_BYTES:
        raise ValueError(f"STEP source exceeds {MAX_STEP_BYTES} byte limit")
    if b"\x00" in raw:
        raise ValueError("binary STEP payload is not supported by the bounded text parser")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    if "ISO-10303-21" not in text.upper() or "END-ISO-10303-21" not in text.upper():
        raise ValueError("STEP source must contain ISO-10303-21 boundaries")
    return text, raw


def _parse_numbers(value: str) -> list[float] | None:
    numbers: list[float] = []
    for token in value.split(","):
        cleaned = token.strip()
        if not cleaned or cleaned in {"$", "*"}:
            return None
        try:
            number = float(cleaned)
        except ValueError:
            return None
        if not isfinite(number):
            return None
        numbers.append(number)
    return numbers if len(numbers) == 3 else None


def _detect_units(text: str) -> tuple[str, list[Dict[str, Any]]]:
    unresolved: list[Dict[str, Any]] = []
    matches = _SI_UNIT_RE.findall(text)
    normalized = {(prefix.upper(), unit.upper()) for prefix, unit in matches}
    if ("MILLI", "METRE") in normalized or _CONVERSION_MM_RE.search(text):
        return "mm", unresolved
    if ("", "METRE") in normalized or any(unit == "METRE" and prefix in {"$", "NONE"} for prefix, unit in normalized):
        return "m", unresolved
    unresolved.append(
        {
            "field": "units",
            "reason": "STEP length units were not unambiguously identified.",
        }
    )
    return "unknown", unresolved


def parse_step_model(
    content: str | bytes,
    *,
    source_id: str,
    model_id: str | None = None,
) -> StepModelSummary:
    """Parse bounded STEP identity and a coarse Cartesian-point envelope."""

    text, raw = _source_text(content)
    digest = f"sha256:{hashlib.sha256(raw).hexdigest()}"
    schemas: list[str] = []
    schema_match = _SCHEMA_RE.search(text)
    if schema_match:
        schemas = [
            value.strip().strip("'").strip('"')
            for value in schema_match.group(1).split(",")
            if value.strip()
        ]
    products = list(
        dict.fromkeys(
            value
            for pair in _PRODUCT_RE.findall(text)
            for value in pair
            if value.strip()
        )
    )
    resolved_model_id = _slug(model_id or (products[0] if products else source_id), "step-model")
    units, unresolved = _detect_units(text)
    points = [
        parsed
        for value in _POINT_RE.findall(text)
        if (parsed := _parse_numbers(value)) is not None
    ]
    bounding_box = None
    if points:
        minimum = [min(point[index] for point in points) for index in range(3)]
        maximum = [max(point[index] for point in points) for index in range(3)]
        bounding_box = StepBoundingBox(
            minimum=minimum,
            maximum=maximum,
            size=[maximum[index] - minimum[index] for index in range(3)],
            point_count=len(points),
            units=units,
        )
    else:
        unresolved.append(
            {
                "field": "bounding_box",
                "reason": "No parseable three-dimensional CARTESIAN_POINT entities were found.",
            }
        )
    if not schemas:
        unresolved.append(
            {
                "field": "file_schema",
                "reason": "FILE_SCHEMA was not parsed from the STEP header.",
            }
        )
    return StepModelSummary(
        source_id=source_id,
        model_id=resolved_model_id,
        content_hash=digest,
        byte_count=len(raw),
        file_schema=schemas,
        products=products,
        units=units,
        entity_count=len(_STEP_ENTITY_RE.findall(text)),
        cartesian_point_count=len(points),
        bounding_box=bounding_box,
        authority=AuthorityState.DECLARED,
        unresolved=unresolved,
        metadata={
            "parser": STEP_GEOMETRY_SCHEMA,
            "full_brep_validation": False,
            "collision_analysis": False,
            "mass_properties_verified": False,
            "fabrication_authorized": False,
        },
    )


def _check(
    check_id: str,
    category: str,
    *,
    passed: bool | None,
    message: str,
    target_ids: Iterable[str] = (),
    source_ids: Iterable[str] = (),
    unresolved_fields: Iterable[str] = (),
    blocking: bool = True,
    metadata: Mapping[str, Any] | None = None,
) -> MechanicalGeometryCheck:
    status = (
        MechanicalCheckStatus.PASS
        if passed is True
        else MechanicalCheckStatus.FAIL
        if passed is False
        else MechanicalCheckStatus.UNKNOWN
    )
    return MechanicalGeometryCheck(
        check_id=check_id,
        category=category,
        status=status,
        message=message,
        target_ids=list(dict.fromkeys(str(value) for value in target_ids if value)),
        source_ids=list(dict.fromkeys(str(value) for value in source_ids if value)),
        unresolved_fields=list(dict.fromkeys(str(value) for value in unresolved_fields if value)),
        blocking=blocking,
        metadata=dict(metadata or {}),
    )


def _within(value: float | None, other: float | None, tolerance: float) -> bool | None:
    if value is None or other is None:
        return None
    return abs(value - other) <= tolerance


def _origin_inside(model: StepModelSummary, origin: list[float] | None) -> bool | None:
    if origin is None or model.bounding_box is None:
        return None
    return all(
        model.bounding_box.minimum[index] <= origin[index] <= model.bounding_box.maximum[index]
        for index in range(3)
    )


def _mount_pair_checks(
    left: DeclaredMountInterface,
    right: DeclaredMountInterface,
) -> list[MechanicalGeometryCheck]:
    prefix = f"mount-pair-{_slug(left.interface_id, 'left')}-{_slug(right.interface_id, 'right')}"
    checks = [
        _check(
            f"{prefix}-type",
            "mount_compatibility",
            passed=left.mount_type == right.mount_type,
            message=(
                f"Mount types match for {left.interface_id} and {right.interface_id}."
                if left.mount_type == right.mount_type
                else f"Mount type mismatch: {left.mount_type!r} versus {right.mount_type!r}."
            ),
            target_ids=[left.interface_id, right.interface_id],
        ),
        _check(
            f"{prefix}-fastener",
            "mount_compatibility",
            passed=(
                left.fastener_spec == right.fastener_spec
                if left.fastener_spec and right.fastener_spec
                else None
            ),
            message=(
                f"Fastener specifications match at {left.fastener_spec}."
                if left.fastener_spec and left.fastener_spec == right.fastener_spec
                else "Fastener specification is unresolved or mismatched across the mating mount pair."
            ),
            target_ids=[left.interface_id, right.interface_id],
            unresolved_fields=([] if left.fastener_spec and right.fastener_spec else ["fastener_spec"]),
        ),
    ]
    if left.hole_pattern is None or right.hole_pattern is None:
        checks.append(
            _check(
                f"{prefix}-hole-pattern",
                "mount_compatibility",
                passed=None,
                message="Mating hole-pattern geometry is incomplete.",
                target_ids=[left.interface_id, right.interface_id],
                unresolved_fields=["hole_pattern"],
            )
        )
        return checks
    lp = left.hole_pattern
    rp = right.hole_pattern
    tolerance = lp.positional_tolerance_mm + rp.positional_tolerance_mm
    diameter_tolerance = lp.diameter_tolerance_mm + rp.diameter_tolerance_mm
    comparisons = {
        "count": lp.count == rp.count,
        "spacing_x_mm": _within(lp.spacing_x_mm, rp.spacing_x_mm, tolerance),
        "spacing_y_mm": _within(lp.spacing_y_mm, rp.spacing_y_mm, tolerance),
        "pitch_circle_diameter_mm": _within(
            lp.pitch_circle_diameter_mm,
            rp.pitch_circle_diameter_mm,
            tolerance,
        ),
        "hole_diameter_mm": _within(
            lp.hole_diameter_mm,
            rp.hole_diameter_mm,
            diameter_tolerance,
        ),
    }
    required_geometry = [
        key
        for key in ("spacing_x_mm", "spacing_y_mm", "pitch_circle_diameter_mm")
        if getattr(lp, key) is not None or getattr(rp, key) is not None
    ]
    relevant = ["count", "hole_diameter_mm", *required_geometry]
    unresolved = [key for key in relevant if comparisons[key] is None]
    failed = [key for key in relevant if comparisons[key] is False]
    passed = None if unresolved else not failed
    checks.append(
        _check(
            f"{prefix}-hole-pattern",
            "mount_compatibility",
            passed=passed,
            message=(
                "Mating hole patterns agree within declared tolerances."
                if passed is True
                else f"Mating hole patterns conflict in: {', '.join(failed)}."
                if failed
                else f"Mating hole-pattern fields are unresolved: {', '.join(unresolved)}."
            ),
            target_ids=[left.interface_id, right.interface_id],
            unresolved_fields=unresolved,
            metadata={
                "comparisons": comparisons,
                "positional_tolerance_mm": tolerance,
                "diameter_tolerance_mm": diameter_tolerance,
            },
        )
    )
    return checks


def build_mechanical_geometry_report(
    *,
    project_id: str,
    models: Iterable[StepModelSummary | Mapping[str, Any]],
    mounts: Iterable[DeclaredMountInterface | Mapping[str, Any]],
) -> MechanicalGeometryReport:
    """Reconcile declared mount identity against selected STEP model summaries."""

    resolved_models = [
        value if isinstance(value, StepModelSummary)
        else StepModelSummary.model_validate(value)
        for value in models
    ]
    resolved_mounts = [
        value if isinstance(value, DeclaredMountInterface)
        else DeclaredMountInterface.model_validate(value)
        for value in mounts
    ]
    checks: list[MechanicalGeometryCheck] = []
    model_by_id: dict[str, StepModelSummary] = {}
    duplicate_model_ids: set[str] = set()
    for model in resolved_models:
        if model.model_id in model_by_id:
            duplicate_model_ids.add(model.model_id)
        model_by_id[model.model_id] = model
    for model_id in sorted(duplicate_model_ids):
        checks.append(
            _check(
                f"step-model-identity-{_slug(model_id, 'model')}",
                "identity_collision",
                passed=False,
                message=f"STEP model_id {model_id!r} is declared more than once.",
                source_ids=[model_id],
                unresolved_fields=["selected_model_revision"],
            )
        )
    mount_by_id: dict[str, DeclaredMountInterface] = {}
    duplicate_mount_ids: set[str] = set()
    for mount in resolved_mounts:
        if mount.interface_id in mount_by_id:
            duplicate_mount_ids.add(mount.interface_id)
        mount_by_id[mount.interface_id] = mount
    for interface_id in sorted(duplicate_mount_ids):
        checks.append(
            _check(
                f"mount-identity-{_slug(interface_id, 'mount')}",
                "identity_collision",
                passed=False,
                message=f"Mount interface_id {interface_id!r} is declared more than once.",
                target_ids=[interface_id],
                unresolved_fields=["selected_mount_declaration"],
            )
        )

    for model in resolved_models:
        checks.append(
            _check(
                f"step-envelope-{_slug(model.model_id, 'model')}",
                "step_identity",
                passed=model.bounding_box is not None and model.units != "unknown",
                message=(
                    f"STEP model {model.model_id} has a declared {model.units} point envelope."
                    if model.bounding_box is not None and model.units != "unknown"
                    else f"STEP model {model.model_id} lacks a usable unit-aware point envelope."
                ),
                source_ids=[model.source_id],
                target_ids=[model.model_id],
                unresolved_fields=[row.get("field", "unknown") for row in model.unresolved],
                metadata={
                    "content_hash": model.content_hash,
                    "bounding_box": (
                        model.bounding_box.model_dump(mode="json")
                        if model.bounding_box is not None
                        else None
                    ),
                },
            )
        )

    paired: set[tuple[str, str]] = set()
    for mount in resolved_mounts:
        model = model_by_id.get(mount.cad_model_id)
        checks.append(
            _check(
                f"mount-model-{_slug(mount.interface_id, 'mount')}",
                "mount_model_identity",
                passed=model is not None,
                message=(
                    f"Mount {mount.interface_id} references STEP model {mount.cad_model_id}."
                    if model is not None
                    else f"Mount {mount.interface_id} references unknown STEP model {mount.cad_model_id}."
                ),
                target_ids=[mount.interface_id, mount.part_id],
                source_ids=[mount.cad_model_id],
                unresolved_fields=[] if model is not None else ["cad_model_id"],
            )
        )
        if model is not None:
            inside = _origin_inside(model, mount.origin_mm)
            checks.append(
                _check(
                    f"mount-origin-{_slug(mount.interface_id, 'mount')}",
                    "mount_envelope",
                    passed=inside,
                    message=(
                        f"Declared mount origin for {mount.interface_id} lies inside the STEP point envelope."
                        if inside is True
                        else f"Declared mount origin for {mount.interface_id} lies outside the STEP point envelope."
                        if inside is False
                        else f"Mount origin or STEP envelope is unresolved for {mount.interface_id}."
                    ),
                    target_ids=[mount.interface_id],
                    source_ids=[model.source_id],
                    unresolved_fields=[] if inside is not None else ["origin_mm", "bounding_box"],
                )
            )
        if mount.mates_with:
            mate = mount_by_id.get(mount.mates_with)
            checks.append(
                _check(
                    f"mount-mate-{_slug(mount.interface_id, 'mount')}",
                    "mount_pair_identity",
                    passed=mate is not None and mate.mates_with == mount.interface_id,
                    message=(
                        f"Mount {mount.interface_id} and {mount.mates_with} declare reciprocal mating identity."
                        if mate is not None and mate.mates_with == mount.interface_id
                        else f"Mount {mount.interface_id} does not have a reciprocal mating declaration."
                    ),
                    target_ids=[mount.interface_id, mount.mates_with],
                    unresolved_fields=[] if mate is not None and mate.mates_with == mount.interface_id else ["mates_with"],
                )
            )
            if mate is not None:
                pair = tuple(sorted((mount.interface_id, mate.interface_id)))
                if pair not in paired:
                    checks.extend(_mount_pair_checks(mount, mate))
                    paired.add(pair)
        else:
            checks.append(
                _check(
                    f"mount-mate-{_slug(mount.interface_id, 'mount')}",
                    "mount_pair_identity",
                    passed=None,
                    message=f"Mating interface is unresolved for mount {mount.interface_id}.",
                    target_ids=[mount.interface_id],
                    unresolved_fields=["mates_with"],
                )
            )

    blocking = [row for row in checks if row.blocking and row.status != MechanicalCheckStatus.PASS]
    required_evidence = [
        {
            "check_id": row.check_id,
            "category": row.category,
            "target_ids": row.target_ids,
            "request": f"Capture mechanical evidence closing: {row.message}",
            "required_fields": row.unresolved_fields,
        }
        for row in blocking
    ]
    return MechanicalGeometryReport(
        project_id=project_id,
        models=resolved_models,
        mounts=resolved_mounts,
        checks=checks,
        status="blocked" if blocking else "candidate",
        required_evidence=required_evidence,
        metadata={
            "model_count": len(resolved_models),
            "mount_count": len(resolved_mounts),
            "check_count": len(checks),
            "blocking_check_count": len(blocking),
            "step_point_envelope_only": True,
            "full_brep_validation": False,
            "collision_analysis": False,
            "manufacturing_authorized": False,
            "fabrication_authorized": False,
            "release_authorized": False,
        },
    )
