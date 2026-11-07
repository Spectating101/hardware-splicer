// Two full panel-thickness proxy solids, NOT manufacturer STEP geometry.
use <base_shell.scad>
use <lid_shell.scad>
hy=76.6;hz=12.5;angle=-135.0;
color([0.12,0.17,0.23]) base_shell();
color([0.31,0.44,0.53]) translate([0,hy,hz]) rotate([angle,0,0]) translate([0,-hy,-hz]) lid_shell();
color([0.03,0.08,0.10]) translate([13.700000000000003,3.3500000000000014,8.649999999999999]) cube([127.6,73.3,3.45]);
translate([0,hy,hz]) rotate([angle,0,0]) translate([0,-hy,-hz]) {
  color([0.03,0.08,0.10]) translate([13.700000000000003,3.3500000000000014,12.9]) cube([127.6,73.3,3.45]);
}
