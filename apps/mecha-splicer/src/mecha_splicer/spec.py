from __future__ import annotations

from typing import Annotated, Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator


Mm = Annotated[float, Field(ge=0.0)]
MmPos = Annotated[float, Field(gt=0.0)]


class Rect2D(BaseModel):
    x_mm: float
    y_mm: float
    w_mm: MmPos
    h_mm: MmPos


class Circle2D(BaseModel):
    x_mm: float
    y_mm: float
    d_mm: MmPos


class Cutout(BaseModel):
    kind: Literal["rect", "circle"] = "rect"
    rect: Optional[Rect2D] = None
    circle: Optional[Circle2D] = None
    label: str = ""
    face: Literal["front", "back", "left", "right", "top"] = "front"

    @field_validator("rect")
    @classmethod
    def _rect_required_for_rect(cls, v, info):
        if info.data.get("kind") == "rect" and v is None:
            raise ValueError("rect is required when kind='rect'")
        return v

    @field_validator("circle")
    @classmethod
    def _circle_required_for_circle(cls, v, info):
        if info.data.get("kind") == "circle" and v is None:
            raise ValueError("circle is required when kind='circle'")
        return v


class MountHole(BaseModel):
    x_mm: float
    y_mm: float
    d_mm: MmPos = 2.2


class EnclosureSpec(BaseModel):
    """
    Simple printable enclosure for a PCB/module.

    Coordinate system:
      - XY plane is the enclosure base.
      - origin is lower-left corner of outer box.
      - Z is up.
    """

    name: str = "enclosure"
    inner_w_mm: MmPos
    inner_d_mm: MmPos
    inner_h_mm: MmPos

    wall_mm: MmPos = 2.4
    floor_mm: MmPos = 2.0
    lid_mm: MmPos = 2.0
    clearance_mm: MmPos = 0.4

    mount_holes: list[MountHole] = Field(default_factory=list)
    cutouts: list[Cutout] = Field(default_factory=list)

    fastener: Literal["m2", "m2.5", "m3"] = "m3"
    lid_style: Literal["screw", "snap"] = "screw"

    # Enclosure integration helpers (v1+):
    # If mount_holes are provided, Mecha-Splicer can generate standoffs and lid screw holes.
    standoff_h_mm: MmPos = 6.0
    standoff_od_mm: MmPos = 6.0
    standoff_hole_d_mm: MmPos = 3.2
    include_standoffs: bool = True

    lid_screw_hole_d_mm: MmPos = 3.2
    include_lid_screw_holes: bool = True


class BracketSpec(BaseModel):
    name: str = "bracket"
    w_mm: MmPos
    d_mm: MmPos
    t_mm: MmPos = 4.0
    hole_d_mm: MmPos = 3.2
    hole_spacing_mm: MmPos = 20.0


class ServoMountSpec(BaseModel):
    """
    v1 robotics template: a printable servo mounting plate with a cutout + flange holes.

    This is intentionally simple (no “perfectly engineered” bracket); it’s meant to be
    good enough to prototype, then iterate.
    """

    name: str = "servo_mount"
    servo_type: Literal["sg90", "mg996r"] = "sg90"
    plate_w_mm: MmPos = 80.0
    plate_h_mm: MmPos = 40.0
    plate_t_mm: MmPos = 6.0
    clearance_mm: MmPos = 0.6
    hole_d_mm: MmPos = 2.2
    countersink: bool = False


class LinearAxisSpec(BaseModel):
    """
    Standalone mechanism primitive: belt-driven linear axis (GT2-style).

    v1 intentionally generates *printable parts* and a conservative check/BOM:
      - motor mount plate/block
      - idler mount plate/block
      - carriage block/plate

    It does not generate a full rigid frame (extrusions/CNC plates) yet.
    """

    name: str = "linear_axis"
    drive: Literal["gt2_belt"] = "gt2_belt"

    travel_mm: MmPos = 200.0
    rod_d_mm: MmPos = 8.0
    rod_spacing_mm: MmPos = 40.0
    rod_length_mm: MmPos = 300.0

    belt_width_mm: MmPos = 6.0
    pulley_teeth: int = Field(default=20, ge=12, le=40)

    motor: Literal["nema17"] = "nema17"
    target_speed_mm_s: MmPos = 80.0
    target_accel_mm_s2: MmPos = 600.0
    payload_n: MmPos = 10.0  # ~1kgf

    wall_mm: MmPos = 3.0
    clearance_mm: MmPos = 0.6

    # Build options
    use_linear_bearings: bool = True  # True: LM8UU style, False: printed bushings
    include_endstops: bool = True
    endstop_type: Literal["micro_switch", "hall"] = "micro_switch"
    include_tensioner: bool = True

    # Frame note (not generated as full CAD yet; used for checks & docs)
    frame: Literal["none", "2020_extrusion", "plate"] = "2020_extrusion"
    frame_length_mm: MmPos = 350.0
    frame_extrusion: Literal["2020"] = "2020"
    include_rod_holders: bool = True
    rod_holder_bolt: Literal["m3"] = "m3"


class LeadScrewAxisSpec(BaseModel):
    """
    Standalone mechanism primitive: lead-screw driven linear axis (T8-style).

    v1 generates printable mounting parts + conservative checks + BOM.
    """

    name: str = "leadscrew_axis"
    screw: Literal["t8"] = "t8"
    lead_mm_per_rev: MmPos = 8.0  # common T8 lead (8mm per rev)

    travel_mm: MmPos = 200.0
    screw_length_mm: MmPos = 300.0
    screw_d_mm: MmPos = 8.0

    rod_d_mm: MmPos = 8.0
    rod_spacing_mm: MmPos = 40.0
    rod_length_mm: MmPos = 320.0

    motor: Literal["nema17"] = "nema17"
    target_speed_mm_s: MmPos = 30.0
    target_accel_mm_s2: MmPos = 300.0
    payload_n: MmPos = 20.0

    wall_mm: MmPos = 3.0
    clearance_mm: MmPos = 0.6

    include_endstops: bool = True
    endstop_type: Literal["micro_switch", "hall"] = "micro_switch"
    include_rod_holders: bool = True
    frame: Literal["none", "2020_extrusion", "plate"] = "2020_extrusion"
    frame_length_mm: MmPos = 350.0


class RotaryJointSpec(BaseModel):
    """
    Standalone mechanism primitive: bearing-supported rotary joint.

    v1 generates:
      - a bearing block (pocket + mounting holes)
      - a simple arm plate that fits on the shaft

    This is meant for prototyping and iteration, not a certified load-rated joint.
    """

    name: str = "rotary_joint"
    bearing: Literal["608zz", "625zz"] = "608zz"

    # Shaft should match bearing ID.
    shaft_d_mm: MmPos = 8.0

    # Geometry
    wall_mm: MmPos = 4.0
    clearance_mm: MmPos = 0.3

    block_w_mm: MmPos = 50.0
    block_d_mm: MmPos = 25.0
    block_h_mm: MmPos = 18.0

    # Mounting holes for the block
    mount_hole_d_mm: MmPos = 3.2
    mount_hole_spacing_x_mm: MmPos = 30.0
    mount_hole_spacing_y_mm: MmPos = 16.0

    # Arm plate (optional, but useful for demos)
    arm_len_mm: MmPos = 80.0
    arm_w_mm: MmPos = 18.0
    arm_t_mm: MmPos = 6.0
    arm_hole_d_mm: MmPos = 3.2
    arm_hole_pitch_mm: MmPos = 20.0
    arm_hole_count: int = Field(default=3, ge=0, le=8)


class BeltReductionSpec(BaseModel):
    """
    Standalone movement primitive: a simple GT2 belt reduction stage.

    v1 generates a printable plate with:
      - NEMA17 motor mount pattern
      - One bearing-supported driven shaft location (625 bearing, 5mm shaft)
      - One bearing-supported idler location (625 bearing, 5mm shaft)

    This is not a full gearbox; it’s a prototype-grade reduction stage for robotics.
    """

    name: str = "belt_reduction"
    belt_pitch_mm: MmPos = 2.0  # GT2
    belt_width_mm: MmPos = 6.0

    motor_pulley_teeth: int = Field(default=20, ge=12, le=40)
    driven_pulley_teeth: int = Field(default=60, ge=20, le=120)

    center_distance_mm: MmPos = 60.0

    plate_w_mm: MmPos = 120.0
    plate_h_mm: MmPos = 80.0
    plate_t_mm: MmPos = 6.0

    clearance_mm: MmPos = 0.4

    include_idler: bool = True
    idler_offset_mm: MmPos = 18.0


class GripperSpec(BaseModel):
    """
    Standalone mechanism primitive: simple servo-driven scissor gripper.

    v1 generates:
      - base plate (servo mount + jaw pivots)
      - two jaws
      - a link plate
      - preview
    """

    name: str = "gripper"
    servo_type: Literal["sg90", "mg996r"] = "sg90"

    jaw_len_mm: MmPos = 70.0
    jaw_w_mm: MmPos = 14.0
    jaw_t_mm: MmPos = 6.0
    jaw_pivot_hole_d_mm: MmPos = 3.2
    jaw_tip_pad_len_mm: MmPos = 12.0

    base_w_mm: MmPos = 110.0
    base_h_mm: MmPos = 60.0
    base_t_mm: MmPos = 6.0

    link_w_mm: MmPos = 12.0
    link_t_mm: MmPos = 4.0
    link_hole_d_mm: MmPos = 3.2

    max_payload_n: MmPos = 8.0
    lever_arm_mm: MmPos = 50.0  # approximate moment arm for torque sanity

    clearance_mm: MmPos = 0.6


class PanTiltSpec(BaseModel):
    """
    Standalone mechanism primitive: 2-DOF pan/tilt using two servos.

    v1 generates:
      - base plate (pan servo)
      - tilt bracket (mounts tilt servo + platform)
      - platform plate
      - preview
    """

    name: str = "pan_tilt"
    pan_servo: Literal["sg90", "mg996r"] = "sg90"
    tilt_servo: Literal["sg90", "mg996r"] = "sg90"

    base_w_mm: MmPos = 120.0
    base_h_mm: MmPos = 80.0
    base_t_mm: MmPos = 6.0

    bracket_w_mm: MmPos = 80.0
    bracket_h_mm: MmPos = 70.0
    bracket_t_mm: MmPos = 6.0

    platform_w_mm: MmPos = 60.0
    platform_h_mm: MmPos = 40.0
    platform_t_mm: MmPos = 4.0

    max_payload_n: MmPos = 6.0
    payload_offset_mm: MmPos = 45.0  # moment arm for tilt torque sanity
    clearance_mm: MmPos = 0.6


class TransformSpec(BaseModel):
    x_mm: float = 0.0
    y_mm: float = 0.0
    z_mm: float = 0.0
    rx_deg: float = 0.0
    ry_deg: float = 0.0
    rz_deg: float = 0.0


class AssemblyInstanceSpec(BaseModel):
    id: str = ""
    output_file: str
    module: str
    transform: TransformSpec = Field(default_factory=TransformSpec)
    fixed: bool = False
    anchors: list["AnchorSpec"] = Field(default_factory=list)
    keepouts: list["KeepoutSpec"] = Field(default_factory=list)


class AssemblySpec(BaseModel):
    """
    Mechanism graph (v1): place generated part modules into a single OpenSCAD assembly.

    Each instance references a generated output file + module name (usually the filename stem).
    """

    name: str = "assembly"
    instances: list[AssemblyInstanceSpec] = Field(default_factory=list)
    mates: list["MateSpec"] = Field(default_factory=list)
    auto_anchors: bool = True
    auto_keepouts: bool = True


class AnchorSpec(BaseModel):
    name: str
    transform: TransformSpec = Field(default_factory=TransformSpec)


class KeepoutSpec(BaseModel):
    """
    Assembly-level access/clearance volumes for heuristic collision checks.

    Shapes are approximations (used as AABBs after transform).
    """

    name: str = "keepout"
    shape: Literal["box", "cylinder"] = "box"
    # box dims
    w_mm: float = 0.0
    d_mm: float = 0.0
    h_mm: float = 0.0
    # cylinder dims
    r_mm: float = 0.0
    z_mm: float = 0.0
    transform: TransformSpec = Field(default_factory=TransformSpec)


class MateSpec(BaseModel):
    """
    Align an anchor on instance A to an anchor on instance B.

    Constraint (with offset):
      T(A_instance) * T(A_anchor) * T(offset) == T(B_instance) * T(B_anchor)

    If exactly one side is placed, the other can be solved.
    """

    name: str = "mate"
    priority: int = 0
    kind: Literal[
        "anchor",
        "center_to_center",
        "mount_plane_flush",
        "shaft_into_bearing",
        "bolt_pattern",
        "rod_pair_align",
        "axis_collinear",
    ] = "anchor"
    a_instance: str
    a_anchor: str
    b_instance: str
    b_anchor: str
    offset: TransformSpec = Field(default_factory=TransformSpec)
    params: dict[str, Any] = Field(default_factory=dict)


AssemblyInstanceSpec.model_rebuild()
AssemblySpec.model_rebuild()


class PrintSettings(BaseModel):
    """
    Print settings used for conservative DFM/strength heuristics.
    (Not a guarantee of strength.)
    """

    material: Literal["PLA", "PETG", "ABS", "NYLON"] = "PETG"
    layer_height_mm: MmPos = 0.2
    perimeters: int = Field(default=4, ge=2, le=10)
    infill_pct: int = Field(default=35, ge=10, le=100)
    nozzle_mm: MmPos = 0.4
    orientation: Literal["best_guess", "strong_in_xy", "strong_in_z"] = "best_guess"


class ElectronicsAnchor(BaseModel):
    """
    Minimal EE→ME bridge (v1):
    Describe a PCB outline + mount holes + key connector cutouts.
    """

    device: str = "device"
    pcb_w_mm: MmPos
    pcb_h_mm: MmPos
    pcb_t_mm: MmPos = 1.6
    mounts: list[MountHole] = Field(default_factory=list)
    ports: list[Cutout] = Field(default_factory=list)


class SystemGoal(BaseModel):
    """
    Optional intent-level target used by the composer engine.
    """

    application: Literal["control_box", "pan_tilt_camera", "mobile_robot", "quadruped", "custom"] = "custom"
    payload_kg: Annotated[float, Field(ge=0.0)] = 0.5
    target_speed_m_s: Annotated[float, Field(ge=0.0)] = 0.2
    budget_usd: Annotated[float, Field(ge=0.0)] = 150.0
    environment: Literal["indoor", "outdoor"] = "indoor"
    workspace_w_mm: MmPos = 200.0
    workspace_h_mm: MmPos = 120.0
    notes: str = ""


class ProjectSpec(BaseModel):
    project_name: str
    mode: Literal["prototype", "professional"] = "prototype"
    process: Literal["fdm"] = "fdm"
    simulation_fidelity: Literal["starter", "high"] = "starter"
    auto_compose: bool = False
    system_goal: Optional[SystemGoal] = None

    # v1 scopes
    enclosure: Optional[EnclosureSpec] = None
    bracket: Optional[BracketSpec] = None
    servo_mount: Optional[ServoMountSpec] = None
    linear_axis: Optional[LinearAxisSpec] = None
    leadscrew_axis: Optional[LeadScrewAxisSpec] = None
    rotary_joint: Optional[RotaryJointSpec] = None
    belt_reduction: Optional[BeltReductionSpec] = None
    gripper: Optional[GripperSpec] = None
    pan_tilt: Optional[PanTiltSpec] = None
    assembly: Optional[AssemblySpec] = None

    # Bridge: optional electronics anchor that can be used to drive enclosure defaults.
    electronics: Optional[ElectronicsAnchor] = None

    print_settings: Optional[PrintSettings] = None

    notes: str = ""

    @field_validator("project_name")
    @classmethod
    def _name_nonempty(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("project_name is required")
        return v
