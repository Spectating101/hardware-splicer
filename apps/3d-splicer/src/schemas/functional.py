from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Union
from enum import Enum

class BoardBBox(BaseModel):
    x: float = Field(..., description="Width in mm")
    y: float = Field(..., description="Height in mm") 
    z: float = Field(..., description="Thickness in mm")

class MountPoint(BaseModel):
    type: Literal["standoff", "screw", "snap"]
    pos: List[float] = Field(..., min_items=2, max_items=2, description="Position [x, y] in mm")
    dia: float = Field(..., description="Diameter in mm")
    height: Optional[float] = Field(None, description="Height in mm")

class KeepoutRegion(BaseModel):
    shape: Literal["rect", "circle"]
    at: List[float] = Field(..., min_items=2, max_items=2, description="Center position [x, y]")
    size: Optional[List[float]] = Field(None, min_items=2, max_items=2, description="Size [width, height] or [diameter, height]")
    z: Optional[List[float]] = Field(None, min_items=2, max_items=2, description="Z range [min, max]")

class IOConnector(BaseModel):
    type: Literal["usb", "hdmi", "ethernet", "power", "audio", "custom"]
    edge: Literal["north", "south", "east", "west"]
    offset_mm: float = Field(..., description="Offset along edge in mm")
    slot: Optional[List[float]] = Field(None, min_items=2, max_items=2, description="Slot dimensions [width, height]")

class Context(BaseModel):
    board_bbox_mm: BoardBBox
    mounts: Optional[List[MountPoint]] = []
    keepouts: Optional[List[KeepoutRegion]] = []
    io: Optional[List[IOConnector]] = []

class FunctionalRequirement(BaseModel):
    id: str
    goal: Literal[
        "drop_protection",
        "thermal_clearance", 
        "toolless_access",
        "water_resistance",
        "electromagnetic_shielding",
        "accessibility"
    ]
    # Drop protection parameters
    absorb_energy_J: Optional[float] = Field(None, ge=0, description="Energy absorption requirement in Joules")
    max_strain_pct: Optional[float] = Field(None, ge=0, le=100, description="Maximum strain percentage")
    
    # Thermal parameters
    min_air_gap_mm: Optional[float] = Field(None, ge=0, description="Minimum air gap for thermal clearance")
    
    # Accessibility parameters
    max_open_time_s: Optional[float] = Field(None, ge=0, description="Maximum time to open case")
    
    # Water resistance
    ip_rating: Optional[Literal["IP54", "IP65", "IP67"]] = Field(None, description="IP protection rating")
    
    # EM shielding
    shielding_db: Optional[float] = Field(None, ge=0, description="Shielding effectiveness in dB")
    
    # Accessibility rating
    accessibility_rating: Optional[Literal["basic", "enhanced", "universal"]] = Field(None, description="Accessibility level")

class Constraint(BaseModel):
    id: str
    rule: Literal[
        "overall_envelope_mm",
        "no_geometry_in_keepouts", 
        "printability:overhang_angle_deg",
        "printability:min_wall_thickness_mm",
        "printability:no_non_manifold",
        "assembly:clearance_mm"
    ]
    value: Optional[Union[float, str]] = Field(None, description="Constraint value (number or string)")
    operator: Optional[Literal["<=", ">=", "==", "!="]] = Field("<=", description="Comparison operator")

class Materials(BaseModel):
    primary: Literal["PLA", "PETG", "ABS", "TPU", "Nylon"] = "PLA"
    infill_pct: float = Field(20, ge=0, le=100, description="Infill percentage")
    layer_height_mm: float = Field(0.2, ge=0.1, le=0.5, description="Layer height in mm")
    wall_count: int = Field(2, ge=1, le=10, description="Number of wall layers")

class Tolerances(BaseModel):
    fit_mm: float = Field(0.3, ge=0, description="Fit tolerance in mm")
    hole_dia_mm: float = Field(0.2, ge=0, description="Hole diameter tolerance in mm")
    surface_roughness_um: Optional[float] = Field(None, ge=0, description="Surface roughness in microns")

class IterationBudget(BaseModel):
    max_iters: int = Field(8, ge=1, le=20, description="Maximum iterations")
    max_seconds: int = Field(300, ge=30, le=1800, description="Maximum time in seconds")

class Outputs(BaseModel):
    stl: bool = True
    glb_preview: bool = True
    report: Literal["markdown", "json", "none"] = "markdown"

class FunctionalSpec(BaseModel):
    """Functional specification for 3D case generation"""
    id: str = Field(..., description="Unique identifier")
    context: Context = Field(..., description="Physical context and constraints")
    functional_requirements: List[FunctionalRequirement] = Field(..., description="What the case must accomplish")
    constraints: Optional[List[Constraint]] = []
    materials: Optional[Materials] = Materials()
    tolerances: Optional[Tolerances] = Tolerances()
    iteration_budget: Optional[IterationBudget] = IterationBudget()
    outputs: Optional[Outputs] = Outputs()

class DesignParameters(BaseModel):
    """Parameters proposed by the LLM planner"""
    shell: dict = Field(..., description="Shell geometry parameters")
    bosses: List[dict] = Field(..., description="Boss/mount parameters")
    vents: dict = Field(..., description="Ventilation parameters")
    io_slots: List[dict] = Field(..., description="IO slot parameters")
    latches: dict = Field(..., description="Latching mechanism parameters")

class EvaluationResult(BaseModel):
    """Result of functional evaluation"""
    test_id: str
    passed: bool
    score: float = Field(..., ge=0, le=1, description="Satisfaction score 0-1")
    margin: Optional[float] = Field(None, description="Margin above/below threshold")
    details: Optional[str] = Field(None, description="Additional details")

class IterationResult(BaseModel):
    """Result of a single iteration"""
    iteration: int
    parameters: DesignParameters
    evaluation: List[EvaluationResult]
    overall_score: float = Field(..., ge=0, le=1)
    all_passed: bool
    elapsed_time_s: float

class JobStatus(BaseModel):
    """Job status and progress"""
    id: str
    spec_id: str
    status: Literal["pending", "running", "completed", "failed"]
    current_iteration: int = 0
    max_iterations: int
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    best_score: float = 0.0
    all_passed: bool = False
    error_message: Optional[str] = None

class JobResult(BaseModel):
    """Final job result"""
    job_id: str
    spec: FunctionalSpec
    iterations: List[IterationResult]
    final_parameters: Optional[DesignParameters] = None
    artifacts: dict = Field(..., description="Paths to generated artifacts")
    report: Optional[str] = Field(None, description="Generated report content")
    success: bool
    total_time_s: float
