"""Small, dependency-free sheet-panel planning adapter for HS/Mecha.

Makes an inspectable preliminary shop packet; not a licensed connector
library, automatic CAM nesting or production-ready panel toolpath.
"""
from __future__ import annotations

import csv
from io import StringIO
from html import escape
import math
from typing import Any, Mapping


def _dimension(value: Any, label: str) -> float:
    try:
        n = float(value)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"{label} must be a finite positive dimension") from exc
    if not math.isfinite(n) or n <= 0 or n > 2500:
        raise ValueError(f"{label} out of concept-planner bounds (0,2500] mm")
    return n


def make_panel_schedule(
    enclosure: Mapping[str, Any],
    construction: Mapping[str, Any],
) -> dict[str, Any]:
    """Create six butt-panel cut blanks around *specified internal dimensions*.

    Front/back overlap side panel ends; floor and lid fit INSIDE the walls.
    The assembly requires separately designed fastening and load support.
    Panel thickness does not inherit printed enclosure's wall thickness.
    """
    t_raw = construction.get("panel_thickness_mm")
    if t_raw is None:
        return {
            "status": "missing_measured_panel_thickness",
            "panels": [], "buildable": False,
            "fabrication_authorized": False,
            "blockers": ["measure_panel_thickness_before_cutting"],
        }
    t = _dimension(t_raw, "panel_thickness_mm")
    iw = _dimension(enclosure.get("inner_w_mm"), "inner_w_mm")
    idepth = _dimension(enclosure.get("inner_d_mm"), "inner_d_mm")
    ih = _dimension(enclosure.get("inner_h_mm"), "inner_h_mm")
    # Inset base/lid fully within the four side panels; external envelope
    # changes if sheet thickness differs from original printed walls.
    ow, od, oh = iw + 2*t, idepth + 2*t, ih + 2*t
    if max(ow,od,oh) > 2500:
        return {"status":"oversized_panel_envelope", "panels":[],
                "buildable":False, "fabrication_authorized":False,
                "blockers":["panel_dimensions_outside_bounded_planner"]}
    panels = [
        {"part_id":"front_back", "faces":["front","back"],
         "quantity":2,"width_mm":ow,"height_mm":oh},
        {"part_id":"left_right", "faces":["left","right"],
         "quantity":2,"width_mm":idepth,"height_mm":oh},
        {"part_id":"floor_lid", "faces":["floor","lid"],
         "quantity":2,"width_mm":iw,"height_mm":idepth},
    ]
    for part in panels:
        part["area_each_mm2"] = round(part["width_mm"]*part["height_mm"],3)
        part["area_total_mm2"] = round(
            part["area_each_mm2"]*part["quantity"],3
        )
        part["cutout_status"] = "rectangular_blank_no_ports_holes_or_nesting"
    cutouts = enclosure.get("cutouts") or []
    if not isinstance(cutouts,list):
        raise ValueError("enclosure cutouts must be a list")
    source_interfaces = [
        {
            "face": c.get("face"),
            "label": c.get("label") or "",
            "kind":c.get("kind"),
            "source_geometry": c.get("rect") if c.get("kind")=="rect" else c.get("circle"),
            "status":"untransformed_mark_for_review_not_cut",
        }
        for c in cutouts if isinstance(c,Mapping)
    ]
    area = round(sum(part["area_total_mm2"] for part in panels),3)
    return {
        "schema_version":"hardware_splicer.sheet_cut_schedule.v1",
        "status":"dimensioned_blank_cut_proposal",
        "topology":"front_back_full_width_sides_between_floor_lid_inset",
        "panel_thickness_mm":t,
        "target_internal_dimensions_mm":[iw,idepth,ih],
        "hybrid_outer_dimensions_mm":[ow,od,oh],
        "panels":panels,
        "unoptimized_total_panel_area_mm2":area,
        "blank_panel_volume_mm3":round(area*t,3),
        "untransformed_interfaces":source_interfaces,
        "blockers":[
            "panel_corner_joiner_interface_not_verified",
            "panel_floor_and_lid_attachment_not_designed",
            "panel_port_and_mount_geometry_not_transferred",
            "kerf_and_nesting_not_included",
            "material_temperature_and_structural_tests_required",
        ],
        "buildable":False,
        "fabrication_authorized":False,
    }


def schedule_csv(schedule: Mapping[str,Any]) -> str:
    buffer=StringIO()
    writer=csv.writer(buffer,lineterminator="\n")
    writer.writerow(["part_id","faces","quantity","width_mm","height_mm",
                     "thickness_mm","cutout_status"])
    for panel in schedule.get("panels") or []:
        writer.writerow([panel["part_id"],"/".join(panel["faces"]),
                         panel["quantity"],panel["width_mm"],panel["height_mm"],
                         schedule.get("panel_thickness_mm"),panel["cutout_status"]])
    return buffer.getvalue()


def schedule_svg(schedule: Mapping[str,Any]) -> str:
    """Dimensioned 1:1 blank outlines, stacked with 10mm gaps; NOT CAM."""
    panels=schedule.get("panels") or []
    if not panels:
        return ('<svg xmlns="http://www.w3.org/2000/svg" width="300" '
                'height="50" viewBox="0 0 300 50"><text x="8" y="25">'
                'NO SHEET GEOMETRY: MEASUREMENT REQUIRED</text></svg>\n')
    # Only THREE representative shapes: quantity is in the label and CSV.
    pad=18.0
    gap=15.0
    width=max(x["width_mm"] for x in panels)+2*pad
    height=sum(x["height_mm"] for x in panels)+gap*(len(panels)-1)+2*pad
    xml=[
        '<svg xmlns="http://www.w3.org/2000/svg" '+
        f'width="{width:.3f}mm" height="{height:.3f}mm" '+
        f'viewBox="0 0 {width:.3f} {height:.3f}">',
        '<title>PRELIMINARY FLAT PANEL BLANKS - NOT VERIFIED CAM</title>',
        '<desc>One representative outline per panel size. Quantities shown in labels. '
        'No kerf, holes, sockets, nesting, or actual connector mating geometry.</desc>',
    ]
    y=pad
    for x in panels:
        w=x["width_mm"]
        h=x["height_mm"]
        label=escape(f'{x["part_id"]}: {x["quantity"]} × {w:g} × {h:g} mm')
        xml.extend([
            f'<rect x="{pad:.3f}" y="{y:.3f}" width="{w:.3f}" '
            f'height="{h:.3f}" fill="none" stroke="black" stroke-width=".3"/>',
            f'<text x="{pad+2:.3f}" y="{y+5:.3f}" font-size="4" '
            f'fill="black">{label}</text>',
        ])
        y+=h+gap
    xml.append('</svg>')
    return "\n".join(xml)+"\n"


def schedule_parts(
    schedule: Mapping[str,Any],
    construction:Mapping[str,Any],
    source:Mapping[str,Any] | None = None,
) -> list[dict[str,Any]]:
    """Alternative-specific component schedule, NOT the existing full-print BOM."""
    if schedule.get("status")!="dimensioned_blank_cut_proposal":
        return []
    parts=[
        {"kind":"sheet_blank","part_id":p["part_id"],
         "quantity":p["quantity"],"width_mm":p["width_mm"],
         "height_mm":p["height_mm"],
         "thickness_mm":schedule["panel_thickness_mm"],
         "material_id":(construction.get("panel_material") or {}).get("material_id"),
         "fit_verified":False}
        for p in schedule["panels"]
    ]
    n=construction.get("connector_count",0)
    if n:
        parts.append({
            "kind":"external_connector_reference",
            "source_key":construction.get("connector_family","unselected"),
            "quantity":n,"file_verified":False,"fit_verified":False,
            "source_url":(source or {}).get("url"),
            "pinned_revision":(source or {}).get("pinned_revision"),
            "upstream_license":(source or {}).get("license"),
            "downloaded_files_repackaged":False,
        })
    parts.append({
        "kind":"external_fasteners_or_joint_support",
        "quantity":None,"fit_verified":False,
        "notes":"Determine physical retention, panel attachment and lid support by test",
    })
    return parts


def schedule_scad_preview(schedule: Mapping[str,Any]) -> str:
    """Assembly geometry visualization only: no connector joints or ports."""
    if schedule.get("status") != "dimensioned_blank_cut_proposal":
        return "// No measured sheet thickness; no hybrid preview available.\n"
    dims=schedule["hybrid_outer_dimensions_mm"]
    inside=schedule["target_internal_dimensions_mm"]
    t=schedule["panel_thickness_mm"]
    ow,od,oh=dims
    iw,idepth,ih=inside
    # full-width front/back, in-between sidewalls, inset base and lid:
    cubes=[
        ("front",0,0,0,ow,t,oh),
        ("back",0,od-t,0,ow,t,oh),
        ("left",0,t,0,t,idepth,oh),
        ("right",ow-t,t,0,t,idepth,oh),
        ("floor",t,t,t,iw,idepth,t),
        ("lid",t,t,oh-2*t,iw,idepth,t),
    ]
    lines=[
        "// HS hybrid assembly geometry - VISUAL STUDY ONLY",
        "// NO CONNECTOR SEATS, PORT CUTOUTS, FASTENER HOLES OR STRUCTURAL VALIDATION",
        "// DO NOT EXPORT THIS AS AN APPROVED MANUFACTURING MODEL",
        "module hybrid_panel_envelope_reference() {",
    ]
    for index,(name,x,y,z,w,d,h) in enumerate(cubes):
        tint=["[0.30,0.55,0.85,0.55]","[0.30,0.55,0.85,0.55]",
              "[0.90,0.60,0.30,0.55]","[0.90,0.60,0.30,0.55]",
              "[0.35,0.80,0.50,0.55]","[0.35,0.80,0.50,0.55]"][index]
        lines.extend([
            f"  // {name}: theoretical blank envelope",
            f"  color({tint}) translate([{x:g},{y:g},{z:g}]) cube([{w:g},{d:g},{h:g}],center=false);",
        ])
    lines.extend(["}","hybrid_panel_envelope_reference();",""])
    return "\n".join(lines)
