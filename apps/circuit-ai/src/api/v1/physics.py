from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.api.v1.auth import get_current_user
from src.engines.netlist_io import netlist_from_dict
from src.engines.power_tree_validator import PowerTreeConstraints, SourceCurrentLimit, validate_pcb_power_tree
from src.engines.circuit_physics import CircuitPhysicsEngine
from src.engines.physics_orchestrator import validate_high_level_design, validation_output_to_dict


router = APIRouter(prefix="/physics", tags=["physics"])


class PowerSourceModel(BaseModel):
    type: Literal["usb", "external"] = "usb"
    voltage_v: float = 5.0
    current_limit_a: float = 0.5
    max_trace_drop_v: float = 0.25


class TraceModel(BaseModel):
    length_m: float = Field(..., gt=0)
    width_m: float = Field(..., gt=0)
    copper_oz: float = Field(1.0, gt=0)


class PCBModel(BaseModel):
    vin_trace: Optional[TraceModel] = None
    vout_trace: Optional[TraceModel] = None

    ldo_dropout_v: float = 0.3
    ldo_max_current_a: float = 1.0
    ldo_quiescent_current_a: float = 0.002
    ldo_r_theta_ja: float = 60.0
    ldo_tj_max_c: float = 125.0
    ambient_c: float = 25.0


class DesignRequest(BaseModel):
    microcontroller: str
    components: List[str] = []
    power_source: PowerSourceModel = PowerSourceModel()
    scenario: Literal["typical", "max"] = "max"
    pcb: Optional[PCBModel] = None


class ValidateDesignResponse(BaseModel):
    compiled: Dict[str, Any]
    results: Dict[str, Any]
    issues: List[Dict[str, Any]]



class NetlistSourceLimitModel(BaseModel):
    source_name: str
    max_current_a: float

class NetlistConstraintsModel(BaseModel):
    source_limits: List[NetlistSourceLimitModel] = []
    max_trace_drop_v: float = 0.25

class NetlistValidateRequest(BaseModel):
    netlist: Dict[str, Any]
    constraints: NetlistConstraintsModel = NetlistConstraintsModel()
@router.post("/validate_design", response_model=ValidateDesignResponse)
def validate_design(
    request: DesignRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    try:
        design_dict = request.model_dump()
        out = validate_high_level_design(design_dict)
        payload = validation_output_to_dict(out)
        payload["compiled"]["meta"] = {"user_id": current_user.get("user_id"), "scenario": design_dict.get("scenario")}
        return payload
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.post("/validate_netlist")
def validate_netlist(request: NetlistValidateRequest, current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    net = netlist_from_dict(request.netlist)
    constraints = PowerTreeConstraints(
        source_limits=[SourceCurrentLimit(**sl.model_dump()) for sl in request.constraints.source_limits],
        max_trace_drop_v=request.constraints.max_trace_drop_v,
    )
    results, issues = validate_pcb_power_tree(net, constraints=constraints)
    return {
        "user_id": current_user.get("user_id"),
        "results": {
            "converged": results["converged"],
            "iterations": results["iterations"],
            "node_v": results["solution"].node_v,
            "vsource_i": results["solution"].vsource_i,
        },
        "issues": [i.__dict__ for i in issues],
    }
@router.get("/design_schema")
def design_schema(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    return {"schema": DesignRequest.model_json_schema(), "user_id": current_user.get("user_id")}
@router.get("/components")
def list_components(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    engine = CircuitPhysicsEngine()
    comps = []
    for cid, comp in engine.component_specs.items():
        comps.append({
            "id": cid,
            "name": comp.name,
            "component_type": getattr(comp.component_type, "value", str(comp.component_type)),
            "electrical": {
                "operating_voltage": comp.electrical.operating_voltage,
                "min_voltage": comp.electrical.min_voltage,
                "max_voltage": comp.electrical.max_voltage,
                "typical_current": comp.electrical.typical_current,
                "max_current": comp.electrical.max_current,
                "output_current_max": comp.electrical.output_current_max,
                "logic_level": comp.electrical.logic_level,
            },
        })
    comps.sort(key=lambda x: x["id"])
    return {"count": len(comps), "components": comps, "user_id": current_user.get("user_id")}
