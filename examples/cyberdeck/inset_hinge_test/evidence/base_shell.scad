// Native Mecha-Splicer side-pin hinge. CAD ONLY; no metal pin, no verified flex/stop/torque.
// Hinge is fully enclosed in the declared closed XY silhouette.
$fn=56;
W=155.0; D=80.0; wall=1.6; floor=1.6;
HBASE=12.1; HLID=5.1; gap=0.8;
hy=76.6; hz=12.5;
kr=3.4; bore=2.7;

module base_shell() {
  difference() {
    union() {
      difference() {
        cube([W,D,HBASE]);
        translate([wall,wall,floor]) cube([W-2*wall,D-2*wall,HBASE+1]);
        // Remove the upper rear wall in swing zone (shell only).
        translate([-0.1,74.0,HBASE-6.7]) cube([W+0.2,6.1,6.9]);
      }
// Side pivot barrels tie into the rear shell wall at both ends.
      translate([1.0,hy,hz]) rotate([0,90,0]) cylinder(h=3.2,r=3.4);
      translate([150.8,hy,hz]) rotate([0,90,0]) cylinder(h=3.2,r=3.4);
    }
// Sculpt relief for the rotating *lid* barrels within the base wall.
    translate([4.680000000000001,hy,hz]) rotate([0,90,0]) cylinder(h=3.64,r=3.75);
    translate([146.68,hy,hz]) rotate([0,90,0]) cylinder(h=3.64,r=3.75);
    translate([0.88,hy,hz]) rotate([0,90,0]) cylinder(h=3.4400000000000004,d=bore);
    translate([150.68,hy,hz]) rotate([0,90,0]) cylinder(h=3.4400000000000004,d=bore);
// Rear center FPC pass-through (bend, EMC and flex cycles NOT VERIFIED).
    translate([63.5,D-wall-0.1,HBASE-3.5]) cube([28,wall+0.2,4.1]);
  }
}
base_shell();
