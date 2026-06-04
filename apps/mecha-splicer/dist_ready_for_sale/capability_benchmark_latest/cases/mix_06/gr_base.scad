module gr_base() {
  w=110.0; h=60.0; t=6.0;
  difference() {
    cube([w,h,t], center=false);
    translate([(w-40.7-2*0.6)/2, (h-19.7-2*0.6)/2, -1])
      cube([40.7+2*0.6, 19.7+2*0.6, t+2], center=false);
    translate([37.0, 15.0, -1]) cylinder(h=t+2, d=3.2, center=false);
    translate([73.0, 15.0, -1]) cylinder(h=t+2, d=3.2, center=false);
  }
}
gr_base();
