module rj_arm() {
  len = 90.0; w = 18.0; t = 6.0;
  shaft_hole_d = 8.6;
  hole_d = 3.2; pitch = 20.0; n = 3;
  difference() {
    cube([len, w, t], center=false);
    translate([w/2, w/2, -1]) cylinder(h=t+2, d=shaft_hole_d, center=false);
    for (i=[0:n-1]) {
      x = w/2 + (i+1)*pitch;
      if (x < len - w/2) translate([x, w/2, -1]) cylinder(h=t+2, d=hole_d, center=false);
    }
  }
}
rj_arm();
