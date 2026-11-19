"""Read the release SVGs and replay the distinct optical and fit trials."""
import itertools
import json
import math
import sys
import tempfile
from pathlib import Path
from xml.etree import ElementTree as ET

from build import ROOT, export

SVG = "{http://www.w3.org/2000/svg}"


def require(result, message):
    if not result:
        raise ValueError(message)


def vals(node, *keys):
    return tuple(float(node.attrib[key]) for key in keys)


def rect(node):
    return vals(node, "x", "y", "width", "height")


def ctr(node):
    x, y, w, h = rect(node)
    return x+w/2, y+h/2


def parse(path):
    root = ET.parse(path).getroot()
    require(root.tag == SVG+"svg", "Invalid SVG root")
    w, h = [float(root.attrib[k].removesuffix("mm")) for k in ("width","height")]
    require(all(root.attrib[k].endswith("mm") for k in ("width","height")), "No physical SVG units")
    require(tuple(map(float,root.attrib["viewBox"].split())) == (0,0,w,h), "SVG physical scale mismatch")
    require(not any("transform" in node.attrib for node in root.iter()), "Unexpected transform")
    nodes = {}
    for node in root:
        if node.tag == SVG+"title":
            continue
        name = node.attrib["id"]
        require(name not in nodes, f"Duplicate element {name}")
        require(node.attrib.get("data-operation") in {"cut","ref","score"}, f"Unknown operation in {name}")
        nodes[name] = node
        if node.tag == SVG+"rect":
            x, y, dx, dy = rect(node)
            require(dx > 0 and dy > 0, f"Invalid cut shape {name}")
            coords = (x,y,x+dx,y+dy)
        elif node.tag == SVG+"circle":
            x,y,r = vals(node,"cx","cy","r")
            require(r > 0, f"Invalid circle {name}")
            coords = (x-r,y-r,x+r,y+r)
        elif node.tag == SVG+"line":
            coords = vals(node,"x1","y1","x2","y2")
        else:
            raise ValueError(f"Unexpected SVG shape {node.tag}")
        require(all(0<=v<=lim for v,lim in zip(coords,(w,h,w,h))), f"{name} extends outside page")
    require(rect(nodes["scale"])[2:] == (20,10), "SVG dimensional coupon has changed")
    return nodes


def m(value, relation, limit, unit="mm"):
    valid = value >= limit-1e-7 if relation == "≥" else value <= limit+1e-7
    return {"value":round(value,5),"relation":relation,"target":limit,"unit":unit,"pass":valid}


def rectangle_margin(opening, target):
    x,y,w,h = rect(opening)
    u,v,a,b = rect(target)
    return min(u-x, v-y, x+w-u-a, y+h-v-b)


def platen(nodes, p):
    _,ky,_,kh = rect(nodes["preserve-calibration-zone"])
    _,cy,_,_ = rect(nodes["carrier"])
    return {
        "Synthetic calibration-zone clearance":m(cy-ky-kh,"≥",3),
        "Carrier to coupon footprint edge":m(rectangle_margin(nodes["host-window-coupon"],nodes["carrier"]),"≥",3),
    }


def light(nodes, p):
    _,_,w,h = rect(nodes["baffle-window"])
    _,_,gw,gh = rect(nodes["projected-film-coupon"])
    _,_,_,thickness = rect(nodes["wall-height-gauge"])
    placement = p["misregistration_mm"] + thickness*math.tan(math.radians(p["ray_deg"]))
    return {
        "Minimum field clearance at maximum ray slope":m(rectangle_margin(nodes["baffle-window"],nodes["projected-film-coupon"])-placement,"≥",1),
        "Bright area outside target as a share of aperture":m(100*(1-gw*gh/(w*h)),"≤",25,"%"),
        "Aperture coverage by published lit field":m(rectangle_margin(nodes["lit-region"],nodes["baffle-window"]),"≥",10),
        "Baffle margin inside outer light body":m(rectangle_margin(nodes["light-body-envelope"],nodes["opaque-baffle"]),"≥",3),
    }


def disc(nodes,p):
    cx,cy = vals(nodes["disc-outer-reference"],"cx","cy")
    key_x,key_y,key_r = vals(nodes["index-tip"],"cx","cy","r")
    half_slack = (rect(nodes["index-shoe-slot"])[2]-2*key_r)/2
    tangential_at_key = math.dist((cx,cy),(key_x,key_y))
    angular_bound = math.asin(half_slack/tangential_at_key)
    x,y,w,h = rect(nodes["target-frame"])
    wx,wy,ww,wh = rect(nodes["optical-window"])
    # Include both angular extremes and densely scan between them for possible corner extrema.
    minimum = math.inf
    for a in range(201):
        theta = angular_bound*(a/100-1)
        for u,v in itertools.product((x,x+w),(y,y+h)):
            xx = cx+(u-cx)*math.cos(theta)-(v-cy)*math.sin(theta)
            yy = cy+(u-cx)*math.sin(theta)+(v-cy)*math.cos(theta)
            minimum = min(minimum,xx-wx,yy-wy,wx+ww-xx,wy+wh-yy)
    angles = []
    for i in range(p["frames"]):
        x2,y2 = vals(nodes[f"index-{i}"],"x2","y2")
        angles.append(math.degrees(math.atan2(x2-cx,cy-y2))%360)
    gaps = [(b-a)%360 for a,b in zip(angles,angles[1:]+angles[:1])]
    return platen(nodes,p) | {
        "Worst indexed frame margin":m(minimum-p["center_tolerance_mm"],"≥",0.12),
        "Largest index scale interval error":m(max(abs(a-360/p["frames"]) for a in gaps),"≤",0.02,"deg"),
        "Rotational seating uncertainty":m(math.degrees(angular_bound),"≤",0.6,"deg"),
    }


def edge_hold(nodes,p):
    spans, image_margins = [], []
    _,y,_,h = rect(nodes["image-target"])
    for side in (-1,1):
        stations = [node for name,node in nodes.items() if name.startswith(f"station-{side}-")]
        xs = sorted(ctr(n)[0] for n in stations)
        spans.extend(b-a for a,b in zip(xs,xs[1:]))
        for station in stations:
            _,sy,_,sh = rect(station)
            image_margins.append(max(sy-y-h,y-sy-sh))
    radius = p["minimum_edge_radius_mm"]
    span = max(spans)+2*p["locator_error_mm"]
    sag = radius-math.sqrt(radius**2-(span/2)**2)
    return platen(nodes,p) | {
        "Worst modeled free-edge rise":m(sag,"≤",0.50),
        "Minimum clamp-to-image margin":m(min(image_margins)-p["locator_error_mm"],"≥",0.30),
        "Minimum aperture margin":m(rectangle_margin(nodes["scan-opening"],nodes["image-target"])-p["locator_error_mm"],"≥",0.5),
    }


def keyed(nodes,p):
    hx,hy,hw,hh = rect(nodes["perforation"])
    mid_line = ctr(nodes["media-ref"])[1]
    pin_fit_margins, reversed_fit = [], []
    for name,node in nodes.items():
        if not name.startswith("orientation-key-"):
            continue
        x,y,r=vals(node,"cx","cy","r")
        pad = r+p["location_error_mm"]
        pin_fit_margins.append(min(x-hx, y-hy, hx+hw-x, hy+hh-y)-pad)
        reflected_y = 2*mid_line-hy-hh
        reversed_fit.append(min(x-hx, y-reflected_y, hx+hw-x, reflected_y+hh-y)-pad)
    return platen(nodes,p) | {
        "Forward orientation minimum pin seating margin":m(min(pin_fit_margins),"≥",0.15),
        "Reversed orientation maximum pin seating margin":m(max(reversed_fit),"≤",-0.15),
        "Minimum aperture margin":m(rectangle_margin(nodes["scan-opening"],nodes["image-target"])-p["location_error_mm"],"≥",0.4),
    }


def focus(nodes,p):
    shims = sorted(rect(n)[3] for k,n in nodes.items() if k.startswith("shim-section-"))
    low,high = p["focus_band_mm"]
    err = p["placement_error_mm"]
    reserves = [min(h-err-low, high-h-err) for h in shims]
    return platen(nodes,p) | {
        "Best worst-case hypothetical focus reserve":m(max(reserves),"≥",0.15),
        "Total prototype shim sweep":m(shims[-1]-shims[0],"≥",0.45),
        "Frame aperture edge margin":m(rectangle_margin(nodes["scan-opening"],nodes["image-target"]),"≥",0.6),
    }


def narrow(nodes,p):
    windows = [nodes[f"window-{i}"] for i in range(4)]
    cover = [rectangle_margin(w,nodes[f"sample-{i}"]) for i,w in enumerate(windows)]
    minimum_bridge = min(rect(b)[0]-rect(a)[0]-rect(a)[2] for a,b in zip(windows,windows[1:]))
    mw = rect(nodes["media-ref"])[3]
    nw = max(rect(w)[3] for w in windows)
    return platen(nodes,p) | {
        "Worst registration margin across all four crops":m(min(cover)-p["placement_error_mm"],"≥",0.25),
        "Smallest crossbar land between apertures":m(minimum_bridge,"≥",0.6),
        "Film overlap per long edge":m((mw-nw)/2,"≥",0.8),
    }


def cine(nodes,p):
    x,y,w,h = rect(nodes["still-window"])
    u,v,a,b = rect(nodes["frame-0"])
    origin = ctr(nodes["media-ref"])
    margins=[]
    tolerance = p["placement_mm"]
    for fx,fy,angle in itertools.product((u,u+a),(v,v+b),(-p["max_skew_deg"],0,p["max_skew_deg"])):
        dx,dy = fx-origin[0],fy-origin[1]
        theta=math.radians(angle)
        xx=origin[0]+math.cos(theta)*dx-math.sin(theta)*dy
        yy=origin[1]+math.sin(theta)*dx+math.cos(theta)*dy
        margins.append(min(xx-x,yy-y,x+w-xx,y+h-yy))
    _,py,_,ph = rect(nodes["perforation-side"])
    left_l = sum(rect(nodes["frame--1"])[i] for i in (0,2))
    right_r = rect(nodes["frame-1"])[0]
    # Include a conservative half-media-width vertical lever arm for neighbor edge motion.
    skew_reserve = rect(nodes["media-ref"])[3]/2*math.sin(math.radians(p["max_skew_deg"]))
    perf_yaw_reserve = (w/2)*math.tan(math.radians(p["max_skew_deg"]))
    return platen(nodes,p) | {
        "Worst full-frame margin through skew sweep":m(min(margins)-tolerance,"≥",0.05),
        "Perforation-side exclusion margin":m(y-py-ph-tolerance-perf_yaw_reserve,"≥",0.10),
        "Minimum neighboring frame exclusion":m(min(x-left_l,right_r-x-w)-tolerance-skew_reserve,"≥",0.1),
    }


TRIALS = {"P009":light,"P011":disc,"P012":edge_hold,"P013":keyed,"P014":focus,"P015":narrow,"P016":cine}


def replay(artifacts):
    parameters=json.loads((ROOT/"parameters.json").read_text(encoding="utf-8"))
    out = {}
    for ident, trial in TRIALS.items():
        out[ident] = {}
        for rev in ("baseline","revised"):
            f=artifacts/ident/f"{rev}.svg"
            out[ident][rev] = trial(parse(f), parameters[ident])
    return out


def main():
    artifacts=ROOT/"artifacts"
    out=replay(artifacts)
    file=ROOT/"results.json"
    if "--write-results" in sys.argv:
        file.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    require(json.loads(file.read_text(encoding="utf-8"))==out,"Saved results differ from replay")
    failures=0
    passed=0
    for ident,report in out.items():
        fail = [k for k,v in report["baseline"].items() if not v["pass"]]
        pending = [k for k,v in report["revised"].items() if not v["pass"]]
        require(fail, f"{ident} baseline lacks a challenged criterion")
        require(not pending, f"{ident} revised checks failed: {', '.join(pending)}")
        failures+=len(fail)
        passed+=len(report["revised"])
        print(f"{ident} · {len(fail)} baseline failures · {len(report['revised'])} revised passes")
    with tempfile.TemporaryDirectory() as tmp:
        path=Path(tmp)
        export(path)
        files={file.relative_to(artifacts) for file in artifacts.rglob("*.svg")}
        require(files=={file.relative_to(path) for file in path.rglob("*.svg")},"Fresh export files differ")
        for name in files:
            require((path/name).read_bytes()==(artifacts/name).read_bytes(), f"{name} fails byte comparison")
    print(f"{len(out)} trials · {failures} baseline failures · {passed} revised passes · {len(files)} reproducible SVGs")


if __name__ == "__main__":
    main()
