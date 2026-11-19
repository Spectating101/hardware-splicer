"""Build dimensioned bench layouts and observable simulation traces."""
import csv
import itertools
import json
import math
from pathlib import Path
import xml.etree.ElementTree as E

HERE = Path(__file__).resolve().parent
MODELS = json.loads((HERE/"designs.json").read_text())


class Sheet:
    def __init__(self, title, width, height):
        self.e = E.Element("svg", xmlns="http://www.w3.org/2000/svg",
                           width=f"{width}mm", height=f"{height}mm", viewBox=f"0 0 {width} {height}")
        E.SubElement(self.e, "title").text = title
        E.SubElement(self.e, "style").text = (
            "text{font:4px sans-serif;fill:#103341} .part,.tool,.test{stroke:#2a4148;stroke-width:.35;"
            "fill:none}.part{fill:#dce9e9;fill-opacity:.45}.tool{stroke:#006557}.test{stroke:#aa4c22;"
            "stroke-dasharray:2 1}"
        )

    def put(self, tag, key, role, **data):
        return E.SubElement(self.e, tag, {"id": key, "class": role, **{
            k: (str(round(v, 5)) if isinstance(v, (float, int)) else str(v)) for k, v in data.items()
        }})

    def rect(self, key, x, y, w, h, style="part"):
        self.put("rect", key, style, x=x, y=y, width=w, height=h)

    def circle(self, key, x, y, r, style="tool"):
        self.put("circle", key, style, cx=x, cy=y, r=r)

    def line(self, key, a, b, style="tool"):
        self.put("line", key, style, x1=a[0], y1=a[1], x2=b[0], y2=b[1])

    def poly(self, key, pts, role="part", tag="polygon", **data):
        self.put(tag, key, role, points=" ".join(f"{x:.5f},{y:.5f}" for x, y in pts), **data)

    def text(self, x, y, label):
        E.SubElement(self.e, "text", x=str(x), y=str(y)).text = label

    def write(self, dest):
        E.indent(self.e, space="  ")
        dest.write_text(E.tostring(self.e, encoding="unicode")+"\n", encoding="utf-8")


def trace(dest, header, rows):
    with dest.open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def cabinet(p, output):
    w, h, scale = p["width"], p["height"], p["scale"]
    s = Sheet("Cabinet handle drilling layout, actual size", 250, 190)
    x, y = 15, 20
    c = p["center"]
    s.rect("panel", x, y, w*scale, h*scale)
    s.line("center", (x+c*scale, y), (x+c*scale, y+h*scale), "test")
    for i, pitch in enumerate(p["pitch"]):
        a, b = [(c+sign*pitch/2)*scale+x for sign in (-1, 1)]
        yy = y+p["setbacks"][i]*scale
        for j, pos in enumerate((a,b)):
            s.circle(f"drill-{i}-{j}", pos, yy, 2.5*scale)
        s.text(a+8, yy-4, f"{pitch} centers at {p['setbacks'][i]} from top edge")
    s.line("scale-x", (x, 145), (x+p["calibration"]*scale, 145))
    s.line("scale-y", (x+210, 30), (x+210, 30+p["calibration"]*scale))
    s.text(15, 156, "Calibration bars must both measure 100 mm before drilling")
    s.text(15, 167, "Print at actual size. Place top line on panel edge and centerline on cabinet mark.")
    s.write(output)


def pcb(p, output):
    s = Sheet("OpenLog carrier and camera reference", 180, 103)
    ox, oy = p["origin"]
    w, d, margin = p["board_w"], p["board_d"], p["margin"]
    s.rect("carrier", 6, 9, p["carrier_w"], p["carrier_d"])
    s.rect("pcb", ox, oy, w, d)
    s.rect("pocket", ox-margin, oy-margin, w+2*margin, d+2*margin, "tool")
    s.rect("header-keepout", ox, oy+d-3, w, 3, "test")
    s.rect("sd-service", ox+.76, oy-p["card_exit"], 11, p["card_exit"], "test")
    cx, cy = p["camera"]
    fw, fh = p["fov"]
    s.rect("camera", cx-fw/2, cy-fh/2, fw, fh, "test")
    for i, y in enumerate((12, 53)):
        for j, x in enumerate((10,47)):
            s.circle(f"carrier-mount-{i}-{j}", x, y, 1.65)
    s.text(63, 16, f"DEV-13712 board outline {w} × {d}")
    s.text(63, 24, f"Pocket allowance {margin} each side")
    s.text(63, 32, f"SD service corridor {p['card_exit']}")
    s.text(63, 40, f"Assumed camera field {fw} × {fh}")
    s.text(6, 72, "Raise on three insulating edge pads. Leave bottom socket and header clear.")
    s.text(6, 81, "Set camera focus and field on a real sample before fixing the stand.")
    s.write(output)


def slide(p, output):
    s = Sheet("Drawer slide alignment pair", 520, 640)
    x, y = 25, 55
    length, span, skew = p["length"], p["space"], p["skew"]
    for i, offset in enumerate((0, span)):
        sy = y+offset
        shift = skew if i else 0
        s.line(f"datum-{i}", (x,sy), (x+length,sy+shift))
        s.poly(f"slide-{i}", [(x,sy),(x+length,sy+shift),(x+length,sy+shift+13),(x,sy+13)])
        for j, dx in enumerate((37, length-37)):
            py = sy+shift*dx/length
            s.rect(f"shoe-{i}-{j}", x+dx-25, py-10, 50, 25, "test")
            s.circle(f"clamp-{i}-{j}", x+dx, py-26, p["clamp_r"], "test")
    s.rect("rail-section", 40, 530, p["rail_thick"], p["rail_height"])
    s.rect("ledge-section", 37, 530+p["rail_height"], 24, p["base_h"], "tool")
    s.text(25, 18, f"Reference span {span}; rail length {length}. Gauge each end before driving screws.")
    s.text(25, 510, "Mirrored locating shoes mount under the slide. Clamps act on adjacent faces.")
    s.text(80, 550, f"Assumed section {p['rail_thick']} × {p['rail_height']}; ledge {p['base_h']} thick")
    s.write(output)


def tray(p, output):
    s = Sheet("Repair fastener tray and transport lid", 190, 190)
    s.rect("tray", 10, 10, 130, 100)
    for i, (name, dia, length, count) in enumerate(p["fasteners"]):
        x, y = 25+i%3*40, 32+i//3*48
        pocket = max(17, math.sqrt(count)*max(dia,length)*.7+4)
        s.circle(f"pocket-{name}", x+5, y, pocket/2, "tool")
        s.rect(f"fastener-{name}", x+1, y-dia/2, length, dia, "test")
        s.text(x, y+17, f"{name} × {count}")
    floor, wall = p["floor"], p["wall_h"]
    s.rect("floor", 10, 150+wall, 130, floor)
    for i, x in enumerate((10, 52, 94, 137)):
        s.rect(f"wall-{i}", x, 150, 3, wall)
    s.rect("lid", 7, 147-p["lid_gap"], 136, 3, "tool")
    s.text(10, 130, f"Floor {floor}; walls {wall} high; closed lid gap over wall {p['lid_gap']}")
    s.write(output)


def tent(p, output):
    s = Sheet("Split keyboard support pair", 410, 344)
    width = p["keyboard_width"]
    for i in (0, 1):
        ox, oy = 16+i*190, 105
        bottom = p["bottom_height"]
        left = (width-p["footprint"])/2
        right = width-left
        z = lambda u: oy-bottom-p["rise"]*(u/width)
        def x(u):
            return ox+(u if i == 0 else width-u)
        s.line(f"keyboard-{i}", (x(0), z(0)), (x(width), z(width)))
        s.poly(f"wedge-{i}", [(x(left),oy),(x(right),oy),(x(right),z(right)),(x(left),z(left))])
        s.rect(f"stop-{i}", x(0)-3, z(0)-p["stop_height"], 6, p["stop_height"], "tool")
        load_span = sorted((x(40), x(width-40)))
        s.line(f"load-{i}", (load_span[0],oy-4), (load_span[1],oy-4), "test")
        s.line(f"cable-{i}", (x(width),z(width)), (x(width),z(width)+p["cable_clear"]), "test")
    s.rect("plan-body", 16, 136, width, p["keyboard_depth"], "test")
    s.text(16, 127, "Wingless top envelope at 1:1.")
    s.text(16, 320, f"Keyboard support: {p['footprint']} base, {p['rise']} rise over {width}")
    s.text(16, 331, "Use non-slip strips. Confirm real underside, cable plugs and stop contact before printing.")
    s.write(output)


def rover(p, output):
    s = Sheet("Dry indoor inspection cart clearance and view", 475, 346)
    ox, oy = 35, 125
    wheel, wb = p["wheel_d"]/2, p["wheelbase"]
    s.line("ground", (5,oy), (288,oy))
    s.line("roof", (5,oy-p["roof"]), (288,oy-p["roof"]), "test")
    s.rect("cart", ox, oy-p["top"], p["length"], p["top"]-p["skid"])
    x1, x2 = ox+(p["length"]-wb)/2, ox+(p["length"]+wb)/2
    for i, x in enumerate((x1,x2)):
        s.circle(f"wheel-{i}", x, oy-wheel, wheel, "test")
    s.rect("threshold", 255, oy-p["threshold"], 16, p["threshold"], "test")
    cx, cy = ox+p["length"]-9, oy-p["camera_h"]
    distance = p["target_distance"]
    spread = math.tan(math.radians(p["camera_fov"]/2))*distance
    s.circle("camera-lens", cx, cy, 4)
    s.line("ray-upper", (cx,cy), (cx+distance,cy-spread), "test")
    s.line("ray-lower", (cx,cy), (cx+distance,cy+spread), "test")
    s.rect("sighting-card", cx+distance, oy-43, 4, 28, "tool")
    s.rect("tow-slot", ox-10, oy-33, p["recovery_w"], 9, "tool")
    ox, oy = 35, 151
    track, ww = p["track"], p["wheel_w"]
    s.rect("top-body", 55, oy+12, 170, track-4)
    for i, x in enumerate((55,205)):
        for j, y in enumerate((oy,oy+track)):
            s.rect(f"top-wheel-{i}-{j}", x, y, p["wheel_d"], ww)
    s.text(300, 16, f"Wheelbase {wb}, Ø{2*wheel} wheel")
    s.text(300, 25, f"Chassis high point {p['top']}, roof {p['roof']}")
    s.text(300, 34, f"Skid {p['skid']}, threshold {p['threshold']}")
    s.text(300, 43, "Camera cone skips optical distortion and obstruction.")
    s.text(300, 52, "Dry indoor use on level floors only.")
    s.write(output)


def count_scale(p, output):
    rows = []
    unit, tol, err = p["sample_g"], p["unit_tol_g"], p["reading_err_g"]
    for n, lot, bias, read in itertools.product(range(p["nominal"]-2,p["nominal"]+3), ("low","ref","high"),
                                                (-1,0,1), (-1,0,1)):
        mass = n*(unit+{"low":-tol,"ref":0,"high":tol}[lot])
        raw = mass+p["pan_g"]+bias*err/2+read*err/2
        net = raw-p["pan_g"]
        possible = [k for k in range(100) if k*(unit-tol)-err-1e-10 <= net <= k*(unit+tol)+err+1e-10]
        rows.append((n, lot, bias, read, f"{raw:.5f}", f"{net:.5f}", "|".join(map(str, possible)), unit-tol, unit+tol, err))
    trace(output, ("truth","lot","zero_error","read_error","gross_g","net_g","possible_counts","low_unit_g","high_unit_g","max_reading_error_g"), rows)


def top_off(p, output):
    cases = ("normal","dry_reservoir","stuck_low","upper_trip","restart_fault")
    rows = []
    for case in cases:
        level, ticks, locked = p["start_ml"], 0, False
        if case == "upper_trip":
            level = p["upper_ml"]-20
        for t in range(28):
            wired_high = case in ("normal","upper_trip","dry_reservoir") and level >= p["upper_ml"]-10
            below = level < p["bottom_ml"] or case in ("stuck_low","upper_trip","restart_fault","dry_reservoir")
            if case=="restart_fault" and t==12 and not p["latch"]:
                locked, ticks = False, 0
            if wired_high or ticks >= p["max_ticks"]:
                locked = True
            dry = case=="dry_reservoir"
            on = not locked and not dry and below
            rows.append((case,t,level,int(below),int(wired_high),int(dry),ticks,int(locked),int(on)))
            ticks = ticks+1 if on else (ticks if locked else 0)
            level += p["pump_ml_step"] if on else (0 if case!="normal" else -p["boiloff_ml_step"])
    trace(output, ("case","step","volume_ml","demand","high","dry","on_ticks","latched","pump"), rows)


def winder(p, output):
    total = round((p["span"]-2*p["edge"])/p["step"])
    revs = p["turns_per_layer"]
    rows = []
    for turn in range(p["turns"]+1):
        row, state = divmod(turn, revs)
        coordinate = state if row%2==0 else revs-state
        command = round(coordinate*total/revs)+p["reverse_error"]*(row%2)
        rows.append((turn,row,turn*360,command,f"{p['edge']+command*p['step']:.5f}"))
    trace(output, ("turn","layer","encoder_angle_deg","traverse_steps","guide_x_mm"), rows)


def photo_mount(p, output):
    sheet = Sheet("Registered tray photo mount for a clean empty test tray", 440, 510)
    cx, plane = 220, 322
    h, lamp_h = p["camera_h"], p["lamp_h"]
    width, depth = p["tray_w"], p["tray_d"]
    sheet.rect("sample", cx-width/2, plane, width, 4)
    sheet.rect("base", 45, plane+4, 350, 16)
    sheet.rect("left-column", 60, 42, 16, plane-42+4)
    sheet.rect("right-column", 364, 42, 16, plane-42+4)
    sheet.rect("beam", 60, 19, 320, 23)
    sheet.circle("lens", cx, plane-h, 4)
    for i, sign in enumerate((-1, 1)):
        lx = cx+sign*p["lamp_offset"]
        sheet.circle(f"lamp-{i}", lx, plane-lamp_h, 5)
        sheet.line(f"aim-{i}", (lx,plane-lamp_h), (cx,plane), "test")
    half = [h*math.tan(math.radians(p[k]/2)) for k in ("horizontal_fov","vertical_fov")]
    for i in (0,1):
        sheet.line(f"hfov-{i}", (cx,plane-h), (cx+(-1)**i*half[0],plane), "test")
    sheet.rect("target-plan", cx-width/2, 350, width, depth)
    sheet.line("depth-scale", (cx+width/2+12,350), (cx+width/2+12,350+depth), "tool")
    sheet.line("vertical-fov-at-tray", (cx-half[1],470), (cx+half[1],470), "test")
    sheet.text(45, 490, f"Lens {h} above tray. LED centers {p['lamp_offset']} off axis, {lamp_h} above tray.")
    sheet.text(45, 501, "Side and plan at true scale. Use empty tray for this setup trial.")
    sheet.write(output)


def arm(p, output):
    s = Sheet("Two-link tabletop arm geometry and clamp", 425, 322)
    a,b = p["links"]
    s.rect("desk", 30, 205, 355, 33)
    s.rect("jaw-top", 29, 195, p["jaw_depth"], 10)
    s.e.set("data-phone-mass-kg",str(p["mass"]))
    s.e.set("data-joint-stiffness",str(p["joint_stiffness"]))
    s.e.set("data-slip-torque",str(p["slip_torque"]))
    s.rect("jaw-bottom", 29, 205+p["screw_opening"], p["jaw_depth"], 10)
    s.rect("jaw-back", 20, 195, 10, p["screw_opening"]+20)
    s.line("jaw-screw", (61,205+p["screw_opening"]), (61,220), "tool")
    base=(57,175)
    for i, angle in enumerate([p["angles"][0],0,p["angles"][-1]]):
        rad=math.radians(angle)
        elbow=(base[0]+a*math.cos(rad),base[1]-a*math.sin(rad))
        tip=(elbow[0]+b,elbow[1])
        s.line(f"link-a-{i}",base,elbow)
        s.line(f"link-b-{i}",elbow,tip)
        s.rect(f"load-{i}",tip[0],tip[1]-8,10,16,"test")
    s.text(20,18,f"Pivot spans {a} + {b}; modeled phone mass {p['mass']} kg")
    s.text(20,298,f"Throat {p['jaw_depth']}; max open {p['screw_opening']}; joint stiffness input {p['joint_stiffness']} Nm/rad")
    s.write(output)


def tactile(p, output):
    s = Sheet("Raised-line teaching layout with separate symbol key", 265, 232)
    s.rect("base", 9, 7, p["width"], p["height"])
    route = [(x+9,y+7) for x,y in p["route"]]
    s.poly("route", route, "tool", tag="polyline", **{"data-ridge-width":p["path_width"],
            "data-ridge-height":p["ridge_height"], "style":f"stroke-width:{p['path_width']}"})
    r = p["mark_radius"]
    for i,(label,shape,x,y) in enumerate(p["marks"]):
        x,y=x+9,y+7
        forms={
            "square":[(-r,-r),(r,-r),(r,r),(-r,r)],
            "triangle":[(0,-r),(r,r),(-r,r)],
            "diamond":[(0,-r),(r,0),(0,r),(-r,0)],
            "cross":[(-2,-r),(2,-r),(2,-2),(r,-2),(r,2),(2,2),(2,r),(-2,r),(-2,2),(-r,2),(-r,-2),(-2,-2)]
        }
        for prefix, (u,v) in (("landmark",(x,y)),("legend",(16,171+i*12))):
            if shape=="circle":
                s.circle(f"{prefix}-{i}",u,v,r)
            else:
                s.poly(f"{prefix}-{i}",[(u+j,v+k) for j,k in forms[shape]])
        s.text(27,172+i*12,label)
    s.text(85,172,"Synthetic desk teaching layout")
    s.text(85,182,"Ridge height and width are export parameters.")
    s.write(output)


BUILDERS = {
    "P003":(cabinet,"svg"),"P004":(pcb,"svg"),"P023":(slide,"svg"),"P025":(tray,"svg"),
    "P026":(tent,"svg"),"P030":(rover,"svg"),"P039":(count_scale,"csv"),"P040":(top_off,"csv"),
    "P045":(winder,"csv"),"P046":(photo_mount,"svg"),"P228":(arm,"svg"),"P229":(tactile,"svg")
}


def build(base):
    for key,(builder,ext) in BUILDERS.items():
        dest = base/key
        dest.mkdir(parents=True,exist_ok=True)
        normal = {name:data for name,data in MODELS[key].items() if name!="bad"}
        for title,model in (("trial",normal),("rejected",normal|MODELS[key]["bad"])):
            builder(model,dest/f"{title}.{ext}")


if __name__ == "__main__":
    build(HERE)
