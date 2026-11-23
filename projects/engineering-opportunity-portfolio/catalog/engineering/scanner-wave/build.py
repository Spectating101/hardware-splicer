"""Generate neutral, millimeter-scale components and reference drawings."""
import json
import math
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent


def number(value):
    return f"{value:.6f}".rstrip("0").rstrip(".") or "0"


class Drawing:
    def __init__(self, product, revision, width=220, height=285):
        self.root = ET.Element("svg", {"xmlns": "http://www.w3.org/2000/svg",
                                      "width": f"{width}mm", "height": f"{height}mm",
                                      "viewBox": f"0 0 {width} {height}"})
        ET.SubElement(self.root, "title").text = f"{product} {revision} · full-size proof coupon"
        self.rectangle("scale", 10, 6, 20, 10, "score")

    def mark(self, tag, name, kind, **attrs):
        data = {key: number(v) for key, v in attrs.items()}
        ET.SubElement(self.root, tag, {"id": name, "data-operation": kind, "stroke-width": "0.16",
                                     "fill": "none", "stroke": {"cut": "#b52e24", "ref": "#216793",
                                                                 "score": "#363636"}[kind], **data})

    def rectangle(self, name, x, y, w, h, kind="cut"):
        self.mark("rect", name, kind, x=x, y=y, width=w, height=h)

    def center(self, name, x, y, w, h, kind="cut"):
        self.rectangle(name, x-w/2, y-h/2, w, h, kind)

    def circle(self, name, x, y, r, kind="cut"):
        self.mark("circle", name, kind, cx=x, cy=y, r=r)

    def line(self, name, a, b, kind="ref"):
        self.mark("line", name, kind, x1=a[0], y1=a[1], x2=b[0], y2=b[1])

    def write(self, path):
        ET.indent(self.root, "  ")
        ET.ElementTree(self.root).write(path, encoding="utf-8", xml_declaration=True)


def light(d, p):
    x,y = 108,94
    d.center("light-body-envelope",x,y,*p["body_mm"],"ref")
    d.center("lit-region",x,y,*p["light_mm"],"ref")
    d.center("opaque-baffle",x,y,157,102)
    d.center("baffle-window",x,y,*p["aperture"])
    d.center("projected-film-coupon",x,y,*p["coupon_frame_mm"],"ref")
    d.rectangle("wall-height-gauge",30,178,35,p["wall_height_mm"])


def platen(d, name, origin, body_origin, dimensions):
    x,y = origin
    keepout_length = {"V600": 24, "4870": 30}[name]
    d.rectangle("host-window-coupon",x,y,112,198,"ref")
    d.rectangle("preserve-calibration-zone",x,y,112,keepout_length,"ref")
    d.rectangle("carrier",*body_origin,*dimensions)


def disc(d,p):
    platen(d,"V600",(20,24),(24,56),(102,111))
    cx,cy = 75,110
    disc_r = p["media_diameter_mm"]/2
    ring_radius = p["frame_radius_mm"]
    d.circle("disc-outer-reference",cx,cy,disc_r,"ref")
    d.circle("spindle-bore",cx,cy,3.2)
    d.center("target-frame",cx,cy-ring_radius,*p["frame_mm"],"ref")
    d.center("optical-window",cx,cy-ring_radius,11.85,9.5)
    for i in range(p["frames"]):
        theta = math.tau*i/p["frames"]
        d.line(f"index-{i}",(cx+(disc_r-1)*math.sin(theta),cy-(disc_r-1)*math.cos(theta)),
               (cx+(disc_r+1.5)*math.sin(theta),cy-(disc_r+1.5)*math.cos(theta)), "score")
    key_y = cy+disc_r-3
    d.center("index-shoe",166,92,20,16)
    d.center("index-shoe-slot",166,92,2+2*p["key_half_slack"],4)
    d.circle("index-tip",cx,key_y,1,"ref")


def edge_hold(d,p):
    platen(d,"V600",(20,24),(25,55),(98,100))
    cx,cy=74,105
    d.center("media-ref",cx,cy,82,p["film_width_mm"],"ref")
    d.center("image-target",cx,cy,p["nominal_frame_mm"],p["nominal_frame_mm"],"ref")
    d.center("scan-opening",cx,cy,44,42.5)
    for j in (-1,1):
        d.center(f"edge-strip-{j}",162,83+20*j,76,2.5)
        for i,x in enumerate(p["clip_x"]):
            d.center(f"station-{j}-{i}",cx+x,cy+j*(p["film_width_mm"]/2-1.3),3.5,1.8,"score")


def keyed(d,p):
    platen(d,"V600",(20,24),(26,56),(98,90))
    cx,cy = 75,99
    d.center("media-ref",cx,cy,74,p["media_w_mm"],"ref")
    d.center("image-target",cx,cy,*p["frame_mm"],"ref")
    d.center("scan-opening",cx,cy,29.3,29.3)
    d.center("perforation",cx-4,cy-15.75,*p["hole_size_mm"],"ref")
    d.circle("orientation-key-0",cx-4,cy-15.75,0.55,"ref")
    if p["engage_both"]:
        d.circle("orientation-key-1",cx-4,cy+15.75,0.55,"ref")
    d.center("key-stock",159,73,24,12)
    d.circle("key-press-hole",159,73,0.55)


def focus(d,p):
    platen(d,"V600",(20,24),(25,54),(101,133))
    cx,cy=75.5,121
    d.center("media-ref",cx,cy,p["media_w_mm"],106,"ref")
    d.center("scan-opening",cx,cy,57.5,68)
    d.center("image-target",cx,cy,*p["frame_mm"],"ref")
    for i,h in enumerate(p["shim_options"]):
        # Stock section, thickness dimension is physically drawn at 1:1.
        d.rectangle(f"shim-section-{i}",146,60+13*i,32,h)
    for x in (46,105):
        d.center(f"shim-footprint-{x}",x,170,10,15,"score")


def narrow(d,p):
    platen(d,"4870",(20,24),(29,62),(96,102))
    cx,cy=77,111
    d.center("media-ref",cx,cy,80,p["film_w_mm"],"ref")
    for i in range(4):
        d.center(f"sample-{i}",cx+(i-1.5)*p["film_pitch_mm"],cy,*p["frame_mm"],"ref")
        d.center(f"window-{i}",cx+(i-1.5)*p["pitch"],cy,18.15,14.1)
    d.rectangle("rail-upper",139,97,80,2.5)
    d.rectangle("rail-lower",139,121,80,2.5)


def cine(d,p):
    platen(d,"V600",(20,24),(27,58),(97,81))
    cx,cy=75.5,99
    d.center("media-ref",cx,cy,78,p["media_w_mm"],"ref")
    for i in (-1,0,1):
        d.center(f"frame-{i}",cx+i*p["frame_pitch_mm"],cy+0.93,*p["frame_mm"],"ref")
    d.center("perforation-side",cx,cy-2.93,78,2.14,"ref")
    d.center("still-window",cx,cy+p["aperture_y"],3.67,5.22)
    d.rectangle("pressure-rail-upper",143,101,69,1.35)
    d.rectangle("pressure-rail-lower",143,115,69,1.35)


DESIGNS = {"P009":light,"P011":disc,"P012":edge_hold,"P013":keyed,"P014":focus,"P015":narrow,"P016":cine}


def export(destination):
    data = json.loads((ROOT/"parameters.json").read_text(encoding="utf-8"))
    for ident, design in DESIGNS.items():
        directory = destination/ident
        directory.mkdir(parents=True, exist_ok=True)
        common = {k:v for k,v in data[ident].items() if k not in ("baseline","revised")}
        for revision in ("baseline","revised"):
            drawing = Drawing(ident,revision)
            design(drawing, common | data[ident][revision])
            drawing.write(directory/f"{revision}.svg")


if __name__ == "__main__":
    export(Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT/"artifacts")
