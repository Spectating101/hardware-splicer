module gr_preview() {
  // Scissor gripper preview (non-kinematic).
  gr_base();
  translate([10, 0, 8]) gr_jaw_left();
  translate([60, 0, 8]) gr_jaw_right();
  // Note: assemble with real fasteners; iterate pivot spacing/geometry as needed.
}
gr_preview();
