"""Read the released drawings and traces and replay the margin studies."""
import argparse
import csv
import itertools
import json
import math
from pathlib import Path
import tempfile
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent


class Sheet:
    def __init__(self,path):
        self.root=ET.parse(path).getroot()
        scale=self.root.get("viewBox").split()[2:]
        for unit,val in zip(("width","height"),scale):
            dim=self.root.get(unit)
            assert dim.endswith("mm") and float(dim[:-2])==float(val)
        self.entities={p.get("id"):p for p in self.root.iter() if p.get("id")}

    def _attrs(self,k,attrs):
        return tuple(float(self.entities[k].get(f)) for f in attrs.split())

    def rect(self,k):
        return self._attrs(k,"x y width height")

    def circle(self,k):
        return self._attrs(k,"cx cy r")

    def line(self,k):
        x,y,u,v=self._attrs(k,"x1 y1 x2 y2")
        return (x,y),(u,v)

    def rows(self,path):
        with path.with_suffix(".csv").open(newline="",encoding="utf-8") as f:
            return list(csv.DictReader(f))


def check(n,yes):
    return {"measured":round(n,6) if isinstance(n,float) else n,"pass":bool(yes)}


def coupon(p):
    s=Sheet(p)
    span=math.dist(*s.line("span"))
    w,h=s.rect("tube-0")[2:]
    iw,ih=s.rect("hollow-0")[2:]
    assert s.rect("tube-1")[2:]==(w,h) and s.rect("hollow-1")[2:]==(iw,ih)
    e=float(s.root.get("data-modulus"))
    f=float(s.root.get("data-rail-force"))
    i=(w*h**3-iw*ih**3)/12
    calculations={(float(r["load_x"]),float(r["indicator_x"])):float(r["deflection_mm"]) for r in s.rows(p)}
    center=calculations[span/2,span/2]
    theory_error=abs(f*span**3/(48*e*i)-center)
    ends=max(abs(v) for (_,x),v in calculations.items() if x in (0,span))
    mirror=max(abs(v-calculations[span-a,span-x]) for (a,x),v in calculations.items())
    maximum=max(calculations.values())
    return {
        "peak modeled unloaded-fixture deadweight sag mm":check(maximum,maximum<=.08),
        "midpoint classical beam formula error mm":check(theory_error,theory_error<1e-7),
        "displacement at support points mm":check(ends,ends<1e-7),
        "load and probe mirror residual mm":check(mirror,mirror<1e-7 and len(calculations)==63)
    }


def pointer(p):
    s=Sheet(p)
    offsets=[]
    drag=[]
    selected=[]
    traces=s.rows(p)
    expected=(("move",0),("press",1),("rest",1),("drag",1),("rest",1),("release",0))
    for (_, _),group in itertools.groupby(traces,key=lambda r:(r["quadrant"],r["trial"])):
        trace=list(group)
        assert tuple((r["phase"],int(r["left_button"])) for r in trace)==expected
        selection=trace[1]
        start=trace[0]
        selected.append(math.dist(tuple(float(start[q]) for q in ("cursor_dx","cursor_dy")),
                                  tuple(float(selection[q]) for q in ("target_x","target_y"))))
        rest=[math.hypot(float(r["cursor_dx"]),float(r["cursor_dy"])) for r in trace if r["phase"]=="rest"]
        offsets.extend(rest)
        shift=trace[3]
        drag.append(math.hypot(float(shift["cursor_dx"]),float(shift["cursor_dy"])))
    rim=s.circle("cleaning-access")[2]-s.circle("ball")[2]
    a,b=[s.circle(f"button-{k}") for k in (0,1)]
    clear=math.dist(a[:2],b[:2])-a[2]-b[2]
    return {
        "maximum cursor jump on stationary sensor noise px":check(max(offsets),max(offsets)<=.5),
        "candidate hit count across four quadrant scripts":check(sum(r<=9 for r in selected),all(r<=9 for r in selected)
                                                                  and len(selected)==40),
        "short drag displacement while button held px":check(min(drag),min(drag)>=7),
        "ball lift-off radial opening margin mm":check(rim,rim>=4),
        "button edge separation mm":check(clear,clear>=28),
    }


def cheeks(p):
    s=Sheet(p)
    bevel=[s.line(f"bevel-{k}") for k in (0,1)]
    angles=[math.degrees(math.atan2(abs(a[0]-b[0]),abs(a[1]-b[1]))) for a,b in bevel]
    errors=abs(angles[0]-angles[1])
    widths=[math.dist(*s.line(f"tip-line-{i}")) for i in (0,1)]
    pv=[abs(a[0]-b[0]) for a,b in bevel]
    shoulder=abs(pv[0]-pv[1])
    x,y,w,_=s.rect("signature")
    a,b=[s.rect(f"seated-cheek-{k}") for k in ("left","right")]
    exposure=min(a[1],b[1])-y
    seated=abs(a[0]+a[2]-x)<.001 and abs(b[0]-x-w)<.001
    return {
        "opposite bevel angular mismatch deg":check(errors,errors<=.5),
        "horizontal shoulder tip mismatch mm":check(shoulder,shoulder<=.10),
        "spine exposed above opposed faces mm":check(exposure,exposure>=8 and seated),
        "matched working lengths mm":check(widths,widths==[290,290]),
    }


def groover(p):
    s=Sheet(p)
    sag_error, offset_error, geometry, rims = [], [], [], []
    for i,radius in enumerate((36,80)):
        for j in (0,1):
            key=f"{i}-{j}"
            chord=s.line("chord-"+key)
            length=math.dist(*chord)
            arc=s.entities["curve-edge-"+key].get("d").split()
            sag=math.dist(*s.line("curve-datum-"+key))
            actual=s.circle("tool-"+key)
            witness=s.circle("witness-"+key)
            gap=math.dist(actual[:2],witness[:2])
            expected=radius-math.sqrt(radius**2-(length/2)**2)
            sag_error.append(gap)
            offset_error.append(abs(abs(actual[1]-chord[0][1])-3))
            geometry.append(abs(sag-expected)+abs(float(arc[4])-radius))
            left,right=[s.circle(f"roller-{key}-{k}") for k in (0,1)]
            rims.append(math.dist(left[:2],right[:2])-left[2]-right[2])
    return {
        "maximum groove offset error over projected curves mm":check(max(sag_error),max(sag_error)<=.4),
        "straight-edge guide nominal error mm":check(max(offset_error),max(offset_error)<=.01),
        "circular arc and section consistency mm":check(max(geometry),max(geometry)<.00001),
        "minimum space between projected rollers mm":check(min(rims),min(rims)>=3),
    }


def tamp(p):
    s=Sheet(p)
    cx,cy,r=s.circle("saddle-opening")
    body=s.circle("bowl")[2]
    basket=s.circle("basket")[2]
    spout=[]
    for i,j in itertools.product(range(5),range(2)):
        x,y,sr=s.circle(f"spout-{i}-{j}")
        spout.append(r-math.dist((x,y),(cx,cy))-sr)
    _,tip_y,_,tip_h=s.rect("section-tip")
    vertical=s.line("section-floor")[0][1]-tip_y-tip_h
    feet=[s.circle(f"foot-{i}-{j}") for i,j in itertools.product(range(2),repeat=2)]
    x,y,_=s.circle("tamp-load")
    margin=min(x-min(p[0] for p in feet),max(p[0] for p in feet)-x,
               y-min(p[1] for p in feet),max(p[1] for p in feet)-y)
    return {
        "closest spout margin in five orientations mm":check(min(spout),min(spout)>=2.5),
        "remaining support annulus width mm":check(body-r,4<=body-r<=7 and basket==29),
        "clearance below spout mm":check(vertical,vertical>=6),
        "bench load projection inside support polygon mm":check(margin,margin>=20)
    }


def dispenser(p):
    s=Sheet(p)
    rolls=[s.rect(f"roll-{i}") for i in range(3)]
    space=[]
    for i in (0,1):
        x,_,w,_=s.rect(f"divider-{i}")
        space.extend((x-rolls[i][0]-rolls[i][2],rolls[i+1][0]-x-w))
    a,b=s.line("incoming")
    c,d=s.line("peel-liner")
    v=(b[0]-a[0],b[1]-a[1])
    u=(d[0]-c[0],d[1]-c[1])
    beta=math.degrees(math.acos(sum(x*y for x,y in zip(v,u))/(math.hypot(*v)*math.hypot(*u))))
    core=s.circle("core")[2]-s.circle("shaft")[2]
    x_start, x_end=[q[0] for q in s.line("peel-edge")]
    exit_margin=min(min(r[0]-x_start,x_end-r[0]-r[2]) for r in rolls)
    return {
        "liner direction change at peel edge deg":check(beta,b==c and beta>=125),
        "minimum axial space at lane dividers mm":check(min(space),min(space)>=.5),
        "shaft to assumed core radial allowance mm":check(core,core>=5),
        "active peel edge overhang across all lanes mm":check(exit_margin,exit_margin>=3),
    }


TRIALS={
    "P082":(coupon,"peak modeled unloaded-fixture deadweight sag mm"),
    "P220":(pointer,"maximum cursor jump on stationary sensor noise px"),
    "P237":(cheeks,"opposite bevel angular mismatch deg"),
    "P243":(groover,"maximum groove offset error over projected curves mm"),
    "P266":(tamp,"closest spout margin in five orientations mm"),
    "P270":(dispenser,"liner direction change at peel edge deg"),
}


def run():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write",action="store_true")
    args=parser.parse_args()
    from build import build
    report={}
    with tempfile.TemporaryDirectory() as directory:
        temp=Path(directory)
        build(temp)
        for case,(verify,expected) in TRIALS.items():
            variants={k:verify(HERE/case/f"{k}.svg") for k in ("trial","rejected")}
            for file in (temp/case).iterdir():
                assert file.read_bytes()==(HERE/case/file.name).read_bytes(),f"Stale export {case}/{file.name}"
            failures=[k for k,r in variants["trial"].items() if not r["pass"]]
            rejected=[k for k,r in variants["rejected"].items() if not r["pass"]]
            report[case]={**variants,"required_rejection":expected,"pass":not failures and expected in rejected}
            print(f"{case}: candidate failures {failures}; rejected on {rejected}")
    stored=HERE/"results.json"
    contents=json.dumps(report,indent=2)+"\n"
    if args.write:
        stored.write_text(contents,encoding="utf-8")
    elif not stored.exists() or stored.read_text()!=contents:
        raise SystemExit("Results differ from saved replay. Review then use --write.")
    return all(r["pass"] for r in report.values())


if __name__=="__main__":
    raise SystemExit(0 if run() else 1)
