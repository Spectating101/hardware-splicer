// Native Mecha-Splicer side-pin hinge. CAD ONLY; no metal pin, no verified flex/stop/torque.
// Hinge is fully enclosed in the declared closed XY silhouette.
$fn=56;
W=155.0; D=80.0; wall=1.6; floor=1.6;
HBASE=12.1; HLID=5.1; gap=0.8;
hy=76.6; hz=12.5;
kr=3.4; bore=2.7;

module lid_shell() {
  difference() {
    union() {
      difference() {
        translate([0,0,12.9]) cube([W,D,HLID]);
        translate([wall,wall,12.8]) cube([W-2*wall,D-2*wall,HLID-floor+0.1]);
        // Remove the lower rear wall in swing zone (shell only).
        translate([-0.1,74.0,12.8]) cube([W+0.2,6.1,4.1]);
      }
// Anchor ears join the inner lid barrels back to outer side rails.
      translate([1.0,72.0,12.9]) cube([7.1000000000000005,3.1,1.3]);
      translate([146.9,72.0,12.9]) cube([7.1000000000000005,3.1,1.3]);
// The two lid barrels lie axially beside the base barrels.
      translate([4.9,hy,hz]) rotate([0,90,0]) cylinder(h=3.2,r=3.4);
      translate([146.9,hy,hz]) rotate([0,90,0]) cylinder(h=3.2,r=3.4);
    }
// Relieve lid shell material for both base hinge barrels.
    translate([0.78,hy,hz]) rotate([0,90,0]) cylinder(h=3.64,r=3.75);
    translate([150.58,hy,hz]) rotate([0,90,0]) cylinder(h=3.64,r=3.75);
    translate([4.78,hy,hz]) rotate([0,90,0]) cylinder(h=3.4400000000000004,d=bore);
    translate([146.78,hy,hz]) rotate([0,90,0]) cylinder(h=3.4400000000000004,d=bore);
// Upper LCD requires separate signal AND touch flex routes.
    translate([63.5,D-wall-0.1,12.8]) cube([28,wall+0.2,3.6]);
  }
}
lid_shell();
