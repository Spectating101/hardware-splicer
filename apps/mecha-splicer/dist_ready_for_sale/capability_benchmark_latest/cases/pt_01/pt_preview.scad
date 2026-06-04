module pt_preview() {
  // Pan/tilt preview (non-kinematic).
  pt_base();
  translate([130.0, 0, 0]) pt_bracket();
  translate([220.0, 0, 0]) pt_platform();
}
pt_preview();
