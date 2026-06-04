from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..spec import EnclosureSpec, ProjectSpec


@dataclass(frozen=True)
class MintTemplate:
    category: str
    name: str
    monetization_angle: str
    default_spec: Dict[str, Any]


def default_templates() -> List[MintTemplate]:
    # “Starter kits”: enough to produce artifacts. Users will override dimensions later.
    return [
        MintTemplate(
            category="enclosure",
            name="generic_devboard_enclosure",
            monetization_angle="Sell as a digital pack: OpenSCAD + variants + print settings + assembly/test checklist.",
            default_spec={
                "project_name": "mint_enclosure_generic",
                "mode": "prototype",
                "process": "fdm",
                "electronics": {
                    "device": "generic_devboard",
                    "pcb_w_mm": 60.0,
                    "pcb_h_mm": 28.0,
                    "pcb_t_mm": 1.6,
                    "mounts": [
                        {"x_mm": 5.0, "y_mm": 5.0, "d_mm": 2.2},
                        {"x_mm": 55.0, "y_mm": 5.0, "d_mm": 2.2},
                        {"x_mm": 5.0, "y_mm": 23.0, "d_mm": 2.2},
                        {"x_mm": 55.0, "y_mm": 23.0, "d_mm": 2.2}
                    ],
                    "ports": [
                        {
                            "kind": "rect",
                            "label": "usb",
                            "face": "front",
                            "rect": {"x_mm": 24.0, "y_mm": 6.0, "w_mm": 12.0, "h_mm": 8.0}
                        }
                    ]
                },
                "enclosure": {
                    "name": "generic",
                    "inner_w_mm": 70.0,
                    "inner_d_mm": 40.0,
                    "inner_h_mm": 25.0,
                    "wall_mm": 2.4,
                    "floor_mm": 2.0,
                    "lid_mm": 2.0,
                    "clearance_mm": 0.5,
                    "lid_style": "screw",
                    "fastener": "m3",
                    "cutouts": [],
                },
            },
        ),
        MintTemplate(
            category="mount",
            name="simple_plate_bracket",
            monetization_angle="Sell as a 'mount kit' design pack: bracket + fastener BOM + drilling template.",
            default_spec={
                "project_name": "mint_bracket_plate",
                "mode": "prototype",
                "process": "fdm",
                "bracket": {
                    "name": "plate",
                    "w_mm": 60.0,
                    "d_mm": 20.0,
                    "t_mm": 4.0,
                    "hole_d_mm": 3.2,
                    "hole_spacing_mm": 40.0,
                },
            },
        ),
        MintTemplate(
            category="fixture_jig",
            name="drill_template_plate",
            monetization_angle="Sell as a 'drill jig pack' with print orientation + usage steps.",
            default_spec={
                "project_name": "mint_fixture_drill_template",
                "mode": "prototype",
                "process": "fdm",
                "bracket": {
                    "name": "drill_template",
                    "w_mm": 100.0,
                    "d_mm": 30.0,
                    "t_mm": 6.0,
                    "hole_d_mm": 3.2,
                    "hole_spacing_mm": 80.0,
                },
                "notes": "Use as a simple drilling/marking jig; replace dimensions/holes for your target.",
            },
        ),
        MintTemplate(
            category="cable_management",
            name="cable_clip_plate",
            monetization_angle="Sell as a printable cable management accessory pack (variants by cable OD).",
            default_spec={
                "project_name": "mint_cable_clip_plate",
                "mode": "prototype",
                "process": "fdm",
                "bracket": {
                    "name": "cable_clip_plate",
                    "w_mm": 50.0,
                    "d_mm": 20.0,
                    "t_mm": 4.0,
                    "hole_d_mm": 3.2,
                    "hole_spacing_mm": 30.0,
                },
                "notes": "Placeholder: real cable clips will become a dedicated template type in v2.",
            },
        ),
        MintTemplate(
            category="robotics",
            name="linear_axis_gt2",
            monetization_angle="Sell as a 'linear axis pack' (GT2) with printable mounts, BOM, and tuning checklist.",
            default_spec={
                "project_name": "mint_robotics_linear_axis_gt2",
                "mode": "prototype",
                "process": "fdm",
                "linear_axis": {
                    "name": "axis_gt2_v1",
                    "drive": "gt2_belt",
                    "travel_mm": 200.0,
                    "rod_d_mm": 8.0,
                    "rod_spacing_mm": 40.0,
                    "rod_length_mm": 320.0,
                    "belt_width_mm": 6.0,
                    "pulley_teeth": 20,
                    "motor": "nema17",
                    "target_speed_mm_s": 80.0,
                    "payload_n": 10.0,
                    "wall_mm": 3.0,
                    "clearance_mm": 0.6
                },
                "notes": "Standalone mechanism primitive. Validate rod straightness and belt tension; iterate mounts as needed.",
            },
        ),
        MintTemplate(
            category="robotics",
            name="linear_axis_leadscrew_t8",
            monetization_angle="Sell as a 'linear axis pack' (T8 lead-screw) with printable mounts, BOM, and tuning checklist.",
            default_spec={
                "project_name": "mint_robotics_linear_axis_leadscrew_t8",
                "mode": "prototype",
                "process": "fdm",
                "leadscrew_axis": {
                    "name": "axis_t8_v1",
                    "screw": "t8",
                    "lead_mm_per_rev": 8.0,
                    "travel_mm": 200.0,
                    "screw_length_mm": 320.0,
                    "screw_d_mm": 8.0,
                    "rod_d_mm": 8.0,
                    "rod_spacing_mm": 40.0,
                    "rod_length_mm": 320.0,
                    "motor": "nema17",
                    "target_speed_mm_s": 30.0,
                    "payload_n": 20.0,
                    "wall_mm": 3.0,
                    "clearance_mm": 0.6,
                },
                "notes": "Standalone mechanism primitive. Align the screw/nut to avoid binding; tune steps/mm based on lead.",
            },
        ),
        MintTemplate(
            category="robotics",
            name="rotary_joint_608",
            monetization_angle="Sell as a 'rotary joint pack' (608 bearing) with printable block/arm variants + mounting patterns.",
            default_spec={
                "project_name": "mint_robotics_rotary_joint_608",
                "mode": "prototype",
                "process": "fdm",
                "rotary_joint": {
                    "name": "rj_608_v1",
                    "bearing": "608zz",
                    "shaft_d_mm": 8.0,
                    "wall_mm": 4.0,
                    "clearance_mm": 0.3,
                    "block_w_mm": 50.0,
                    "block_d_mm": 25.0,
                    "block_h_mm": 18.0,
                    "mount_hole_d_mm": 3.2,
                    "mount_hole_spacing_x_mm": 30.0,
                    "mount_hole_spacing_y_mm": 16.0,
                    "arm_len_mm": 80.0,
                    "arm_w_mm": 18.0,
                    "arm_t_mm": 6.0,
                    "arm_hole_d_mm": 3.2,
                    "arm_hole_pitch_mm": 20.0,
                    "arm_hole_count": 3
                },
                "notes": "Standalone mechanism primitive. For higher loads, use thicker walls and a real hub/set-screw on the shaft.",
            },
        ),
        MintTemplate(
            category="robotics",
            name="belt_reduction_gt2",
            monetization_angle="Sell as a 'belt reduction stage' pack (GT2) with printable plates + belt length guidance + tuning checklist.",
            default_spec={
                "project_name": "mint_robotics_belt_reduction_gt2",
                "mode": "prototype",
                "process": "fdm",
                "belt_reduction": {
                    "name": "br_gt2_v1",
                    "belt_pitch_mm": 2.0,
                    "belt_width_mm": 6.0,
                    "motor_pulley_teeth": 20,
                    "driven_pulley_teeth": 60,
                    "center_distance_mm": 60.0,
                    "plate_w_mm": 120.0,
                    "plate_h_mm": 80.0,
                    "plate_t_mm": 6.0,
                    "clearance_mm": 0.4,
                    "include_idler": true,
                    "idler_offset_mm": 18.0
                },
                "notes": "Prototype-grade reduction stage. Use real pulleys/belt; iterate plate thickness and mounting to match your loads.",
            },
        ),
        MintTemplate(
            category="robotics",
            name="gripper_scissor_servo",
            monetization_angle="Sell as a 'servo gripper pack' with jaw variants + assembly checklist + torque sanity checks.",
            default_spec={
                "project_name": "mint_robotics_gripper_scissor",
                "mode": "prototype",
                "process": "fdm",
                "gripper": {
                    "name": "gr_scissor_v1",
                    "servo_type": "sg90",
                    "jaw_len_mm": 70.0,
                    "jaw_w_mm": 14.0,
                    "jaw_t_mm": 6.0,
                    "jaw_pivot_hole_d_mm": 3.2,
                    "base_w_mm": 110.0,
                    "base_h_mm": 60.0,
                    "base_t_mm": 6.0,
                    "max_payload_n": 8.0,
                    "lever_arm_mm": 50.0,
                    "clearance_mm": 0.6
                },
                "notes": "Prototype-grade gripper. For real use, add bushings/pins and tune geometry for mechanical advantage.",
            },
        ),
        MintTemplate(
            category="robotics",
            name="pan_tilt_servo",
            monetization_angle="Sell as a 'pan/tilt mount pack' for cameras/sensors with servo size variants + payload sanity checks.",
            default_spec={
                "project_name": "mint_robotics_pan_tilt",
                "mode": "prototype",
                "process": "fdm",
                "pan_tilt": {
                    "name": "pt_v1",
                    "pan_servo": "sg90",
                    "tilt_servo": "sg90",
                    "base_w_mm": 120.0,
                    "base_h_mm": 80.0,
                    "base_t_mm": 6.0,
                    "bracket_w_mm": 80.0,
                    "bracket_h_mm": 70.0,
                    "bracket_t_mm": 6.0,
                    "platform_w_mm": 60.0,
                    "platform_h_mm": 40.0,
                    "platform_t_mm": 4.0,
                    "max_payload_n": 6.0,
                    "payload_offset_mm": 45.0,
                    "clearance_mm": 0.6
                },
                "notes": "Prototype-grade pan/tilt. For higher payloads use stronger servos and thicker plates.",
            },
        ),
    ]


def template_for_name(name: str) -> Optional[MintTemplate]:
    name = (name or "").strip()
    if not name:
        return None
    for t in default_templates():
        if t.name == name:
            return t
    return None


def spec_for_template(name: str) -> Optional[Dict[str, Any]]:
    t = template_for_name(name)
    return t.default_spec if t else None


def spec_for_category(category: str, *, template_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
    if template_name:
        t = template_for_name(template_name)
        if t and t.category == category:
            return t.default_spec
        return None
    for t in default_templates():
        if t.category == category:
            return t.default_spec
    return None
