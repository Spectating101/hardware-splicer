"""Read the release SVGs and replay the distinct optical and fit trials."""
import csv
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
        elif node.tag == SVG+"polygon":
            points = polygon(node)
            px,py = zip(*points)
            coords = min(px), min(py), max(px), max(py)
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



def polygon(node):
    return [tuple(map(float,point.split(","))) for point in node.attrib["points"].split()]


def point(node):
    return vals(node,"cx","cy")


def segment(node):
    x1,y1,x2,y2=vals(node,"x1","y1","x2","y2")
    return (x1,y1),(x2,y2)


def length(node):
    return math.dist(*segment(node))


def clearance(a,b):
    x,y,w,h=rect(a)
    u,v,g,k=rect(b)
    return max(u-x-w,x-u-g,v-y-h,y-v-k)


def focus_rail(nodes,p,path):
    with path.with_name(path.stem+"-focus.csv").open(newline="",encoding="utf-8") as f:
        seq=[(row["event"],int(row["position_um"])) for row in csv.DictReader(f)]
    require(seq[0][0]=="jog" and all(name=="expose" for name,k in seq[1:]),"Invalid motion event ordering")
    samples=[k for name,k in seq[1:]]
    require(all(a<b for a,b in zip(samples,samples[1:])),"Focus motion reverses between exposures")
    coupling = samples[0]-seq[0][1]
    reach = abs(segment(nodes["travel-high"])[0][1]-segment(nodes["travel-low"])[0][1])
    require(0 <= seq[0][1] and samples[-1] <= reach*1000,"Focus sequence exceeds mechanical travel")
    optics=p["optical"]
    magnification=optics["magnification"]
    depth = 1000*2*optics["f_number"]*optics["coc_mm"]*(1+magnification)/magnification**2
    takeup_deficit=max(0,p["backlash_um"]-coupling)
    estimated = [max(0,a-samples[0]-takeup_deficit) for a in samples]
    gaps = [b-a for a,b in zip(estimated,estimated[1:])]
    worst = max(gaps)+2*p["stage_error_um"]
    pitch_min=max(0,min(gaps)-2*p["stage_error_um"])
    return {
        "Backlash pre-roll reserve":m(coupling-p["backlash_um"],"≥",15,"µm"),
        "Worst modeled focal-slice overlap":m(100*max(0,1-worst/depth),"≥",55,"%"),
        "Guaranteed advance between exposures":m(pitch_min,"≥",2,"µm"),
        "Commanded stack depth":m(samples[-1]-samples[0],"≥",600,"µm"),
    }


def xy_stage(nodes,p,path):
    xo,xf=segment(nodes["axis-x"])
    yo,yf=segment(nodes["axis-y"])
    vx=(xf[0]-xo[0],xf[1]-xo[1])
    vy=(yf[0]-yo[0],yf[1]-yo[1])
    angle=math.acos(sum(a*b for a,b in zip(vx,vy))/(math.hypot(*vx)*math.hypot(*vy)))
    x,y=p["xy_command_mm"]
    error=p["stage_error_mm"]
    ox,oy,ow,oh=rect(nodes["view-window"])
    sx,sy,sw,sh=rect(nodes["specimen"])
    reserved_x=x+abs(y*math.cos(angle))+error
    reserved_y=y+error
    view_edge= min(sx-ox-reserved_x,sy-oy-reserved_y, ox+ow-sx-sw-reserved_x,oy+oh-sy-sh-reserved_y)
    return {
        "Worst orthogonal cross-axis drift":m(abs(y*math.cos(angle))+error,"≤",0.15),
        "View-window margin for positioned specimen":m(view_edge,"≥",3),
        "Axis reserve past requested X travel":m(length(nodes["axis-x"])/2-x,"≥",0.5),
        "Axis reserve past requested Y travel":m(length(nodes["axis-y"])/2-y,"≥",0.5),
    }


def dolly(nodes,p,path):
    r0,r1=point(nodes["rear-0"]),point(nodes["rear-1"])
    f=point(nodes["steering-axle"])
    c=point(nodes["camera-mount"])
    steer=segment(nodes["steered-wheel"])
    wheelbase=(r0[1]+r1[1])/2-f[1]
    angle=math.atan2(steer[1][0]-steer[0][0],steer[0][1]-steer[1][1])
    radius=wheelbase/math.tan(angle)
    margins=[]
    for a,b in ((r0,r1),(r1,f),(f,r0)):
        dx,dy=b[0]-a[0],b[1]-a[1]
        margins.append(abs((c[0]-a[0])*dy-(c[1]-a[1])*dx)/math.hypot(dx,dy))
    return {
        "Rear axle midpoint orbit radius error":m(abs(radius-p["target_orbit_r_mm"]),"≤",10),
        "Worst projected support-polygon margin":m(min(margins)-p["load_shift_mm"],"≥",12),
        "Modeled steering angle":m(math.degrees(angle),"≤",35,"deg"),
    }


def cable(nodes,p,path):
    gauge=rect(nodes["jaw-opening-gauge"])[3]
    pad=rect(nodes["pad-thickness-gauge"])[3]
    rubber_gap = gauge - 2*pad
    cable_min,cable_max=p["cable_d_mm"]
    guide=vals(nodes["cable-guide"],"r")[0]
    hole_l,hole_r=point(nodes["cage-bore-0"]),point(nodes["cage-bore-1"])
    return {
        "Worst inside-surface bend radius":m(guide-cable_max/2,"≥",p["min_inside_bend_mm"]),
        "Minimum pad interference on smallest cable":m(cable_min-rubber_gap,"≥",0.15),
        "Maximum pad interference on largest cable":m(cable_max-rubber_gap,"≤",0.9),
        "Nominal fastener separation":m(math.dist(hole_l,hole_r),"≥",25),
    }


def cage(nodes,p,path):
    error=p["nominal_position_error_mm"]
    rails=[nodes[k] for k in ("lower-plate","right-riser","top-plate")]
    distances={}
    for key in ("door-sweep","connector-corridor","top-shoe-corridor"):
        gap=min(clearance(n,nodes[key]) for n in rails)
        distances[key]=m(gap-error,"≥",3)
    plate=nodes["lower-plate"]
    x,y,w,h=rect(plate)
    margins=[]
    for i in range(2):
        a,b,r=vals(nodes[f"base-hole-{i}"],"cx","cy","r")
        margins.append(min(a-x,b-y,x+w-a,y+h-b)-r)
    distances["Base-hole edge distance"]=m(min(margins),"≥",3)
    return distances


def gear(nodes,p,path):
    rr,rp=[vals(nodes[f"{key}-pitch"],"r")[0] for key in ("lens-ring","pinion")]
    center=math.dist(point(nodes["lens-ring-pitch"]),point(nodes["pinion-pitch"]))
    offset=center-rr-rp
    mod=p["module_mm"]
    pa=math.radians(p["pressure_deg"])
    ring_n,pinion_n=round(2*rr/mod),round(2*rp/mod)
    peak_radii=[]
    for key,tooth_count in (("lens-ring",ring_n),("pinion",pinion_n)):
        c=point(nodes[f"{key}-bore"])
        radii=[math.dist(c,k) for k in polygon(nodes[key])]
        peak=max(radii)
        foot=min(radii)
        peak_radii.append(peak)
        require(sum(abs(r-peak)<1e-5 for r in radii)==2*tooth_count, "Gear polygon tooth count or tip radius differs")
        require(abs(foot-(mod*tooth_count/2-1.25*mod))<1e-5, "Unexpected tooth dedendum")
    far_center=center+p["mount_error_mm"]
    rb1,rb2=rr*math.cos(pa),rp*math.cos(pa)
    pa_work=math.acos((rb1+rb2)/far_center)
    path_length=math.sqrt(peak_radii[0]**2-rb1**2)+math.sqrt(peak_radii[1]**2-rb2**2)-far_center*math.sin(pa_work)
    contact=path_length/(math.pi*mod*math.cos(pa))
    lash=p["nominal_lash_mm"]+2*(offset+p["mount_error_mm"])*math.tan(pa)
    bore_r=vals(nodes["lens-ring-bore"],"r")[0]
    throw=p["lens_throw_deg"]*ring_n/pinion_n
    return {
        "Worst modeled lens-ring reversal play":m(math.degrees(lash/rr),"≤",0.45,"deg"),
        "Transverse contact ratio at far limit":m(contact,"≥",1.45,"teeth"),
        "Root-to-bore lens-ring land":m(rr-1.25*mod-bore_r,"≥",2),
        "Manual wheel sweep for 90 degree lens throw":m(throw,"≤",460,"deg"),
    }


def sail(nodes,p,path):
    _,_,w,h=rect(nodes["usable-sail"])
    _,_,edge,_=rect(nodes["ballast-gauge"])
    g=9.80665
    tip=segment(nodes["tip-axis"])[0][0]-segment(nodes["table-center"])[0][0]
    lift=length(nodes["support-height"])
    force=0.5*p["air_density_kgm3"]*p["drag_coefficient"]*p["air_speed_ms"]**2*w*h/1e6
    ballast=edge**2*p["ballast_thickness_mm"]*p["ballast_density_gmm3"]/1000
    overturn=force*lift/1000
    restoring=(p["base_mass_kg"]+ballast)*g*tip/1000
    return {
        "Restoring to disturbance moment ratio":m(restoring/overturn,"≥",1.8,"ratio"),
        "Minimum visible reflector area":m(w*h,"≥",95000,"mm²"),
        "Maximum centered base ballast mass":m(ballast,"≤",0.5,"kg"),
    }


def winder(nodes,p,path):
    radius=vals(nodes["brake-contact"],"r")[0]
    coeff,err=p["friction_nominal"],p["friction_rel_error"]
    nominal=p["brake_normal_n"]*radius/1000*coeff
    low=nominal*(1-err)
    high=nominal*(1+err)
    small=vals(nodes["roll-low"],"r")[0]/1000
    large=vals(nodes["roll-high"],"r")[0]/1000
    handle=math.dist(point(nodes["lever-axis"]),point(nodes["handle-center"]))/1000
    return {
        "Minimum paper tension at full roll":m(low/large,"≥",1.5,"N"),
        "Maximum paper tension near core":m(high/small,"≤",6,"N"),
        "Worst estimated hand force":m((high+p["wind_extra_nm"])/handle,"≤",8,"N"),
    }


def chroma(nodes,p,path):
    cut=rect(nodes["strap-cut"])[2]
    routes=[length(nodes[f"installed-chair-route-{r}"]) for r in ("low","high")]
    strains=[100*(r/cut-1) for r in routes]
    area=rect(nodes["keyable-field"])[2]*rect(nodes["keyable-field"])[3]
    return {
        "Minimum fitted strap strain":m(min(strains),"≥",3,"%"),
        "Maximum fitted strap strain":m(max(strains),"≤",16,"%"),
        "Flat green field":m(area,"≥",260000,"mm²"),
    }


def mic_arm(nodes,p,path):
    px,py=point(nodes["pivot"])
    x_fixed,y_fixed=point(nodes["fixed-anchor"])
    anchor=math.dist((px,py),point(nodes["arm-anchor"]))
    reach=length(nodes["arm-level"])
    fixed=(x_fixed-px,py-y_fixed)
    rest=rect(nodes["spring-length-gauge"])[2]
    a,b=p["angle_range_deg"]
    torque=[]
    elong=[]
    for i in range(501):
        angle=math.radians(a+(b-a)*i/500)
        x,y=anchor*math.cos(angle),anchor*math.sin(angle)
        dx,dy=fixed[0]-x,fixed[1]-y
        q=math.hypot(dx,dy)
        stretch=max(0,q-rest)
        tension=p["spring_rate_nm"]*stretch/1000
        gravity=p["load_kg"]*9.80665*reach/1000*math.cos(angle)
        support=(x*dy-y*dx)*tension/q/1000
        torque.append(gravity-support)
        elong.append(stretch)
    return {
        "Peak uncompensated pivot moment":m(max(abs(x) for x in torque),"≤",0.45,"N·m"),
        "Minimum spring preload travel":m(min(elong),"≥",20),
        "Peak spring extension":m(max(elong),"≤",125),
    }


def pop(nodes,p,path):
    plane=lambda key:segment(nodes[key])[0][0]
    mouth=plane("mouth-plane")
    first=plane("mesh-plane-0")-mouth
    second=plane("mesh-plane-1")-mouth
    dia=plane("diaphragm-plane")-mouth
    radius=vals(nodes["mesh-aperture-0"],"r")[0]
    require(radius == vals(nodes["mesh-aperture-1"],"r")[0], "Filter mesh apertures differ")
    require(abs(second-first-rect(nodes["spacer-strip"])[3]) < 0.01, "Mesh spacing and gauge disagree")
    need=p["mouth_offset_mm"]+second*math.tan(math.radians(p["signal_cone_deg"]))
    return {
        "Mesh edge clearance around source cone":m(radius-need,"≥",7),
        "Minimum separation between meshes":m(second-first,"≥",8),
        "Maximum separation between meshes":m(second-first,"≤",15),
        "Rear mesh to diaphragm stand-off":m(dia-second,"≥",45),
    }


def shock(nodes,p,path):
    rope=rect(nodes["stiffness-gauge-calibration-span"])[2]
    require(all(abs(length(nodes[f"cord-{i}"])-rope) < .01 for i in range(4)),"Elastic span gauge disagrees with drawing")
    gauge=rect(nodes["calibration-pull-travel"])[2]/1000
    # Small-angle stiffness for two opposing axial cords and two transverse cords under modeled pretension.
    stiffness=2*p["pull_n_at_gauge"]/gauge + 2*1.0/(rope/1000)
    freq_nat=math.sqrt(stiffness/p["mic_mass_kg"])/(2*math.pi)
    r=p["trial_freq_hz"]/freq_nat
    damp=p["damping_ratio"]
    transfer=math.sqrt((1+(2*damp*r)**2)/((1-r*r)**2+(2*damp*r)**2))
    static_sag=1000*p["mic_mass_kg"]*9.80665/stiffness
    return {
        "Modeled 30 Hz base motion transmissibility":m(transfer,"≤",0.17,"ratio"),
        "Static cord travel reserve after 6 mm excursion":m(rope-static_sag-6,"≥",15),
    }


def acoustic(nodes,p,path):
    mic=point(nodes["mic-datum"])
    trace=segment(nodes["rear-trace"])
    require(abs(length(nodes["rear-trace"])-rect(nodes["rear-panel"])[2]) < .01,"Rear panel drawing differs from fixture plan")
    coverage=[]
    for i,a in enumerate(trace):
        root,edge=segment(nodes[f"wing-trace-{i}"])
        require(math.dist(a,root) < .01 and abs(math.dist(root,edge)-rect(nodes[f"wing-cut-{i}"])[2]) < .01,
                "Wing fold or trim dimensions differ from fixture plan")
        coverage.append(math.degrees(math.atan2(abs(edge[0]-mic[0]),edge[1]-mic[1])))
    return {
        "Screened half angle measured from rear":m(min(coverage),"≥",95,"deg"),
        "Minimum panel height":m(rect(nodes["rear-panel"])[3],"≥",250),
    }


def wedge(nodes,p,path):
    angles=[]
    static=[]
    seating=[]
    for i in range(2):
        bottom_left,bottom_right,high,low=polygon(nodes[f"side-{i}"])
        depth=bottom_right[0]-bottom_left[0]
        angle=math.atan2(low[1]-high[1],depth)
        angles.append(math.degrees(angle))
        seating.append(rectangle_margin(nodes[f"plan-{i}"],nodes[f"speaker-base-{i}"]))
        static.append(p["friction_minimum"]-math.tan(angle))
    return {
        "Smallest wedge tilt":m(min(angles),"≥",7.5,"deg"),
        "Largest wedge tilt":m(max(angles),"≤",8.5,"deg"),
        "Pair angle agreement":m(max(angles)-min(angles),"≤",0.1,"deg"),
        "Speaker footprint inset":m(min(seating),"≥",7.5),
        "Modeled static friction reserve":m(min(static),"≥",0.15,"coefficient"),
    }


TRIALS = {"P036":focus_rail,"P037":xy_stage,"P193":dolly,"P194":cable,"P197":cage,"P198":gear,"P201":sail,"P202":winder,"P204":chroma,
          "P206":mic_arm,"P207":pop,"P208":shock,"P209":acoustic,"P210":wedge}

def replay(artifacts):
    parameters=json.loads((ROOT/"parameters.json").read_text(encoding="utf-8"))
    out = {}
    for ident, trial in TRIALS.items():
        out[ident] = {}
        for rev in ("baseline","revised"):
            f=artifacts/ident/f"{rev}.svg"
            out[ident][rev] = trial(parse(f), parameters[ident] | parameters[ident][rev], f)
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
        files={file.relative_to(artifacts) for file in artifacts.rglob("*.*")}
        require(files=={file.relative_to(path) for file in path.rglob("*.*")},"Fresh export files differ")
        for name in files:
            require((path/name).read_bytes()==(artifacts/name).read_bytes(), f"{name} fails byte comparison")
    print(f"{len(out)} trials · {failures} baseline failures · {passed} revised passes · {len(files)} reproducible exports")


if __name__ == "__main__":
    main()
