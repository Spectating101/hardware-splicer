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


def focus_rail(d, p, folder, revision):
    d.rectangle("mount-blank",20,46,98,164)
    d.line("axis",(69,55),(69,199),"score")
    d.line("travel-low",(55,74),(83,74))
    d.line("travel-high",(55,174),(83,174))
    for i, (x,y) in enumerate(((38,58),(100,58),(38,198),(100,198))):
        d.circle(f"slot-mount-{i}",x,y,3.3)
    with (folder/f"{revision}-focus.csv").open("w",newline="",encoding="utf-8") as f:
        writer = csv.writer(f,lineterminator="\n")
        writer.writerow(("event", "position_um"))
        writer.writerow(("jog", p["start_um"]-p["preroll_um"]))
        for i in range(p["exposures"]):
            writer.writerow(("expose", p["start_um"]+p["step_um"]*i))


def xy_stage(d,p,folder,revision):
    x,y=87,94
    d.center("stage-plate",x,y,118,90)
    d.center("view-window",x,y,56,42)
    d.center("specimen",x,y,20,15,"ref")
    d.line("axis-x",(x-15,y),(x+15,y),"score")
    skew=math.radians(p["y_skew_deg"])
    dx,dy=10*math.sin(skew),10*math.cos(skew)
    d.line("axis-y",(x-dx,y-dy),(x+dx,y+dy),"score")
    d.center("traveler-plate",88,201,76,52)
    for yy in (182,220):
        for xx in (58,118):
            d.circle(f"traveler-mount-{xx}-{yy}",xx,yy,2.2)


def dolly(d,p,folder,revision):
    origin=(105,174)
    axle_y=origin[1]-p["wheelbase_mm"]
    d.polygon("deck-outline",[(57,183),(62,108),(83,22),(127,22),(148,108),(153,183)])
    for i,x in enumerate((65,145)):
        d.circle(f"rear-{i}",x,origin[1],4.2)
    d.circle("steering-axle",105,axle_y,4.2)
    d.circle("camera-mount",105,126,3.2)
    d.line("fore-aft-axis",origin,(105,axle_y))
    theta=math.radians(p["steer_deg"])
    d.line("steered-wheel",(105,axle_y),(105+26*math.sin(theta),axle_y-26*math.cos(theta)),"score")
    d.center("steering-arm-stock",174,97,14,44)


def cable(d,p,folder,revision):
    d.center("cage-mount",62,83,48,31)
    for i,x in enumerate((48,76)):
        d.circle(f"cage-bore-{i}",x,83,2.2)
    d.center("split-jaw-0",133,65,39,21)
    d.center("split-jaw-1",133,104,39,21)
    d.center("pad-0",133,65,32,10,"score")
    d.center("pad-1",133,104,32,10,"score")
    d.circle("cable-guide",82,174,p["bend_radius_mm"],"ref")
    d.line("port-axis",(45,174),(82,174))
    d.rectangle("jaw-opening-gauge",138,163,28,p["jaw_open_mm"])
    d.rectangle("pad-thickness-gauge",138,192,24,p["pad_mm"])


def cage(d,p,folder,revision):
    d.rectangle("shell-coupon",35,48,132,83,"ref")
    d.rectangle("connector-corridor",35,68,40,37,"ref")
    d.rectangle("top-shoe-corridor",87,42,25,11,"ref")
    d.rectangle("door-sweep",96,120,52,38,"ref")
    d.rectangle("lower-plate",40,125,p["plate_w_mm"],12)
    d.rectangle("right-riser",154,99,9,26)
    d.rectangle("top-plate",119,43,43,8)
    for i,x in enumerate((47,81)):
        d.circle(f"base-hole-{i}",x,131,2.25)


def spur_points(x,y,mod,teeth,pa):
    pitch = mod*teeth/2
    base = pitch*math.cos(pa)
    dedendum = pitch-1.25*mod
    outside = pitch+mod

    def flank_angle(radius):
        alpha = math.acos(base/radius)
        involute = math.tan(alpha)-alpha
        pitch_involute = math.tan(pa)-pa
        return math.pi/(2*teeth) + pitch_involute-involute

    def pt(radius,angle):
        return (x+radius*math.cos(angle),y+radius*math.sin(angle))

    points = []
    lower = max(dedendum,base)
    radii = [lower+(outside-lower)*i/7 for i in range(8)]
    for tooth in range(teeth):
        phase = math.tau*tooth/teeth
        points.append(pt(dedendum,phase-math.pi/teeth))
        if dedendum < lower:
            points.append(pt(dedendum,phase-flank_angle(lower)))
        points.extend(pt(r,phase-flank_angle(r)) for r in radii)
        points.extend(pt(r,phase+flank_angle(r)) for r in reversed(radii))
        if dedendum < lower:
            points.append(pt(dedendum,phase+flank_angle(lower)))
    return points


def focus_gear(d,p,folder,revision):
    x,y=66,91
    mod = p["module_mm"]
    ring, pinion = p["teeth_ring"], p["teeth_pinion"]
    r1,r2 = mod*ring/2, mod*pinion/2
    xx = x+r1+r2+p["carriage_offset_mm"]
    d.polygon("lens-ring", spur_points(x,y,mod,ring,math.radians(p["pressure_deg"])))
    d.polygon("pinion", spur_points(157,78,mod,pinion,math.radians(p["pressure_deg"])))
    d.circle("lens-ring-pitch",x,225,r1,"ref")
    d.circle("pinion-pitch",xx,225,r2,"ref")
    d.circle("lens-ring-bore",x,y,p["bare_lens_mm"]/2)
    d.circle("pinion-bore",157,78,3.2)
    d.circle("index-disc",166,170,35)
    d.circle("index-bore",166,170,3.2)
    for i in range(36):
        angle = math.tau*i/36
        d.line(f"erasable-tick-{i}",(166+30*math.cos(angle),170+30*math.sin(angle)),
               (166+34*math.cos(angle),170+34*math.sin(angle)),"score")


def sail(d,p,folder,revision):
    d.rectangle("cloth-blank",34,27,300,375)
    d.rectangle("usable-sail",46,39,276,351,"ref")
    d.line("support-height",(370,403),(370,403-p["cp_mm"]),"ref")
    for i,y in enumerate((87,322)):
        d.rectangle(f"batten-{i}",47,y,274,9,"score")
    d.line("table-center",(389,479),(389,502))
    d.line("tip-axis",(389+p["base_radius_mm"],479),(389+p["base_radius_mm"],502))
    d.rectangle("ballast-gauge",386,428,p["ballast_edge_mm"],p["ballast_edge_mm"])


def winder(d,p,folder,revision):
    d.circle("brake-disc",62,78,32)
    d.circle("brake-contact",62,78,p["contact_mm"],"score")
    d.circle("through-bore",62,78,6.1)
    d.rectangle("lever-blank",116,127,65,22)
    d.circle("lever-axis",126,138,6.1)
    d.circle("handle-center",126+p["crank_arm_mm"],138,4.2)
    d.circle("roll-low",77,185,p["roll_radii_mm"][0],"ref")
    d.circle("roll-high",77,185,p["roll_radii_mm"][1],"ref")


def chroma(d,p,folder,revision):
    w,h=620,510
    d.rectangle("fabric-blank",23,29,w,h)
    d.rectangle("keyable-field",43,49,w-40,h-40,"ref")
    for i,y in enumerate((78,462)):
        d.rectangle(f"strap-anchor-{i}-left",35,y,14,26,"score")
        d.rectangle(f"strap-anchor-{i}-right",617,y,14,26,"score")
    d.rectangle("strap-cut",51,569,p["strap_mm"],24)
    d.line("installed-chair-route-low",(51,614),(51+p["chair_routes_mm"][0],614))
    d.line("installed-chair-route-high",(51,640),(51+p["chair_routes_mm"][1],640))


def mic_arm(d,p,folder,revision):
    pivot = (155,180)
    d.circle("pivot",*pivot,3)
    d.line("arm-level",pivot,(pivot[0]+p["outreach"],pivot[1]))
    d.circle("arm-anchor",pivot[0]+p["arm_anchor"],pivot[1],2.1,"score")
    d.circle("fixed-anchor",pivot[0]+p["fixed_anchor"][0],pivot[1]-p["fixed_anchor"][1],2.1,"score")
    d.rectangle("spring-length-gauge",30,254,p["spring_rest_mm"],7)
    d.rectangle("brace-coupon",24,27,90,42)
    for i,x in enumerate((36,99)):
        d.circle(f"brace-hole-{i}",x,47,3.1)


def pop(d,p,folder,revision):
    radius = p["screen_radius"]
    for i,x in enumerate((80,238)):
        d.circle(f"mesh-retainer-{i}",x,88,radius+6)
        d.circle(f"mesh-aperture-{i}",x,88,radius)
    d.line("mouth-plane",(65,198),(65,232))
    d.line("mesh-plane-0",(65+p["mesh_distance"],198),(65+p["mesh_distance"],232))
    d.line("mesh-plane-1",(65+p["mesh_distance"]+p["mesh_gap"],198),
           (65+p["mesh_distance"]+p["mesh_gap"],232))
    d.line("diaphragm-plane",(65+p["mic_distance"],198),(65+p["mic_distance"],232))
    d.rectangle("spacer-strip",20,260,75,p["mesh_gap"])


def shock(d,p,folder,revision):
    x,y=84,92
    d.circle("suspension-ring",x,y,p["outer_r_mm"]+5)
    d.circle("suspension-opening",x,y,p["outer_r_mm"],"cut")
    d.circle("barrel-coupon",x,y,p["barrel_r_mm"],"ref")
    free=p["outer_r_mm"]-p["barrel_r_mm"]
    for i,(dx,dy) in enumerate(((0,-1),(1,0),(0,1),(-1,0))):
        d.line(f"cord-{i}",(x+dx*p["barrel_r_mm"], y+dy*p["barrel_r_mm"]),
               (x+dx*p["outer_r_mm"], y+dy*p["outer_r_mm"]))
    d.rectangle("stiffness-gauge-calibration-span",24,178,free,9)
    d.rectangle("calibration-pull-travel",24,201,p["pull_mm"],9)


def acoustic(d,p,folder,revision):
    d.rectangle("rear-panel",22,25,360,260)
    for i,y in enumerate((310,595)):
        d.rectangle(f"wing-cut-{i}",22,y,p["wing_length"],260)
    mic=(628,600)
    d.circle("mic-datum",*mic,3,"ref")
    rear_y=700
    d.line("rear-trace",(448,rear_y),(808,rear_y))
    for i,s in enumerate((-1,1)):
        root=(mic[0]+180*s,rear_y)
        end=(root[0]+s*p["wing_length"]*math.cos(math.radians(61)),
             root[1]-p["wing_length"]*math.sin(math.radians(61)))
        d.line(f"wing-trace-{i}",root,end)


def wedge(d,p,folder,revision):
    depth=p["depth"]
    heel=p["heel"]
    toe=p["toe"]
    for i,x in enumerate((24,224)):
        y=145
        d.polygon(f"side-{i}",[(x,y),(x+depth,y),(x+depth,y-heel),(x,y-toe)])
        d.rectangle(f"plan-{i}",x,168,depth,124)
        d.center(f"speaker-base-{i}",x+depth/2,230,150,108,"ref")


DESIGNS={
    "P036":(focus_rail,235,285), "P037":(xy_stage,220,260),
    "P193":(dolly,220,240), "P194":(cable,230,250),
    "P197":(cage,240,285), "P198":(focus_gear,230,285), "P201":(sail,650,550),
    "P202":(winder,240,260), "P204":(chroma,700,680), "P206":(mic_arm,520,295),
    "P207":(pop,320,300), "P208":(shock,230,240), "P209":(acoustic,960,890),
    "P210":(wedge,440,320),
}


def export(destination):
    data=json.loads((ROOT/"parameters.json").read_text(encoding="utf-8"))
    if data.keys() != DESIGNS.keys():
        raise ValueError("Each catalog trial needs parameters and an SVG design")
    for ident,(design,w,h) in DESIGNS.items():
        folder=destination/ident
        folder.mkdir(parents=True,exist_ok=True)
        common={k:v for k,v in data[ident].items() if k not in ("baseline","revised")}
        for revision in ("baseline","revised"):
            drawing=Drawing(ident,revision,w,h)
            design(drawing,common | data[ident][revision],folder,revision)
            drawing.write(folder/f"{revision}.svg")


if __name__ == "__main__":
    export(Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT/"artifacts")
