"""Replay candidate acceptance and rejected revisions from the saved SVG and CSV."""
import argparse
import csv
import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent


class Drawing:
    def __init__(self, path):
        self.root = ET.parse(path).getroot()
        width, height = [self.root.get(x) for x in ("width","height")]
        view = self.root.get("viewBox").split()
        assert width.endswith("mm") and height.endswith("mm")
        assert list(map(float,view)) == [0,0,float(width[:-2]),float(height[:-2])]
        nodes = [node for node in self.root.iter() if "id" in node.attrib]
        self.entities = {node.get("id"):node for node in nodes}
        assert len(nodes)==len(self.entities)

    def get(self,key,attrs):
        return tuple(float(self.entities[key].attrib[a]) for a in attrs.split())

    def rect(self,key):
        return self.get(key,"x y width height")

    def circle(self,key):
        return self.get(key,"cx cy r")

    def line(self,key):
        nodes=self.get(key,"x1 y1 x2 y2")
        return nodes[:2],nodes[2:]

    def points(self,key):
        return [tuple(map(float, coords.split(","))) for coords in self.entities[key].get("points").split()]


def check(measure, passes):
    return {"pass":bool(passes),"measured":round(measure,6) if isinstance(measure,float) else measure}


def cabinet(p):
    s = Drawing(p)
    spans=[math.dist(*s.line(f"scale-{axis}")) for axis in ("x","y")]
    cx=s.line("center")[0][0]
    _, top, _, _=s.rect("panel")
    pitch, center, set_error = [], [], []
    for i, target in enumerate((96,128,160)):
        a,b=[s.circle(f"drill-{i}-{j}")[:2] for j in (0,1)]
        pitch.append(abs(math.dist(a,b)-target))
        center.append(abs((a[0]+b[0])/2-cx))
        set_error.append(abs(a[1]-top-(22,38,60)[i]))
    return {
        "print calibration span error mm":check(max(abs(a-100) for a in spans),all(abs(a-100)<=.15 for a in spans)),
        "maximum screw pitch error mm":check(max(pitch),max(pitch)<=.15),
        "handle pair center offset mm":check(max(center),max(center)<=.1),
        "edge setback maximum error mm":check(max(set_error),max(set_error)<=.15)
    }


def pcb(p):
    s=Drawing(p)
    x,y,w,d=s.rect("pcb")
    ix,iy,iw,ih=s.rect("pocket")
    fx,fy,fw,fh=s.rect("camera")
    card_x, card_y, card_w, pull=s.rect("sd-service")
    carrier_x,carrier_y,carrier_w,carrier_h=s.rect("carrier")
    gap=min(x-ix,y-iy,ix+iw-x-w,iy+ih-y-d)
    camera=min(x-fx,y-fy,fx+fw-x-w,fy+fh-y-d)
    borings=[s.circle(f"carrier-mount-{i}-{j}") for i in (0,1) for j in (0,1)]
    land=min(min(u-carrier_x,v-carrier_y,carrier_x+carrier_w-u,carrier_y+carrier_h-v)-r for u,v,r in borings)
    card_fits=carrier_x<=card_x<=card_x+card_w<=carrier_x+carrier_w and card_y<=carrier_y
    return {
        "source outline agreement mm":check(max(abs(w-15.24),abs(d-19.05)),abs(w-15.24)<.01 and abs(d-19.05)<.01),
        "radial pocket allowance mm":check(gap,.25<=gap<=.45),
        "SD pull travel mm":check(pull,pull>=10 and card_fits and abs(card_y+pull-y)<.01),
        "board margin inside camera view mm":check(camera,camera>=5),
        "carrier corner hole edge land mm":check(land,land>=1.2)
    }


def slide(p):
    s=Drawing(p)
    a,b=s.line("datum-0"),s.line("datum-1")
    starts=b[0][1]-a[0][1]
    ends=b[1][1]-a[1][1]
    skew=abs(starts-ends)
    clamp=[]
    for i in (0,1):
        for j in (0,1):
            _,y,_,_=s.rect(f"shoe-{i}-{j}")
            _,cy,r=s.circle(f"clamp-{i}-{j}")
            clamp.append(y-cy-r)
    rx,ry,rw,rh=s.rect("rail-section")
    bx,by,bw,_=s.rect("ledge-section")
    return {
        "end-to-end parallelism error mm":check(skew,skew<=.4),
        "mean distance between slide faces mm":check((starts+ends)/2,abs((starts+ends)/2-410)<=.4),
        "clamp pad clearance from locating shoe mm":check(min(clamp),min(clamp)>=3),
        "ledge support across rail footprint":check(rw,bx<=rx and by==ry+rh and bx+bw>=rx+rw)
    }


def tray(p):
    s=Drawing(p)
    _,lid_y,_,lid_h=s.rect("lid")
    _,wall_y,_,wall_h=s.rect("wall-0")
    _,floor_y,_,floor=s.rect("floor")
    lids=wall_y-lid_y-lid_h
    coupons=sorted(k for k in s.entities if k.startswith("fastener-"))
    fit,pockets=[],[]
    for name in coupons:
        key=name.split("-")[1]
        x,y,r=s.circle("pocket-"+key)
        _,_,length,diam=s.rect(name)
        fit.append(2*r-math.hypot(diam,length))
        pockets.append((x,y,r))
    land=min(math.dist(a[:2],b[:2])-a[2]-b[2] for i,a in enumerate(pockets) for b in pockets[i+1:])
    return {
        "lid bypass gap below thin washer thickness mm":check(lids,0<=lids<=.9),
        "fastener diagonal clearance inside retrieval pocket mm":check(min(fit),min(fit)>=2),
        "minimum pocket separation mm":check(land,land>=12),
        "wall and tray floor engagement mm":check(floor,abs(wall_y+wall_h-floor_y)<=.001 and floor>=3)
    }


def tent(p):
    s=Drawing(p)
    errors, support, angles=[],[],[]
    for i in (0,1):
        board=s.line(f"keyboard-{i}")
        run=abs(board[1][0]-board[0][0])
        rise=abs(board[1][1]-board[0][1])
        angle=math.degrees(math.atan2(rise,run))
        angles.append(angle)
        errors.append(abs(run-170))
        wedge=s.points(f"wedge-{i}")
        loads=s.line(f"load-{i}")
        support.extend((loads[0][0]-min(x for x,_ in wedge),
                        max(x for x,_ in wedge)-loads[1][0]))
    cable=min(math.dist(*s.line(f"cable-{i}")) for i in (0,1))
    return {
        "nominal width error mm":check(max(errors),max(errors)<=.1),
        "tent angle deg":check(angles[0],all(13.4<=a<=14.2 for a in angles) and abs(angles[0]-angles[1])<.01),
        "minimum supported typing load margin mm":check(min(support),min(support)>=20),
        "assumed plug projection allowance mm":check(cable,cable>=15),
        "friction margin for clean surface coupon":check(.45-math.tan(math.radians(angles[0])),
                                                           .45-math.tan(math.radians(angles[0]))>=.12)
    }


def rover(p):
    s=Drawing(p)
    ground=s.line("ground")[0][1]
    roof=s.line("roof")[0][1]
    x,y,w,h=s.rect("cart")
    block=s.rect("threshold")[3]
    axles=[s.circle(f"wheel-{i}")[:2] for i in (0,1)]
    wb=math.dist(*axles)
    tilt=math.asin(block/wb)
    margin=ground-roof-(ground-y)-block-(w/2-wb/2)*math.sin(tilt)
    skid=ground-y-h-block
    _,target_top,_,target_height=s.rect("sighting-card")
    upper=s.line("ray-upper")[1][1]
    lower=s.line("ray-lower")[1][1]
    vision=min(target_top-upper,lower-target_top-target_height)
    return {
        "worst overhead clearance on threshold mm":check(margin,margin>=5),
        "skid clearance above threshold mm":check(skid,skid>=4),
        "target within camera cone margin mm":check(vision,vision>=15),
        "recovery slot width mm":check(s.rect("tow-slot")[2],s.rect("tow-slot")[2]>=8),
        "track between axle centrelines mm":check(s.rect("top-wheel-0-1")[1]-s.rect("top-wheel-0-0")[1],
                                                 s.rect("top-wheel-0-1")[1]-s.rect("top-wheel-0-0")[1]>=140)
    }


def rows(path):
    with path.open(newline="",encoding="utf-8") as f:
        return list(csv.DictReader(f))


def count_scale(p):
    observations=rows(p)
    counts=[[int(value) for value in r["possible_counts"].split("|") if value] for r in observations]
    intervals=[]
    for r in observations:
        net,low,high,err=[float(r[key]) for key in ("net_g","low_unit_g","high_unit_g","max_reading_error_g")]
        intervals.append(list(range(math.ceil((net-err-1e-8)/high),math.floor((net+err+1e-8)/low)+1)))
    truth=[int(r["truth"]) for r in observations]
    bad_count=sum(actual not in predicted for actual,predicted in zip(truth,counts))
    wrong_accepted=sum(actual!=20 for actual,predicted in zip(truth,counts) if predicted==[20])
    ambiguous=sum(len(got)!=1 for got in counts)
    estimated_net=max(abs(float(r["gross_g"])-float(r["net_g"])-37.5) for r in observations)
    highest=max(float(r["gross_g"]) for r in observations)
    return {
        "ambiguous readings in full-factorial trial":check(ambiguous,ambiguous==0),
        "count set differences from independent interval inversion":check(sum(a!=b for a,b in zip(counts,intervals)),counts==intervals),
        "neighboring counts falsely accepted as twenty":check(wrong_accepted,wrong_accepted==0),
        "candidate set excludes true count":check(bad_count,bad_count==0 and len(observations)==135),
        "tare subtraction disagreement g":check(estimated_net,estimated_net<.0001),
        "gross scale headroom g":check(150-highest,150-highest>=50)
    }


def top_off(p):
    observations=rows(p)
    max_fill=max(int(r["volume_ml"]) for r in observations)
    dry_on=sum(int(r["pump"]) for r in observations if r["dry"]=="1")
    unsafe_on=sum(int(r["pump"]) for r in observations if r["high"]=="1" or r["latched"]=="1")
    restart_on=sum(int(r["pump"]) for r in observations if r["case"]=="restart_fault" and int(r["step"])>=12)
    step_errors=[]
    for a,b in zip(observations,observations[1:]):
        if a["case"]==b["case"]:
            increment=int(b["volume_ml"])-int(a["volume_ml"])
            expected=18 if a["pump"]=="1" else (-10 if a["case"]=="normal" else 0)
            step_errors.append(abs(increment-expected))
    return {
        "maximum simulated fill ml":check(max_fill,max_fill<=3100),
        "pump steps with dry reservoir":check(dry_on,dry_on==0),
        "pump steps on asserted upper stop or latch":check(unsafe_on,unsafe_on==0),
        "pumping steps after restart with retained fault":check(restart_on,restart_on==0),
        "mass-balance residual ml":check(max(step_errors),max(step_errors)==0 and len(observations)==140)
    }


def winder(p):
    data=rows(p)
    x=[float(r["guide_x_mm"]) for r in data]
    pitch=[round(abs(a-b),5) for a,b in zip(x,x[1:])]
    sign=[b>a for a,b in zip(x,x[1:])]
    reversals=[i for i,(a,b) in enumerate(zip(sign,sign[1:]),1) if a!=b]
    count=max(int(r["turn"]) for r in data)
    encoder=max(abs(int(r["encoder_angle_deg"])-i*360) for i,r in enumerate(data))
    return {
        "minimum adjacent turn pitch mm":check(min(pitch),min(pitch)>=.075),
        "maximum adjacent turn pitch mm":check(max(pitch),max(pitch)<=.10),
        "guide edge margin mm":check(min(min(x),10-max(x)),min(min(x),10-max(x))>=.49),
        "encoder turn count":check(count,encoder==0 and count==6000 and len(data)==6001),
        "reversal dwell-free count":check(len(reversals),len(reversals)>=45 and min(pitch)>.001)
    }


def photo_mount(p):
    s=Drawing(p)
    tray_x,plane,w,_=s.rect("sample")
    cx,cy,_=s.circle("lens")
    views=[s.line(f"hfov-{i}")[1][0] for i in (0,1)]
    width_margin=min(tray_x-min(views), max(views)-tray_x-w)
    depth=s.rect("target-plan")[3]
    depth_margin=(math.dist(*s.line("vertical-fov-at-tray"))-depth)/2
    h=plane-cy
    reflection=[]
    for key in ("lamp-0","lamp-1"):
        lx,ly,_=s.circle(key)
        lh=plane-ly
        for light_error in (-5,5):
            for camera_error in (-5,5):
                spot=(cx+camera_error)+(lx+light_error-cx-camera_error)*h/(h+lh)
                reflection.append(abs(spot-(tray_x+w/2))-w/2)
    return {
        "minimum reflected spot distance outside tray with positioning error mm":check(min(reflection),
                                                                                       min(reflection)>=10),
        "horizontal camera field margin per side mm":check(width_margin,width_margin>=20),
        "vertical camera field margin per side mm":check(depth_margin,depth_margin>=20),
        "height repeatability datum mm":check(h,h==280)
    }


def arm(p):
    s=Drawing(p)
    stiffness=float(s.root.get("data-joint-stiffness"))
    mass=float(s.root.get("data-phone-mass-kg"))
    slip=float(s.root.get("data-slip-torque"))
    spans=[[(a[0],b[0]) for a,b in (s.line(f"link-a-{i}"),s.line(f"link-b-{i}"))] for i in (0,1,2)]
    lever=max(abs(points[-1][1]-points[0][0])/1000 for points in spans)
    torque=mass*9.80665*lever
    sag=1000*lever*math.sin(torque/stiffness)
    jaw_opening=s.rect("jaw-bottom")[1]-s.rect("jaw-top")[1]-s.rect("jaw-top")[3]
    return {
        "nominal phone-load droop mm":check(sag,sag<=6),
        "pivot slip torque divided by modeled phone-only demand":check(slip/torque,slip/torque>=1.5),
        "table thickness range mm":check(jaw_opening,jaw_opening-45>=5 and (jaw_opening-18)<=40),
        "jaw engagement length mm":check(s.rect("jaw-top")[2],s.rect("jaw-top")[2]>=48)
    }


def segment_distance(point,a,b):
    dx,dy=b[0]-a[0],b[1]-a[1]
    q=max(0,min(1,((point[0]-a[0])*dx+(point[1]-a[1])*dy)/(dx*dx+dy*dy)))
    return math.dist(point,(a[0]+q*dx,a[1]+q*dy))


def tactile(p):
    s=Drawing(p)
    route=s.points("route")
    rim=float(s.entities["route"].get("data-ridge-width"))/2
    ridge=float(s.entities["route"].get("data-ridge-height"))
    x,y,w,h=s.rect("base")
    symbols, distances, clearance=[],[],[]
    for i in range(5):
        name=f"landmark-{i}"
        key=f"legend-{i}"
        if s.entities[name].tag.endswith("circle"):
            cx,cy,r=s.circle(name)
            signature=("circle",r)
            assert abs(s.circle(key)[2]-r)<.01
        else:
            nodes=s.points(name)
            cx=(max(a for a,_ in nodes)+min(a for a,_ in nodes))/2
            cy=(max(b for _,b in nodes)+min(b for _,b in nodes))/2
            r=max(math.dist(p,(cx,cy)) for p in nodes)
            sig=lambda vertices:[round(math.dist(a,b),5) for a,b in zip(vertices,vertices[1:]+vertices[:1])]
            signature=tuple(sig(nodes))
            assert sig(s.points(key))==list(signature)
        symbols.append(signature)
        distances.append(min(segment_distance((cx,cy),a,b) for a,b in zip(route,route[1:]))-r-rim)
        clearance.append(min(cx-x,x+w-cx,cy-y,y+h-cy)-r)
    source_error=max(math.dist(k,m) for k,m in zip(route,((34,89),(194,89),(194,49),(213,49))))
    return {
        "minimum clear tactile gap between path and landmark mm":check(min(distances),min(distances)>=15),
        "unique shape signatures matching separate key":check(len(set(symbols)),len(set(symbols))==5),
        "ridge height mm":check(ridge,.7<=ridge<=1.2),
        "landmark to base edge margin mm":check(min(clearance),min(clearance)>=6),
        "training source route coordinate maximum error mm":check(source_error,source_error<=.1)
    }


CHECKS={
    "P003":(cabinet,"svg","print calibration span error mm"),
    "P004":(pcb,"svg","SD pull travel mm"),
    "P023":(slide,"svg","end-to-end parallelism error mm"),
    "P025":(tray,"svg","lid bypass gap below thin washer thickness mm"),
    "P026":(tent,"svg","minimum supported typing load margin mm"),
    "P030":(rover,"svg","worst overhead clearance on threshold mm"),
    "P039":(count_scale,"csv","ambiguous readings in full-factorial trial"),
    "P040":(top_off,"csv","maximum simulated fill ml"),
    "P045":(winder,"csv","minimum adjacent turn pitch mm"),
    "P046":(photo_mount,"svg","minimum reflected spot distance outside tray with positioning error mm"),
    "P228":(arm,"svg","nominal phone-load droop mm"),
    "P229":(tactile,"svg","minimum clear tactile gap between path and landmark mm")
}


def run():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write",action="store_true")
    args=parser.parse_args()
    from build import build
    reports={}
    with TemporaryDirectory() as tmp:
        tmp=Path(tmp)
        build(tmp)
        for key,(checker,ext,required) in CHECKS.items():
            revisions={}
            for variant in ("trial","rejected"):
                relative=Path(key)/f"{variant}.{ext}"
                revisions[variant]=checker(HERE/relative)
                if (tmp/relative).read_bytes()!=(HERE/relative).read_bytes():
                    raise SystemExit(f"Stale export {relative}")
            issues=[name for name,v in revisions["trial"].items() if not v["pass"]]
            controls=[name for name,v in revisions["rejected"].items() if not v["pass"]]
            okay=not issues and required in controls
            reports[key]={**revisions,"required_rejection":required,"pass":okay}
            print(f"{key}: candidate failures {issues}; rejected on {controls}")
    path=HERE/"results.json"
    result=json.dumps(reports,indent=2)+"\n"
    if args.write:
        path.write_text(result,encoding="utf-8")
    elif not path.exists() or path.read_text()!=result:
        raise SystemExit("Saved evidence differs. Review then run verify.py --write.")
    return all(r["pass"] for r in reports.values())


if __name__=="__main__":
    raise SystemExit(0 if run() else 1)
