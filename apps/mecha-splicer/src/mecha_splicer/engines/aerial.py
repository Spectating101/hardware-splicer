"""HS Mecha-Splicer aerial frame generator.

A genuine configurable quadrotor *frame* model: full duct geometry, motor
plates and 3x M1.4 holes at 6.6 mm PCD, FC bosses and 26 mm mounting
pattern rotated 45 degrees, structural struts, plus removable battery cradle.
No geometry in this file is copied from any source drone's CAD model.

Engineering scope: geometrically printable candidate only. Dynamic strength,
motor loading, thrust, prop safety, crash tolerance and hardware fit are
UNVERIFIED until physical measurement. Props may never be energized based
solely on this CAD.
"""
from __future__ import annotations

from ..spec import AerialFrameSpec


def _n(value: float) -> str:
    return f"{float(value):.5f}".rstrip("0").rstrip(".") or "0"


def generate_aerial_frame_scad(a: AerialFrameSpec) -> dict[str, str]:
    """Build genuinely new 65/75 mm unibody with named parametric features."""
    # The wheelbase is opposite motor-axis separation. Motors sit on a square.
    # FC 26x26 holes are rotated 45° on the cardinal axes, as on source whoops.
    d = {
        "wheelbase": a.wheelbase_mm,
        "prop_d": a.prop_diameter_mm,
        "radial": a.prop_radial_clearance_mm,
        "duct_wall": a.duct_wall_mm,
        "duct_h": a.duct_height_mm,
        "plate_h": a.plate_thickness_mm,
        "strut_w": a.strut_width_mm,
        "motor_pad_d": a.motor_plate_diameter_mm,
        "motor_bolt_pcd": a.motor_bolt_pcd_mm,
        "motor_bolt_hole": a.motor_bolt_hole_d_mm,
        "motor_center_hole": a.motor_wire_hole_d_mm,
        "fc_pitch": a.fc_mount_pitch_mm,
        "fc_hole_d": a.fc_mount_hole_d_mm,
        "fc_boss_d": a.fc_boss_diameter_mm,
        "chamfer": a.chamfer_mm,
    }
    vars = "\n".join(f"{k}={_n(v)};" for k, v in d.items())
    body = r'''// Generated directly by Hardware Splicer: parametric ducted quadrotor.
// Four real ducts, four 3-hole motor mounts, four 26mm-rotated FC holes.
// Source equipment dimensional contract ≠ evidence of physical fit.
$fn = 72;
__PARAMS__
cx = wheelbase / (2 * sqrt(2));
fc_r = fc_pitch / sqrt(2);
duct_r_in = prop_d/2 + radial;
duct_r_out = duct_r_in + duct_wall;
eps = 0.06;

module motor_locations() {
  for (sx = [-1,1], sy = [-1,1])
    translate([sx*cx,sy*cx,0]) children();
}
module fc_locations() {
  for (angle = [0,90,180,270])
    rotate([0,0,angle]) translate([fc_r,0,0]) children();
}
module full_duct() {
  // Lightened ring cage: bottom and top toroidal rails joined by 16 pillars.
  // Full-height solid tubes were ~15g on 65mm; too heavy for micro-whoops.
  // Structural impact/finger-safety are NOT certified by this geometry.
  union() {
    difference() {
      cylinder(r=duct_r_out,h=2.2);
      translate([0,0,-eps]) cylinder(r=duct_r_in,h=2.2+2*eps);
    }
    translate([0,0,duct_h-3.0])
      difference() {
        cylinder(r=duct_r_out,h=3.0);
        translate([0,0,-eps]) cylinder(r=duct_r_in,h=3.0+2*eps);
      }
    for (a=[0:22.5:337.5])
      rotate([0,0,a]) translate([duct_r_in+duct_wall/2,0,0])
        cylinder(d=duct_wall*1.18,h=duct_h);
  }
}
module rotor_mount() {
  // Three 1S tinywhoop M1.4 motor screws at 6.6mm PCD.
  // The central opening is for wires/inspection; screw depths need confirmation.
  difference() {
    cylinder(d=motor_pad_d,h=plate_h);
    translate([0,0,-eps])
      cylinder(d=motor_center_hole,h=plate_h+2*eps);
    for (angle=[0,120,240])
      rotate([0,0,angle])
        translate([motor_bolt_pcd/2,0,-eps])
          cylinder(d=motor_bolt_hole,h=plate_h+2*eps);
  }
}
module fc_mount() {
  difference() {
    cylinder(d=fc_boss_d,h=plate_h);
    translate([0,0,-eps])
      cylinder(d=fc_hole_d,h=plate_h+2*eps);
  }
}
module radial_rib() {
  hull() {
    cylinder(d=strut_w,h=plate_h);
    translate([duct_r_in+duct_wall*0.75,0,0])
      cylinder(d=strut_w,h=plate_h);
  }
}
module motor_to_center_beam(sx,sy) {
  hull() {
    cylinder(d=strut_w+1,h=plate_h);
    translate([sx*cx,sy*cx,0]) cylinder(d=strut_w+1,h=plate_h);
  }
}
module fc_to_center_beam(angle) {
  rotate([0,0,angle]) hull() {
    cylinder(d=strut_w+1,h=plate_h);
    translate([fc_r,0,0]) cylinder(d=strut_w+1,h=plate_h);
  }
}
// Flat-bottom FDM candidate; no supports assumed in base orientation.
// Tall hollow ducts are purposefully one printable solid with the struts.
module drone_frame() {
  union() {
    cylinder(d=11,h=plate_h);
    motor_locations() {
      full_duct();
      rotor_mount();
      for (angle=[0,90,180,270])
        rotate([0,0,angle]) radial_rib();
    }
    for (sx=[-1,1],sy=[-1,1]) motor_to_center_beam(sx,sy);
    for (angle=[0,90,180,270]) fc_to_center_beam(angle);
    fc_locations() fc_mount();
  }
}
drone_frame();
'''
    frame = body.replace("__PARAMS__", vars)

    # Separate open-top battery channel, not a fictitious cell model.
    cradle_vars = "\n".join([
        f"battery_w={_n(a.battery_w_mm)};",
        f"battery_h={_n(a.battery_h_mm)};",
        f"battery_l={_n(a.battery_l_mm)};",
        f"clearance={_n(a.battery_clearance_mm)};",
        f"wall={_n(a.battery_cradle_wall_mm)};",
    ])
    cradle = r'''// HS removable battery *fit prototype* (physical pack dimensions must
// be independently measured). Open top prevents bridging and makes printing
// possible flat on the build plate. Attach with a verified restraint strap.
$fn=48;
__PARAMS__
inner_w=battery_w+clearance;
inner_h=battery_h+clearance;
outer_w=inner_w+2*wall;
base_h=wall;
channel_l=max(16,battery_l-4);
module battery_channel() {
  union() {
    cube([outer_w,channel_l,base_h]);
    cube([wall,channel_l,inner_h+wall]);
    translate([outer_w-wall,0,0])
      cube([wall,channel_l,inner_h+wall]);
    // Two unobstructed cross-strap tunnel feet, outside pack contact zone.
    for (y=[2,channel_l-5])
      translate([-3,y,0]) cube([outer_w+6,3,base_h]);
  }
}
battery_channel();
'''
    return {
        "aerial_frame.scad": frame,
        "battery_cradle.scad": cradle.replace("__PARAMS__", cradle_vars),
    }
