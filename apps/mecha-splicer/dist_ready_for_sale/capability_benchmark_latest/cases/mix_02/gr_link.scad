module gr_link() {
  w=12.0; t=4.0;
  len = 50;
  difference() {
    cube([len,w,t], center=false);
    translate([w/2, w/2, -1]) cylinder(h=t+2, d=3.2, center=false);
    translate([len-w/2, w/2, -1]) cylinder(h=t+2, d=3.2, center=false);
  }
}
gr_link();
