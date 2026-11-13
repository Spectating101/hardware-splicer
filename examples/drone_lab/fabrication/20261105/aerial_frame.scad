// Generated directly by Hardware Splicer: parametric ducted quadrotor.
// Four real ducts, four 3-hole motor mounts, four 26mm-rotated FC holes.
// Source equipment dimensional contract ≠ evidence of physical fit.
$fn = 72;
wheelbase=65;
prop_d=31;
radial=0.8;
duct_wall=1.2;
duct_h=16;
plate_h=2.2;
strut_w=2.6;
motor_pad_d=11.5;
motor_bolt_pcd=6.6;
motor_bolt_hole=1.6;
motor_center_hole=2.9;
fc_pitch=26;
fc_hole_d=2;
fc_boss_d=6;
chamfer=0;
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
