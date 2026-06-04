module tensioner_block() {
  difference() {
    cube([40.0, 25.0, 10.0], center=false);
    translate([10.0, 9.5, -1]) cube([20.0, 6.0, 12.0], center=false);
    translate([20.0, 12.5, -1]) cylinder(h=12.0, d=5.2, center=false);
  }
}
tensioner_block();
