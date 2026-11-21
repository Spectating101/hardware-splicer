"""Original, vendor-agnostic indoor router support bracket (print-fit prototype).

One repeatable bracket is printed TWICE: two small supports avoid requiring
a 300-mm print bed. Site-installed anchors, printed material and physical
strength have NOT been measured or approved. The assembled product is NOT
released for supporting a live device yet.
"""
from __future__ import annotations

from ..spec import IndoorRouterMountSpec


def generate_indoor_router_mount_scad(spec: IndoorRouterMountSpec) -> str:
    """Return parametric original OpenSCAD for ONE of the required two brackets.

    Coordinate system: X = bracket width, Y = distance out from wall,
    Z = height above the bottom support. Print with bottom shelf on bed.
    """
    # The device body sits between back plate inner face and lip inner face.
    # Use device depth + measured-clearance * 2 for nominal receiving gap.
    values = {
        "device_depth": spec.device_depth_mm,
        "fit_clearance": spec.clearance_mm,
        "bracket_w": spec.bracket_width_mm,
        "back_h": spec.back_height_mm,
        "back_t": spec.back_thickness_mm,
        "shelf_t": spec.shelf_thickness_mm,
        "lip_h": spec.lip_height_mm,
        "lip_t": spec.lip_thickness_mm,
        "gusset_t": spec.gusset_thickness_mm,
        "bolt_hole": spec.anchor_hole_d_mm,
        "bolt_pitch": spec.anchor_hole_pitch_mm,
    }
    vars = "\n".join(f"{k}={v:.5f};" for k,v in values.items())
    body = r"""// Authored by HS Mecha-Splicer; NOT a copy of seller/OEM CAD.
// Requires physical fit, loading, anchor and thermal verification.
// Quantity TWO for one router. Indoor wall only. No adhesive-only mounting.
$fn=64;
__VALUES__
total_depth=back_t+device_depth+fit_clearance*2+lip_t;
eps=0.08;

// L-section, with gussets OUTSIDE the central device-receiving section.
// Bottom is printable without support; z=0 lies on print bed.
module gusset(xpos) {
    // x-extruded triangular rib; three triangle vertices on each x face.
    polyhedron(
      points=[
        [xpos,0,0], [xpos,total_depth,0], [xpos,0,back_h*0.55],
        [xpos+gusset_t,0,0], [xpos+gusset_t,total_depth,0],
        [xpos+gusset_t,0,back_h*0.55]],
      faces=[[0,2,1],[3,4,5],[0,1,4,3],[1,2,5,4],[2,0,3,5]]);
}

module mount_piece() {
  difference() {
    union() {
      // wall plate and bottom supporting shelf
      cube([bracket_w,back_t,back_h]);
      cube([bracket_w,total_depth,shelf_t]);
      // positive front lip (unverified retention)
      translate([0,total_depth-lip_t,0])
        cube([bracket_w,lip_t,lip_h]);
      // side gussets: print geometry only; physical load unverified
      // triangular cross-section in Y/Z plane
      for(x=[0,bracket_w-gusset_t])
        gusset(x);
    }
    // Two M4 nominal through-holes, from wall-facing back to device-facing front.
    // Print-hole diameter/tolerance must be checked by calipers.
    for (z=[back_h/2-bolt_pitch/2,back_h/2+bolt_pitch/2])
      translate([bracket_w/2,-eps,z])
        rotate([-90,0,0])
          cylinder(h=back_t+2*eps,d=bolt_hole);
  }
}

mount_piece();
"""
    return body.replace("__VALUES__", vars)
