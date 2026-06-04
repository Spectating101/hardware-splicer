module belt_clamp() {
  difference() {
    cube([30.0, 16.0, 6.0], center=false);
    translate([6.0, 4.5, 1.8]) cube([18.0, 7.0, 2.4], center=false);
    translate([7.5, 8.0, -1]) cylinder(h=8.0, d=3.2, center=false);
    translate([22.5, 8.0, -1]) cylinder(h=8.0, d=3.2, center=false);
  }
}
belt_clamp();
