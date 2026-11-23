"""Export dimensioned, true-size SVGs from the editable fixture dimensions."""
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
MODELS = json.loads((HERE / "designs.json").read_text())
SVG_NS = "http://www.w3.org/2000/svg"


def number(value):
    return f"{value:.5f}".rstrip("0").rstrip(".")


class Drawing:
    def __init__(self, product, revision):
        self.root = ET.Element("svg", xmlns=SVG_NS, version="1.1")
        ET.SubElement(self.root, "title").text = f"{product} {revision} shop drawing, millimetres"
        ET.SubElement(self.root, "style").text = (
            "text{font:4px sans-serif;fill:#162930} .heading{font:bold 5px sans-serif}"
            ".part,.bore,.guide,.limit{fill:none;stroke:#223842;stroke-width:.38}"
            ".bore{stroke:#00645c}.guide{stroke:#964314;stroke-dasharray:2 1}"
            ".limit{stroke:#a1384e;stroke-dasharray:1 1}.part{fill:#e6eef0;fill-opacity:.28}"
        )
        self.height = 5
        self.width = 0

    def view(self, key, heading, width, height):
        self.width = max(self.width, width + 24)
        self.group = ET.SubElement(self.root, "g", {
            "data-view": key, "transform": f"translate(12 {self.height})"
        })
        self.text(0, 4, heading, "heading")
        self.shape_group = ET.SubElement(self.group, "g", {"transform": "translate(0 10)"})
        self.height += height + 26

    def _geometry(self, tag, key, style, **attrs):
        return ET.SubElement(self.shape_group, tag, {"id": key, "class": style, **{
            name: number(value) if isinstance(value, (int, float)) else value
            for name, value in attrs.items()
        }})

    def rect(self, key, x, y, w, h, style="part"):
        self._geometry("rect", key, style, x=x, y=y, width=w, height=h)

    def circle(self, key, x, y, r, style="bore"):
        self._geometry("circle", key, style, cx=x, cy=y, r=r)

    def line(self, key, x1, y1, x2, y2, style="guide"):
        self._geometry("line", key, style, x1=x1, y1=y1, x2=x2, y2=y2)

    def poly(self, key, points, style="part"):
        self._geometry("polygon", key, style, points=" ".join(
            f"{number(x)},{number(y)}" for x, y in points
        ))

    def arc(self, key, cx, cy, r):
        self._geometry("path", key, "part",
                       d=f"M {cx-r} {cy} A {r} {r} 0 0 1 {cx} {cy-r}")

    def text(self, x, y, content, style=""):
        element = ET.SubElement(self.group, "text", {"x": number(x), "y": number(y)})
        if style:
            element.set("class", style)
        element.text = content

    def write(self, path):
        self.root.set("width", f"{self.width}mm")
        self.root.set("height", f"{self.height}mm")
        self.root.set("viewBox", f"0 0 {self.width} {self.height}")
        ET.indent(self.root, space="  ")
        path.write_text(ET.tostring(self.root, encoding="unicode") + "\n", encoding="utf-8")


def punch_cradle(s, p):
    length, depth = p["length"], p["depth"]
    fold, gap = depth / 2, p["apex_gap"]
    s.view("plan", "Cradle plan and interchangeable drill guide", max(length, 270), depth+13)
    s.rect("base", 0, 0, length, depth)

    s.rect("guide", 8, p["guide_y"]-9, length-16, 18)
    for i, x in enumerate((9, length-9)):
        s.rect(f"bridge-{i}", x-5, fold-36, 10, 72)
        for j, y in enumerate((fold-29, fold+29)):
            s.circle(f"bridge-mount-{i}-{j}", x, y, 2.2)
    for i, x in enumerate(p["fold_x"]):
        s.circle(f"awl-{i}", x, p["guide_y"], p["hole_d"]/2)
    s.line("gap-left", 0, fold-gap/2, length, fold-gap/2)
    s.line("gap-right", 0, fold+gap/2, length, fold+gap/2)
    s.text(0, depth+19, f"Base {length} × {depth}; awl holes Ø{p['hole_d']} at x = {p['fold_x']}")
    s.view("section", "End section with two rails and open awl exit", 270, 62)
    drop = p["v_drop"]
    for label, sign in (("left", -1), ("right", 1)):
        s.poly(f"rail-{label}", [(fold+sign*gap/2, 8+drop),
                                  (fold+sign*(gap/2+drop), 8),
                                  (fold+sign*(gap/2+drop), 19),
                                  (fold+sign*gap/2, 19+drop)])
    s.rect("guide-edge", p["guide_y"]-9, 0, 18, p["guide_t"])
    s.line("awl-axis", p["guide_y"], 0, p["guide_y"], 55)
    s.text(0, 67, f"Two 45° rails; apex slit {gap}; guide thickness {p['guide_t']}")


def nipping_press(s, p):
    w, d = p["width"], p["depth"]
    pw, pd = p["platen_width"], p["platen_depth"]
    left, top = (w-pw)/2, (d-pd)/2
    s.view("plan", "Plan of platen, screws and rotating handles", w, d+12)
    s.rect("frame", 0, 0, w, d)
    s.rect("working-platen", left, top, pw, pd)
    x_positions = (p["screw_inset"], w-p["screw_inset"])
    for i, x in enumerate(x_positions):
        s.circle(f"rod-bore-{i}", x, d/2, p["rod_d"]/2+.3)
        s.circle(f"handle-envelope-{i}", x, d/2, p["knob_radius"], "limit")
    s.text(0, d+18, f"Frame {w} × {d}; flat caul face {pw} × {pd}; handles Ø{2*p['knob_radius']}")
    for i, gap in enumerate(p["clamp_gaps"]):
        t, sleeve, thread = p["platen_t"], p["sleeve_t"], p["screw_thread"]
        z = 52
        s.view(f"gap-{i}", f"Screw section at {gap} mm opening", w, z+sleeve+gap+2*t+10)
        for j, x in enumerate(x_positions):
            s.rect(f"sleeve-{i}-{j}", x-10, z, 20, sleeve)
            s.rect(f"thread-{i}-{j}", x-p["rod_d"]/2, z+sleeve+gap+t-thread, p["rod_d"], thread, "guide")
        s.rect(f"upper-{i}", left, z+sleeve, pw, t)
        s.rect(f"book-{i}", left+5, z+sleeve+t, pw-10, gap, "guide")
        s.rect(f"lower-{i}", left, z+sleeve+t+gap, pw, t)
        s.text(0, z+sleeve+gap+2*t+16, f"Cauls {t} thick; threaded collar {sleeve}; usable thread {thread}")


def sewing_frame(s, p):
    w, d, h = p["width"], p["depth"], p["height"]
    s.view("plan", "Base plan and slotted rail blank", w, d+62)
    s.rect("base", 0, 0, w, d)
    sw = p["side"]
    for i, x in enumerate((10, w-10-sw)):
        s.rect(f"post-foot-{i}", x, d/2-sw/2, sw, sw)
        s.circle(f"post-bolt-{i}", x+sw/2, d/2, 3.3)
    s.rect("rail-blank", 10, d+15, w-20, 30)
    s.rect("anchor-slot", p["slot_start"], d+30-p["slot_width"]/2,
           p["slot_end"]-p["slot_start"], p["slot_width"], "bore")
    s.text(0, d+65, f"Base {w} × {d}; anchor slot {p['slot_end']-p['slot_start']} × {p['slot_width']}")
    for i, cords in enumerate(p["cord_sets"]):
        s.view(f"cords-{i}", f"Elevation of cord setup {i+1}", w, h+28)
        s.rect(f"plinth-{i}", 0, h, w, 18)
        for j, x in enumerate((10, w-10-sw)):
            s.rect(f"post-{i}-{j}", x, 0, sw, h)
        s.rect(f"top-bar-{i}", 10, 0, w-20, 30)
        left = (w-p["book_width"])/2
        s.rect(f"book-{i}", left, h-48, p["book_width"], 48, "limit")
        for j, x in enumerate(cords):
            s.circle(f"key-{i}-{j}", x, 15, p["key_d"]/2)
            s.circle(f"washer-{i}-{j}", x, 15, p["washer_d"]/2, "limit")
            s.line(f"cord-{i}-{j}", x, 30, x, h)
        s.text(0, h+33, f"Clear height below bar {h-30}; book width {p['book_width']}; anchor x = {cords}")


def spine_press(s, p):
    length, depth = p["jaw_len"], p["jaw_depth"]
    s.view("side", "Fixed jaw elevation and clear tool stroke", length, depth+40)
    spine = 26-p["spine_exposure"]
    s.rect("jaw-face", 0, 26, length, depth)
    s.rect("spine", (length-p["book_len"])/2, spine, p["book_len"], p["spine_exposure"], "guide")
    s.line("tool-envelope", (length-p["book_len"])/2, spine+p["tool_reach"],
           (length+p["book_len"])/2, spine+p["tool_reach"], "limit")
    for i, x in enumerate((p["rod_inset"], length-p["rod_inset"])):
        s.circle(f"rod-{i}", x, 26+depth/2, p["rod_d"]/2+.4)
    s.text(0, depth+45, f"Jaw {length} × {depth}; shaft holes Ø{p['rod_d']+.8}; book length {p['book_len']}")
    s.view("section", "Cross-section of opposing jaws and exposed spine", length, depth+38)
    t, g = p["jaw_t"], p["block_t"]
    s.poly("fixed-jaw", [(0, 26), (t, 26), (t, 26+depth), (0, 26+depth)])
    s.poly("travel-jaw", [(t+g, 26), (2*t+g, 26), (2*t+g, 26+depth), (t+g, 26+depth)])
    s.rect("block", t, spine, g, depth/1.5)
    s.text(0, depth+43, f"Jaw thickness {t}; book block {g}; spine projection {p['spine_exposure']}")


def fan_clamp(s, p):
    width, px, pz = p["base_width"], p["pivot_x"], p["pivot_z"]
    bottom, half = p["rocker_bottom"], p["rocker_half_width"]
    gap, jaw, overlap = p["stack_width"], p["jaw_t"], p["jaw_overlap"]
    offset = p["stack_height"]+28
    components = {
        "rocker": [(-half, -bottom), (half, -bottom), (half, -bottom+12), (-half, -bottom+12)],
        "carrier": [(-24, -bottom+12), (24, -bottom+12), (24, 0), (-24, 0)],
        "stack": [(-gap/2, 0), (gap/2, 0), (gap/2, p["stack_height"]), (-gap/2, p["stack_height"])],
        "near-jaw": [(-gap/2-jaw, 0), (-gap/2, 0), (-gap/2, overlap), (-gap/2-jaw, overlap)],
        "far-jaw": [(gap/2, 0), (gap/2+jaw, 0), (gap/2+jaw, overlap), (gap/2, overlap)]
    }
    for i, angle in enumerate((-p["tilt"], 0, p["tilt"])):
        angle_r = math.radians(angle)
        ground = offset+pz
        s.view(f"tilt-{i}", f"End assembly at {angle:+}°", width, ground+28)
        s.rect(f"base-{i}", 0, ground, width, 16)
        s.circle(f"pivot-{i}", px, offset, p["pivot_d"]/2)
        if i != 1:
            sign = 1 if angle < 0 else -1
            tip_x = px+sign*half*math.cos(angle_r)+bottom*math.sin(angle_r)
            tip_y = offset-(sign*half*math.sin(angle_r)-bottom*math.cos(angle_r))
            s.circle(f"stop-{i}", tip_x, tip_y+p["stop_pin_d"]/2, p["stop_pin_d"]/2)
        for key, points in components.items():
            s.poly(f"{key}-{i}", [
                (px+x*math.cos(angle_r)-z*math.sin(angle_r),
                 offset-x*math.sin(angle_r)-z*math.cos(angle_r))
                for x, z in points
            ])
        s.text(0, ground+33, f"Pivot axis {pz} above deck; stack {gap} × {p['stack_height']}; free leaves {p['stack_height']-overlap}")
    s.view("end-plate", "End plate blank and drill coordinates", width, pz+33)
    s.rect("end-cheek", px-half-12, 0, 2*half+24, pz+14)
    s.circle("pivot-bore", px, 8, p["pivot_d"]/2+.2)
    for i, sign in enumerate((1, -1)):
        rad = math.radians(-sign*p["tilt"])
        x = px+sign*half*math.cos(rad)+bottom*math.sin(rad)
        y = 8-sign*half*math.sin(rad)+bottom*math.cos(rad)+p["stop_pin_d"]/2
        s.circle(f"drill-stop-{i}", x, y, p["stop_pin_d"]/2)
    s.text(0, pz+39, f"Plate thickness {p['end_plate_t']}; pivot Ø{p['pivot_d']+.4}; stop pins Ø{p['stop_pin_d']}")


def punch_fence(s, p):
    w, d = p["deck_width"], p["deck_depth"]
    host_w, host_d = p["press_base_width"], p["press_base_depth"]
    host_x, host_y = (w-host_w)/2, (d-host_d)/2
    px, py = p["punch_x"], p["punch_y"]
    for i, offset in enumerate(p["offsets"]):
        s.view(f"offset-{i}", f"Plan with {offset} mm hole offset", w+85, d+15)
        s.rect(f"deck-{i}", 0, 0, w, d)
        s.rect(f"host-{i}", host_x, host_y, host_w, host_d, "limit")
        rail = p["edge_rail"]
        s.rect(f"left-rail-{i}", 8, host_y, rail, host_d)
        s.rect(f"right-rail-{i}", w-8-rail, host_y, rail, host_d)
        for j, x in enumerate(p["fence_mount_x"]):
            s.rect(f"slot-{i}-{j}", x-3, py, 6, 25, "bore")
            s.circle(f"fastener-{i}-{j}", x, py+offset+4, 2.5)
        s.rect(f"fence-{i}", 10, py+offset, w-20, 10)
        s.rect(f"strip-{i}", 0, py+offset-p["strip_width"], w, p["strip_width"], "guide")
        s.circle(f"punch-{i}", px, py, 2)
        s.line(f"visibility-{i}", px-p["sight_width"]/2, py, px+p["sight_width"]/2, py)
        s.text(0, d+20, f"Deck {w} × {d}; synthetic host base {host_w} × {host_d}; strip {p['strip_width']} wide")
    s.view("shoe", "Section of lift-off shoe through assumed host lip", w, 44)
    s.rect("shoe-deck", 0, 30, w, 12)
    s.rect("base-lip", 32, 30-p["base_lip"], 24, p["base_lip"], "guide")
    s.poly("clamp-shoe", [(16, 30), (16, 17), (44, 17),
                         (44, 30-p["shoe_throat"]), (22, 30-p["shoe_throat"]), (22, 30)])
    s.circle("shoe-bolt", 19, 21, 2.7)
    s.text(0, 49, f"Lip {p['base_lip']}; shoe throat {p['shoe_throat']}; two opposed shoes")


def dye_roller(s, p):
    tray, depth = p["tray_width"], p["tray_depth"]
    radius, az = p["roller_d"]/2, p["axle_z"]
    floor = 65
    for i, gap in enumerate(p["guide_gaps"]):
        s.view(f"wet-{i}", f"Roller section at {gap} mm edge slot", 260, floor+15)
        s.poly(f"tray-{i}", [(0, floor-depth), (3, floor-depth), (3, floor),
                             (tray-3, floor), (tray-3, floor-depth), (tray, floor-depth),
                             (tray, floor+3), (0, floor+3)])
        s.line(f"dye-{i}", 3, floor-p["dye_height"], tray-3, floor-p["dye_height"])
        s.circle(f"roller-{i}", tray/2, floor-az, radius, "part")
        s.circle(f"axle-{i}", tray/2, floor-az, p["axle_d"]/2)
        s.circle(f"lifted-{i}", tray/2, floor-az-p["lift"], radius, "limit")
        s.text(0, floor+20, f"Roller Ø{p['roller_d']}; bath fill {p['dye_height']}; cleaning lift {p['lift']}")
    s.view("axle", "Face width, open bearing slots and top gap guide", 260, 95)
    face = p["roller_face_width"]
    s.rect("face", 30, 25, face, 36)
    s.rect("shaft", 15, 43-p["axle_d"]/2, face+30, p["axle_d"])
    for i in (0, 1):
        x = (22, 38+face)[i]
        s.line(f"slot-edge-{i}-left", x-p["slot_width"]/2, 12, x-p["slot_width"]/2, 43)
        s.line(f"slot-edge-{i}-right", x+p["slot_width"]/2, 12, x+p["slot_width"]/2, 43)
    for i, gap in enumerate(p["guide_gaps"]):
        x = 30 + i*30
        s.rect(f"edge-gap-{i}", x, 77, gap, 12, "guide")
    s.text(0, 99, f"Roller face {face}; open slots {p['slot_width']}; replaceable guide gaps {p['guide_gaps']}")


def blank_sander(s, p):
    track, shoe, blank = p["track_len"], p["shoe_len"], p["blank_len"]
    offset = (shoe-blank)/2
    for i, setting in enumerate(p["settings"]):
        s.view(f"set-{i}", f"Carrier plan at {setting} mm finished thickness", 260, 100)
        s.rect(f"track-{i}", 0, 0, track, p["track_width"])
        height = p["shoe_width"]
        s.rect(f"abrasive-{i}", p["abrasive_start"], height+3,
               p["abrasive_end"]-p["abrasive_start"], 4)
        s.rect(f"start-stop-{i}", p["stroke_start"]-5, 4, 5, 20)
        s.rect(f"end-stop-{i}", p["stroke_end"]+shoe, 4, 5, 20)
        for j, start in enumerate((p["stroke_start"], p["stroke_end"])):
            s.rect(f"shoe-{i}-{j}", start, 1, shoe, height, "guide")
            s.rect(f"blank-{i}-{j}", start+offset, height+3-setting, blank, setting, "limit")
        s.rect(f"sanding-fence-{i}", 0, height+7, track, 13)
        s.text(0, 69, f"Track {track} × {p['track_width']}; shoe {shoe} × {height}; blank length {blank}")
        s.text(0, 75, f"Carrier backing shim sets {setting}; abrasive span x={p['abrasive_start']}–{p['abrasive_end']}")
        s.rect(f"stock-section-{i}", 172, 8, p["blank_initial_t"], p["blank_height"])
        s.rect(f"finish-section-{i}", 172, 8, setting, p["blank_height"], "limit")
        s.rect(f"hold-down-{i}", 167, 5, p["blank_initial_t"]+10, 3)
        s.text(156, 29, f"Initial blank {p['blank_initial_t']} × {p['blank_height']}")


def radius_template(s, p):
    body, fence, coupon = p["body"], p["fence_t"], p["minimum_panel"]
    for i, rad in enumerate(p["radii"]):
        s.view(f"radius-{i}", f"R{rad} template in top view, fences under plate", 255, body+20)
        s.poly(f"rough-panel-{i}", [(0, 0), (coupon, 0), (coupon, body), (0, body)], "guide")
        s.arc(f"guide-arc-{i}", rad, rad, rad)
        s.line(f"edge-h-{i}", rad, 0, body, 0, "part")
        s.line(f"edge-v-{i}", 0, rad, 0, body, "part")
        s.line(f"edge-back-h-{i}", 0, body, body, body, "part")
        s.line(f"edge-back-v-{i}", body, 0, body, body, "part")
        s.rect(f"fence-x-{i}", -fence, rad+3, fence, body-rad-3)
        s.rect(f"fence-y-{i}", rad+3, -fence, body-rad-3, fence)
        for j, q in enumerate(p["pad_locations"]):
            s.circle(f"clamp-pad-{i}-{j}", q, coupon+p["pad_r"]+10, p["pad_r"], "limit")
        s.circle(f"bearing-{i}", 157, 14, p["bearing_d"]/2, "guide")
        s.circle(f"cutter-{i}", 190, 14, p["cutter_d"]/2, "limit")
        s.text(145, 29, "Assumed bearing and cutter")
        s.text(0, body+25, f"Plate envelope {body} × {body}; fence width {fence}; minimum coupon width {coupon}")


def dividing_disc(s, p):
    radius = p["disc_r"]
    s.view("disc", "Marking face with independent indexed rings", 250, 2*radius+17)
    s.circle("blank", radius, radius, radius, "part")
    s.circle("receptacle", radius, radius, p["receptacle_d"]/2)
    s.circle("key-seat", radius+p["key_x"], radius, p["key_r"]+.2)
    for group, (ring, count) in enumerate(zip(p["ring_radii"], p["divisions"])):
        s.circle(f"reference-{group}", radius, radius, ring, "guide")
        for i in range(count):
            theta = 2*math.pi*i/count-math.pi/2
            s.line(f"tick-{group}-{i}", radius+(ring-4)*math.cos(theta),
                   radius+(ring-4)*math.sin(theta), radius+(ring+4)*math.cos(theta),
                   radius+(ring+4)*math.sin(theta), "part")
    s.text(0, 2*radius+22, f"Blank Ø{2*radius}; rings {p['ring_radii']}; evenly spaced counts {p['divisions']}")
    s.view("insert", "Removable centering insert and key", 250, 70)
    s.rect("insert", 12, 12, p["key_x"]+34, 36)
    s.circle("boss", 28, 30, p["boss_d"]/2)
    s.circle("key", 28+p["key_x"], 30, p["key_r"])
    s.text(0, 61, f"Boss Ø{p['boss_d']} fits Ø{p['receptacle_d']}; key offset {p['key_x']}")


def fringe_twister(s, p):
    axles = p["axles"]
    crank = p["crank_r"]
    link = p["link_len"]
    for i, degrees in enumerate((0, 90, 180, 270)):
        s.view(f"phase-{i}", f"Projected drive plate at crank phase {degrees}°", 240, p["plate_height"]+13)
        s.rect(f"drive-plate-{i}", 0, 0, p["plate_width"], p["plate_height"])
        for j, (x, y) in enumerate(axles):
            s.circle(f"shaft-{i}-{j}", x, y, p["axle_d"]/2)
            s.circle(f"clip-{i}-{j}", x, y, p["clip_r"], "limit")
        for j, phase in enumerate((0, 90)):
            ang = math.radians(degrees+phase)
            x, y = axles[0][0]+crank*math.cos(ang), axles[0][1]+crank*math.sin(ang)
            rx, ry = axles[1][0]+crank*math.cos(ang), axles[1][1]+crank*math.sin(ang)
            s.line(f"crank-l-{i}-{j}", *axles[0], x, y, "part")
            s.line(f"crank-r-{i}-{j}", *axles[1], rx, ry, "part")
            s.rect(f"link-{i}-{j}", x-6, y-p["link_width"]/2, link+12,
                   p["link_width"], ("part", "guide")[j])
            s.circle(f"link-l-{i}-{j}", x, y, p["joint_d"]/2)
            s.circle(f"link-r-{i}-{j}", x+link, y, p["joint_d"]/2)
        s.text(0, p["plate_height"]+18, f"Crank throw {crank}; connecting rod hole pitch {link}; disks Ø{2*p['clip_r']}")
    s.view("layers", "Stack along shafts through link planes", 250, 60)
    s.rect("side-plate", 15, 22, 8, 26)
    for i, layer in enumerate(p["link_layers"]):
        s.rect(f"layer-{i}", 23+layer, 20, p["link_t"], 30, "guide")
    s.rect("shaft-side", 4, 35-p["axle_d"]/2, 54, p["axle_d"])
    s.text(0, 63, f"Link planes at {p['link_layers']} from plate; links {p['link_t']} thick")


def warping_board(s, p):
    w, h = p["width"], p["height"]
    for i, indexes in enumerate(((0, 3), (1, 2))):
        s.view(f"route-{i}", f"Frame plan and removable peg recipe {i+1}", w, h+13)
        rw, sw = p["rail_w"], p["side_w"]
        for j, y in enumerate((0, h-rw)):
            s.rect(f"rail-{i}-{j}", 0, y, w, rw)
        for j, x in enumerate((0, w-sw)):
            s.rect(f"stile-{i}-{j}", x, 0, sw, h)
        for j, y in enumerate(p["peg_rows"]):
            for k, x in enumerate(p["joint_x"]):
                s.circle(f"bolt-{i}-{j}-{k}", x, y, p["bolt_d"]/2)
            for k, x in enumerate(p["peg_x"]):
                s.circle(f"peg-{i}-{j}-{k}", x, y, p["peg_d"]/2,
                         "part" if k in indexes else "bore")
        r = p["peg_d"]/2
        x1, x2 = (p["peg_x"][k] for k in indexes)
        y1, y2 = p["peg_rows"]
        s.line(f"yarn-top-{i}", x1, y1-r, x2, y1-r)
        s.line(f"yarn-bottom-{i}", x1, y2+r, x2, y2+r)
        s.line(f"yarn-left-{i}", x1-r, y1, x1-r, y2)
        s.line(f"yarn-right-{i}", x2+r, y1, x2+r, y2)
        path = (f"M {x1-r} {y1} A {r} {r} 0 0 1 {x1} {y1-r} "
                f"M {x2} {y1-r} A {r} {r} 0 0 1 {x2+r} {y1} "
                f"M {x2+r} {y2} A {r} {r} 0 0 1 {x2} {y2+r} "
                f"M {x1} {y2+r} A {r} {r} 0 0 1 {x1-r} {y2}")
        s._geometry("path", f"yarn-wrap-{i}", "guide", d=path)
        s.text(0, h+18, f"Rail {rw} wide; stile {sw} wide; removable Ø{p['peg_d']} pegs, Ø{p['bolt_d']} bolts")


BUILDERS = {
    "P232": punch_cradle, "P233": nipping_press, "P234": sewing_frame,
    "P235": spine_press, "P236": fan_clamp, "P240": punch_fence,
    "P241": dye_roller, "P246": blank_sander, "P251": radius_template,
    "P261": dividing_disc, "P263": fringe_twister, "P264": warping_board,
}


def build(directory):
    for product, builder in BUILDERS.items():
        destination = directory / product
        destination.mkdir(parents=True, exist_ok=True)
        nominal = {k: v for k, v in MODELS[product].items() if k != "rejected"}
        for revision, model in (("trial", nominal), ("rejected", nominal | MODELS[product]["rejected"])):
            sheet = Drawing(product, revision)
            builder(sheet, model)
            sheet.write(destination / f"{revision}.svg")


if __name__ == "__main__":
    build(HERE)
