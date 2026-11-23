// HS removable battery *fit prototype* (physical pack dimensions must
// be independently measured). Open top prevents bridging and makes printing
// possible flat on the build plate. Attach with a verified restraint strap.
$fn=48;
battery_w=11.9;
battery_h=7;
battery_l=27;
clearance=0.5;
wall=1.2;
inner_w=battery_w+clearance;
inner_h=battery_h+clearance;
outer_w=inner_w+2*wall;
base_h=wall;
channel_l=max(16,battery_l-4);
module battery_channel() {
  union() {
    cube([outer_w,channel_l,base_h]);
    cube([wall,channel_l,inner_h+wall]);
    translate([outer_w-wall,0,0])
      cube([wall,channel_l,inner_h+wall]);
    // Two unobstructed cross-strap tunnel feet, outside pack contact zone.
    for (y=[2,channel_l-5])
      translate([-3,y,0]) cube([outer_w+6,3,base_h]);
  }
}
battery_channel();
