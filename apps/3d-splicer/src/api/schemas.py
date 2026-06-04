from pydantic import BaseModel, Field
from typing import List, Literal

class PCB(BaseModel):
    width_mm: float
    height_mm: float
    thickness_mm: float
    corner_radius_mm: float = 3.0

class Enclosure(BaseModel):
    wall_mm: float = 1.6
    clearance_mm: float = 0.6
    lip_mm: float = 1.2
    fillet_mm: float = 1.0

class Port(BaseModel):
    name: str
    type: Literal["rect"] = "rect"
    x_mm: float
    y_mm: float
    w_mm: float
    h_mm: float
    side: Literal["left", "right", "top", "bottom"]

class Mount(BaseModel):
    x_mm: float
    y_mm: float
    diameter_mm: float

class Description(BaseModel):
    version: str = "v1"
    device: str
    pcb: PCB
    enclosure: Enclosure
    ports: List[Port] = []
    mounts: List[Mount] = []

class SpliceResponse(BaseModel):
    stl_path: str
    validation: dict
    success: bool = True
    message: str = "STL generated successfully"
