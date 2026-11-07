// Mecha-Splicer assembly preview only. Angle 0=closed; -135=open.
use <base_shell.scad>
use <lid_shell.scad>
angle_deg = -135.0;
hy=81.2; hz=12.5;
color([0.17,0.23,0.31]) base_shell();
color([0.42,0.53,0.61])
translate([0,hy,hz]) rotate([angle_deg,0,0])
  translate([0,-hy,-hz]) lid_shell();
