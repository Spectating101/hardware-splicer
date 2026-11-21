"""Write full-scale fabrication contours in mm. Run verify.py to test them."""

import json
import struct
import sys
from pathlib import Path
from xml.etree import ElementTree as ET


HERE = Path(__file__).resolve().parent


def solid(filename, length, width, holes, diameter, window, height):
    from shapely import constrained_delaunay_triangles
    from shapely.geometry import Point, box
    from shapely.geometry.polygon import orient

    face = box(0, 0, length, width)
    if window is not None:
        x, y = (length-window)/2, (width-window)/2
        face = face.difference(box(x, y, x+window, y+window))
    for x, y in holes:
        face = face.difference(Point(x,y).buffer(diameter/2, quad_segs=12))
    face = orient(face, sign=1)
    facets = []
    for triangle in constrained_delaunay_triangles(face).geoms:
        a, b, c = list(orient(triangle, sign=1).exterior.coords)[:3]
        facets.extend([((*a,height), (*b,height), (*c,height)), ((*c,0), (*b,0), (*a,0))])
    for ring in (face.exterior, *face.interiors):
        for a,b in zip(ring.coords, list(ring.coords)[1:]):
            facets.extend([((*a,0), (*b,0), (*b,height)), ((*a,0), (*b,height), (*a,height))])
    with (HERE / filename).with_suffix(".stl").open("wb") as out:
        out.write(b"P010 millimetres".ljust(80, b"\0") + struct.pack("<I", len(facets)))
        for a,b,c in facets:
            u = [bi-ai for ai,bi in zip(a,b)]
            v = [ci-ai for ai,ci in zip(a,c)]
            normal = [u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0]]
            magnitude = sum(n*n for n in normal)**0.5
            out.write(struct.pack("<12fH", *(n/magnitude for n in normal), *a, *b, *c, 0))


def cut_sheet(filename, length, width, holes, diameter, height, window=None):
    svg = ET.Element("svg", {
        "xmlns": "http://www.w3.org/2000/svg", "width": f"{length:g}mm",
        "height": f"{width:g}mm", "viewBox": f"0 0 {length:g} {width:g}",
        "fill": "none", "stroke": "#000000", "stroke-width": "0.02",
    })
    ET.SubElement(svg, "title").text = filename
    ET.SubElement(svg, "rect", id="outline", x="0", y="0", width=f"{length:g}", height=f"{width:g}")
    if window is not None:
        ET.SubElement(svg, "rect", id="aperture", x=f"{(length-window)/2:g}",
                      y=f"{(width-window)/2:g}", width=f"{window:g}", height=f"{window:g}")
    for x, y in holes:
        ET.SubElement(svg, "circle", cx=f"{x:g}", cy=f"{y:g}", r=f"{diameter/2:g}")
    ET.indent(svg)
    (HERE / filename).write_text(ET.tostring(svg, encoding="unicode") + "\n", encoding="utf-8")
    if "--stl" in sys.argv[1:]:
        solid(filename, length, width, holes, diameter, window, height)


def main():
    d = json.loads((HERE / "design.json").read_text())
    length, width = d["sheet_length_mm"], d["sheet_width_mm"]
    inset_x, inset_y = d["locator_inset_x_mm"], d["locator_inset_y_mm"]
    diameter = d["locator_diameter_mm"]
    if not 0 < diameter / 2 < min(inset_x, inset_y):
        raise ValueError("Locator holes cross an outside edge")
    corners = [(x, y) for x in (inset_x, length-inset_x) for y in (inset_y, width-inset_y)]
    for part in ("base", "mask"):
        window = d[part + "_window_mm"]
        if not 0 < window < min(width, length):
            raise ValueError("Aperture exceeds plate")
        cut_sheet(part + ".svg", length, width, corners, diameter, d[part+"_thickness_mm"], window)
    strips = {"support": d["support_gap_mm"]}
    strips.update({"guide-" + name: v["gap_mm"] for name, v in d["guide_profiles"].items()})
    for part, gap in strips.items():
        strip_width = (width-gap)/2
        if not inset_y + diameter/2 < strip_width < width/2:
            raise ValueError("Strip does not contain the two locating holes")
        height = d["support_thickness_mm"] if part == "support" else d["guide_thickness_mm"]
        cut_sheet(part+".svg", length, strip_width,
                  [(inset_x, inset_y), (length-inset_x, inset_y)], diameter, height)


if __name__ == "__main__":
    main()
