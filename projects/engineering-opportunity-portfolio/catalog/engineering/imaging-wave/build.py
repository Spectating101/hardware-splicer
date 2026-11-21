"""Export study coupons in full-size SVG and indexed motion as CSV."""
import csv
import json
import math
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent
PARAMS = ROOT / "parameters.json"


def num(value):
    return f"{value:.6f}".rstrip("0").rstrip(".") or "0"


class Sheet:
    def __init__(self, product, revision, width, height):
        self.root = ET.Element("svg", {"xmlns": "http://www.w3.org/2000/svg",
                                      "width": f"{num(width)}mm", "height": f"{num(height)}mm",
                                      "viewBox": f"0 0 {num(width)} {num(height)}"})
        ET.SubElement(self.root, "title").text = f"{product} {revision} | full-size study patterns"
        self.mark("rect", "scale", "engrave", x=8, y=8, width=20, height=10)
        self.label("scale-label", "20 × 10 mm", 9, 14, 2.6)

    def mark(self, tag, key, operation, **attrs):
        values = {k.replace("_", "-"): num(v) if isinstance(v, (int, float)) else v
                  for k, v in attrs.items()}
        return ET.SubElement(self.root, tag, {
            "id": key, "data-operation": operation, "fill": "none",
            "stroke": {"cut": "#b82b28", "engrave": "#333333", "reference": "#2475a9"}[operation],
            "stroke-width": "0.17", **values})

    def rect(self, key, x, y, width, height, operation="cut"):
        return self.mark("rect", key, operation, x=x, y=y, width=width, height=height)

    def centered(self, key, x, y, width, height, operation="cut"):
        return self.rect(key, x-width/2, y-height/2, width, height, operation)

    def circle(self, key, cx, cy, r, operation="cut"):
        return self.mark("circle", key, operation, cx=cx, cy=cy, r=r)

    def line(self, key, x1, y1, x2, y2, operation="reference"):
        return self.mark("line", key, operation, x1=x1, y1=y1, x2=x2, y2=y2)

    def poly(self, key, points, operation="cut"):
        coords = " ".join(f"{num(x)},{num(y)}" for x, y in points)
        return self.mark("polygon", key, operation, points=coords)

    def label(self, key, label, x, y, size=3):
        node = self.mark("text", key, "engrave", x=x, y=y, font_size=size,
                         fill="#333333", stroke="none", font_family="sans-serif")
        node.text = label

    def write(self, path):
        ET.indent(self.root, "  ")
        ET.ElementTree(self.root).write(path, encoding="utf-8", xml_declaration=True)


def film(product, revision, p, folder):
    w, h = p["body"]
    gap = p["gap"]
    s = Sheet(product, revision, 140, 246)
    for key, y in (("base", 24), ("lid", 103)):
        s.rect(f"{key}-blank", 14, y, w, h)
        s.centered(f"{key}-window", 14+w/2, y+h/2, *p["window"])
        for i, x in enumerate((22, 118)):
            for j, yy in enumerate((y+8, y+h-8)):
                s.circle(f"{key}-register-{i}-{j}", x, yy, 1.6)
    s.rect("guide-upper", 14, 184, w, 7)
    s.rect("guide-lower", 14, 184 + 7 + gap, w, 7)
    return s


def indexed(product, revision, p, folder):
    r = p["dial_r"]
    cx = cy = r+25
    s = Sheet(product, revision, 2*cx, 2*cy)
    s.circle("dial", cx, cy, r)
    s.circle("shaft-mark", cx, cy, 3)
    rows = []
    for index in range(p["captures"] + 1):
        exact_steps = index * p["steps_per_rev"] / p["captures"]
        step = round(exact_steps) if p["absolute"] else index * round(p["steps_per_rev"]/p["captures"])
        rows.append((index, step, p["dwell_ms"], int(index < p["captures"])))
        if index < p["captures"]:
            angle = math.tau * step/p["steps_per_rev"]
            x, y = math.sin(angle), -math.cos(angle)
            s.line(f"tick-{index}", cx + (r-5)*x, cy + (r-5)*y,
                   cx + (r-1)*x, cy + (r-1)*y, "engrave")
    with (folder / f"{revision}-capture.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(("index", "position_steps", "hold_before_capture_ms", "capture"))
        w.writerows(rows)
    return s


def deck(product, revision, p, folder):
    r = p["deck_diameter"]/2
    x, y = 10+r, 25+r
    s = Sheet(product, revision, 2*x, 2*r+100)
    s.circle("deck", x, y, r)
    s.circle("safe-cog-zone", x, y, p["load_radius"], "engrave")
    for i, (sx, sy) in enumerate(((-1,-1), (1,-1), (1,1), (-1,1))):
        s.circle(f"host-foot-{i}", x+sx*p["base_half_spacing"],
                 y+sy*p["base_half_spacing"], 3, "reference")
    for prefix, yy in (("deck", y), ("hub", 2*r+60)):
        s.circle(f"{prefix}-pilot", x, yy, p["holes_mm"][0]/2)
        s.circle(f"{prefix}-key", x+p["offset_pin_mm"], yy, p["holes_mm"][1]/2)
    s.centered("hub-blank", x, 2*r+60, 64, 38)
    return s


def photo_box(product, revision, p, folder):
    w, d = p["base"]
    depth, h = p["nominal_side_depth"], p["height"]
    s = Sheet(product, revision, w+24, 3*h+2*d+126)
    s.rect("floor", 12, 24, w, d)
    s.rect("back", 12, d+34, w, h)
    panel_width = (depth-p["hinge_gap"])/2 if p["split"] else depth
    for side, y in enumerate((d+h+44, d+2*h+54)):
        s.rect(f"side-{side}-inner", 12, y, panel_width, h)
        if p["split"]:
            s.rect(f"side-{side}-outer", 12+panel_width+p["hinge_gap"],
                   y, panel_width, h)
        s.line(f"hinge-offset-{side}", 12+p["hinge_offset"], y+3,
               12+p["hinge_offset"], y+h-3, "engrave")
    s.rect("top-diffuser", 12, d+3*h+64, w, d)
    return s


def portal(product, revision, p, folder):
    w, depth, span = p["width"], p["depth"], p["span_mm"]
    s = Sheet(product, revision, span+60, 180)
    s.rect("lintel-blank", 12, 28, span+36, w)
    for i, x in enumerate((30, 30+span)):
        s.line(f"post-center-{i}", x, 23, x, 65)
        s.centered(f"bearing-pad-{i}", x, 42, 18, w, "reference")
    s.rect("section-gauge", 14, 86, w, depth)
    s.rect("stock-depth-check", 14+w+18, 86, depth, w)
    return s


def hood(product, revision, p, folder):
    w, h = p["anchor"]
    d = p["depth"]
    s = Sheet(product, revision, 252, 268)
    s.centered("screen-reference", 80, 133, *p["host_active_mm"], "reference")
    s.centered("body-reference", 80, 133, *p["host_body_mm"], "reference")
    s.centered("frame-opening", 80, 133, w, h)
    s.centered("frame-blank", 80, 133, w+12, h+12)
    s.rect("top-panel", 14, 24, w, d)
    for i, x in enumerate((14, 23+d)):
        s.rect(f"side-panel-{i}", x, 191, d, h)
    return s


def saddle(product, revision, p, folder):
    s = Sheet(product, revision, 182, 146)
    cx, rod_y = 55, 118
    separation = p["rod_spacing_mm"]
    s.rect("plate", 9, 55, 92, 77)
    for i, x in enumerate((cx-separation/2, cx+separation/2)):
        s.circle(f"rod-{i}", x, rod_y, (p["rod_diameter_mm"]+0.6)/2)
    top, low = rod_y-p["apex_high"], rod_y-p["apex_low"]
    s.rect("adjustment-slot", cx-3.4, top-3.4, 6.8, low-top+6.8)
    s.circle("optical-axis", cx, rod_y-p["axis_above_rod_centers_mm"], 1, "reference")
    s.poly("saddle-blank", [(111,58), (138,85), (165,58), (165,104), (111,104)])
    s.centered("pad-cut-stock", 136, 123, 38, 12)
    return s


def matte_box(product, revision, p, folder):
    s = Sheet(product, revision, 210, 410)
    for key, y, perimeter, opening in (
        ("rear", 65, (116,88), (58,46)),
        ("filter", 174, (165,112), (125,82)),
        ("front", 292, (157,103), p["front_aperture"]),
    ):
        s.centered(f"{key}-blank", 105, y, *perimeter)
        s.centered(f"{key}-aperture", 105, y, *opening)
        if key == "filter":
            s.centered("filter-envelope", 105, y, *p["filter_mm"], "reference")
    for n, z in enumerate(p["positions_mm"]):
        s.line(f"plane-{n}", 25+z, 360, 25+z, 379)
    s.line("pupil-datum", 25, 360, 25, 379)
    s.rect("top-flag", 90, 361, 102, 38)
    s.line("flag-hinge", 90, 366, 192, 366, "engrave")
    return s


def grid(product, revision, p, folder):
    s = Sheet(product, revision, 120, 135)
    w, h = p["clear_mm"]
    cx, cy = 61, 56
    s.centered("cell-blank", cx, cy, w+8, h+8)
    s.centered("head-reference", cx, cy, w, h, "reference")
    r = p["cell_across_flats"]/math.sqrt(3)
    pitch = p["cell_across_flats"] + p["web"]
    nx, ny = p["grid"]
    for i in range(ny):
        for j in range(nx):
            x = cx+(j-(nx-1)/2+(i%2)/2-0.25)*pitch
            y = cy+(i-(ny-1)/2)*pitch*math.sqrt(3)/2
            points = [(x+r*math.sin(k*math.tau/6), y+r*math.cos(k*math.tau/6))
                      for k in range(6)]
            s.poly(f"cell-{i}-{j}", points)
    s.rect("depth-gauge", 13, 94, 20, p["sheet_mm"]*p["layers"])
    s.label("layers", f'{p["layers"]} plates × {p["sheet_mm"]} mm', 46, 102)
    return s


def slate(product, revision, p, folder):
    w, h = p["body_mm"]
    jaw = p["jaw_mm"]
    origin_x, origin_y = 12, 27
    s = Sheet(product, revision, 158, 171)
    s.rect("slate-board", origin_x, origin_y, w, h)
    s.rect("fixed-jaw", origin_x, origin_y, w, jaw, "engrave")
    s.rect("swing-jaw", origin_x, 127, w, jaw)
    for key, y in (("fixed", origin_y), ("swing", 127)):
        s.circle(f"{key}-pivot", origin_x+p["pivot_mm"], y+jaw/2, p["hole_d_mm"]/2)
    s.circle("pivot-axis", origin_x+p["pivot_mm"], 157, 0.5, "reference")
    s.line("jaw-gap-gauge", 33, 157, 33+p["jaw_clearance"], 157)
    for i, label in enumerate(p["reading_samples"]):
        x = origin_x+5+(i%2)*62
        y = origin_y+26+(i//2)*32
        s.label(f"label-{i}", label, x, y, p["label_height_mm"])
        s.rect(f"write-{i}", x, y+2, 57, p["write_height_mm"], "engrave")
    return s


def prompter(product, revision, p, folder):
    phone_l, phone_w = p["phone_mm"]
    s = Sheet(product, revision, 218, 397)
    s.centered("glass-blank", 109, 88, p["glass_w"], p["glass_len"])
    s.centered("phone-tray", 109, 212, phone_l+8, phone_w+8)
    allowance = 2*p["case_allowance_mm"]
    s.centered("phone-pocket", 109, 212, phone_l+allowance, phone_w+allowance)
    s.centered("active-source", 109, 212, *p["screen_mm"], "reference")
    x, y = 86, 319
    glass_half_span = p["glass_len"]/(2*math.sqrt(2))
    s.line("pupil-plane", x-p["camera_offset_mm"], y-10, x-p["camera_offset_mm"], y+10)
    s.line("optical-datum", x, y, 196, y)
    s.line("glass-trace", x-glass_half_span, y+glass_half_span, x+glass_half_span, y-glass_half_span)
    s.line("phone-trace", x-32, y+p["phone_drop_mm"], x+32, y+p["phone_drop_mm"])
    s.label("scale-section", "Optical section through display center", 12, 387, 2.8)
    return s


DESIGNS = {
    "P008": film, "P017": indexed, "P018": deck, "P019": photo_box, "P020": portal,
    "P195": hood, "P196": saddle, "P199": matte_box, "P200": grid, "P203": slate, "P205": prompter,
}


def export(target, parameter_path=PARAMS):
    params = json.loads(parameter_path.read_text(encoding="utf-8"))
    if params.keys() != DESIGNS.keys():
        raise ValueError("Parameters must have one entry per catalog design")
    for product, design in DESIGNS.items():
        config = params[product]
        folder = target / product
        folder.mkdir(parents=True, exist_ok=True)
        common = {key: value for key, value in config.items() if key not in ("baseline", "revised")}
        for revision in ("baseline", "revised"):
            sheet = design(product, revision, common | config[revision], folder)
            sheet.write(folder / f"{revision}.svg")


if __name__ == "__main__":
    export(Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "artifacts")
