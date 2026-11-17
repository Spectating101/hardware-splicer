"""Revision-bound material requirements and inventory reconciliation.

Assessments live beside the existing project, without advancing its design
revision or altering its engineering/physical authority.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path
import re
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from .project_store import CorruptProject, ProjectNotFound, ProjectStore, RevisionConflict, _atomic_write_json

SCHEMA = "hardware_splicer.material_assessment.v1"
_ID = re.compile(r"materials-[a-f0-9]{32}\Z")
Quantity = Annotated[Decimal, Field(ge=0, le=1_000_000, allow_inf_nan=False, max_digits=16, decimal_places=6)]
Text = Annotated[str, Field(max_length=512)]


class MaterialModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("*", mode="before")
    @classmethod
    def no_boolean_numbers(cls, value, info):
        if info.field_name in {"quantity", "allocated", "catalog_part_id", "expected_revision"} and isinstance(value, bool):
            raise ValueError("boolean values are not quantities or part identifiers")
        return value


class MaterialIdentity(MaterialModel):
    manufacturer: Text = ""
    mpn: Text = ""
    specification: Text = ""
    catalog_part_id: int | None = Field(default=None, ge=1, strict=True)


class MaterialRequirement(MaterialIdentity):
    material_id: str = Field(min_length=1, max_length=96, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    description: str = Field(min_length=1, max_length=512)
    quantity: Quantity = Field(gt=0)
    unit: str = Field(default="ea", min_length=1, max_length=24)
    acquisition: Literal["buy", "make"] = "buy"
    source_ref: Text = ""
    unresolved: list[Text] = Field(default_factory=list, max_length=32)


class InventoryLot(MaterialIdentity):
    stock_id: str = Field(min_length=1, max_length=128)
    quantity: Quantity
    allocated: Quantity = Decimal(0)
    unit: str = Field(default="ea", min_length=1, max_length=24)
    condition: Literal["ok", "unchecked", "damaged", "unavailable"] = "unchecked"
    source_ref: Text = ""
    expires_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def allocation_within_quantity(self):
        if self.allocated > self.quantity:
            raise ValueError("allocated stock exceeds the lot quantity")
        return self


class SupplierReference(MaterialModel):
    catalog_part_id: int = Field(ge=1, strict=True)
    supplier: Text = ""
    sku: Text = ""
    url: Text = ""
    # This is the inventory server's cached supplier data, not a live quote.
    reported_available: Quantity | None = None


class InventoryCapture(MaterialModel):
    source: Literal["declared", "inventree"]
    captured_at: AwareDatetime
    source_url: Text = ""
    simulated: bool = False
    lots: list[InventoryLot] = Field(default_factory=list, max_length=2000)
    suppliers: list[SupplierReference] = Field(default_factory=list, max_length=2000)
    response_sha256: dict[str, str] = Field(default_factory=dict, max_length=2000)

    @field_validator("source_url")
    @classmethod
    def credential_free_url(cls, value):
        if value:
            parsed = urlsplit(value)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
                raise ValueError("inventory source_url must be an HTTP URL without credentials, query or fragment")
        return value

    @model_validator(mode="after")
    def unique_lots(self):
        if len({lot.stock_id for lot in self.lots}) != len(self.lots):
            raise ValueError("duplicate stock lots would double-count inventory")
        return self


def _canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def _digest(value) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _number(value: Decimal) -> str:
    return format(value, "f")


def _same_identity(requirement: MaterialRequirement, lot: InventoryLot, capture: InventoryCapture) -> bool:
    if requirement.catalog_part_id is not None:
        # Explicit catalog bindings belong to this one InvenTree capture.
        return capture.source == "inventree" and requirement.catalog_part_id == lot.catalog_part_id
    if requirement.manufacturer.strip() and requirement.mpn.strip():
        return (requirement.manufacturer.strip().casefold(), requirement.mpn.strip()) == (lot.manufacturer.strip().casefold(), lot.mpn.strip())
    return bool(requirement.specification.strip() and requirement.specification.strip() == lot.specification.strip())


def reconcile_materials(requirements: list[MaterialRequirement], capture: InventoryCapture, *, evaluated_at: datetime, max_age_hours: int = 24) -> dict:
    if not requirements or len(requirements) > 500:
        raise ValueError("expected 1–500 material requirements")
    if len({row.material_id for row in requirements}) != len(requirements):
        raise ValueError("material IDs must be unique")
    if evaluated_at.tzinfo is None or evaluated_at.utcoffset() is None:
        raise ValueError("evaluation time must include a timezone")
    age = (evaluated_at - capture.captured_at).total_seconds()
    current = -300 <= age <= max_age_hours * 3600
    remaining = {lot.stock_id: lot.quantity - lot.allocated for lot in capture.lots}
    rows = []
    for requirement in requirements:
        issues = list(requirement.unresolved)
        exact_identity = bool((requirement.manufacturer.strip() and requirement.mpn.strip()) or requirement.specification.strip())
        if not exact_identity:
            issues.append("exact_identity_missing")
        if not current:
            issues.append("inventory_capture_out_of_date")
        if capture.simulated:
            issues.append("simulated_inventory_is_not_owned_stock")
        needed = requirement.quantity
        allocations, excluded = [], []
        for lot in capture.lots:
            if not _same_identity(requirement, lot, capture):
                continue
            reason = None
            if lot.unit != requirement.unit:
                reason = "unit_mismatch"
            elif lot.condition != "ok":
                reason = "condition_" + lot.condition
            elif lot.expires_at is not None and lot.expires_at <= evaluated_at:
                reason = "expired"
            elif requirement.manufacturer and lot.manufacturer and requirement.manufacturer.strip().casefold() != lot.manufacturer.strip().casefold():
                reason = "manufacturer_conflict"
            elif requirement.mpn and lot.mpn and requirement.mpn.strip() != lot.mpn.strip():
                reason = "mpn_conflict"
            elif requirement.specification.strip() and requirement.specification.strip() != lot.specification.strip():
                reason = "material_specification_not_confirmed"
            if reason:
                excluded.append({"stock_id": lot.stock_id, "reason": reason, "quantity": _number(remaining[lot.stock_id])})
                continue
            if not current or capture.simulated or needed <= 0:
                continue
            taken = min(needed, remaining[lot.stock_id])
            if taken:
                allocations.append({"stock_id": lot.stock_id, "quantity": _number(taken), "source_ref": lot.source_ref})
                remaining[lot.stock_id] -= taken
                needed -= taken
        available = requirement.quantity - needed
        action = ("resolve_identity" if not exact_identity else "reuse" if needed == 0 else requirement.acquisition)
        rows.append({
            **requirement.model_dump(mode="json"),
            "available_for_plan": _number(available), "shortage": _number(needed), "action": action,
            "identity_basis": "explicit_inventory_part_binding" if requirement.catalog_part_id is not None else "exact_manufacturer_and_mpn" if requirement.mpn and requirement.manufacturer else "declared_specification" if exact_identity else "unresolved",
            "planned_allocations": allocations, "excluded_lots": excluded, "issues": issues,
            "supplier_references": [s.model_dump(mode="json") for s in capture.suppliers if requirement.catalog_part_id is not None and s.catalog_part_id == requirement.catalog_part_id],
        })
    return {
        "schema_version": "hardware_splicer.material_reconciliation.v1",
        "evaluated_at": evaluated_at.isoformat(), "inventory_current_at_evaluation": current,
        "lines": rows,
        "summary": {
            "required_lines": len(rows),
            "fully_covered_lines": sum(Decimal(row["shortage"]) == 0 for row in rows),
            "shortage_lines": sum(Decimal(row["shortage"]) > 0 for row in rows),
            "unresolved_lines": sum(bool(row["issues"]) for row in rows),
            "buy_lines": sum(row["action"] == "buy" for row in rows),
            "make_lines": sum(row["action"] == "make" for row in rows),
        },
        "stock_reserved": False, "supplier_stock_live_verified": False,
        "engineering_compatibility": "not_assessed_by_inventory_reconciliation",
        "purchase_ready": False, "physical_authority_granted": False,
    }


def _directory(store: ProjectStore, project_id: str) -> Path:
    project = store._project_dir(project_id)
    directory = (project / "material_assessments").resolve()
    if directory.parent != project:
        raise CorruptProject("material assessment directory escapes the project")
    return directory


def assess_project_materials(store: ProjectStore, project_id: str, *, expected_revision: int, requirements: list[dict | MaterialRequirement], inventory: dict | InventoryCapture, _inventory_provenance: str = "provided_snapshot") -> dict:
    if isinstance(expected_revision, bool) or not isinstance(expected_revision, int) or expected_revision < 1:
        raise ValueError("expected_revision must be a positive integer")
    envelope = store.load(project_id)
    if envelope["revision"] != expected_revision:
        raise RevisionConflict("The project changed. Reload before assessing materials.")
    if not isinstance(requirements, list) or not 1 <= len(requirements) <= 500:
        raise ValueError("expected 1–500 material requirements")
    requirements = [MaterialRequirement.model_validate(row) for row in requirements]
    capture = InventoryCapture.model_validate(inventory)
    now = datetime.now(timezone.utc)
    report = reconcile_materials(requirements, capture, evaluated_at=now)
    record = {
        "schema_version": SCHEMA, "project_id": project_id, "source_revision": expected_revision,
        "source_snapshot_sha256": _digest(envelope["snapshot"]),
        "requirements": [row.model_dump(mode="json") for row in requirements],
        "inventory": capture.model_dump(mode="json"), "report": report,
        "inventory_provenance": _inventory_provenance,
    }
    record["assessment_id"] = "materials-" + _digest(record)[:32]
    if len(_canonical(record)) > 2_000_000:
        raise ValueError("material assessment exceeds 2 MB")
    if store.load(project_id)["revision"] != expected_revision:
        raise RevisionConflict("The project changed while assessing materials.")
    path = _directory(store, project_id) / (record["assessment_id"] + ".json")
    _atomic_write_json(path, record, exclusive=True)
    return load_material_assessment(store, project_id, record["assessment_id"])


def load_material_assessment(store: ProjectStore, project_id: str, assessment_id: str) -> dict:
    if not _ID.fullmatch(assessment_id):
        raise ValueError("invalid material assessment ID")
    directory = _directory(store, project_id)
    path = directory / (assessment_id + ".json")
    if path.is_symlink():
        raise CorruptProject("unsafe material assessment")
    if not path.is_file():
        raise ProjectNotFound("Material assessment not found in this project.")
    if path.stat().st_size > 2_000_000:
        raise CorruptProject("unsafe material assessment")
    try:
        record = json.loads(path.read_text())
        if not isinstance(record, dict):
            raise CorruptProject("material assessment must be an object")
        if set(record) != {"schema_version", "project_id", "source_revision", "source_snapshot_sha256",
                           "requirements", "inventory", "report", "inventory_provenance", "assessment_id"}:
            raise CorruptProject("material assessment has unexpected fields")
        if type(record["source_revision"]) is not int or record["source_revision"] < 1:
            raise CorruptProject("material assessment has an invalid source revision")
        if record["inventory_provenance"] not in {"provided_snapshot", "inventree_http_read"}:
            raise CorruptProject("material assessment has an invalid inventory origin")
        unsigned = {key: value for key, value in record.items() if key != "assessment_id"}
        if record["schema_version"] != SCHEMA or record["project_id"] != project_id or record["assessment_id"] != assessment_id or "materials-" + _digest(unsigned)[:32] != assessment_id:
            raise CorruptProject("material assessment identity/hash mismatch")
        source = store.load(project_id, record["source_revision"])
        if _digest(source["snapshot"]) != record["source_snapshot_sha256"]:
            raise CorruptProject("material assessment source revision changed")
        capture = InventoryCapture.model_validate(record["inventory"])
        calculated = reconcile_materials([MaterialRequirement.model_validate(row) for row in record["requirements"]], capture, evaluated_at=datetime.fromisoformat(record["report"]["evaluated_at"]))
        if calculated != record["report"]:
            raise CorruptProject("material assessment claims differ from inputs")
    except (KeyError, TypeError, ValueError) as exc:
        raise CorruptProject("invalid material assessment") from exc
    age = (datetime.now(timezone.utc) - capture.captured_at).total_seconds()
    return {"ok": True, "assessment": record,
            "current_for_project": store.load(project_id)["revision"] == record["source_revision"],
            "inventory_current_now": -300 <= age <= 86400}


def import_inventree_materials(store: ProjectStore, project_id: str, *, expected_revision: int, assembly_part_id: int, build_quantity: int = 1, client=None) -> dict:
    if isinstance(expected_revision, bool) or not isinstance(expected_revision, int) or expected_revision < 1:
        raise ValueError("expected_revision must be a positive integer")
    if store.load(project_id)["revision"] != expected_revision:
        raise RevisionConflict("The project changed. Reload before importing materials.")
    from .integrations.inventree import InvenTreeClient

    client = client or InvenTreeClient.from_env()
    requirements, inventory = client.read_assembly(assembly_part_id, build_quantity=build_quantity)
    return assess_project_materials(store, project_id, expected_revision=expected_revision,
                                    requirements=requirements, inventory=inventory, _inventory_provenance="inventree_http_read")


def list_material_assessments(store: ProjectStore, project_id: str) -> dict:
    store.load(project_id)
    paths = list(_directory(store, project_id).glob("materials-*.json"))
    if len(paths) > 200:
        raise ValueError("material assessment listing exceeds 200 records")
    results = []
    for path in paths:
        result = load_material_assessment(store, project_id, path.stem)
        record = result["assessment"]
        results.append({"assessment_id": record["assessment_id"], "source_revision": record["source_revision"],
                        "evaluated_at": record["report"]["evaluated_at"], "summary": record["report"]["summary"],
                        "current_for_project": result["current_for_project"],
                        "inventory_current_now": result["inventory_current_now"]})
    return {"ok": True, "assessments": sorted(results, key=lambda row: row["evaluated_at"], reverse=True)}


def material_csv(record: dict) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    fields = ["material_id", "description", "manufacturer", "mpn", "specification", "unit",
              "quantity", "available_for_plan", "shortage", "action", "source_ref", "issues"]
    writer.writerow(fields)
    for row in record["report"]["lines"]:
        values = [row[field] if field != "issues" else "; ".join(row[field]) for field in fields]
        # Preserve untrusted part descriptions as text in spreadsheet readers.
        writer.writerow(["'" + value if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r")) else value for value in values])
    return output.getvalue()
