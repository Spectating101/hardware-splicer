module rj_bearing_block() {
  w = 50.0; d = 35.0; h = 18.0;
  pocket_d = 22.6; pocket_h = 7.3;
  hole_d = 3.2;
  hx = 15.0; hy = 8.0;
  difference() {
    cube([w, d, h], center=false);
    translate([w/2, d/2, h-pocket_h]) cylinder(h=pocket_h+1, d=pocket_d, center=false);
    translate([w/2, d/2, -1]) cylinder(h=h+2, d=8.6, center=false);
    translate([w/2 + -1*hx, d/2 + -1*hy, -1]) cylinder(h=h+2, d=hole_d, center=false);
    translate([w/2 + -1*hx, d/2 + 1*hy, -1]) cylinder(h=h+2, d=hole_d, center=false);
    translate([w/2 + 1*hx, d/2 + -1*hy, -1]) cylinder(h=h+2, d=hole_d, center=false);
    translate([w/2 + 1*hx, d/2 + 1*hy, -1]) cylinder(h=h+2, d=hole_d, center=false);
  }
}
rj_bearing_block();
