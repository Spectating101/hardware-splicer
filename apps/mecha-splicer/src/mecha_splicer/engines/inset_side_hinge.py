"""Alternative *inset* twin side-pin hinge for the native HS clamshell.

This is an engineering geometry hypothesis, not qualified friction hinges.
No cable goes through the pin; 40-pin display + 6-pin touch flex routing,
strain relief and flex cycling remain unverified.
"""
from __future__ import annotations

from ..spec import ClamshellTerminalSpec


def generate_inset_side_hinge(p: ClamshellTerminalSpec) -> dict[str, str]:
    if p.hinge_style != "inset_side_pins":
        raise ValueError("inset side hinge generator must not be called for legacy external hinge")
    w,d=p.case_w_mm,p.case_d_mm
    hb,hl,gap=p.base_h_mm,p.lid_h_mm,p.closed_gap_mm
    wall,floor=p.wall_mm,p.floor_mm
    r=p.hinge_outer_d_mm/2
    hy=d-p.hinge_inset_from_rear_mm
    hz=hb+gap/2
    lenx=p.hinge_side_knuckle_axial_length_mm
    agap=p.hinge_side_axial_gap_mm
    # Each pair has a steel pin spanning a base and lid barrel. Both barrel
    # x-spans remain OUTSIDE the touch module's declared outer XY rectangle.
    edge=wall-0.6  # physically merge side-barrel with the sidewall
    left_base=(edge,lenx)
    left_lid=(edge+lenx+agap,lenx)
    right_lid=(w-edge-2*lenx-agap,lenx)
    right_base=(w-edge-lenx,lenx)
    base_positions=(left_base,right_base)
    lid_positions=(left_lid,right_lid)
    relief=r+p.pin_radial_clearance_mm
    bore=p.hinge_pin_d_mm+2*p.pin_radial_clearance_mm
    zbottom=hb+gap
    # Clearance cut from native shell BEFORE hinge cylinders are added.
    # An open rear edge is a real dust/strength trade-off, not a sealed case.
    rear_relief_start=d-p.hinge_rear_relief_length_mm
    # Rear FPC window must accommodate a 40-pin 0.5mm pitch connector plus
    # separate touch harness; clearance here is conceptual only.
    cable_w=28
    cable_x=(w-cable_w)/2
    head=[
        "// Native Mecha-Splicer side-pin hinge. CAD ONLY; no metal pin, no verified flex/stop/torque.",
        "// Hinge is fully enclosed in the declared closed XY silhouette.",
        "$fn=56;",
        f"W={w}; D={d}; wall={wall}; floor={floor};",
        f"HBASE={hb}; HLID={hl}; gap={gap};",
        f"hy={hy}; hz={hz};",
        f"kr={r}; bore={bore};",
        "",
    ]
    def cyl(x,l,radius):
        return f"translate([{x},hy,hz]) rotate([0,90,0]) cylinder(h={l},r={radius});"
    def drilled(x,l):
        return f"translate([{x-0.12},hy,hz]) rotate([0,90,0]) cylinder(h={l+0.24},d=bore);"

    base=head+[
        "module base_shell() {",
        "  difference() {",
        "    union() {",
        "      difference() {",
        "        cube([W,D,HBASE]);",
        "        translate([wall,wall,floor]) cube([W-2*wall,D-2*wall,HBASE+1]);",
        "        // Remove the upper rear wall in swing zone (shell only).",
        f"        translate([-0.1,{rear_relief_start},HBASE-{p.hinge_base_rear_relief_height_mm}]) cube([W+0.2,{d-rear_relief_start+0.1},{p.hinge_base_rear_relief_height_mm+0.2}]);",
        "      }",
        "// Side pivot barrels tie into the rear shell wall at both ends.",
    ]
    for x,l in base_positions:base.append("      "+cyl(x,l,r))
    base += [
        "    }",
        "// Sculpt relief for the rotating *lid* barrels within the base wall.",
    ]
    for x,l in lid_positions:base.append("    "+cyl(x-0.22,l+0.44,relief))
    for x,l in base_positions:base.append("    "+drilled(x,l))
    base += [
        "// Rear center FPC pass-through (bend, EMC and flex cycles NOT VERIFIED).",
        f"    translate([{cable_x},D-wall-0.1,HBASE-3.5]) cube([{cable_w},wall+0.2,4.1]);",
        "  }",
        "}",
        "base_shell();",
        "",
    ]

    lid=head+[
        "module lid_shell() {",
        "  difference() {",
        "    union() {",
        "      difference() {",
        f"        translate([0,0,{zbottom}]) cube([W,D,HLID]);",
        f"        translate([wall,wall,{zbottom-0.1}]) cube([W-2*wall,D-2*wall,HLID-floor+0.1]);",
        "        // Remove the lower rear wall in swing zone (shell only).",
        f"        translate([-0.1,{rear_relief_start},{zbottom-0.1}]) cube([W+0.2,{d-rear_relief_start+0.1},4.1]);",
        "      }",
        "// Anchor ears join the inner lid barrels back to outer side rails.",
        f"      translate([{edge},72.0,{zbottom}]) cube([{2*lenx+agap},3.1,1.3]);",
        f"      translate([{w-edge-2*lenx-agap},72.0,{zbottom}]) cube([{2*lenx+agap},3.1,1.3]);",
        "// The two lid barrels lie axially beside the base barrels.",
    ]
    for x,l in lid_positions:lid.append("      "+cyl(x,l,r))
    lid += [
        "    }",
        "// Relieve lid shell material for both base hinge barrels.",
    ]
    for x,l in base_positions:lid.append("    "+cyl(x-0.22,l+0.44,relief))
    for x,l in lid_positions:lid.append("    "+drilled(x,l))
    lid += [
        "// Upper LCD requires separate signal AND touch flex routes.",
        f"    translate([{cable_x},D-wall-0.1,{zbottom-0.1}]) cube([{cable_w},wall+0.2,3.6]);",
        "  }",
        "}",
        "lid_shell();",
        "",
    ]
    preview=[
        "// Side-pin candidate; lid rotation around internal X axis, not a hardware test.",
        "use <base_shell.scad>","use <lid_shell.scad>",
        f"angle_deg={p.preview_open_angle_deg};hy={hy};hz={hz};",
        "color([0.15,0.24,0.31]) base_shell();",
        "color([0.4,0.54,0.63])",
        "translate([0,hy,hz]) rotate([angle_deg,0,0])",
        "  translate([0,-hy,-hz]) lid_shell();",
    ]
    output={
        "base_shell.scad":"\n".join(base).rstrip()+"\n",
        "lid_shell.scad":"\n".join(lid).rstrip()+"\n",
        "clamshell_open_preview.scad":"\n".join(preview)+"\n",
    }
    if p.input_surface_mode=="dual_touch":
        bw,bd=p.lower_touch_board_w_mm,p.lower_touch_board_d_mm
        ux,uy=(w-p.display_board_w_mm)/2,(d-p.display_board_d_mm)/2
        lx,ly=(w-bw)/2,(d-bd)/2
        # Actual bounding boxes, not thin fake glass planes: useful for
        # visual collision localization while still only nominal placement.
        lower_panel_t=3.45
        upper_panel_t=3.45
        lower_panel_z=hb-lower_panel_t
        upper_panel_z=zbottom
        visual=[
            "// Two full panel-thickness proxy solids, NOT manufacturer STEP geometry.",
            "use <base_shell.scad>","use <lid_shell.scad>",
            f"hy={hy};hz={hz};angle={p.preview_open_angle_deg};",
            "color([0.12,0.17,0.23]) base_shell();",
            "color([0.31,0.44,0.53]) translate([0,hy,hz]) rotate([angle,0,0]) translate([0,-hy,-hz]) lid_shell();",
            f"color([0.03,0.08,0.10]) translate([{lx},{ly},{lower_panel_z}]) cube([{bw},{bd},{lower_panel_t}]);",
            "translate([0,hy,hz]) rotate([angle,0,0]) translate([0,-hy,-hz]) {",
            f"  color([0.03,0.08,0.10]) translate([{ux},{uy},{upper_panel_z}]) cube([{p.display_board_w_mm},{p.display_board_d_mm},{upper_panel_t}]);",
            "}",
            "",
        ]
        output["dual_touch_visual_preview.scad"]="\n".join(visual)
    return output
