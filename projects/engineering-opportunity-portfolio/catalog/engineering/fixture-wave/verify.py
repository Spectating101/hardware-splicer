"""Measure the released fixture drawings and check each intended rejection."""
import argparse
import csv
import hashlib
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
        for unit, span in zip(("width","height"),self.root.get("viewBox").split()[2:]):
            nominal=self.root.get(unit)
            assert nominal.endswith("mm") and float(nominal[:-2])==float(span)
        nodes=[node for node in self.root.iter() if node.get("id")]
        self.shape={node.get("id"):node for node in nodes}
        assert len(nodes)==len(self.shape)

    def _get(self,id_,properties):
        return tuple(float(self.shape[id_].get(k)) for k in properties.split())

    def line(self,id_):
        return self._get(id_,"x1 y1 x2 y2")

    def rect(self,id_):
        return self._get(id_,"x y width height")

    def circle(self,id_):
        return self._get(id_,"cx cy r")


def check(value,valid):
    return {"measured":round(value,6) if isinstance(value,float) else value,"pass":bool(valid)}


def shelf(svg):
    s=Sheet(svg)
    pitch=[]
    offsets=[]
    for i in (0,1):
        _,y,_,_=s.rect(f"work-{i}")
        holes=[s.circle(f"hole-{i}-{j}") for j in range(5)]
        pitch.extend(abs(b[0]-a[0]-32) for a,b in zip(holes,holes[1:]))
        offsets.extend(abs(point[1]-y-37) for point in holes)
        assert all(abs(2*p[2]-5)<.001 for p in holes)
    splice=abs(s.circle("hole-0-4")[0]-s.circle("index-pin")[0])
    difference=s.circle("hole-0-4")[2]-s.circle("index-pin")[2]
    return {
        "reposition splice error mm":check(splice,splice<=.15),
        "intra-segment pitch error mm":check(max(pitch),max(pitch)<=.1),
        "reference edge setback error mm":check(max(offsets),max(offsets)<=.1),
        "indexing pin radial allowance mm":check(difference,.02<=difference<=.08),
    }


def vise(svg):
    s=Sheet(svg)
    board_width, component, slot, spring = [],[],[],[]
    for i in range(3):
        x,y,w,t=s.rect(f"pcb-{i}")
        jl=s.rect(f"fixed-{i}")
        jr=s.rect(f"moving-{i}")
        board_width.append(jr[0]-jl[0]-jl[2])
        assert abs(jr[0]-x-w)<.001
        _,cy,_,h=s.rect(f"keepout-{i}")
        component.append(s.rect(f"bed-{i}")[1]-cy-h)
        slot.append(min(jl[3],jr[3])-t)
        a,_,b,_=s.line(f"spring-{i}")
        c,_,d,_=s.line(f"spring-limit-{i}")
        spring.append((b-a,d-c-b+a))
    return {
        "underside part clearance above vise bed mm":check(min(component),min(component)>=1),
        "jaw width settings mm":check(board_width,board_width==[22,45,70]),
        "board thickness clearance in jaw slots mm":check(min(slot),all(.25<=p<=.5 for p in slot)),
        "minimum spring travel reserve mm":check(min(p[1] for p in spring),
                                                 min(p[1] for p in spring)>=2 and min(p[0] for p in spring)>=2),
    }


def contact(svg):
    s=Sheet(svg)
    source=json.loads((HERE/"source-board.json").read_text())
    source_file=HERE.parents[4]/"hardware/reference_designs/spi_flash_adapter_v1"/source["board"]
    if source_file.is_file():
        assert hashlib.sha256(source_file.read_bytes()).hexdigest()==source["board_sha256"], "Fixture board changed"
    points={p["ref"]:p for p in source["points"] if p["ref"].startswith("TP")}
    with svg.with_suffix(".csv").open(newline="",encoding="utf-8") as f:
        rows=list(csv.DictReader(f))
    origin=s.rect("pcb")
    mapping={}
    radial, stroke, offset=[],[],[]
    for row in rows:
        pin=row["pin"]
        pad=s.circle("pad-"+pin)
        tip=s.circle("tip-"+pin)
        point=points[pin]
        anchor=(origin[0]+point["x"],origin[1]+origin[3]-point["y"])
        offset.append(math.dist(pad[:2],anchor)+abs(pad[2]-point["diameter"]/2))
        radial.append(pad[2]-tip[2]-math.dist(pad[:2],tip[:2])-float(row["radial_error_mm"]))
        low,travel,high=(float(row[k]) for k in ("minimum_stroke_mm","stroke_mm","maximum_stroke_mm"))
        stroke.append(min(travel-low,high-travel))
        assert row["net"]==point["net"]
        if row["lead"]==pin:
            mapping[pin]=row["net"]
    key=s.rect("key")
    inverse=s.rect("reverse-key")
    window=s.rect("key-window")
    assert window[0]<=key[0] and window[0]+window[2]>=key[0]+key[2]
    reverse_miss=inverse[0]-window[0]-window[2]
    return {
        "mapped instrument leads with simulated connection":check(len(mapping),len(mapping)==18),
        "distinct connected nets with shared grounds":check(len(set(mapping.values())),len(set(mapping.values()))==16),
        "source coordinate disagreement mm":check(max(offset),max(offset)<=.001 and len(rows)==54),
        "probe tip radial margin mm":check(min(radial),min(radial)>=.09),
        "spring stroke reserve mm":check(min(stroke),min(stroke)>=.15),
        "reversed key clearance beyond receiving window mm":check(reverse_miss,reverse_miss>=5),
    }


def box_distance(point,box):
    x,y=point
    a,b,w,h=box
    return math.hypot(max(a-x,0,x-a-w),max(b-y,0,y-b-h))


def staging(svg):
    s=Sheet(svg)
    x,y,w,h=s.rect("carrier")
    mount=[s.circle(f"mount-{i}") for i in range(4)]
    expected=((10,12),(130,12),(10,83),(130,83))
    hole_error=max(math.dist((i-x,j-y),e) for (i,j,_),e in zip(mount,expected))
    edges=[s.rect(f"toe-{i}") for i in (0,1)]
    tips=[s.circle(f"nozzle-{i}") for i in range(3)]
    fiducials=[s.circle(f"fiducial-{i}") for i in range(3)]
    area=abs((fiducials[1][0]-fiducials[0][0])*(fiducials[2][1]-fiducials[0][1])-
             (fiducials[2][0]-fiducials[0][0])*(fiducials[1][1]-fiducials[0][1]))/2
    clearance=min(box_distance(tip[:2],edge)-tip[2] for tip in tips for edge in edges)
    height=s.line("side-clamp")[1]-s.line("safe-traverse")[1]
    lands=min(min(a-x,x+w-a,b-y,y+h-b)-r for a,b,r in mount)
    board=s.rect("board")
    land_margin=min(min(f[0]-board[0],board[0]+board[2]-f[0],
                        f[1]-board[1],board[1]+board[3]-f[1])-f[2] for f in fiducials)
    return {
        "nozzle-to-clamp repeat clearance mm":check(clearance,clearance>=4),
        "in-plane stage coupon hole disagreement mm":check(hole_error,hole_error<=.1 and lands>=5),
        "fiducial triangle area mm2":check(area,area>=600 and land_margin>=5),
        "safe travel height above clamps mm":check(height,height>=4),
    }


def stencil(svg):
    s=Sheet(svg)
    cx,cy,_=s.circle("pivot")
    play=float(s.root.get("data-play-mm"))
    a=math.radians(float(s.root.get("data-angular-error-deg")))
    errors=[]
    spare=[]
    for i in range(4):
        x,y,pr=s.circle(f"pad-{i}")
        ox,oy,r=s.circle(f"opening-{i}")
        for u,v,a_sign in itertools.product((-1,1),repeat=3):
            c,sn=math.cos(a),a_sign*math.sin(a)
            bx=cx+c*(ox-cx)-sn*(oy-cy)+u*play
            by=cy+sn*(ox-cx)+c*(oy-cy)+v*play
            error=math.dist((x,y),(bx,by))
            errors.append(error)
            spare.append(pr-r-error)
    x,y,_=s.circle("side-pivot")
    board_x,board_z,*_=s.line("board-face")
    lower_clear=math.tan(math.radians(5))*(board_x-x)-(y-board_z)
    opened=s.line("opened-foil")
    angle=math.degrees(math.atan2(opened[1]-opened[3],opened[2]-opened[0]))
    return {
        "maximum aperture-to-land displacement mm":check(max(errors),max(errors)<=.08),
        "remaining copper margin around worst aperture mm":check(min(spare),min(spare)>=.02),
        "minimum initial lift clearance at 5 degrees mm":check(lower_clear,lower_clear>=1.5),
        "open angle deg":check(angle,49.9<=angle<=50.1),
    }


def coupling(svg):
    s=Sheet(svg)
    x,y,w,h=s.rect("plate-0")
    pins=[s.circle(f"pin-0-{j}") for j in (0,1)]
    seats=[s.circle(f"seat-0-{j}") for j in (0,1)]
    play=[b[2]-a[2] for a,b in zip(pins,seats)]
    baseline=math.dist(pins[0][:2],pins[1][:2])
    a,b,u,v=s.line("tip-offset")
    reach=math.hypot(u-a,v-b)
    drift=play[0]+reach*(play[0]+play[1])/baseline
    reverse_spans=[math.dist((2*x+w-a[0],2*y+h-a[1]),b[:2]) for a,b in zip(pins,reversed(seats))]
    slot=s.rect("latch-slot-0")
    hook=s.rect("latch-hook-0")
    unlocked=abs(s.line("release-motion")[3]-s.line("release-motion")[1])
    depth=hook[3]
    clip_land=min(slot[0]+slot[2],hook[0]+hook[2])-max(slot[0],hook[0])
    return {
        "worst geometry-only tool tip drift mm":check(drift,drift<=.5),
        "prevent reverse dowel seating mm":check(min(reverse_spans),min(reverse_spans)>max(play)+2),
        "latch hook depth engagement mm":check(depth,depth>=3 and clip_land>=3),
        "release travel reserve mm":check(unlocked-depth,unlocked>=depth+2),
    }


TRIALS={
    "P022":(shelf,"reposition splice error mm"),
    "P024":(vise,"underside part clearance above vise bed mm"),
    "P033":(contact,"mapped instrument leads with simulated connection"),
    "P034":(staging,"nozzle-to-clamp repeat clearance mm"),
    "P048":(stencil,"maximum aperture-to-land displacement mm"),
    "P216":(coupling,"worst geometry-only tool tip drift mm"),
}


def run():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write",action="store_true")
    args=parser.parse_args()
    from build import build
    evidence={}
    with tempfile.TemporaryDirectory() as location:
        temp=Path(location)
        build(temp)
        for product,(verify,required) in TRIALS.items():
            revisions={rev:verify(HERE/product/f"{rev}.svg") for rev in ("trial","rejected")}
            for out in (temp/product).iterdir():
                if out.read_bytes()!=(HERE/product/out.name).read_bytes():
                    raise SystemExit(f"Stale export {product}/{out.name}")
            bad_trial=[k for k,r in revisions["trial"].items() if not r["pass"]]
            bad_variant=[k for k,r in revisions["rejected"].items() if not r["pass"]]
            evidence[product]={**revisions,"required_rejection":required,
                               "pass":not bad_trial and required in bad_variant}
            print(f"{product}: candidate failures {bad_trial}; rejected on {bad_variant}")
    result=HERE/"results.json"
    report=json.dumps(evidence,indent=2)+"\n"
    if args.write:
        result.write_text(report,encoding="utf-8")
    elif not result.exists() or result.read_text()!=report:
        raise SystemExit("Replay differs from saved results. Review then run verify.py --write.")
    return all(row["pass"] for row in evidence.values())


if __name__=="__main__":
    raise SystemExit(0 if run() else 1)
