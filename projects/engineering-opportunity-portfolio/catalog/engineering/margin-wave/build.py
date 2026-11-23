"""Export the near-break-even designs and simulated behavior traces."""
import csv
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
MODEL=json.loads((HERE/"designs.json").read_text())


class Sheet:
    def __init__(self,title,w,h):
        self.root=ET.Element("svg",xmlns="http://www.w3.org/2000/svg",width=f"{w}mm",height=f"{h}mm",
                             viewBox=f"0 0 {w} {h}")
        ET.SubElement(self.root,"title").text=title
        ET.SubElement(self.root,"style").text=(
            "text{font:4px sans-serif;fill:#18323a} .part,.dim,.test{fill:none;stroke:#22424a;stroke-width:.4}"
            ".part{fill:#dfebeb;fill-opacity:.4}.dim{stroke:#13746a}.test{stroke:#a54b25;stroke-dasharray:2 1}"
        )

    def elem(self,tag,ident,kind,**attrs):
        ET.SubElement(self.root,tag,{"id":ident,"class":kind,**{
            k:str(round(v,6)) if isinstance(v,(float,int)) else str(v) for k,v in attrs.items()}})

    def rect(self,key,x,y,w,h,kind="part"):
        self.elem("rect",key,kind,x=x,y=y,width=w,height=h)

    def circle(self,key,x,y,r,kind="part"):
        self.elem("circle",key,kind,cx=x,cy=y,r=r)

    def line(self,key,a,b,kind="dim"):
        self.elem("line",key,kind,x1=a[0],y1=a[1],x2=b[0],y2=b[1])

    def polygon(self,key,points,kind="part"):
        self.elem("polygon",key,kind,points=" ".join(f"{x:.6f},{y:.6f}" for x,y in points))

    def text(self,x,y,label):
        ET.SubElement(self.root,"text",x=str(x),y=str(y)).text=label

    def write(self,path):
        ET.indent(self.root,space="  ")
        path.write_text(ET.tostring(self.root,encoding="unicode")+"\n",encoding="utf-8")


def csv_rows(path,header,values):
    with path.open("w",newline="",encoding="utf-8") as output:
        writer=csv.writer(output,lineterminator="\n")
        writer.writerow(header)
        writer.writerows(values)


def coupon(p,out):
    s=Sheet("Unpowered crossbeam alignment coupon",590,178)
    span=p["span"]
    x,y=28,21
    s.line("span",(x,y),(x+span,y))
    for i,pos in enumerate((x,x+span)):
        s.polygon(f"support-{i}",[(pos,y),(pos-10,y+13),(pos+10,y+13)])
    for i,frac in enumerate((.25,.5,.75)):
        pos=x+span*frac
        s.line(f"load-{i}",(pos,y-11),(pos,y),"test")
    h,w,t=p["section_height"],p["section_width"],p["wall"]
    for i in (0,1):
        u=28+i*46
        s.rect(f"tube-{i}",u,51,w,h)
        s.rect(f"hollow-{i}",u+t,51+t,w-2*t,h-2*t,"dim")
    s.root.set("data-modulus",str(p["modulus_n_mm2"]))
    s.root.set("data-rail-force",str(p["rail_force_n"]))
    s.text(27,108,f"Two isolated {w} × {h} × {t} tubes; measured span {span}; {p['rail_force_n']} N per tube")
    s.text(27,119,"Check support height and sample midpoint with a dial indicator. Use weights only.")
    s.text(27,131,"No powered tool is part of this setup.")
    s.write(out)
    second=(w*h**3-(w-2*t)*(h-2*t)**3)/12
    ei=p["modulus_n_mm2"]*second
    rows=[]
    for loc in (span/4,span/2,span*3/4):
        for probe in range(0,span+1,span//20):
            a,x=loc,probe
            if x>a:
                a,x=span-a,span-x
            b=span-a
            y=p["rail_force_n"]*b*x*(span**2-b**2-x**2)/(6*span*ei)
            rows.append((loc,probe,f"{y:.8f}"))
    csv_rows(out.with_suffix(".csv"),("load_x","indicator_x","deflection_mm"),rows)


def pointer(p,out):
    s=Sheet("Large-ball desktop USB pointer housing coupon",218,180)
    x,y=21,16
    w,h=p["shell"]
    cx,cy=x+w/2,y+44
    s.rect("cover",x,y,w,h)
    s.circle("ball",cx,cy,p["ball_d"]/2)
    s.circle("cleaning-access",cx,cy,p["access_d"]/2,"dim")
    for i,k in enumerate((-1,1)):
        s.circle(f"button-{i}",cx+k*p["button_span"]/2,y+91,p["button_d"]/2)
        s.rect(f"foot-{i}",x+7+i*(w-19),y+h-8,5,5,"test")
    s.rect("usb-relief",cx-7,y-6,14,6,"dim")
    s.text(21,146,f"Ball Ø{p['ball_d']}; lift-off ring Ø{p['access_d']}; button centers {p['button_span']} apart")
    s.text(21,156,"Assumed cleanable donor ball, two large buttons and wired USB controller.")
    s.text(21,166,"Check button position and ball force with the intended operator.")
    s.write(out)
    rows=[]
    deadband,gain=p["deadband"],p["gain"]
    for quad,(sx,sy) in enumerate(((-1,-1),(1,-1),(-1,1),(1,1)),1):
        for trial in range(10):
            aim_x,aim_y=sx*(9+trial*.7),sy*(6+trial*.55)
            err=(trial%5-2)*.085
            events=[("move",aim_x+err,aim_y-err,0),("press",0,0,1),
                    ("rest",.21,-.18,1),("drag",sx*.55,sy*.75,1),
                    ("rest",-.18,.21,1),("release",0,0,0)]
            for phase,a,b,btn in events:
                conv=lambda z: round(z*gain,5) if abs(z)>=deadband else 0
                rows.append((quad,trial,phase,round(aim_x*gain,5),round(aim_y*gain,5),
                             round(a,5),round(b,5),conv(a),conv(b),btn))
    csv_rows(out.with_suffix(".csv"),("quadrant","trial","phase","target_x","target_y","raw_dx","raw_dy",
                                     "cursor_dx","cursor_dy","left_button"),rows)


def cheeks(p,out):
    length,w,h=p["length"],p["cheek_width"],p["height"]
    s=Sheet("Matched tapered book backing cheeks",335,214)
    for i,angle in enumerate(p["angles"]):
        x=20+i*113
        toe=p["recess"]*math.tan(math.radians(angle))
        s.polygon(f"cheek-{i}",[(x,79),(x+toe,79-p["recess"]),(x+w,79-p["recess"]),(x+w,79+h),(x,79+h)])
        s.line(f"bevel-{i}",(x,79),(x+toe,79-p["recess"]),"dim")
        s.rect(f"jaw-{i}",x+5,102,p["stock_t"],34,"test")
        s.text(x,58,f"{('Left','Right')[i]} cheek, bevel {angle}°")
        s.rect(f"blank-{i}",20,17+i*12,length,8)
        s.line(f"tip-line-{i}",(20,16+i*12),(20+length,16+i*12))
    s.rect("signature",213,92,71,41,"test")
    s.rect("seated-cheek-left",193,101,20,32)
    s.rect("seated-cheek-right",284,101,20,32)
    s.line("finished-shoulder-check",(213,92),(284,92),"dim")
    s.text(18,174,f"Jaw blanks {length} long; active rebate depth {p['recess']}; assumed jaw backing {p['stock_t']} thick")
    s.text(18,185,"Cut a matched pair from one straight board. Mirror both bevels when installing.")
    s.text(18,196,"Compare dry shoulders with a gauge before working a glued text block.")
    s.write(out)


def groover(p,out):
    s=Sheet("Spline-guided leather groove offset coupon",291,220)
    offset=p["offset"]
    for i, radius in enumerate(p["curve_radii"]):
        for j,side in enumerate((-1,1)):
            cx=44+i*146
            cy=67+j*104
            half=p["roller_span"]/2
            q=math.sqrt(radius**2-half**2)
            for k,x in enumerate((cx-half,cx+half)):
                s.circle(f"roller-{i}-{j}-{k}",x,cy+p["wheel_d"]/2,p["wheel_d"]/2)
            s.elem("path",f"curve-edge-{i}-{j}","test",
                   d=f"M {cx-half} {cy} A {radius} {radius} 0 0 1 {cx+half} {cy}")
            s.line(f"chord-{i}-{j}",(cx-half,cy),(cx+half,cy))
            s.line(f"curve-datum-{i}-{j}",(cx,cy),(cx,cy-radius+q),"test")
            s.circle(f"tool-{i}-{j}",cx,cy+side*offset,.55,"dim")
            s.circle(f"witness-{i}-{j}",cx,cy-radius+q+side*offset,.55,"test")
            s.text(cx-26,cy-14,f"R{radius}   {'outside' if not j else 'inside'} guide")
    s.text(18,192,f"Guide wheel pitch {p['roller_span']}; nominal grooving offset {offset}; verify with blunt witness tip.")
    s.text(18,203,"Use two rollers on the reference edge and lock the offset at the center of their chord.")
    s.write(out)


def tamp(p,out):
    s=Sheet("Cradle layout for spouted 58 mm portafilter envelope",292,209)
    cx,cy=83,83
    s.rect("base",18,32,130,100)
    s.circle("bowl",cx,cy,p["body_d"]/2)
    s.circle("basket",cx,cy,p["basket_d"]/2,"test")
    s.circle("saddle-opening",cx,cy,p["aperture_d"]/2,"dim")
    for i,angle in enumerate((-90,-45,0,45,90)):
        a=math.radians(angle)
        for j,k in enumerate((-1,1)):
            s.circle(f"spout-{i}-{j}",cx+k*p["spout_offset"]*math.cos(a),
                     cy+k*p["spout_offset"]*math.sin(a),p["spout_r"],"test")
    for i,sign in enumerate((-1,1)):
        for j,k in enumerate((-1,1)):
            s.circle(f"foot-{i}-{j}",cx+sign*p["feet"][0]/2,cy+k*p["feet"][1]/2,5)
    s.circle("tamp-load",cx+p["eccentricity"],cy,2,"test")
    s.line("section-floor",(162,113),(262,113))
    face=113-p["cup_floor"]
    s.line("section-seat",(162,face),(262,face),"dim")
    s.rect("section-tip",194,face,15,p["spout_depth"],"test")
    s.root.set("data-bench-load-n",str(p["target_force"]))
    s.text(18,149,"Support the bowl under the rim. Keep spout and handle outside their load paths.")
    s.text(18,160,f"Nominal basket {p['basket_d']}; assumed body {p['body_d']}; assumed recess {p['cup_floor']}")
    s.text(18,171,"Confirm the real body's shoulder, handle angle and spout dimensions before cutting.")
    s.write(out)


def dispenser(p,out):
    s=Sheet("Three-lane label liner dispenser",257,285)
    widths=p["roll_widths"]
    left=21
    for i,w in enumerate(widths):
        s.rect(f"roll-{i}",left,22,w,p["roll_od"])
        s.rect(f"liner-{i}",left,101,w,29,"test")
        middle=left+w/2
        s.line(f"feed-{i}",(middle,101),(middle,139),"dim")
        if i+1<len(widths):
            s.rect(f"divider-{i}",left+w+p["separator_gap"]/2-1,22,2,82)
        left+=w+p["separator_gap"]
    s.line("peel-edge",(17,139),(left+4,139),"part")
    cx,cy=23,208
    s.circle("roll-end",cx+20,cy-12,p["roll_od"]/2)
    s.circle("core",cx+20,cy-12,p["core_id"]/2,"dim")
    s.circle("shaft",cx+20,cy-12,p["axle_d"]/2,"test")
    bend=(111,cy+12)
    s.line("incoming",(54,cy+11),bend)
    s.line("peel-liner",bend,(p["release_x"],cy+43),"test")
    s.line("label-continue",bend,(161,cy+11),"part")
    s.text(18,260,f"Three assumed widths {widths}; dividers use {p['separator_gap']} pitch allowance")
    s.text(18,271,"Hand-pull the liner down over a smooth rigid edge. Verify the release angle with real stock.")
    s.write(out)


CASES={"P082":coupon,"P220":pointer,"P237":cheeks,"P243":groover,"P266":tamp,"P270":dispenser}


def build(root):
    for key,builder in CASES.items():
        dst=root/key
        dst.mkdir(parents=True,exist_ok=True)
        base={k:v for k,v in MODEL[key].items() if k!="bad"}
        for title,params in (("trial",base),("rejected",base|MODEL[key]["bad"])):
            builder(params,dst/f"{title}.svg")


if __name__=="__main__":
    build(HERE)
