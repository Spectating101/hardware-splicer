module rod_holder() {
  rod_clear = 9.2;
  od = 18.0; w = 24.0; t = 10.0; slit = 1.5;
  bolt_d = 3.2; nut_flat = 5.6;
  difference() {
    cube([w, od, t], center=false);
    translate([w/2, od/2, -1]) cylinder(h=t+2, d=rod_clear, center=false);
    translate([w/2 - slit/2, 0, -1]) cube([slit, od, t+2], center=false);
    translate([w*0.25, od*0.25, -1]) cylinder(h=t+2, d=bolt_d, center=false);
    translate([w*0.75, od*0.75, -1]) cylinder(h=t+2, d=bolt_d, center=false);
    translate([w*0.25, od*0.25, 0]) cylinder(h=4, d=nut_flat, $fn=6, center=false);
    translate([w*0.75, od*0.75, 0]) cylinder(h=4, d=nut_flat, $fn=6, center=false);
  }
}
rod_holder();
