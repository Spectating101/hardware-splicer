module endstop_mount() {
  difference() {
    cube([30.0, 20.0, 6.0], center=false);
    translate([10.5, 10.0, -1]) cylinder(h=8.0, d=2.2, center=false);
    translate([19.5, 10.0, -1]) cylinder(h=8.0, d=2.2, center=false);
    translate([7.0, 14.0, 2.0]) cube([16, 5, 2], center=false);
  }
}
endstop_mount();
