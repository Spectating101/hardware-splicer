"""Generate neutral, millimeter-scale components and reference drawings."""
import csv
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

    def polygon(self, name, points, kind="cut"):
        node = ET.SubElement(self.root, "polygon", {
            "id": name, "data-operation": kind, "stroke-width": "0.16", "fill": "none",
            "stroke": {"cut": "#b52e24", "ref": "#216793", "score": "#363636"}[kind],
            "points": " ".join(f"{number(x)},{number(y)}" for x,y in points),
        })
        return node

    def write(self, path):
        ET.indent(self.root, "  ")
        ET.ElementTree(self.root).write(path, encoding="utf-8", xml_declaration=True)


def write_rows(path, headings, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(headings)
        writer.writerows(rows)


def origin_block(d, p, folder, revision):
    x_wall,y_wall,z_top=p["face_offsets_mm"]
    d.rectangle("machined-block-top",25,30,70,55)
    d.rectangle("stock-relief",25+x_wall,30+y_wall,70-x_wall-8,55-y_wall-8,"ref")
    d.rectangle("top-wall-section",122,54,54,z_top)
    d.circle("contact-stylus",155,101,p["stylus_r_mm"],"ref")
    d.rectangle("isolated-connector",128,132,27,17)
    d.circle("orientation-key",135,139,2.2,"score")
    rows=[]
    for i,fixture in enumerate(p["job_origins_mm"]):
        for j,axis in enumerate("XYZ"):
            face=p["face_offsets_mm"][j]
            polarity=p["face_sign"][j]
            radius=p["stylus_r_mm"] if axis in "XY" else 0
            raw=fixture[j]+polarity*(face+radius)+p["event_error_mm"][i][j]
            rows.append((i+1,axis,f"{raw:.3f}", radius if p["radius_comp"] else 0))
    write_rows(folder/f"{revision}-touch.csv",("job","axis","trigger_mm","applied_stylus_mm"), rows)


def setter(d,p,folder,revision):
    d.circle("puck-body",56,65,27)
    d.circle("contact-target",56,65,13)
    for y in (48,82):
        d.circle(f"bed-fastener-{y}",40,y,2.55)
    d.rectangle("bed-foot-section",104,118,56,9)
    d.line("uncompressed",(105,73),(158,73),"ref")
    d.line("nominal-trigger",(105,73+p["trip_mm"]),(158,73+p["trip_mm"]),"score")
    d.line("bottom-of-stroke",(105,73+p["travel_mm"]),(158,73+p["travel_mm"]),"ref")
    d.rectangle("spring-pocket-section",108,138,48,p["travel_mm"])


def tram(d,p,folder,revision):
    x,y=150,95
    l=p["span_mm"]
    d.center("beam-blank",x,y,l+44,33)
    d.circle("center-shank",x,y,6)
    for i,xx in enumerate((x-l/2,x+l/2)):
        d.circle(f"indicator-{i}",xx,y,4)
        d.center(f"indicator-foot-{i}",xx,155,26,22)
        d.circle(f"foot-bore-{i}",xx,155,4)
    rows=[]
    for pair,(err1,err2) in enumerate(p["events_mm"],1):
        for sign in ((1,-1) if p["reverse"] else (1,)):
            if sign == -1:
                err1,err2 = p["reversed_events_mm"][pair-1]
            input_delta=sign*math.tan(math.radians(p["test_tilt_deg"]))*l
            left=1.35-input_delta/2+p["zero_bias_mm"][0]+err1
            right=1.35+input_delta/2+p["zero_bias_mm"][1]+err2
            rows.append((pair,sign,f"{left:.5f}",f"{right:.5f}"))
    write_rows(folder/f"{revision}-readings.csv",("pair","direction","indicator_a_mm","indicator_b_mm"),rows)


def kerf(d,p,folder,revision):
    d.rectangle("guide-body",16,35,143,25)
    d.rectangle("lock-travel",25,43,104,8)
    d.rectangle("fixed-stop",172,35,18,25)
    d.rectangle("moving-stop",172,70,18,25)
    for i,run in enumerate(p["samples"]):
        y=96+i*30
        stock,kerf_width,set_error=run
        advance=stock-(kerf_width if p["compensation"] else 0)+set_error
        d.line(f"mating-stock-{i}",(25,y),(25+stock,y),"ref")
        d.line(f"actual-kerf-{i}",(62,y),(62+kerf_width,y),"ref")
        d.line(f"gauge-transfer-{i}",(95,y),(95+advance,y),"score")


def insert(d,p,folder,revision):
    upper=60
    sep=p["guide_span_mm"]
    d.rectangle("upright-blank",25,40,60,150)
    d.circle("guide-0",55,upper,5.15)
    d.circle("guide-1",55,upper+sep,5.15)
    d.circle("rod-gauge",143,67,5,"ref")
    d.center("collar-blank",143,67,44,36)
    d.circle("iron-bore",143,67,10)
    d.line("tip-throw",(98,166),(98,166+p["tip_arm_mm"]),"ref")
    d.line("depth-travel",(113,166),(113,166+p["depth_stop_mm"]),"score")
    d.rectangle("base-plate-blank",108,213,98,36)
    for x in (120,194):
        d.circle(f"base-mount-{x}",x,231,3.2)


def balancer(d,p,folder,revision):
    d.rectangle("stand-foot",19,35,150,31)
    d.rectangle("stand-cheek-0",19,85,63,88)
    d.rectangle("stand-cheek-1",96,85,63,88)
    for i,x in enumerate((51,128)):
        d.circle(f"seat-{i}",x,108,5.1)
    d.circle("arbor",56,212,2.5)
    d.circle("friction-contact-radius",56,212,p["friction_r_mm"],"ref")
    d.center("wheel-envelope",151,198,2*p["test_weight_arm_mm"],2*p["test_weight_arm_mm"],"ref")
    d.line("imbalance-arm",(151,198),(151+p["test_weight_arm_mm"],198),"ref")
    d.polygon("cone-section",[(101,224),(123,216),(123,236),(101,228)])


def dish(d,p,folder,revision):
    x=365
    d.center("arch-blank",x,72,666,36)
    for i,s in enumerate((-1,1)):
        lo,hi=p["slot_mm"]
        center=x+s*(hi+lo)/2
        d.center(f"foot-slot-{i}",center,72,hi-lo,8)
    d.center("hub-stem-slot",x,72,9,24)
    for i,r in enumerate(p["wheel_radii_mm"]):
        d.line(f"wheel-rim-span-{i}",(x-r,112+13*i),(x+r,112+13*i),"ref")
    a,b=p["pad_heights_mm"]
    d.rectangle("left-pad-section",87,161,28,a)
    d.rectangle("right-pad-section",126,161,28,b)
    d.rectangle("rim-surface-thickness-gauge",215,161,p["rim_face_width_mm"],8,"ref")


def hanger(d,p,folder,revision):
    d.rectangle("swing-arm-blank",19,31,334,27)
    d.circle("spindle",34,44,5)
    d.rectangle("indicator-travel-slot",283,40,60,8)
    for i,endy in enumerate((93,126)):
        d.circle(f"support-seat-{i}",35,endy,p["bore_mm"]/2)
    d.circle("shaft-gauge",93,93,5,"ref")
    d.rectangle("separation-gauge",118,82,p["seat_distance_mm"],21)
    x,y=45,173
    for k in range(4):
        theta=math.tau*k/4
        d.line(f"rim-direction-{k}",(x,y),(x+22*math.cos(theta),y-22*math.sin(theta)),"score")
    rows=[]
    for k,(vx,vy) in enumerate(((1,0),(0,1),(-1,0),(0,-1))):
        value=p["indicator_zero_mm"]+p["known_components_mm"][0]*vx+p["known_components_mm"][1]*vy
        rows.append((k,f"{value+p['sample_error_mm'][k]:.3f}"))
    write_rows(folder/f"{revision}-indicator.csv",("pose","synthetic_reading_mm"),rows)


def angle_stop(d,p,folder,revision):
    x,y=157,158
    d.rectangle("fence-blank",30,192,215,24)
    d.circle("pivot",x,y,3.1)
    rr=p["index_radius_mm"]
    for angle in (-45,0,45):
        t=math.radians(angle)
        d.circle(f"index-{angle}",x+math.sin(t)*rr,y-math.cos(t)*rr,2.2)
    d.line("square-reference",(x,y),(x,y-rr-8))
    a=33
    for i,xx in enumerate((a,a+p["contacts_mm"])):
        d.rectangle(f"rail-pad-{i}",xx,240,10,10,"score")
    d.rectangle("guide-profile-reference",25,232,224,25,"ref")
    d.rectangle("rail-key-width-gauge",263,39,16,p["key_width_mm"])
    d.rectangle("host-groove-envelope",287,39,16,p["groove_mm"],"ref")


def straightedge(d,p,folder,revision):
    x,y=26,57
    d.line("nut-datum",(x,49),(x,65),"score")
    points=[(x-8,28),(x-8,y)]
    n=p["frets"]
    for f in range(1,n+1):
        center=x+p["scale_mm"]*(1-2**(-f/12))
        w=p["notch_mm"]/2
        points += [(center-w,y),(center-w,y-p["relief_mm"]),
                   (center+w,y-p["relief_mm"]),(center+w,y)]
    points += [(x+521,y),(x+521,28)]
    d.polygon("straightedge-blank",points)
    for f in (1,12,n):
        position=x+p["scale_mm"]*(1-2**(-f/12))
        d.line(f"fret-mark-{f}",(position,34),(position,40),"score")


DESIGNS = {
    "P076":(origin_block,230,200), "P077":(setter,210,190), "P078":(tram,300,230),
    "P086":(kerf,230,200), "P099":(insert,230,270), "P105":(balancer,220,260),
    "P106":(dish,730,225), "P107":(hanger,400,215), "P110":(angle_stop,330,280),
    "P245":(straightedge,580,90),
}


def export(destination):
    params=json.loads((ROOT/"parameters.json").read_text(encoding="utf-8"))
    if params.keys() != DESIGNS.keys():
        raise ValueError("Each catalog trial needs parameters and an SVG design")
    for ident,(design,w,h) in DESIGNS.items():
        folder=destination/ident
        folder.mkdir(parents=True,exist_ok=True)
        common={k:v for k,v in params[ident].items() if k not in ("baseline","revised")}
        for revision in ("baseline","revised"):
            drawing=Drawing(ident,revision,w,h)
            design(drawing,common | params[ident][revision],folder,revision)
            drawing.write(folder/f"{revision}.svg")


if __name__ == "__main__":
    export(Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT/"artifacts")
