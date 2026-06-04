module carriage() {
  w = 68.0; h = 28.0; t = 10.0;
  rod_clear = 9.2; rod_spacing = 40.0;
  belt_w = 6.0; belt_slot_h = 2.4;
  difference() {
    cube([w, h, t], center=false);
    // rod bores
    translate([w/2 - rod_spacing/2, h/2, -1]) cylinder(h=t+2, d=rod_clear, center=false);
    translate([w/2 + rod_spacing/2, h/2, -1]) cylinder(h=t+2, d=rod_clear, center=false);
    // belt slot
    translate([w/2 - 14, h/2 - belt_w/2, t/2 - belt_slot_h/2]) cube([28, belt_w, belt_slot_h], center=false);
  }
}
carriage();
