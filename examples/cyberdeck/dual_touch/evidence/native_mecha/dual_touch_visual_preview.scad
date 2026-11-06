// HS source-backed dual-touch *visual mock-up*, not operating electronics
use <base_shell.scad>
use <lid_shell.scad>
angle=-135.0; hy=86.2; hz=14.8;
color([0.14,0.19,0.26]) base_shell();
color([0.23,0.30,0.39]) translate([0,hy,hz]) rotate([angle,0,0]) translate([0,-hy,-hz]) lid_shell();
color([0.03,0.09,0.13]) translate([6.950000000000003,8.600000000000001,13.5]) cube([106.1,67.8,0.3]);
// Draw the SOFTWARE keyboard on the lower virtual screen, NOT on the case
for(row=[0:3]) for(col=[0:9]) translate([10.950000000000003+col*9.809999999999999,17.6+row*11,13.85])
  color([0.25,0.38,0.48]) cube([8.909999999999998,9,0.15]);
// Model placeholder for upper LCD and terminal. It rotates with the lid.
translate([0,hy,hz]) rotate([angle,0,0]) translate([0,-hy,-hz]) {
  color([0.025,0.065,0.085]) translate([6.950000000000003,8.600000000000001,16.3]) cube([106.1,67.8,0.3]);
  color([0.21,0.92,0.61]) translate([10.950000000000003,23.6,16.2]) linear_extrude(height=0.02) text("ssh optiplex",size=4);
  color([0.14,0.65,0.45]) translate([10.950000000000003,33.6,16.2]) linear_extrude(height=0.02) text("tmux attach",size=4);
}
