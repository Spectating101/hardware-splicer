module pt_base() {
  w=120.0; h=80.0; t=6.0;
  difference() {
    cube([w,h,t], center=false);
    translate([(w-40.7-2*0.6)/2, (h-19.7-2*0.6)/2, -1])
      cube([40.7+2*0.6, 19.7+2*0.6, t+2], center=false);
  }
}
pt_base();
