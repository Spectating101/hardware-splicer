module motor_mount() {
  plate_w = 70.0;
  plate_h = 70.0;
  t = 6.0;
  hole_spacing = 31.0;
  bore_d = 22.0;
  mount_hole_d = 3.4;
  difference() {
    cube([plate_w, plate_h, t], center=false);
    translate([plate_w/2, plate_h/2, -1]) cylinder(h=t+2, d=bore_d, center=false);
    translate([plate_w/2 + -1*hole_spacing/2, plate_h/2 + -1*hole_spacing/2, -1]) cylinder(h=t+2, d=mount_hole_d, center=false);
    translate([plate_w/2 + -1*hole_spacing/2, plate_h/2 + 1*hole_spacing/2, -1]) cylinder(h=t+2, d=mount_hole_d, center=false);
    translate([plate_w/2 + 1*hole_spacing/2, plate_h/2 + -1*hole_spacing/2, -1]) cylinder(h=t+2, d=mount_hole_d, center=false);
    translate([plate_w/2 + 1*hole_spacing/2, plate_h/2 + 1*hole_spacing/2, -1]) cylinder(h=t+2, d=mount_hole_d, center=false);
    // rod clearances
    translate([plate_w/2 - 40.0/2, 12.0, -1]) cylinder(h=t+2, d=10.0, center=false);
    translate([plate_w/2 + 40.0/2, 12.0, -1]) cylinder(h=t+2, d=10.0, center=false);
  }
}
motor_mount();
