// HS source-backed dual-touch *visual mock-up*, not operating electronics
use <base_shell.scad>
use <lid_shell.scad>
angle=-135.0; hy=81.2; hz=13.8;
color([0.14,0.19,0.26]) base_shell();
color([0.23,0.30,0.39]) translate([0,hy,hz]) rotate([angle,0,0]) translate([0,-hy,-hz]) lid_shell();
color([0.03,0.09,0.13]) translate([13.700000000000003,3.3500000000000014,12.9]) cube([127.6,73.3,0.3]);
// Draw the SOFTWARE keyboard on the lower virtual screen, NOT on the case
for(row=[0:3]) for(col=[0:9]) translate([17.700000000000003+col*11.959999999999999,12.350000000000001+row*11,13.25])
  color([0.25,0.38,0.48]) cube([11.059999999999999,9,0.15]);
// Model placeholder for upper LCD and terminal. It rotates with the lid.
translate([0,hy,hz]) rotate([angle,0,0]) translate([0,-hy,-hz]) {
  color([0.025,0.065,0.085]) translate([13.700000000000003,3.3500000000000014,14.9]) cube([127.6,73.3,0.3]);
  color([0.21,0.92,0.61]) translate([17.700000000000003,18.35,14.8]) linear_extrude(height=0.02) text("ssh optiplex",size=4);
  color([0.14,0.65,0.45]) translate([17.700000000000003,28.35,14.8]) linear_extrude(height=0.02) text("tmux attach",size=4);
}
