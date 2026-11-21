// Thor QWERTY retrofit conceptual solids, mm
// Source scan and exact inner housing *not* redistributed or certified.
// Two attachments are displayed OVER original control areas.
// This is not a cutting template or closed-lid clearance proof.
include_scan = false;
source_scan = "/tmp/hs-thor-open-reference-20261109.stl";
if (include_scan) color([0.55,0.55,0.58,0.4]) import(source_scan, convexity=3);
pcb_thickness = 1.0;  // exploratory, not KiCad stackup qualified
switch_height = 1.9; // C&K KMR2 spec over PCB
cap_extra_height = 1.2; // unverified cap geometry
module_z = 28.0; // placeholder: NOT qualified from internal scan
module_mounts_known = false;
module_lid_clearance_known = false;
// left: original controls should be removed, but mounts unproven
color([0.12,0.36,0.48,0.76]) translate([-72.7,-67.0,module_z]) cube([36.0,57.0,pcb_thickness]);
color([0.81,0.92,0.78]) translate([-71.450,-19.500,module_z+pcb_thickness+switch_height]) cube([5.5,7.0,cap_extra_height]); // Q
color([0.81,0.92,0.78]) translate([-64.450,-19.500,module_z+pcb_thickness+switch_height]) cube([5.5,7.0,cap_extra_height]); // W
color([0.81,0.92,0.78]) translate([-57.450,-19.500,module_z+pcb_thickness+switch_height]) cube([5.5,7.0,cap_extra_height]); // E
color([0.81,0.92,0.78]) translate([-50.450,-19.500,module_z+pcb_thickness+switch_height]) cube([5.5,7.0,cap_extra_height]); // R
color([0.81,0.92,0.78]) translate([-43.450,-19.500,module_z+pcb_thickness+switch_height]) cube([5.5,7.0,cap_extra_height]); // T
color([0.81,0.92,0.78]) translate([-71.450,-30.000,module_z+pcb_thickness+switch_height]) cube([5.5,7.0,cap_extra_height]); // A
color([0.81,0.92,0.78]) translate([-64.450,-30.000,module_z+pcb_thickness+switch_height]) cube([5.5,7.0,cap_extra_height]); // S
color([0.81,0.92,0.78]) translate([-57.450,-30.000,module_z+pcb_thickness+switch_height]) cube([5.5,7.0,cap_extra_height]); // D
color([0.81,0.92,0.78]) translate([-50.450,-30.000,module_z+pcb_thickness+switch_height]) cube([5.5,7.0,cap_extra_height]); // F
color([0.81,0.92,0.78]) translate([-43.450,-30.000,module_z+pcb_thickness+switch_height]) cube([5.5,7.0,cap_extra_height]); // G
color([0.81,0.92,0.78]) translate([-71.450,-40.500,module_z+pcb_thickness+switch_height]) cube([5.5,7.0,cap_extra_height]); // Z
color([0.81,0.92,0.78]) translate([-64.450,-40.500,module_z+pcb_thickness+switch_height]) cube([5.5,7.0,cap_extra_height]); // X
color([0.81,0.92,0.78]) translate([-57.450,-40.500,module_z+pcb_thickness+switch_height]) cube([5.5,7.0,cap_extra_height]); // C
color([0.81,0.92,0.78]) translate([-50.450,-40.500,module_z+pcb_thickness+switch_height]) cube([5.5,7.0,cap_extra_height]); // V
color([0.81,0.92,0.78]) translate([-43.450,-40.500,module_z+pcb_thickness+switch_height]) cube([5.5,7.0,cap_extra_height]); // B
color([0.81,0.92,0.78]) translate([-71.450,-51.000,module_z+pcb_thickness+switch_height]) cube([5.5,7.0,cap_extra_height]); // 1
color([0.81,0.92,0.78]) translate([-64.450,-51.000,module_z+pcb_thickness+switch_height]) cube([5.5,7.0,cap_extra_height]); // 2
color([0.81,0.92,0.78]) translate([-57.450,-51.000,module_z+pcb_thickness+switch_height]) cube([5.5,7.0,cap_extra_height]); // 3
color([0.81,0.92,0.78]) translate([-50.450,-51.000,module_z+pcb_thickness+switch_height]) cube([5.5,7.0,cap_extra_height]); // 4
color([0.81,0.92,0.78]) translate([-43.450,-51.000,module_z+pcb_thickness+switch_height]) cube([5.5,7.0,cap_extra_height]); // 5
color([0.81,0.92,0.78]) translate([-71.450,-61.500,module_z+pcb_thickness+switch_height]) cube([5.5,7.0,cap_extra_height]); // SHIFT
color([0.81,0.92,0.78]) translate([-64.450,-61.500,module_z+pcb_thickness+switch_height]) cube([5.5,7.0,cap_extra_height]); // CTRL
color([0.81,0.92,0.78]) translate([-57.450,-61.500,module_z+pcb_thickness+switch_height]) cube([5.5,7.0,cap_extra_height]); // ALT
color([0.81,0.92,0.78]) translate([-50.450,-61.500,module_z+pcb_thickness+switch_height]) cube([5.5,7.0,cap_extra_height]); // TAB
color([0.81,0.92,0.78]) translate([-43.450,-61.500,module_z+pcb_thickness+switch_height]) cube([5.5,7.0,cap_extra_height]); // FN
// right: original controls should be removed, but mounts unproven
color([0.12,0.36,0.48,0.76]) translate([40.0,-67.0,module_z]) cube([36.0,57.0,pcb_thickness]);
color([0.81,0.92,0.78]) translate([41.250,-19.500,module_z+pcb_thickness+switch_height]) cube([5.5,7.0,cap_extra_height]); // Y
color([0.81,0.92,0.78]) translate([48.250,-19.500,module_z+pcb_thickness+switch_height]) cube([5.5,7.0,cap_extra_height]); // U
color([0.81,0.92,0.78]) translate([55.250,-19.500,module_z+pcb_thickness+switch_height]) cube([5.5,7.0,cap_extra_height]); // I
color([0.81,0.92,0.78]) translate([62.250,-19.500,module_z+pcb_thickness+switch_height]) cube([5.5,7.0,cap_extra_height]); // O
color([0.81,0.92,0.78]) translate([69.250,-19.500,module_z+pcb_thickness+switch_height]) cube([5.5,7.0,cap_extra_height]); // P
color([0.81,0.92,0.78]) translate([41.250,-30.000,module_z+pcb_thickness+switch_height]) cube([5.5,7.0,cap_extra_height]); // H
color([0.81,0.92,0.78]) translate([48.250,-30.000,module_z+pcb_thickness+switch_height]) cube([5.5,7.0,cap_extra_height]); // J
color([0.81,0.92,0.78]) translate([55.250,-30.000,module_z+pcb_thickness+switch_height]) cube([5.5,7.0,cap_extra_height]); // K
color([0.81,0.92,0.78]) translate([62.250,-30.000,module_z+pcb_thickness+switch_height]) cube([5.5,7.0,cap_extra_height]); // L
color([0.81,0.92,0.78]) translate([69.250,-30.000,module_z+pcb_thickness+switch_height]) cube([5.5,7.0,cap_extra_height]); // ;
color([0.81,0.92,0.78]) translate([41.250,-40.500,module_z+pcb_thickness+switch_height]) cube([5.5,7.0,cap_extra_height]); // N
color([0.81,0.92,0.78]) translate([48.250,-40.500,module_z+pcb_thickness+switch_height]) cube([5.5,7.0,cap_extra_height]); // M
color([0.81,0.92,0.78]) translate([55.250,-40.500,module_z+pcb_thickness+switch_height]) cube([5.5,7.0,cap_extra_height]); // ,
color([0.81,0.92,0.78]) translate([62.250,-40.500,module_z+pcb_thickness+switch_height]) cube([5.5,7.0,cap_extra_height]); // .
color([0.81,0.92,0.78]) translate([69.250,-40.500,module_z+pcb_thickness+switch_height]) cube([5.5,7.0,cap_extra_height]); // /
color([0.81,0.92,0.78]) translate([41.250,-51.000,module_z+pcb_thickness+switch_height]) cube([5.5,7.0,cap_extra_height]); // 6
color([0.81,0.92,0.78]) translate([48.250,-51.000,module_z+pcb_thickness+switch_height]) cube([5.5,7.0,cap_extra_height]); // 7
color([0.81,0.92,0.78]) translate([55.250,-51.000,module_z+pcb_thickness+switch_height]) cube([5.5,7.0,cap_extra_height]); // 8
color([0.81,0.92,0.78]) translate([62.250,-51.000,module_z+pcb_thickness+switch_height]) cube([5.5,7.0,cap_extra_height]); // 9
color([0.81,0.92,0.78]) translate([69.250,-51.000,module_z+pcb_thickness+switch_height]) cube([5.5,7.0,cap_extra_height]); // 0
color([0.81,0.92,0.78]) translate([41.250,-61.500,module_z+pcb_thickness+switch_height]) cube([5.5,7.0,cap_extra_height]); // SYM
color([0.81,0.92,0.78]) translate([48.250,-61.500,module_z+pcb_thickness+switch_height]) cube([5.5,7.0,cap_extra_height]); // SPACE
color([0.81,0.92,0.78]) translate([55.250,-61.500,module_z+pcb_thickness+switch_height]) cube([5.5,7.0,cap_extra_height]); // ENTER
color([0.81,0.92,0.78]) translate([62.250,-61.500,module_z+pcb_thickness+switch_height]) cube([5.5,7.0,cap_extra_height]); // BSPC
color([0.81,0.92,0.78]) translate([69.250,-61.500,module_z+pcb_thickness+switch_height]) cube([5.5,7.0,cap_extra_height]); // ESC
