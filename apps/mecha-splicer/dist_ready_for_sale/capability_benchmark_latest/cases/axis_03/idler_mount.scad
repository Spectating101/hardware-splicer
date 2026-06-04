module idler_mount() {
  plate_w = 70.0;
  plate_h = 55.0;
  t = 6.0;
  difference() {
    cube([plate_w, plate_h, t], center=false);
    translate([plate_w/2 - 12.0/2, plate_h/2 - 18.0/2, -1]) cube([12.0, 18.0, t+2], center=false);
    translate([plate_w/2, plate_h/2, -1]) cylinder(h=t+2, d=5.2, center=false);
    translate([plate_w/2 - 40.0/2, 10.0, -1]) cylinder(h=t+2, d=10.0, center=false);
    translate([plate_w/2 + 40.0/2, 10.0, -1]) cylinder(h=t+2, d=10.0, center=false);
  }
}
idler_mount();
