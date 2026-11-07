// Side-pin candidate; lid rotation around internal X axis, not a hardware test.
use <base_shell.scad>
use <lid_shell.scad>
angle_deg=-135.0;hy=76.6;hz=12.5;
color([0.15,0.24,0.31]) base_shell();
color([0.4,0.54,0.63])
translate([0,hy,hz]) rotate([angle_deg,0,0])
  translate([0,-hy,-hz]) lid_shell();
