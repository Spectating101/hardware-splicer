"""Model two captive jaw shoes and a locating nest around the HS SPI-board pallet."""

import argparse
import hashlib
import json
import math
from pathlib import Path

import cadquery as cq


ROOT = Path(__file__).resolve().parent
SHOE_X = (96.0, 109.0)
TAB_SIDE = 19.0
PALLET_MID_Y = 25.0
TAB_HEIGHT = 5.0


def block(x0, x1, y0, y1, z0, z1):
    return cq.Solid.makeBox(x1 - x0, y1 - y0, z1 - z0, cq.Vector(x0, y0, z0))


def near_shoe(p, sweep=0.0, machine_bores=True, centered=False):
    # The continuous opening stroke runs outwards along negative Y.
    y = (-4 if centered else TAB_SIDE) - p["jaw_side_clearance_mm"]
    z = p["jaw_vertical_clearance_mm"]
    thickness = p["lip_thickness_mm"]
    reach = p["lip_reach_mm"]
    x0, x1 = (30.0, 60.0) if centered else SHOE_X
    side = block(x0, x1, y - 7 - sweep, y, -z - thickness, TAB_HEIGHT + z + thickness)
    bearing = p["min_bearing_patch_length_mm"]
    zones = [(x0, x0 + bearing), (x1 - bearing, x1)] if centered else [(x0, x1)]
    lower_pads = [
        block(a, b, y - sweep - 0.1, y + reach, -z - thickness, -z) for a, b in zones
    ]
    top = block(
        x0, x1, y - sweep - 0.1, y + reach, TAB_HEIGHT + z, TAB_HEIGHT + z + thickness
    )
    shoe = side.fuse(top, *lower_pads).clean()
    if machine_bores:
        middle = (x0 + x1) / 2
        for x in [middle - 3.5, middle + 3.5]:
            pilot = cq.Solid.makeCylinder(
                0.8, 4.0, cq.Vector(x, y - 7, 2.5), cq.Vector(0, 1, 0)
            )
            shoe = shoe.cut(pilot)
    return shoe


def far_shoe(shoe):
    return shoe.mirror("XZ", (0, PALLET_MID_Y, 0))


def nest(p, centered=False):
    seat = p["seat_height_mm"]
    gap = p["nest_clearance_per_side_mm"]
    base = block(-12, 100, -12, 62, 0, seat)
    # Leave the PCB underside and the two opening shoes accessible.
    base = base.cut(
        block(1, 89, 1, 49, -1, seat + 1), block(94, 102, 7, 43, -1, seat + 1)
    )
    if centered:
        # Leave a 2 mm floor beneath both shoe sweeps, keeping the nest one piece.
        base = base.cut(
            block(28, 62, -13, 2, 2, seat + 1), block(28, 62, 48, 63, 2, seat + 1)
        )
    walls = [
        (-8 - gap, -4 - gap, 16, 34),
        (94 + gap, 98 + gap, -1, 6),
        (94 + gap, 98 + gap, 44, 51),
        (0, 15, -8 - gap, -4 - gap),
        (75, 90, -8 - gap, -4 - gap),
        (0, 15, 54 + gap, 58 + gap),
        (75, 90, 54 + gap, 58 + gap),
    ]
    for x0, x1, y0, y1 in walls:
        base = base.fuse(block(x0, x1, y0, y1, seat, seat + 3.5))
    for x in [-8, 94]:
        for y in [-8, 58]:
            base = base.cut(cq.Solid.makeCylinder(1.7, seat + 1, cq.Vector(x, y, 0)))
    return base.clean()


def overlap(a, b):
    return sum(s.Volume() for s in a.intersect(b).Solids())


def lip_loading(p, thickness):
    # Model one shoe carrying the complete factored load. The near lower lip and
    # far upper lip form a reaction couple in X across two edge-bearing patches.
    patch = p["min_bearing_patch_length_mm"]
    near = SHOE_X[0] + patch / 2
    far = SHOE_X[1] - patch / 2
    force = (
        p["design_mass_kg"]
        * (9.81 + p["vertical_acceleration_m_s2"])
        * p["load_factor"]
    )
    cg = min(p["cg_x_range_mm"])
    upper = force * (near - cg) / (far - near)
    lower = upper + force
    stress = 6 * lower * p["lip_reach_mm"] / (patch * thickness**2)
    return {
        "factored_weight_N": force,
        "upper_reaction_N": upper,
        "lower_reaction_N": lower,
        "lip_root_stress_mpa": stress,
        "within_assumed_stress": stress <= p["assumed_design_stress_mpa"],
    }


def free_pitch(p):
    """Two rigid contact patches, no preload. Find pitch that takes up the channel play."""
    span = SHOE_X[1] - SHOE_X[0] - p["min_bearing_patch_length_mm"]
    height = TAB_HEIGHT + 2 * p["jaw_vertical_clearance_mm"]
    low, high = 0.0, math.radians(30)
    for _ in range(50):
        angle = (low + high) / 2
        separation = TAB_HEIGHT / math.cos(angle) + span * math.tan(angle)
        if separation < height:
            low = angle
        else:
            high = angle
    return (low + high) / 2


def rail_support(p):
    # A patch can bear anywhere inside its face. Use the smallest separation
    # between inner edges and the worst midpoint shift, not nominal pad centers.
    patch = p["min_bearing_patch_length_mm"]
    overlap_y = p["lip_reach_mm"] - p["jaw_side_clearance_mm"]
    xspan = 30 - 2 * patch
    yspan = 58 - 2 * overlap_y
    cg_margin = min(
        min(p["cg_x_range_mm"]) - (30 + patch),
        (60 - patch) - max(p["cg_x_range_mm"]),
        min(p["cg_y_range_mm"]) - (-4 + overlap_y),
        (54 - overlap_y) - max(p["cg_y_range_mm"]),
    )

    def edge_error(x, y, spread):
        slope_allowance = (abs(x - 45) + patch / 2) / xspan + (
            abs(y - 25) + overlap_y / 2
        ) / yspan
        return (
            p["jaw_vertical_clearance_mm"]
            + p["pickup_z_error_mm"]
            + p["combined_channel_face_error_mm"]
            + spread * slope_allowance
        )

    def worst(spread):
        # Outer body corner and the furthest tip corner bound this symmetric outline.
        return max(edge_error(-4, -4, spread), edge_error(110, 19, spread))

    force = (
        p["design_mass_kg"]
        * (9.81 + p["vertical_acceleration_m_s2"])
        * p["load_factor"]
    )
    stress = 6 * force * p["lip_reach_mm"] / (patch * p["lip_thickness_mm"] ** 2)
    proposed = worst(p["centered_support_height_spread_mm"])
    twisted = worst(0.35)
    limit = p["proposed_handoff_edge_error_limit_mm"]
    if (
        cg_margin <= 0
        or stress > p["assumed_design_stress_mpa"]
        or not proposed <= limit < twisted
    ):
        raise ValueError("Centered support envelope or warp control failed")
    return {
        "minimum_cg_margin_inside_supports_mm": cg_margin,
        "single_pad_stress_bound_mpa": stress,
        "height_spread_mm": p["centered_support_height_spread_mm"],
        "max_edge_error_bound_mm": proposed,
        "warp_control_height_spread_mm": 0.35,
        "warp_control_edge_error_bound_mm": twisted,
        "closed_inside_width_mm": 58 + 2 * p["jaw_side_clearance_mm"],
        "open_inside_width_mm": 58
        + 2 * (p["jaw_side_clearance_mm"] + p["open_stroke_per_shoe_mm"]),
        "shoe_clearance_above_nest_floor_mm": p["seat_height_mm"]
        - p["jaw_vertical_clearance_mm"]
        - p["lip_thickness_mm"]
        - 2,
        "vertical_handoff_screen_passes": True,
    }


def run(out):
    p = json.loads((ROOT / "design.json").read_text())
    reference = ROOT / "reference-pallet.step"
    if hashlib.sha256(reference.read_bytes()).hexdigest() != p["pallet_sha256"]:
        raise ValueError("Pallet does not match this fixture revision")
    out.mkdir(parents=True, exist_ok=True)
    seat = p["seat_height_mm"]
    solids = {
        "nest": nest(p, centered=True),
        "near-shoe": near_shoe(p, centered=True),
        "far-shoe": far_shoe(near_shoe(p, centered=True)),
    }
    checked = {}
    for name, solid in solids.items():
        path = out / (name + ".step")
        cq.exporters.export(solid, str(path))
        (imported,) = cq.importers.importStep(str(path)).solids().vals()
        if not imported.isValid() or abs(solid.Volume() - imported.Volume()) > 0.01:
            raise ValueError(f"Invalid exported part: {name}")
        checked[name] = imported
    (pallet,) = cq.importers.importStep(str(reference)).solids().vals()
    pallet = pallet.translate((0, 0, seat))
    fixture = checked["nest"]
    swept_near = near_shoe(
        p, sweep=p["open_stroke_per_shoe_mm"], machine_bores=False, centered=True
    )
    swept_shoes = [
        s.translate((0, 0, seat)) for s in (swept_near, far_shoe(swept_near))
    ]
    contacts = {
        "pallet_nest_nominal": overlap(pallet, fixture),
        "swept_shoes_nest": sum(overlap(s, fixture) for s in swept_shoes),
        "swept_shoes_pallet": sum(overlap(s, pallet) for s in swept_shoes),
        "reversed_pallet_nest": overlap(
            pallet.rotate((45, 25, 0), (45, 25, 1), 180), fixture
        ),
        "pallet_1mm_off_center": overlap(pallet.translate((1, 0, 0)), fixture),
    }
    for name in ["pallet_nest_nominal", "swept_shoes_nest", "swept_shoes_pallet"]:
        if contacts[name] > 1e-4:
            raise ValueError(f"Nominal interference: {name} {contacts[name]} mm³")
    if min(contacts["reversed_pallet_nest"], contacts["pallet_1mm_off_center"]) < 1:
        raise ValueError("Misloaded pallets escaped the geometric checks")
    angle = math.radians(p["placement_yaw_deg"])
    # 98 × 58 pallet body, rotated about its center, projected onto both axes.
    yaw_growth = max(
        49 * math.cos(angle) + 29 * math.sin(angle) - 49,
        29 * math.cos(angle) + 49 * math.sin(angle) - 29,
    )
    xy_margin = (
        p["nest_clearance_per_side_mm"]
        - p["placement_xy_error_mm"]
        - p["combined_in_plane_face_error_mm"]
        - yaw_growth
    )
    z_margin = (
        p["jaw_vertical_clearance_mm"]
        - p["combined_channel_face_error_mm"]
        - p["pickup_z_error_mm"]
    )
    lip_overlap = (
        p["lip_reach_mm"]
        - p["jaw_side_clearance_mm"]
        - p["combined_in_plane_face_error_mm"]
        - p["placement_xy_error_mm"]
    )
    open_margin = (
        p["open_stroke_per_shoe_mm"]
        - (p["lip_reach_mm"] - p["jaw_side_clearance_mm"])
        - p["placement_xy_error_mm"]
        - p["combined_in_plane_face_error_mm"]
    )
    floor_margin = seat - p["lip_thickness_mm"] - p["jaw_vertical_clearance_mm"]
    if min(xy_margin, z_margin, lip_overlap, open_margin, floor_margin) <= 0:
        raise ValueError("Tolerance or release envelope exhausted")
    rejected = lip_loading(p, 1.5)
    improved = lip_loading(p, p["lip_thickness_mm"])
    if rejected["within_assumed_stress"] or not improved["within_assumed_stress"]:
        raise ValueError("Lip revision did not resolve modeled bending failure")
    pitch = free_pitch(p)
    pivot = SHOE_X[0] + p["min_bearing_patch_length_mm"] / 2
    droop = p["jaw_vertical_clearance_mm"] + (pivot + 4) * math.sin(pitch)
    tipped = pallet.rotate(
        (pivot, 25, seat), (pivot, 26, seat), -math.degrees(pitch)
    ).translate((0, 0, -p["jaw_vertical_clearance_mm"]))
    tilted_intersection = overlap(tipped, nest(p))
    handoff_pass = (
        droop <= p["proposed_handoff_edge_error_limit_mm"]
        and tilted_intersection <= 1e-4
    )
    assembly = cq.Assembly()
    assembly.add(fixture, name="nest", color=cq.Color(0.18, 0.36, 0.37))
    assembly.add(pallet, name="reference-pallet", color=cq.Color(0.78, 0.77, 0.68))
    for name in ["near-shoe", "far-shoe"]:
        assembly.add(
            checked[name].translate((0, 0, seat)),
            name=name,
            color=cq.Color(0.89, 0.48, 0.18),
        )
    assembly.export(str(out / "seated-assembly.step"))
    assembly_parts = (
        cq.importers.importStep(str(out / "seated-assembly.step")).solids().vals()
    )
    if len(assembly_parts) != 4 or any(not solid.isValid() for solid in assembly_parts):
        raise ValueError("Seated assembly did not round trip as four solids")
    cq.exporters.export(
        cq.Compound.makeCompound(assembly_parts),
        str(out / "seated-view.svg"),
        opt={
            "width": 600,
            "height": 320,
            "showAxes": False,
            "showHidden": False,
            "projectionDir": (0.7, -1.5, 1.25),
            "strokeWidth": 0.4,
        },
    )
    dimensions = pallet.BoundingBox()
    report = {
        "units": "mm, N, MPa",
        "pallet_extents_mm": [
            round(x, 3) for x in (dimensions.xlen, dimensions.ylen, dimensions.zlen)
        ],
        "solid_volumes_mm3": {k: round(v.Volume(), 3) for k, v in checked.items()},
        "assembly_solids": len(assembly_parts),
        "intersections_mm3": contacts,
        "nest_worst_side_margin_mm": xy_margin,
        "channel_vertical_margin_mm": z_margin,
        "minimum_closed_lip_overlap_mm_at_aligned_pickup": lip_overlap,
        "open_release_margin_mm_at_aligned_pickup": open_margin,
        "shoe_to_bench_mm": floor_margin,
        "rejected_1p5mm_lip": rejected,
        "revised_lip": improved,
        "rejected_tab_handoff": {
            "pitch_deg": math.degrees(pitch),
            "projected_far_edge_drop_mm": droop,
            "allowed_edge_drop_mm": p["proposed_handoff_edge_error_limit_mm"],
            "overlap_if_commanded_to_nominal_seat_mm3": tilted_intersection,
            "passes_proposed_handoff": handoff_pass,
        },
        "centered_rail_handoff": rail_support(p),
        "stage": "CAD collision and analytical vertical-load screen",
        "physical_tests": 0,
    }
    (out / "results.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--out", type=Path, default=ROOT)
    run(cli.parse_args().out)
