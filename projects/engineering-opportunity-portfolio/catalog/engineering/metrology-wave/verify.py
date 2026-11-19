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


def rows(path, label):
    filename=path.with_name(path.stem+f"-{label}.csv")
    with filename.open(newline="",encoding="utf-8") as f:
        return list(csv.DictReader(f))


def origin_block(nodes,p,path):
    dx,dy,_,_=rect(nodes["stock-relief"])
    x,y,_,_=rect(nodes["machined-block-top"])
    offsets=[dx-x,dy-y,rect(nodes["top-wall-section"])[3]]
    ball_radius=vals(nodes["contact-stylus"],"r")[0]
    seen=set()
    errors=[]
    for row in rows(path,"touch"):
        idx=int(row["job"])-1
        i="XYZ".index(row["axis"])
        require((idx,i) not in seen,"Duplicated synthetic touch event")
        seen.add((idx,i))
        comp=float(row["applied_stylus_mm"])
        require(comp in (0,ball_radius),"Touch compensation does not follow drawn stylus")
        measured=float(row["trigger_mm"])
        reconstructed=measured-p["face_sign"][i]*(offsets[i]+comp)
        errors.append(abs(reconstructed-p["job_origins_mm"][idx][i]))
    require(len(seen)==3*len(p["job_origins_mm"]),"Missing touch events")
    return {
        "Worst three-axis reconstruction error with face tolerance":m(max(errors)+p["face_tolerance_mm"],"≤",0.04),
        "Smallest modeled conductor wall at stock faces":m(min(offsets),"≥",3),
    }


def setter(nodes,p,path):
    uncompressed=segment(nodes["uncompressed"])[0][1]
    trigger=segment(nodes["nominal-trigger"])[0][1]-uncompressed
    stop=segment(nodes["bottom-of-stroke"])[0][1]-uncompressed
    drawn=rect(nodes["spring-pocket-section"])[3]
    require(abs(drawn-stop)<.001,"Section does not match the stopper travel")
    earliest=trigger-p["trip_error_mm"]
    worst_avail=stop-trigger-p["trip_error_mm"]-p["stroke_error_mm"]
    v=p["sim_speed_mm_s"]
    expected=v*p["sim_delay_s"]+v*v/(2*p["sim_decel_mm_s2"])
    return {
        "Worst modeled travel reserve after trigger and stop":m(worst_avail-expected,"≥",0.35),
        "Earliest trigger compression":m(earliest,"≥",0.25),
        "Full bounded trigger spread":m(2*p["trip_error_mm"],"≤",0.07),
    }


def tram(nodes,p,path):
    spacing=math.dist(point(nodes["indicator-0"]),point(nodes["indicator-1"]))
    readings={}
    for row in rows(path,"readings"):
        i=int(row["pair"])
        pair=readings.setdefault(i,{})
        sign=int(row["direction"])
        require(sign in (1,-1) and sign not in pair,"Unexpected orientation record")
        pair[sign]=float(row["indicator_b_mm"])-float(row["indicator_a_mm"])
    require(len(readings)==len(p["events_mm"]),"Missing tramming readings")
    estimates=[]
    for pair in readings.values():
        delta=(pair[1]-pair[-1])/2 if -1 in pair else pair[1]
        estimates.append(math.degrees(math.atan2(delta,spacing)))
    return {
        "Worst spindle tilt inference error":m(max(abs(t-p["test_tilt_deg"]) for t in estimates),"≤",0.006,"deg"),
        "Repeated estimate spread":m(max(estimates)-min(estimates),"≤",0.003,"deg"),
        "Indicator pad separation":m(spacing,"≥",165),
    }


def kerf(nodes,p,path):
    errors=[]
    advances=[]
    for i in range(len(p["samples"])):
        expected=length(nodes[f"mating-stock-{i}"])
        raw=length(nodes[f"gauge-transfer-{i}"])
        blade=length(nodes[f"actual-kerf-{i}"])
        width=raw+blade
        errors.append(abs(width-expected))
        advances.append(raw)
    shift=rect(nodes["lock-travel"])[2]
    return {
        "Worst modeled slot-width error":m(max(errors)+p["lock_error_mm"],"≤",0.12),
        "Smallest two-stop displacement":m(min(advances),"≥",3),
        "Lock slot reserve above longest displacement":m(shift-max(advances),"≥",5),
    }


def insert(nodes,p,path):
    guide_r=vals(nodes["guide-0"],"r")[0]
    require(abs(guide_r-vals(nodes["guide-1"],"r")[0]) <= .001,"Guide dimensions differ")
    rod_r=vals(nodes["rod-gauge"],"r")[0]
    separation=math.dist(point(nodes["guide-0"]),point(nodes["guide-1"]))
    theta=math.atan2(2*(guide_r-rod_r),separation)
    tilt_drift=length(nodes["tip-throw"])*math.tan(theta)+p["fixed_axis_error_mm"]
    offset=abs(length(nodes["depth-travel"])-p["desired_depth_mm"])
    return {
        "Worst insert center displacement at overhang":m(tilt_drift,"≤",0.19),
        "Guide-clearance tilt bound":m(math.degrees(theta),"≤",0.30,"deg"),
        "Worst depth stop error":m(offset+p["depth_error_mm"],"≤",0.12),
    }


def balancer(nodes,p,path):
    radius=length(nodes["imbalance-arm"])/1000
    g=9.80665
    friction_r=vals(nodes["friction-contact-radius"],"r")[0]/1000
    opposing=p["breakaway_force_n"]*friction_r+p["arbor_fixture_bias_gmm"]*1e-6*g
    expected=p["test_weight_g"]/1000*g*radius
    return {
        "Known imbalance torque ratio over deadband":m(expected/opposing,"≥",1.65,"ratio"),
        "Equivalent worst-case detected-mass threshold":m(1000*opposing/(radius*g),"≤",0.5,"g"),
        "Stand foot depth":m(rect(nodes["stand-foot"])[3],"≥",28),
    }


def dish(nodes,p,path):
    spans=[length(n)/2 for k,n in nodes.items() if k.startswith("wheel-rim-span-")]
    x=ctr(nodes["arch-blank"])[0]
    distances=[]
    for i in range(2):
        minimum,_,width,_=rect(nodes[f"foot-slot-{i}"])
        limits=sorted((abs(minimum-x),abs(minimum+width-x)))
        distances.extend(min(r-limits[0],limits[1]-r) for r in spans)
    pad_diff=abs(rect(nodes["left-pad-section"])[3]-rect(nodes["right-pad-section"])[3])
    budget=pad_diff+p["hub_tip_error_mm"]
    # Bound the difference observed after flipping the same calibrated three-point gauge.
    return {
        "Minimum radial adjustment reserve":m(min(distances),"≥",5),
        "Maximum modeled pad and hub-tip differential budget":m(budget,"≤",0.2),
        "Minimum difference from known dish shim after flip":m(2*p["test_shim_dish_mm"]-budget,"≥",1.5),
    }


def hanger(nodes,p,path):
    shaft=vals(nodes["shaft-gauge"],"r")[0]
    rb1=vals(nodes["support-seat-0"],"r")[0]
    rb2=vals(nodes["support-seat-1"],"r")[0]
    seat=rect(nodes["separation-gauge"])[2]
    slope=(rb1+rb2-2*shaft)/seat
    seen={}
    for row in rows(path,"indicator"):
        pose=int(row["pose"])
        require(pose in range(4) and pose not in seen,"Malformed four-position replay")
        a,b=segment(nodes[f"rim-direction-{pose}"])
        angle=math.atan2(a[1]-b[1],b[0]-a[0])%math.tau
        require(abs(angle-pose*math.pi/2)<.001,"Reading marker has incorrect rim pose")
        seen[pose]=float(row["synthetic_reading_mm"])
    estimates=((seen[0]-seen[2])/2,(seen[1]-seen[3])/2)
    cross=math.dist(estimates,p["known_components_mm"])
    scaled=p["fixture_rim_r_mm"]*slope
    return {
        "Worst single-reading spindle-clearance projection":m(scaled,"≤",0.6),
        "Maximum vector recovery error incl. clearance":m(cross+math.sqrt(2)*scaled,"≤",0.9),
        "Conservative lower bound on detected tilt-equivalent displacement":m(math.hypot(*estimates)-math.sqrt(2)*scaled,"≥",1.8),
    }


def angle_stop(nodes,p,path):
    centroid=point(nodes["pivot"])
    radius=[]
    mark_error=[]
    for angle in (-45,0,45):
        x,y=point(nodes[f"index-{angle}"])
        radius.append(math.dist((x,y),centroid))
        derived=math.degrees(math.atan2(x-centroid[0],centroid[1]-y))
        mark_error.append(abs(derived-angle))
    nominal_axis=segment(nodes["square-reference"])
    require(nominal_axis[0]==centroid and nominal_axis[1][0]==centroid[0],"Square datum is not vertical on the drawing")
    contacts=math.dist(ctr(nodes["rail-pad-0"]),ctr(nodes["rail-pad-1"]))
    groove=rect(nodes["host-groove-envelope"])[3]
    key=rect(nodes["rail-key-width-gauge"])[3]
    lever=p["panel_end_dist_mm"]
    error=math.atan2(groove-key,contacts)+math.atan2(p["lock_play_mm"],min(radius))+math.radians(max(mark_error))
    return {
        "Worst modeled layout drift over panel length":m(lever*math.sin(error),"≤",1.2),
        "Nominal index angle error":m(max(mark_error),"≤",.05,"deg"),
        "Minimum modeled rail key clearance":m(groove-key,"≥",0.10),
    }


def straightedge(nodes,p,path):
    coords=polygon(nodes["straightedge-blank"])
    edge_y=coords[1][1]
    nut=segment(nodes["nut-datum"])[0][0]
    n=p["frets"]
    require(len(coords)==4*n+4,"Profile notch count does not match configured frets")
    margins, land, relief = [],[],[]
    previous=coords[1][0]
    errors=[]
    for f in range(1,n+1):
        ix=2+(f-1)*4
        a,b,c,d=coords[ix:ix+4]
        require(a[1]==d[1]==edge_y and previous<a[0]<d[0],"Discontinuous fret land")
        require(b[0]==a[0] and c[0]==d[0] and b[1]==c[1],"Malformed relief")
        land.append(a[0]-previous)
        previous=d[0]
        nominal=nut+p["target_scale_mm"]*(1-math.pow(2,-f/12))
        crown=p["fret_crown_width_mm"]/2
        margins.append(min(nominal-crown-a[0],d[0]-nominal-crown)-p["registration_error_mm"])
        relief.append(edge_y-b[1])
        errors.append(abs(nominal-(a[0]+d[0])/2))
    land.append(coords[-2][0]-previous)
    return {
        "Worst crown-to-notch edge clearance incl. registration":m(min(margins),"≥",0.75),
        "Smallest remaining fretboard contact land":m(min(land),"≥",4),
        "Minimum depth over fret crown":m(min(relief),"≥",3.5),
        "Maximum fret center position deviation":m(max(errors),"≤",0.09),
    }


TRIALS={"P076":origin_block,"P077":setter,"P078":tram,"P086":kerf,"P099":insert,
        "P105":balancer,"P106":dish,"P107":hanger,"P110":angle_stop,"P245":straightedge}

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
