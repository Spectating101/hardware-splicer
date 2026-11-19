"""Create trial drawings and the programming-fixture contact matrix."""
import csv
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
MODEL=json.loads((HERE/"designs.json").read_text())
BOARD=json.loads((HERE/"source-board.json").read_text())


class Drawing:
    def __init__(self,title,w,h):
        self.root=ET.Element("svg",xmlns="http://www.w3.org/2000/svg",width=f"{w}mm",height=f"{h}mm",
                             viewBox=f"0 0 {w} {h}")
        ET.SubElement(self.root,"title").text=title
        ET.SubElement(self.root,"style").text=(
            "text{font:4px sans-serif; fill:#21363c} .part,.cut,.limit{fill:none;stroke:#293c44;stroke-width:.35}"
            ".part{fill:#ddeaea;fill-opacity:.4}.cut{stroke:#006454}.limit{stroke:#ab492b;stroke-dasharray:2 1}"
        )

    def shape(self,tag,ident,kind,**attrs):
        ET.SubElement(self.root,tag,{"id":ident,"class":kind,**{
            k:str(round(v,6)) for k,v in attrs.items()}})

    def rect(self,name,x,y,w,h,kind="part"):
        self.shape("rect",name,kind,x=x,y=y,width=w,height=h)

    def circle(self,name,x,y,r,kind="cut"):
        self.shape("circle",name,kind,cx=x,cy=y,r=r)

    def line(self,name,x1,y1,x2,y2,kind="limit"):
        self.shape("line",name,kind,x1=x1,y1=y1,x2=x2,y2=y2)

    def text(self,x,y,label):
        ET.SubElement(self.root,"text",x=str(x),y=str(y)).text=label

    def write(self,p):
        ET.indent(self.root,space="  ")
        p.write_text(ET.tostring(self.root,encoding="unicode")+"\n",encoding="utf-8")


def shelf(m,dst):
    d=Drawing("Indexing shelf pin jig",342,183)
    pitch=m["pitch"]
    for i, row in enumerate((42,106)):
        origin=32+i*(4*pitch+m["splice_error"])
        d.rect(f"work-{i}",20,row,310,52)
        d.rect(f"jig-{i}",origin-9,row+10,4*pitch+18,42)
        d.rect(f"fence-{i}",origin-9,row-5,4*pitch+18,5,"cut")
        for j in range(5):
            x=origin+j*pitch
            y=row+m["land"]
            d.circle(f"bush-{i}-{j}",x,y,m["bore_d"]/2)
            d.circle(f"hole-{i}-{j}",x,y,m["shelf_drill_d"]/2,"limit")
        if i==1:
            d.circle("index-pin",origin,row+m["land"],m["pin_d"]/2)
        d.text(20,row-9,f"Placement {i+1}   pitch {pitch}; hole line {m['land']} from reference edge")
    d.text(20,173,"Seat fence. Start next segment with the index pin in the last drilled hole.")
    d.write(dst)


def vise(m,dst):
    d=Drawing("Spring preloaded PCB vise",262,243)
    for i,w in enumerate(m["widths"]):
        y=15+i*67
        base=m["base_z"]
        z=m["pcb_z"]
        x=18
        d.rect(f"bed-{i}",x,y+z-m["bed_z"],119,m["bed_z"]-base)
        d.rect(f"pcb-{i}",x+12,y,w,m["pcb_t"],"cut")
        d.rect(f"keepout-{i}",x+18,y+m["pcb_t"],w-12,m["bottom_component_z"],"limit")
        d.rect(f"fixed-{i}",x+6,y-.3,m["jaw_t"],m["slot"],"part")
        d.rect(f"moving-{i}",x+12+w,y-.3,m["jaw_t"],m["slot"],"part")
        gap=m["preload"]+(w-m["widths"][0])*.09
        d.line(f"spring-{i}",155,y+8,155+gap,y+8)
        d.line(f"spring-limit-{i}",155,y+16,165,y+16)
        d.text(150,y,f"Board {w} wide; spring deflection {gap:.2f}")
    d.text(18,222,f"Jaw slot {m['slot']} for {m['pcb_t']} board; assumed component height ≤{m['bottom_component_z']}")
    d.text(18,231,"Replaceable edge jaws attach to rail blocks under the section datum.")
    d.write(dst)


def contact(m,dst):
    d=Drawing("SPI adapter spring probe and keyed cassette",235,200)
    d.rect("carrier",12,11,117,76)
    d.rect("pcb",19,17,BOARD["width"],BOARD["height"])
    d.rect("key",m["key_x"],72,10,8,"cut")
    d.rect("key-window",m["key_x"]-.2,71.8,10.4,8.4,"limit")
    d.rect("reverse-key",145-m["key_x"],72,10,8,"limit")
    contacts=[p for p in BOARD["points"] if p["ref"].startswith("TP")]
    for point in contacts:
        name=point["ref"]
        x,y=19+point["x"],17+BOARD["height"]-point["y"]
        d.circle("pad-"+name,x,y,point["diameter"]/2,"part")
        d.circle("tip-"+name,x,y,m["tip_radius"],"cut")
        d.text(x+1.1,y-1.1,name)
    for i,point in enumerate(p for p in BOARD["points"] if p["ref"].startswith("H")):
        d.circle(f"mount-{i}",19+point["x"],17+BOARD["height"]-point["y"],point["diameter"]/2)
    d.rect("section-guide",18,113,116,8)
    d.rect("section-board",19,140,90,1.6,"cut")
    d.line("unloaded-tip",28,121,28,140+m["nominal_stroke"])
    d.line("hard-stop",15,121,15,140)
    d.text(18,158,"Install replaceable board-side cassette with a positive orientation tab.")
    d.text(18,169,"Probe tips Ø0.50. Working travel and radial error are bench assumptions.")
    d.text(18,179,"Connect each probe lead by name. Test grounds as a connected group.")
    d.write(dst)
    with dst.with_suffix(".csv").open("w",newline="",encoding="utf-8") as f:
        writer=csv.writer(f,lineterminator="\n")
        writer.writerow(("pin","net","lead","stroke_mm","radial_error_mm","minimum_stroke_mm","maximum_stroke_mm"))
        for point in contacts:
            for offset in (-m["z_error"],0,m["z_error"]):
                writer.writerow((point["ref"],point["net"],point["ref"] if point["ref"]!=m["open_lead"] else "",
                                 round(m["nominal_stroke"]+offset,5),m["radial_error"],*m["working_stroke"]))


def staging(m,dst):
    d=Drawing("Transfer carrier for pick-and-place bench staging",208,202)
    x,y=17,15
    d.rect("carrier",x,y,*m["plate"])
    for i,(a,b) in enumerate(m["host"]):
        d.circle(f"mount-{i}",x+a,y+b,m["screw_d"]/2)
    d.rect("board",x+25,y+22,*m["board"])
    for i,a in enumerate((m["clamp_left"],m["clamp_right"])):
        d.rect(f"toe-{i}",x+a-8,y+m["clamp_y"],16,22)
    for i,(u,v) in enumerate(((36,31),(106,64),(38,61))):
        d.circle(f"fiducial-{i}",x+u,y+v,.65)
    for i,(u,v) in enumerate(((37,46),(83,46),(100,49))):
        d.circle(f"nozzle-{i}",x+u,y+v,m["nozzle_d"]/2,"limit")
    base=145
    d.rect("side-plate",x,base,m["plate"][0],4)
    d.line("side-board",x+25,base-m["top_z"],x+115,base-m["top_z"],"cut")
    d.line("side-clamp",x+13,base-m["clamp_z"],x+27,base-m["clamp_z"],"part")
    d.line("safe-traverse",x+11,base-m["approach_z"],x+127,base-m["approach_z"])
    d.text(17,164,"Plan 140 × 95. Trial 90 × 50 coupon and four transfer mounting holes.")
    d.text(17,176,"Use qualified adapter feet to match the actual stage datum and hole coordinates.")
    d.text(17,187,"Set placement Z and confirm overhead approach in a no-paste dry run.")
    d.write(dst)


def stencil(m,dst):
    d=Drawing("Small PCB stencil frame with registration controls",205,202)
    x,y=21,28
    w,h=m["board"]
    sw,sh=m["stencil"]
    d.rect("foil",x-12,y-12,sw,sh)
    d.rect("coupon",x,y,w,h)
    d.line("hinge",x-12,y-m["lift_pivot"],x+sw-12,y-m["lift_pivot"])
    d.circle("pivot",x+w/2,y+h/2,.6)
    for i,(px,py) in enumerate(m["apertures"]):
        d.circle(f"pad-{i}",x+px,y+py,.75)
        d.circle(f"opening-{i}",x+px,y+py+m["hinge_offset_y"],.65,"limit")
    d.rect("left-guide",x-3,y+3,3,h-6,"cut")
    d.rect("lower-guide",x+4,y+h,w-8,3,"cut")
    d.rect("wipe-handle",x+sw-13,y+sh-40,8,24)
    d.root.set("data-play-mm",str(m["xy_play"]))
    d.root.set("data-angular-error-deg",str(m["angular_error"]))
    base=144
    pivot=(x-m["lift_pivot"],base)
    d.circle("side-pivot",*pivot,1)
    d.line("board-face",x,base,x+w,base,"part")
    d.line("closed-foil",*pivot,x+w+10,base,"cut")
    rad=math.radians(50)
    d.line("opened-foil",*pivot,pivot[0]+(w+28)*math.cos(rad),base-(w+28)*math.sin(rad),"cut")
    d.text(9,161,f"Coupon {w} × {h}; foil {sw} × {sh}. Four witness apertures.")
    d.text(9,172,"Use two fixed edge datums and one spring fence. Align with fixture closed.")
    d.text(9,183,"Lift 50° for remove-and-wipe cycle. Transfer actual stencil artwork before use.")
    d.write(dst)


def coupling(m,dst):
    d=Drawing("Manual coupler and two register plates",226,176)
    for i,y in enumerate((18,79)):
        x=16
        d.rect(f"plate-{i}",x,y,*m["plate"])
        for j,(u,v) in enumerate(m["dowels"]):
            d.circle(f"pin-{i}-{j}",x+u,y+v,m["pin_d"][j]/2)
            d.circle(f"seat-{i}-{j}",x+u,y+v,m["seat_d"][j]/2,"limit")
        d.rect(f"latch-slot-{i}",x+12,y+32,10,m["lock_enter"],"cut")
        d.rect(f"latch-hook-{i}",x+11,y+32,4,m["locked_overlap"])
        d.rect(f"reversed-tab-{i}",x+44,y+32,4,m["locked_overlap"],"limit")
        d.text(88,y+12,("Wrist-side plate","Tool-side plate and second identical blank")[i])
    d.line("tip-offset",108,78,108+m["tip_offset"],78)
    d.line("release-motion",112,116,112,116-m["lock_lift"])
    d.text(16,143,"Seat plain tool plate on round and relieved locators, then push latch home.")
    d.text(16,154,"Blank interface for measured wrist adapter. Section refers to registered face, not horn.")
    d.text(16,165,"Test unloaded over a catching mat before adding the 100 g dummy tool.")
    d.write(dst)


BUILDERS={"P022":shelf,"P024":vise,"P033":contact,"P034":staging,"P048":stencil,"P216":coupling}


def build(base):
    for key,func in BUILDERS.items():
        folder=base/key
        folder.mkdir(parents=True,exist_ok=True)
        nominal={k:v for k,v in MODEL[key].items() if k!="bad"}
        for rev,params in (("trial",nominal),("rejected",nominal|MODEL[key]["bad"])):
            func(params,folder/f"{rev}.svg")


if __name__=="__main__":
    build(HERE)
