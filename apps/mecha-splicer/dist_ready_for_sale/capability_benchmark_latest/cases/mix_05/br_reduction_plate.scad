module br_reduction_plate() {
  w=120.0; h=80.0; t=6.0;
  difference() {
    cube([w, h, t], center=false);
    translate([28.0, 40.0, -1]) cylinder(h=t+2, d=22.0, center=false);
    translate([28.0 + -1*31.0/2, 40.0 + -1*31.0/2, -1]) cylinder(h=t+2, d=3.4, center=false);
    translate([28.0 + -1*31.0/2, 40.0 + 1*31.0/2, -1]) cylinder(h=t+2, d=3.4, center=false);
    translate([28.0 + 1*31.0/2, 40.0 + -1*31.0/2, -1]) cylinder(h=t+2, d=3.4, center=false);
    translate([28.0 + 1*31.0/2, 40.0 + 1*31.0/2, -1]) cylinder(h=t+2, d=3.4, center=false);
    translate([88.0, 40.0, t-(5.4)]) cylinder(h=6.4, d=16.8, center=false);
    translate([88.0, 40.0, -1]) cylinder(h=t+2, d=5.8, center=false);
    translate([58.0, 58.0, t-(5.4)]) cylinder(h=6.4, d=16.8, center=false);
    translate([58.0, 58.0, -1]) cylinder(h=t+2, d=5.8, center=false);
  }
}
br_reduction_plate();
