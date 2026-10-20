"""Product/MCP surface for opt-in computational chemical engineering."""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .chemical_gas import gas_state_report
from .chemical_battery import battery_discharge_report
from .chemical_materials import solid_composition_report
from .chemical_source_bridge import draft_iso75_evidence
from .material_evidence import evaluate_material_evidence, compare_material_candidates
from .machine_project import MachineProject
from .chemical_engineering import (
    EngineUnavailable,
    engines_report,
    mass_balance_report,
    molecule_report,
    property_report,
)


class MoleculeInspectRequest(BaseModel):
    smiles: str = Field(min_length=1, max_length=512)
    source_refs: list[str] = Field(default_factory=list, max_length=32)


class PropertyInspectRequest(BaseModel):
    chemical_id: str = Field(min_length=1, max_length=128)
    temperature_k: float = Field(ge=100, le=2000)
    pressure_pa: float = Field(ge=1000, le=1e8)
    source_refs: list[str] = Field(default_factory=list, max_length=32)


class Stream(BaseModel):
    stream_id: str = Field(min_length=1, max_length=128)
    direction: Literal["inlet", "outlet"]
    mass_flow_kg_h: float = Field(ge=0)
    components_kg_h: dict[str, float] | None = None


class MassBalanceRequest(BaseModel):
    streams: list[Stream] = Field(min_length=2, max_length=100)
    reaction_present: bool = False
    absolute_tolerance_kg_h: float = Field(default=1e-6, ge=0, le=1)
    relative_tolerance: float = Field(default=1e-4, ge=0, le=0.1)



class GasStateRequest(BaseModel):
    temperature_k: float = Field(ge=250, le=1200)
    pressure_pa: float = Field(ge=5e4, le=5e6)
    mole_fractions: dict[str, float] = Field(min_length=1, max_length=3)
    equilibrium: bool = False
    source_refs: list[str] = Field(default_factory=list, max_length=32)


class MaterialEvidenceRequest(BaseModel):
    project: MachineProject
    component_id: str = Field(min_length=1, max_length=128)


class MaterialDocumentClaimRequest(BaseModel):
    claim: dict[str, Any]
    component_id: str = Field(min_length=1, max_length=128)
    constraint_id: str = Field(min_length=1, max_length=128)
    material_id: str = Field(min_length=1, max_length=128)


class MaterialCompareRequest(BaseModel):
    project: MachineProject
    component_ids: list[str] = Field(min_length=2, max_length=20)


class BatteryDischargeRequest(BaseModel):
    c_rate: float = Field(ge=0.1, le=1.0)
    duration_s: float = Field(ge=60, le=3600)
    source_refs: list[str] = Field(default_factory=list, max_length=32)


class MaterialCompositionRequest(BaseModel):
    formula: str = Field(min_length=1, max_length=128)
    source_refs: list[str] = Field(default_factory=list, max_length=32)

def _call(engine: Any, *args: Any, **kwargs: Any) -> dict[str, Any]:
    try:
        return engine(*args, **kwargs)
    except EngineUnavailable as exc:
        raise HTTPException(status_code=503, detail={"type": "optional_engine_missing", "message": str(exc)}) from exc
    except (TypeError, ValueError, OverflowError) as exc:
        raise HTTPException(status_code=422, detail={"type": "invalid_chemical_model_input", "message": str(exc)}) from exc


def create_chemical_router() -> APIRouter:
    router = APIRouter(prefix="/v1/engineering/chemical", tags=["engineering", "chemical"])

    @router.get("/engines")
    def list_chemical_engines() -> dict[str, Any]:
        return engines_report()

    @router.post("/molecule/inspect")
    def inspect_molecule(request: MoleculeInspectRequest) -> dict[str, Any]:
        return _call(molecule_report, request.smiles, source_refs=request.source_refs)

    @router.post("/properties/inspect")
    def inspect_properties(request: PropertyInspectRequest) -> dict[str, Any]:
        return _call(property_report, request.chemical_id, request.temperature_k, request.pressure_pa,
                     source_refs=request.source_refs)

    @router.post("/materials/composition")
    def inspect_solid_composition(request: MaterialCompositionRequest) -> dict[str, Any]:
        return _call(solid_composition_report, request.formula, source_refs=request.source_refs)

    @router.post("/materials/evidence-check")
    def review_material_evidence(request: MaterialEvidenceRequest) -> dict[str, Any]:
        return _call(evaluate_material_evidence, request.project, request.component_id)

    @router.post("/materials/document-claim/evidence-draft")
    def draft_material_document_evidence(request: MaterialDocumentClaimRequest) -> dict[str, Any]:
        return _call(draft_iso75_evidence, request.claim, component_id=request.component_id,
                     constraint_id=request.constraint_id, material_id=request.material_id)

    @router.post("/materials/compare")
    def compare_materials(request: MaterialCompareRequest) -> dict[str, Any]:
        return _call(compare_material_candidates, request.project, request.component_ids)

    @router.post("/battery/discharge")
    def model_battery_discharge(request: BatteryDischargeRequest) -> dict[str, Any]:
        return _call(battery_discharge_report,
                     c_rate=request.c_rate, duration_s=request.duration_s,
                     source_refs=request.source_refs)

    @router.post("/gas/state")
    def inspect_gas_state(request: GasStateRequest) -> dict[str, Any]:
        return _call(gas_state_report,
                     temperature_k=request.temperature_k, pressure_pa=request.pressure_pa,
                     mole_fractions=request.mole_fractions, equilibrium=request.equilibrium,
                     source_refs=request.source_refs)

    @router.post("/process/mass-balance")
    def check_mass_balance(request: MassBalanceRequest) -> dict[str, Any]:
        return _call(mass_balance_report, [row.model_dump() for row in request.streams],
                     reaction_present=request.reaction_present,
                     absolute_tolerance_kg_h=request.absolute_tolerance_kg_h,
                     relative_tolerance=request.relative_tolerance)

    return router
