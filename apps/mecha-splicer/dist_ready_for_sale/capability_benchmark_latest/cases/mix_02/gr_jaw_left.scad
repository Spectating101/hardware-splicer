module gr_jaw_left() {
  mirror([0,1,0]) {
    len=70.0; w=14.0; t=6.0;
    difference() {
      cube([len,w,t], center=false);
      translate([w/2, w/2, -1]) cylinder(h=t+2, d=3.2, center=false);
      translate([31.50, w/2, -1]) cylinder(h=t+2, d=3.2, center=false);
    }
  }
}
gr_jaw_left();
