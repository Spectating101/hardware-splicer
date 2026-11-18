"""Source-bound mechanical preview for two existing PCB halves and key apertures.

Native Edge.Cuts polygon, not a board bounding box. The source switch plate
geometry is conservatively represented as axis-aligned 14 mm apertures and
must be validated against actual switches, stabilizers and donor hardware.
The OpenSCAD files are parametric source *previews*, not an authorized case.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree as ET

from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union


APERTURE_MM=14.0
MODEL_PLATE_THICKNESS_MM=1.6


def verify_route_receipt(route:dict) -> None:
    expected=route.get("payload_sha256")
    payload={k:v for k,v in route.items() if k!="payload_sha256"}
    digest=hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False,
                                     separators=(",",":")).encode()).hexdigest()
    if digest!=expected:
        raise ValueError("source cut SHA-bound route receipt changed")
    if route.get("physical_cut_authorized") is not False:
        raise ValueError("source saw model claims physical authorization")


def _fmt(v):
    return f"{v:.5f}".rstrip("0").rstrip(".")


def _outline_scad(half, keys, origin):
    x0,y0=origin
    exterior=list(half.exterior.coords)[:-1]
    points=",".join("["+_fmt(x-x0)+","+_fmt(y-y0)+"]" for x,y in exterior)
    holes="\n".join(
        f"    translate([{_fmt(k['x']-x0-APERTURE_MM/2)},{_fmt(k['y']-y0-APERTURE_MM/2)},-0.15]) "
        f"cube([{APERTURE_MM},{APERTURE_MM},plate_thickness+0.3]);"
        for k in keys
    )
    return (
        "// HS source-bound research preview; NOT a finished or printed keyboard plate.\n"
        "// Original KiCad board edges and selected virtual cut are immutable evidence.\n"
        "// Key aperture axis/orientation/stabilizers and mounting are NOT physically verified.\n"
        f"plate_thickness={MODEL_PLATE_THICKNESS_MM};\n"
        f"// {len(keys)} retained source key centers; no mounting points designed.\n"
        "difference(){\n"
        f"  linear_extrude(height=plate_thickness) polygon(points=[{points}]);\n"
        f"{holes}\n"
        "}\n"
    )


def _svg_path(poly):
    if poly.is_empty:
        return ""
    coords=list(poly.exterior.coords)
    return "M "+" L ".join(_fmt(x)+" "+_fmt(y) for x,y in coords)+" Z"


def create_plate_preview(source:dict, route:dict, consequence:dict,
                         outline:dict, output:Path) -> dict:
    sha=source.get("source_sha256")
    if not sha or any(s!=sha for s in (
        route.get("source_sha256"),consequence.get("source_sha256"),
        outline.get("source_file_sha256")
    )):
        raise ValueError("source donor PCB hashes differ")
    verify_route_receipt(route)
    if (consequence.get("cut_path_sha256")!=route.get("payload_sha256") or
        consequence.get("nominally_salvageable_except_sacrificed_switches") is not True):
        raise ValueError("original electrical/component cut not source-bound and safe within model")
    if outline.get("source_edge_geometry_measured") is not True:
        raise ValueError("original native Edge.Cuts not established")
    polygon=Polygon(outline["tessellated_edge_cuts_points_mm"])
    if not polygon.is_valid or polygon.is_empty or len(polygon.interiors):
        raise ValueError("source board outline invalid or slotted")
    cut=LineString(route["cut_points_mm"]).buffer(
        float(route["kerf_mm"])/2,cap_style="flat",join_style="mitre"
    )
    result=polygon.difference(cut)
    if result.geom_type!="MultiPolygon" or len(result.geoms)!=2:
        raise ValueError("modeled kerf does not form exactly two isolated PCB halves")
    halves=sorted(result.geoms,key=lambda g:g.centroid.x)
    original_keys={str(s["ref"]):s for s in source.get("switch_positions",[])}
    sacrificed={str(s["ref"]) for s in consequence.get("sacrificed_switches",[])}
    if len(original_keys)!=len(source.get("switch_positions",[])):
        raise ValueError("source switch positions duplicate")
    if sacrificed-set(original_keys):
        raise ValueError("removed switch not present on source donor")
    allocated=[[],[]]
    margin=[]
    min_hole_distance=float("inf")
    for key in source.get("switch_positions",[]):
        if key["ref"] in sacrificed:
            continue
        hole=box(key["x"]-APERTURE_MM/2,key["y"]-APERTURE_MM/2,
                 key["x"]+APERTURE_MM/2,key["y"]+APERTURE_MM/2)
        touching=[i for i,half in enumerate(halves) if half.covers(Point(key["x"],key["y"]))]
        if len(touching)!=1:
            raise ValueError(f"original retained switch {key['ref']} lies on the cut or outside board")
        i=touching[0]
        if not halves[i].covers(hole):
            raise ValueError(f"original switch aperture clipped by saw or source edge: {key['ref']}")
        dist=hole.distance(halves[i].boundary)
        if dist<1.0:
            raise ValueError(f"source switch plate wall smaller than 1 mm: {key['ref']}")
        min_hole_distance=min(min_hole_distance,dist)
        allocated[i].append(key)
        margin.append((key["ref"],round(dist,5)))
    count=sum(len(k) for k in allocated)
    if count+len(sacrificed)!=len(original_keys):
        raise ValueError("retained and remounted source keys not accounted for")
    if [len(x) for x in allocated]!=[
        consequence["remaining_left"],consequence["remaining_right"]
    ]:
        raise ValueError("source cut consequence does not match new physical plate halves")
    for idx,keys in enumerate(allocated):
        all_holes=[
            box(k["x"]-APERTURE_MM/2,k["y"]-APERTURE_MM/2,
                k["x"]+APERTURE_MM/2,k["y"]+APERTURE_MM/2)
            for k in keys
        ]
        for j,a in enumerate(all_holes):
            for b in all_holes[j+1:]:
                if a.distance(b)<1.0:
                    raise ValueError("adjacent source switch apertures leave insufficient web")
    output.mkdir(parents=True,exist_ok=True)
    names=("left","right")
    for i,(half,keys) in enumerate(zip(halves,allocated)):
        origin=half.bounds[:2]
        (output/(names[i]+".scad")).write_text(
            _outline_scad(half,keys,origin),encoding="utf-8"
        )
    minx,miny,maxx,maxy=polygon.bounds
    xmlns="http://www.w3.org/2000/svg"
    ET.register_namespace("",xmlns)
    svg=ET.Element("{"+xmlns+"}svg",{
        "viewBox":f"{_fmt(minx-3)} {_fmt(miny-3)} {_fmt(maxx-minx+6)} {_fmt(maxy-miny+6)}",
        "width":_fmt(maxx-minx+6)+"mm",
        "height":_fmt(maxy-miny+6)+"mm"
    })
    for name,half,keys in zip(names,halves,allocated):
        group=ET.SubElement(svg,"{"+xmlns+"}g",{"id":name,"fill":"none"})
        ET.SubElement(group,"{"+xmlns+"}path",{
            "d":_svg_path(half),"stroke":"#475569","stroke-width":"0.45",
            "fill":"#64748b","fill-opacity":".11",
        })
        for key in keys:
            ET.SubElement(group,"{"+xmlns+"}rect",{
                "x":_fmt(key["x"]-APERTURE_MM/2),
                "y":_fmt(key["y"]-APERTURE_MM/2),
                "width":_fmt(APERTURE_MM),"height":_fmt(APERTURE_MM),
                "stroke":"#64748b","stroke-width":".23"
            })
    ET.SubElement(svg,"{"+xmlns+"}path",{
        "d":_svg_path(cut),"stroke":"#ef4444",
        "stroke-width":".1","fill":"#ef4444","fill-opacity":".25"
    })
    (output/"board_half_switch_plate.svg").write_bytes(
        ET.tostring(svg,encoding="utf-8",xml_declaration=True)
    )
    summary={
        "schema":"hs.keyboard-half-plate-source-outline-preview.v1",
        "source_sha256":sha,
        "cut_path_sha256":route["payload_sha256"],
        "native_edge_cuts_source":outline.get("source_name"),
        "original_board_outline_vertices":len(outline["tessellated_edge_cuts_points_mm"]),
        "original_source_board_area_mm2":round(polygon.area,4),
        "postcut_halves_area_mm2":[round(h.area,4) for h in halves],
        "modeled_cut_removed_board_area_mm2":round(polygon.area-sum(h.area for h in halves),4),
        "retained_switch_positions_left_right":[len(x) for x in allocated],
        "source_switches_relocated":sorted(sacrificed),
        "accounted_original_switch_count":len(original_keys),
        "switch_aperture_mm":APERTURE_MM,
        "minimum_modeled_aperture_to_source_outline_or_cut_mm":round(min_hole_distance,4),
        "switch_cutout_to_cut_web_pass":True,
        "original_switch_population_physically_confirmed":False,
        "original_source_stabilizer_geometry_verified":False,
        "actual_case_mounting_design_verified":False,
        "source_np_through_holes_used_as_case_mounts":False,
        "native_scad_render_or_print_verified":False,
        "fabrication_release":"BLOCKED_MECHANICAL_REFERENCE_ONLY",
        "output_files":["left.scad","right.scad","board_half_switch_plate.svg"],
    }
    (output/"PLATE_GEOMETRY_CHECK.json").write_text(
        json.dumps(summary,ensure_ascii=False,indent=2)+"\n",
        encoding="utf-8"
    )
    return summary


def main():
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--source-json",required=True,type=Path)
    parser.add_argument("--route-json",required=True,type=Path)
    parser.add_argument("--multi-route-json",required=True,type=Path)
    parser.add_argument("--outline-json",required=True,type=Path)
    parser.add_argument("--out",required=True,type=Path)
    args=parser.parse_args()
    source=json.loads(args.source_json.read_text(encoding="utf-8"))
    route=json.loads(args.route_json.read_text(encoding="utf-8"))
    audit=json.loads(args.multi_route_json.read_text(encoding="utf-8"))
    outline=json.loads(args.outline_json.read_text(encoding="utf-8"))
    result=create_plate_preview(source,route,audit["selected_consequence"],outline,args.out)
    print("ORIGINAL_KICAD_OUTLINE_VERTICES",result["original_board_outline_vertices"])
    print("POSTCUT_RETENTION",result["retained_switch_positions_left_right"])
    print("MINIMUM_APERTURE_CLEARANCE_MM",result["minimum_modeled_aperture_to_source_outline_or_cut_mm"])
    print("PLATE_SOURCE_STATUS",result["fabrication_release"])


if __name__=="__main__":
    main()
