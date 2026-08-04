"""Cross-domain manufacturing closure for guided hardware and robotics projects.

The closure graph reconciles design identities across electrical, firmware, harness,
BOM, physical assembly, CAD, and fabrication artifacts.  It is deliberately
fail-closed: absence, ambiguity, or mixed revisions become blockers rather than being
interpreted as manufacturing readiness.
"""

from __future__ import annotations

import hashlib
import json
from enum import Enum
from typing import Any, Dict, Iterable, Mapping

from pydantic import BaseModel, ConfigDict, Field

from .machine_project import MachineProject


MANUFACTURING_CLOSURE_SCHEMA = "hardware_splicer.manufacturing_closure.v1"


class ClosureBase(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class ClosureStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


class ClosureSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ClosureCheck(ClosureBase):
    check_id: str = Field(min_length=1)
    category: str = Field(min_length=1)
    status: ClosureStatus
    severity: ClosureSeverity = ClosureSeverity.ERROR
    message: str = Field(min_length=1)
    source_ids: list[str] = Field(default_factory=list)
    target_ids: list[str] = Field(default_factory=list)
    unresolved_fields: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def blocking(self) -> bool:
        return self.severity == ClosureSeverity.ERROR and self.status != ClosureStatus.PASS


class ManufacturingClosureReport(ClosureBase):
    schema_version: str = MANUFACTURING_CLOSURE_SCHEMA
    project_id: str = Field(min_length=1)
    candidate_revision: str | None = None
    checks: list[ClosureCheck] = Field(default_factory=list)
    identity_matrix: Dict[str, Any] = Field(default_factory=dict)
    required_evidence: list[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def blocking_checks(self) -> list[ClosureCheck]:
        return [row for row in self.checks if row.blocking]

    @property
    def warning_checks(self) -> list[ClosureCheck]:
        return [row for row in self.checks if row.severity == ClosureSeverity.WARNING and row.status != ClosureStatus.PASS]

    @property
    def status(self) -> str:
        if self.blocking_checks:
            return "blocked"
        if any(row.status in {ClosureStatus.UNKNOWN, ClosureStatus.BLOCKED} for row in self.checks):
            return "candidate"
        return "closed"


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, Mapping):
        result: list[dict[str, Any]] = []
        for key, item in value.items():
            if isinstance(item, Mapping):
                row = dict(item)
                row.setdefault("id", str(key))
                result.append(row)
            elif isinstance(item, list):
                result.extend(dict(row) for row in item if isinstance(row, Mapping))
        return result
    if isinstance(value, (list, tuple)):
        return [dict(row) for row in value if isinstance(row, Mapping)]
    return []


def _first_value(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def _id(row: Mapping[str, Any], *fields: str, fallback: str = "") -> str:
    for field in fields:
        value = row.get(field)
        if value not in (None, ""):
            return str(value)
    return fallback


def _quantity(row: Mapping[str, Any]) -> int:
    raw = _first_value(row.get("quantity"), row.get("qty"), row.get("count"), 1)
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return 0


def _canonical(value: Any) -> str:
    return str(value or "").strip().lower().replace(" ", "-").replace("_", "-")


def _fingerprint(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


def _check(
    check_id: str,
    category: str,
    *,
    passed: bool | None,
    message: str,
    source_ids: Iterable[str] = (),
    target_ids: Iterable[str] = (),
    unresolved_fields: Iterable[str] = (),
    evidence_ids: Iterable[str] = (),
    severity: ClosureSeverity = ClosureSeverity.ERROR,
    metadata: Mapping[str, Any] | None = None,
) -> ClosureCheck:
    status = ClosureStatus.PASS if passed is True else ClosureStatus.FAIL if passed is False else ClosureStatus.UNKNOWN
    return ClosureCheck(
        check_id=check_id,
        category=category,
        status=status,
        severity=severity,
        message=message,
        source_ids=sorted({str(value) for value in source_ids if value}),
        target_ids=sorted({str(value) for value in target_ids if value}),
        unresolved_fields=sorted({str(value) for value in unresolved_fields if value}),
        evidence_ids=sorted({str(value) for value in evidence_ids if value}),
        metadata=dict(metadata or {}),
    )


def _collect(plan: Mapping[str, Any], intake: Mapping[str, Any]) -> Dict[str, list[dict[str, Any]]]:
    normalized = _mapping(plan.get("normalized_intake"))
    scenario = _mapping(plan.get("scenario"))
    compile_spec = _mapping(scenario.get("compile_spec"))
    machine = _mapping(plan.get("machine_project"))
    discipline = _mapping(machine.get("discipline_payloads"))

    sources = [intake, normalized, plan, compile_spec, discipline]

    def gather(*keys: str) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for source in sources:
            for key in keys:
                result.extend(_rows(source.get(key)))
        return result

    return {
        "electrical_components": gather("electrical_components", "components", "parts"),
        "electrical_pins": gather("electrical_pins", "pin_assignments", "pins"),
        "nets": gather("nets", "electrical_nets"),
        "firmware_pins": gather("firmware_pins", "firmware_pin_map", "pin_map"),
        "connectors": gather("connectors", "connector_instances"),
        "harnesses": gather("harnesses", "cables", "wire_harnesses"),
        "bom": gather("bom", "bom_rows", "bill_of_materials", "shopping_list"),
        "instances": gather("physical_instances", "part_instances", "assembly_instances"),
        "fasteners": gather("fasteners", "fastener_schedule"),
        "assembly_steps": gather("assembly_steps", "assembly", "build_steps"),
        "mounts": gather("mounts", "mechanical_mounts", "mounting_interfaces"),
        "cad": gather("cad_models", "step_models", "mechanical_models"),
        "fabrication": gather("fabrication_artifacts", "manufacturing_artifacts", "release_artifacts"),
    }


def _electrical_firmware_checks(data: Mapping[str, list[dict[str, Any]]]) -> list[ClosureCheck]:
    electrical = data["electrical_pins"]
    firmware = data["firmware_pins"]
    checks: list[ClosureCheck] = []
    if not electrical:
        checks.append(_check("electrical-pin-map-present", "electrical_firmware", passed=None, message="No canonical electrical pin map was supplied.", unresolved_fields=["electrical_pins"]))
    if not firmware:
        checks.append(_check("firmware-pin-map-present", "electrical_firmware", passed=None, message="No firmware pin map was supplied.", unresolved_fields=["firmware_pins"]))
    if not electrical or not firmware:
        return checks

    electrical_index: dict[tuple[str, str], str] = {}
    for row in electrical:
        component = _canonical(_id(row, "component_id", "component", "device_id"))
        pin = _canonical(_id(row, "pin", "pin_id", "pad", "port"))
        net = _canonical(_id(row, "net", "net_id", "signal"))
        if component and pin and net:
            electrical_index[(component, pin)] = net

    firmware_index: dict[tuple[str, str], str] = {}
    for row in firmware:
        component = _canonical(_id(row, "component_id", "controller_id", "device_id", fallback="controller"))
        pin = _canonical(_id(row, "physical_pin", "pin", "pad", "gpio"))
        net = _canonical(_id(row, "net", "net_id", "signal", "function"))
        if component and pin and net:
            firmware_index[(component, pin)] = net

    all_keys = sorted(set(electrical_index) | set(firmware_index))
    for component, pin in all_keys:
        electrical_net = electrical_index.get((component, pin))
        firmware_net = firmware_index.get((component, pin))
        check_id = f"pin-{component}-{pin}"
        if electrical_net is None or firmware_net is None:
            checks.append(
                _check(
                    check_id,
                    "electrical_firmware",
                    passed=False,
                    message=f"Pin {component}.{pin} is not represented in both electrical and firmware maps.",
                    source_ids=[component],
                    target_ids=[pin],
                    unresolved_fields=["electrical_net" if electrical_net is None else "firmware_net"],
                    metadata={"electrical_net": electrical_net, "firmware_net": firmware_net},
                )
            )
        else:
            checks.append(
                _check(
                    check_id,
                    "electrical_firmware",
                    passed=electrical_net == firmware_net,
                    message=(
                        f"Electrical and firmware identity agree for {component}.{pin}."
                        if electrical_net == firmware_net
                        else f"Electrical net {electrical_net!r} conflicts with firmware net {firmware_net!r} at {component}.{pin}."
                    ),
                    source_ids=[component],
                    target_ids=[pin, electrical_net, firmware_net],
                    metadata={"electrical_net": electrical_net, "firmware_net": firmware_net},
                )
            )
    return checks


def _connector_harness_checks(data: Mapping[str, list[dict[str, Any]]]) -> list[ClosureCheck]:
    connectors = data["connectors"]
    harnesses = data["harnesses"]
    checks: list[ClosureCheck] = []
    connector_ids = {_canonical(_id(row, "connector_id", "instance_id", "id", "name")) for row in connectors}
    connector_ids.discard("")
    if not connectors:
        checks.append(_check("connector-inventory-present", "connector_harness", passed=None, message="No connector instance inventory was supplied.", unresolved_fields=["connectors"]))
    if not harnesses:
        checks.append(_check("harness-definition-present", "connector_harness", passed=None, message="No harness or cable definitions were supplied.", unresolved_fields=["harnesses"]))
    for index, row in enumerate(connectors):
        connector_id = _canonical(_id(row, "connector_id", "instance_id", "id", "name", fallback=f"connector-{index + 1}"))
        mate = _canonical(_id(row, "mates_with", "mate_id", "mating_connector_id"))
        checks.append(
            _check(
                f"connector-mate-{connector_id}",
                "connector_harness",
                passed=bool(mate and mate in connector_ids),
                message=(f"Connector {connector_id} has a declared mating connector {mate}." if mate and mate in connector_ids else f"Connector {connector_id} has no resolvable mating connector."),
                source_ids=[connector_id],
                target_ids=[mate],
                unresolved_fields=[] if mate and mate in connector_ids else ["mating_connector_id"],
            )
        )
    for index, row in enumerate(harnesses):
        harness_id = _canonical(_id(row, "harness_id", "cable_id", "id", "name", fallback=f"harness-{index + 1}"))
        endpoints = row.get("endpoints") if isinstance(row.get("endpoints"), (list, tuple)) else [row.get("from"), row.get("to")]
        endpoint_ids = [_canonical(value.get("connector_id") if isinstance(value, Mapping) else value) for value in endpoints if value]
        valid = len(endpoint_ids) >= 2 and all(value in connector_ids for value in endpoint_ids)
        conductors = row.get("conductors") if isinstance(row.get("conductors"), list) else []
        checks.append(
            _check(
                f"harness-endpoints-{harness_id}",
                "connector_harness",
                passed=valid,
                message=(f"Harness {harness_id} endpoints resolve to declared connectors." if valid else f"Harness {harness_id} has unresolved connector endpoints."),
                source_ids=[harness_id],
                target_ids=endpoint_ids,
                unresolved_fields=[] if valid else ["endpoints"],
            )
        )
        checks.append(
            _check(
                f"harness-conductors-{harness_id}",
                "connector_harness",
                passed=bool(conductors),
                message=(f"Harness {harness_id} has an explicit conductor schedule." if conductors else f"Harness {harness_id} lacks a conductor/pin schedule."),
                source_ids=[harness_id],
                unresolved_fields=[] if conductors else ["conductors"],
            )
        )
    return checks


def _bom_instance_checks(data: Mapping[str, list[dict[str, Any]]]) -> list[ClosureCheck]:
    bom = data["bom"]
    instances = data["instances"]
    checks: list[ClosureCheck] = []
    if not bom:
        checks.append(_check("bom-present", "bom_instances", passed=None, message="No release BOM was supplied.", unresolved_fields=["bom"]))
        return checks
    bom_qty: dict[str, int] = {}
    for row in bom:
        part_id = _canonical(_id(row, "part_id", "component_id", "mpn", "sku", "name"))
        if part_id:
            bom_qty[part_id] = bom_qty.get(part_id, 0) + _quantity(row)
    instance_qty: dict[str, int] = {}
    for row in instances:
        part_id = _canonical(_id(row, "part_id", "component_id", "mpn", "sku", "name"))
        if part_id:
            instance_qty[part_id] = instance_qty.get(part_id, 0) + _quantity(row)
    for part_id in sorted(set(bom_qty) | set(instance_qty)):
        required = instance_qty.get(part_id, 0)
        supplied = bom_qty.get(part_id, 0)
        checks.append(
            _check(
                f"bom-quantity-{part_id}",
                "bom_instances",
                passed=required > 0 and supplied >= required,
                message=(
                    f"BOM quantity {supplied} covers {required} physical instances of {part_id}."
                    if required > 0 and supplied >= required
                    else f"BOM/instance quantity mismatch for {part_id}: BOM={supplied}, instances={required}."
                ),
                source_ids=[part_id],
                metadata={"bom_quantity": supplied, "instance_quantity": required},
                unresolved_fields=["physical_instances"] if required == 0 else [],
            )
        )
    if not instances:
        checks.append(_check("physical-instance-register-present", "bom_instances", passed=None, message="No physical instance register was supplied; BOM quantity cannot prove assembly completeness.", unresolved_fields=["physical_instances"]))
    return checks


def _mechanical_assembly_checks(data: Mapping[str, list[dict[str, Any]]]) -> list[ClosureCheck]:
    fasteners = data["fasteners"]
    steps = data["assembly_steps"]
    mounts = data["mounts"]
    cad = data["cad"]
    checks: list[ClosureCheck] = []
    step_text = " ".join(json.dumps(row, sort_keys=True, default=str) for row in steps).lower()
    mount_ids = {_canonical(_id(row, "mount_id", "interface_id", "id", "name")) for row in mounts}
    cad_ids = {_canonical(_id(row, "cad_id", "model_id", "part_id", "id", "name")) for row in cad}
    mount_ids.discard("")
    cad_ids.discard("")
    for index, row in enumerate(fasteners):
        fastener_id = _canonical(_id(row, "fastener_id", "part_id", "id", "name", fallback=f"fastener-{index + 1}"))
        referenced = fastener_id in step_text or any(token and token in step_text for token in (_canonical(row.get("size")), _canonical(row.get("thread"))))
        checks.append(
            _check(
                f"fastener-assembly-{fastener_id}",
                "mechanical_assembly",
                passed=referenced,
                message=(f"Fastener {fastener_id} is referenced by the assembly procedure." if referenced else f"Fastener {fastener_id} is absent from the assembly procedure."),
                source_ids=[fastener_id],
                unresolved_fields=[] if referenced else ["assembly_step"],
            )
        )
    for index, row in enumerate(mounts):
        mount_id = _canonical(_id(row, "mount_id", "interface_id", "id", "name", fallback=f"mount-{index + 1}"))
        cad_ref = _canonical(_id(row, "cad_id", "model_id", "step_model_id", "geometry_ref"))
        checks.append(
            _check(
                f"mount-cad-{mount_id}",
                "mechanical_assembly",
                passed=bool(cad_ref and cad_ref in cad_ids),
                message=(f"Mount {mount_id} resolves to CAD model {cad_ref}." if cad_ref and cad_ref in cad_ids else f"Mount {mount_id} has no resolvable CAD/STEP model."),
                source_ids=[mount_id],
                target_ids=[cad_ref],
                unresolved_fields=[] if cad_ref and cad_ref in cad_ids else ["cad_model"],
            )
        )
    if not fasteners:
        checks.append(_check("fastener-schedule-present", "mechanical_assembly", passed=None, message="No fastener schedule was supplied.", unresolved_fields=["fasteners"]))
    if not steps:
        checks.append(_check("assembly-procedure-present", "mechanical_assembly", passed=None, message="No assembly procedure was supplied.", unresolved_fields=["assembly_steps"]))
    if not mounts:
        checks.append(_check("mount-register-present", "mechanical_assembly", passed=None, message="No mechanical mount/interface register was supplied.", unresolved_fields=["mounts"]))
    if not cad:
        checks.append(_check("cad-register-present", "mechanical_assembly", passed=None, message="No CAD/STEP model register was supplied.", unresolved_fields=["cad_models"]))
    return checks


def _revision_checks(data: Mapping[str, list[dict[str, Any]]], candidate_revision: str | None) -> list[ClosureCheck]:
    artifacts = data["fabrication"]
    checks: list[ClosureCheck] = []
    if not artifacts:
        return [_check("fabrication-artifacts-present", "release_boundary", passed=None, message="No fabrication/release artifact register was supplied.", unresolved_fields=["fabrication_artifacts"])]
    revisions: dict[str, str] = {}
    for index, row in enumerate(artifacts):
        artifact_id = _canonical(_id(row, "artifact_id", "id", "name", "path", fallback=f"artifact-{index + 1}"))
        revision = str(_first_value(row.get("revision"), row.get("source_revision"), row.get("commit"), row.get("version")) or "")
        content_hash = str(_first_value(row.get("content_hash"), row.get("sha256"), row.get("hash")) or "")
        revisions[artifact_id] = revision
        checks.append(
            _check(
                f"artifact-pinned-{artifact_id}",
                "release_boundary",
                passed=bool(revision and content_hash),
                message=(f"Artifact {artifact_id} is pinned to revision and content hash." if revision and content_hash else f"Artifact {artifact_id} is not pinned to both revision and content hash."),
                source_ids=[artifact_id],
                unresolved_fields=[field for field, value in (("revision", revision), ("content_hash", content_hash)) if not value],
                metadata={"revision": revision, "content_hash": content_hash},
            )
        )
    nonempty = {value for value in revisions.values() if value}
    expected = str(candidate_revision or "")
    coherent = bool(nonempty) and len(nonempty) == 1 and (not expected or expected in nonempty)
    checks.append(
        _check(
            "fabrication-revision-coherence",
            "release_boundary",
            passed=coherent,
            message=(f"Fabrication artifacts share revision {next(iter(nonempty))}." if coherent else f"Fabrication artifacts cross revision boundaries: {sorted(nonempty)}; candidate={expected or 'unspecified'}."),
            source_ids=revisions.keys(),
            target_ids=nonempty,
            unresolved_fields=[] if coherent else ["candidate_revision", "artifact_revision"],
            metadata={"artifact_revisions": revisions, "candidate_revision": expected or None},
        )
    )
    return checks


def build_manufacturing_closure(
    plan: Mapping[str, Any],
    *,
    intake: Mapping[str, Any] | None = None,
    project: MachineProject | Mapping[str, Any] | None = None,
) -> ManufacturingClosureReport:
    """Reconcile manufacturing identities and produce explicit closure blockers."""

    body = dict(intake or {})
    project_value = project.model_dump(mode="json") if isinstance(project, MachineProject) else _mapping(project or plan.get("machine_project"))
    project_id = str(project_value.get("project_id") or body.get("project_name") or plan.get("project_name") or "engineering-project")
    candidate_revision = _first_value(
        plan.get("candidate_revision"),
        body.get("candidate_revision"),
        _mapping(body.get("change_request")).get("candidate_revision"),
        project_value.get("metadata", {}).get("candidate_revision") if isinstance(project_value.get("metadata"), Mapping) else None,
    )
    candidate_revision_text = str(candidate_revision) if candidate_revision not in (None, "") else None
    data = _collect(plan, body)

    checks: list[ClosureCheck] = []
    checks.extend(_electrical_firmware_checks(data))
    checks.extend(_connector_harness_checks(data))
    checks.extend(_bom_instance_checks(data))
    checks.extend(_mechanical_assembly_checks(data))
    checks.extend(_revision_checks(data, candidate_revision_text))

    required_evidence = [
        {
            "check_id": row.check_id,
            "category": row.category,
            "target_ids": row.target_ids,
            "request": f"Capture evidence closing: {row.message}",
            "required_fields": row.unresolved_fields,
        }
        for row in checks
        if row.blocking
    ]
    identity_matrix = {
        key: {
            "count": len(rows),
            "ids": sorted(
                {
                    _canonical(_id(row, "id", "component_id", "part_id", "connector_id", "harness_id", "artifact_id", "name"))
                    for row in rows
                    if _id(row, "id", "component_id", "part_id", "connector_id", "harness_id", "artifact_id", "name")
                }
            ),
        }
        for key, rows in data.items()
    }
    return ManufacturingClosureReport(
        project_id=project_id,
        candidate_revision=candidate_revision_text,
        checks=checks,
        identity_matrix=identity_matrix,
        required_evidence=required_evidence,
        metadata={
            "input_fingerprint": _fingerprint(data),
            "blocking_check_count": len([row for row in checks if row.blocking]),
            "warning_check_count": len([row for row in checks if row.severity == ClosureSeverity.WARNING and row.status != ClosureStatus.PASS]),
            "manufacturing_authorized": False,
            "fabrication_authorized": False,
            "release_authorized": False,
        },
    )
