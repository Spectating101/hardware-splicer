"""Read the neutral exports and replay their engineering acceptance checks."""
import argparse
import json
import math
import tempfile
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
MM = "http://www.w3.org/2000/svg"
TOL = 0.00015


class Sheet:
    def __init__(self, path):
        root = ET.parse(path).getroot()
        self.elements = {}
        for node in root.iter():
            if "id" in node.attrib:
                key = node.get("id")
                if key in self.elements:
                    raise ValueError(f"{path}: duplicate entity {key}")
                self.elements[key] = node
        dims = [float(root.get(key).removesuffix("mm")) for key in ("width", "height")]
        if root.tag != f"{{{MM}}}svg" or root.get("viewBox").split()[:2] != ["0", "0"]:
            raise ValueError(f"{path}: invalid neutral sheet")
        if not all(root.get(key).endswith("mm") for key in ("width", "height")):
            raise ValueError(f"{path}: missing millimetre units")
        if dims != list(map(float, root.get("viewBox").split()[2:])):
            raise ValueError(f"{path}: drawing is not one user unit per millimetre")

    def _attrs(self, name, attrs):
        return tuple(float(self.elements[name].attrib[key]) for key in attrs.split())

    def circle(self, name):
        return self._attrs(name, "cx cy r")

    def rect(self, name):
        return self._attrs(name, "x y width height")

    def line(self, name):
        values = self._attrs(name, "x1 y1 x2 y2")
        return values[:2], values[2:]

    def poly(self, name):
        return [tuple(map(float, pair.split(",")))
                for pair in self.elements[name].attrib["points"].split()]

    def path(self, name):
        return self.elements[name].attrib["d"].split()

    def indices(self, prefix):
        return sorted(key for key in self.elements if key.startswith(prefix))


def overlap(a0, a1, b0, b1):
    return min(a1, b1) - max(a0, b0)


def close(a, b):
    return abs(a-b) <= TOL


def check(value, accept):
    if isinstance(value, float):
        value = round(value, 5)
    return {"measured": value, "pass": bool(accept)}


def punch_cradle(s):
    (_, left), _ = s.line("gap-left")
    (_, right), _ = s.line("gap-right")
    holes = [s.circle(key) for key in s.indices("awl-") if key != "awl-axis"]
    clearance = min(min(y-left, right-y)-r for _, y, r in holes)
    pitch_error = max(abs(b[0]-a[0]-37.5) for a, b in zip(holes, holes[1:]))
    (axis_x, _), _ = s.line("awl-axis")
    feet = [s.poly(f"rail-{side}")[:2] for side in ("left", "right")]
    rail_error = max(abs(abs(x1-x2)-abs(y1-y2)) for ((x1, y1), (x2, y2)) in feet)
    return {
        "awl exit radial clearance mm": check(clearance, clearance >= .5),
        "station pitch maximum error mm": check(pitch_error, close(pitch_error, 0)),
        "section axis and 45 degree rails": check(rail_error, close(rail_error, 0) and
                                                  all(close(y, axis_x) for _, y, _ in holes)),
    }


def nipping_press(s):
    left, _, width, _ = s.rect("working-platen")
    x1, _, r1 = s.circle("handle-envelope-0")
    x2, _, r2 = s.circle("handle-envelope-1")
    clearance = min(left-x1-r1, x2-r2-left-width)
    engagement, overlaps = [], []
    for i in (0, 1):
        _, uy, _, uh = s.rect(f"upper-{i}")
        _, ly, _, _ = s.rect(f"lower-{i}")
        _, by, _, gap = s.rect(f"book-{i}")
        overlaps.extend((by-(uy+uh), ly-(by+gap)))
        for j in (0, 1):
            sx, sy, sw, sh = s.rect(f"sleeve-{i}-{j}")
            tx, ty, tw, th = s.rect(f"thread-{i}-{j}")
            if not close(sx+sw/2, tx+tw/2):
                raise ValueError("Thread axis misses collar")
            engagement.append(overlap(sy, sy+sh, ty, ty+th))
    return {
        "hand knob sweep clear of flat platen mm": check(clearance, clearance >= 4),
        "minimum engaged thread over opening range mm": check(min(engagement), min(engagement) >= 15),
        "book coupon flush to both cauls": check(max(map(abs, overlaps)), all(close(v, 0) for v in overlaps)),
    }


def sewing_frame(s):
    x, _, width, slot = s.rect("anchor-slot")
    radial_margins = []
    washer_land = []
    vertical_error = []
    throat = []
    for i in (0, 1):
        left, _, w, _ = s.rect(f"book-{i}")
        post_l, _, post_w, _ = s.rect(f"post-{i}-0")
        post_r, _, _, _ = s.rect(f"post-{i}-1")
        throat.append(min(left-post_l-post_w, post_r-left-w))
        for key in s.indices(f"key-{i}-"):
            j = key.split("-")[-1]
            cx, _, r = s.circle(key)
            _, _, wr = s.circle(f"washer-{i}-{j}")
            start, end = s.line(f"cord-{i}-{j}")
            radial_margins.extend((slot/2-r, cx-x-r, x+width-cx-r))
            washer_land.append(wr-slot/2)
            vertical_error.extend((abs(start[0]-end[0]), abs(start[0]-cx)))
    return {
        "key clearance inside continuous slot mm": check(min(radial_margins), min(radial_margins) >= .6),
        "washer coverage per side mm": check(min(washer_land), min(washer_land) >= 4),
        "book lateral insertion clearance mm": check(min(throat), min(throat) >= 8),
        "cord misalignment mm": check(max(vertical_error), close(max(vertical_error), 0)),
    }


def spine_press(s):
    x, top, length, _ = s.rect("jaw-face")
    book_x, _, book_len, _ = s.rect("spine")
    (tx, ty), (ux, uy) = s.line("tool-envelope")
    stroke_depth = top-max(ty, uy)
    x1, _, r1 = s.circle("rod-0")
    x2, _, r2 = s.circle("rod-1")
    rod_clear = min(book_x-x1-r1, x2-r2-book_x-book_len)
    block_x, block_top, block_w, height = s.rect("block")
    fixed, sliding = s.poly("fixed-jaw"), s.poly("travel-jaw")
    contact = min(max(p[1] for p in fixed), max(p[1] for p in sliding), block_top+height)-top
    mates = close(max(p[0] for p in fixed), block_x) and close(min(p[0] for p in sliding), block_x+block_w)
    return {
        "tool clearance above both jaw tops mm": check(stroke_depth, stroke_depth >= 4),
        "axial jaw coverage over spine": check(book_len, x <= book_x and book_x+book_len <= x+length
                                              and close(tx, book_x) and close(ux, book_x+book_len)),
        "rod edge clearance to block ends mm": check(rod_clear, rod_clear >= 8),
        "facing jaw contact height mm": check(contact, mates and contact >= 30),
    }


def rotate(point, center, angle):
    u, v = point[0]-center[0], point[1]-center[1]
    c, s = math.cos(angle), math.sin(angle)
    return center[0]+u*c-v*s, center[1]+u*s+v*c


def segment_distance(point, a, b):
    delta = (b[0]-a[0], b[1]-a[1])
    dot = sum((p-v)*d for p, v, d in zip(point, a, delta))
    fraction = max(0, min(1, dot/sum(d*d for d in delta)))
    projected = tuple(v+fraction*d for v, d in zip(a, delta))
    return math.dist(point, projected)


def fan_clamp(s):
    center = s.circle("pivot-1")[:2]
    _, ground, _, _ = s.rect("base-1")
    moving = ("rocker", "carrier", "near-jaw", "far-jaw", "stack")
    straight = {part: s.poly(f"{part}-1") for part in moving}
    v = straight["rocker"][0]
    angle_of = lambda point: math.atan2(point[1]-center[1], point[0]-center[0])
    limit = abs(angle_of(s.poly("rocker-2")[0])-angle_of(v))
    swept_clearance = math.inf
    stop_clearance, artifact_error = [], []
    stops = [s.circle(f"stop-{i}") for i in (0, 2)]
    for step in range(-160, 161):
        angle = limit*step/160
        sweep = {part: [rotate(point, center, angle) for point in vertices]
                 for part, vertices in straight.items()}
        swept_clearance = min(swept_clearance, ground-max(y for poly in sweep.values() for _, y in poly))
        for px, py, radius in stops:
            rocker = sweep["rocker"]
            stop_clearance.append(min(segment_distance((px, py), a, b)
                                      for a, b in zip(rocker, rocker[1:]+rocker[:1]))-radius)
        if step in (-160, 160):
            i = 0 if step > 0 else 2
            for part in moving:
                artifact_error.extend(math.dist(a, b) for a, b in zip(sweep[part], s.poly(f"{part}-{i}")))
    contacts = []
    for i, (px, py, radius) in zip((0, 2), stops):
        rocker = s.poly(f"rocker-{i}")
        contacts.append(min(segment_distance((px, py), a, b)
                            for a, b in zip(rocker, rocker[1:]+rocker[:1]))-radius)
    exposed = min(y for _, y in straight["near-jaw"])-min(y for _, y in straight["stack"])
    return {
        "rocker sweep above base mm": check(swept_clearance, swept_clearance >= 20),
        "end plate stops contact without early collision": check(min(stop_clearance), min(stop_clearance) >= -TOL
                                                                 and all(close(v, 0) for v in contacts)),
        "exported rotation endpoint maximum error mm": check(max(artifact_error), max(artifact_error) <= TOL),
        "leaf length above clamp jaws mm": check(exposed, exposed >= 25),
    }


def punch_fence(s):
    errors, travel, mount_span, support, visibility = [], [], [], [], []
    for i, target in enumerate((4, 8, 12)):
        _, fy, _, _ = s.rect(f"fence-{i}")
        px, py, r = s.circle(f"punch-{i}")
        _, sy, _, sh = s.rect(f"strip-{i}")
        errors.extend((abs(fy-py-target), abs(sy+sh-fy)))
        support.append(py-r-sy)
        centers = []
        for j in (0, 1):
            x, y, w, h = s.rect(f"slot-{i}-{j}")
            bx, by, br = s.circle(f"fastener-{i}-{j}")
            travel.extend((by-y-br, y+h-by-br, (w-2*br)/2-abs(bx-(x+w/2))))
            centers.append(bx)
        mount_span.append(centers[1]-centers[0])
        sight, other = s.line(f"visibility-{i}")
        visibility.append(sight[0] < px-r < px+r < other[0] and close(sight[1], py))
    _, lip_y, _, _ = s.rect("base-lip")
    poly = s.poly("clamp-shoe")
    gap = lip_y-poly[3][1]
    return {
        "offset and strip registration error mm": check(max(errors), max(errors) <= .01),
        "minimum slot margin over all offsets mm": check(min(travel), min(travel) >= .4),
        "two-point fence restraint span mm": check(min(mount_span), min(mount_span) >= 80),
        "strip remaining under punch mm": check(min(support), min(support) >= 10 and all(visibility)),
        "shoe insertion allowance mm": check(gap, .5 <= gap <= 2),
    }


def dye_roller(s):
    dip, sediment, lifting, guide_margin = [], [], [], []
    _, _, _, shaft = s.rect("shaft")
    for i in (0, 1):
        l, _ = s.line(f"slot-edge-{i}-left")
        r, _ = s.line(f"slot-edge-{i}-right")
        guide_margin.append(r[0]-l[0]-shaft)
    for i, target in enumerate((2, 3.5, 5)):
        tray = s.poly(f"tray-{i}")
        _, cy, radius = s.circle(f"roller-{i}")
        _, raised, raised_r = s.circle(f"lifted-{i}")
        (_, fluid), _ = s.line(f"dye-{i}")
        width = s.rect(f"edge-gap-{i}")[2]
        dip.append(cy+radius-fluid)
        sediment.append(tray[2][1]-(cy+radius))
        lifting.append(tray[0][1]-(raised+raised_r))
        if not close(width, target):
            raise ValueError("Exported guide slot size incorrect")
    return {
        "minimum bath immersion mm": check(min(dip), min(dip) >= 1 and max(dip) <= 3),
        "roller off floor mm": check(min(sediment), min(sediment) >= 4),
        "cleaning lift clears tray wall mm": check(min(lifting), min(lifting) >= 1),
        "axle removal slot clearance mm": check(min(guide_margin), min(guide_margin) >= .7),
    }


def blank_sander(s):
    coverage, lateral, ends, thickness_error = [], [], [], []
    for i, target in enumerate((2.5, 4, 5.5)):
        _, _, tl, tw = s.rect(f"track-{i}")
        a, ay, aw, _ = s.rect(f"abrasive-{i}")
        first, _, _, _ = s.rect(f"blank-{i}-0")
        last, _, bw, _ = s.rect(f"blank-{i}-1")
        coverage.extend(overlap(x, x+last-first, a, a+aw) for x in (first, first+bw))
        for j in (0, 1):
            x, y, sw, sh = s.rect(f"shoe-{i}-{j}")
            bx, by, _, bt = s.rect(f"blank-{i}-{j}")
            lateral.extend((y, tw-y-sh))
            ends.extend((x, tl-x-sw))
            thickness_error.extend((abs(bt-target), abs(by+bt-ay)))
            if bx < x or bx+bw > x+sw:
                raise ValueError("Blank overhangs the holding area")
        end, _, stop_w, _ = s.rect(f"end-stop-{i}")
        ends.append(tl-end-stop_w)
    return {
        "all blank points cross the abrasive span mm": check(min(coverage), min(coverage) >= 35),
        "carrier side clearance mm": check(min(lateral), .7 <= min(lateral) <= 1.3),
        "carrier end margin mm": check(min(ends), min(ends) >= 8),
        "assembled set thickness error mm": check(max(thickness_error), max(thickness_error) <= .01),
    }


def radius_template(s):
    arc_error, transfer, secured_land, pad_space = [], [], [], []
    for i, radius in enumerate((12, 25, 40)):
        path = s.path(f"guide-arc-{i}")
        if (path[0], path[3], path[6:9]) != ("M", "A", ["0", "0", "1"]):
            raise ValueError("Quarter circle arc flags changed")
        dimensions = map(float, (path[1], path[2], path[4], path[5], path[9], path[10]))
        arc_error.extend(abs(x-y) for x, y in zip(dimensions, (0, radius, radius, radius, radius, 0)))
        transfer.append(abs(s.circle(f"bearing-{i}")[2]-s.circle(f"cutter-{i}")[2]))
        panel = s.poly(f"rough-panel-{i}")
        panel_w, panel_h = panel[2]
        rail_x, rail_y, rail_w, rail_h = s.rect(f"fence-x-{i}")
        forward_x, forward_y, forward_w, forward_h = s.rect(f"fence-y-{i}")
        secured_land.extend((overlap(rail_y, rail_y+rail_h, 0, panel_h),
                             overlap(forward_x, forward_x+forward_w, 0, panel_w)))
        if not (close(rail_x+rail_w, 0) and close(forward_y+forward_h, 0)):
            raise ValueError("Fence face misses its corresponding datum")
        for j in (0, 1):
            x, y, pad = s.circle(f"clamp-pad-{i}-{j}")
            pad_space.append(min(x, panel_w-x, y-radius, panel_h-y)-pad)
    return {
        "quarter circle and tangent endpoint error mm": check(max(arc_error), max(arc_error) <= .01),
        "bearing to cutting radius transfer error mm": check(max(transfer), max(transfer) <= .25),
        "minimum indexing fence overlap on narrow panel mm": check(min(secured_land), min(secured_land) >= 15),
        "clamp pad edge clearance mm": check(min(pad_space), min(pad_space) >= 5),
    }


def dividing_disc(s):
    cx, cy, disc_r = s.circle("blank")
    rx, ry, receptacle = s.circle("receptacle")
    bx, by, boss = s.circle("boss")
    kx, ky, key = s.circle("key")
    sx, sy, key_seat = s.circle("key-seat")
    radial_play = receptacle-boss
    angle_error, radial_error, edge = [], [], []
    for group, count in enumerate((6, 8, 12)):
        ox, oy, radius = s.circle(f"reference-{group}")
        angles = []
        for i in range(count):
            point, tip = s.line(f"tick-{group}-{i}")
            angle = math.degrees(math.atan2(tip[1]-cy, tip[0]-cx))
            angles.append((angle+90) % 360)
            radial_error.extend((abs(math.dist(point, (ox, oy))-radius+4),
                                 abs(math.dist(tip, (ox, oy))-radius-4)))
            edge.append(disc_r-math.dist(tip, (cx, cy)))
        angles.sort()
        angles.append(angles[0]+360)
        angle_error.extend(abs(b-a-360/count) for a, b in zip(angles, angles[1:]))
    ax_error = math.dist((kx-bx, ky-by), (sx-rx, sy-ry))
    return {
        "maximum angular interval error deg": check(max(angle_error), max(angle_error) <= .02),
        "tick placement radial error mm": check(max(radial_error), max(radial_error) <= .01),
        "centering insert radial play mm": check(radial_play, .10 <= radial_play <= .25 and close(cx, rx)
                                                  and close(cy, ry)),
        "center key alignment error mm": check(ax_error, close(ax_error, 0) and .1 <= key_seat-key <= .3),
        "minimum edge land mm": check(min(edge), min(edge) >= 4),
    }


def fringe_twister(s):
    centers = [s.circle(f"shaft-0-{j}")[:2] for j in (0, 1)]
    spacing = math.dist(*centers)
    expected, length_errors, edge_clearance, clip_margin = [], [], [], []
    px, py, pw, ph = s.rect("drive-plate-0")
    _, _, layer_t, _ = s.rect("layer-0")
    layer_gap = s.rect("layer-1")[0]-s.rect("layer-0")[0]-layer_t
    for phase in range(4):
        phases = []
        for i in range(2):
            _, left_pin = s.line(f"crank-l-{phase}-{i}")
            _, right_pin = s.line(f"crank-r-{phase}-{i}")
            left_bore = s.circle(f"link-l-{phase}-{i}")[:2]
            right_bore = s.circle(f"link-r-{phase}-{i}")[:2]
            length_errors.extend((math.dist(left_bore, left_pin), math.dist(right_bore, right_pin),
                                  abs(math.dist(left_bore, right_bore)-spacing)))
            throws = [math.dist(a, b) for a, b in zip((left_pin, right_pin), centers)]
            direction = (left_pin[0]-centers[0][0], left_pin[1]-centers[0][1])
            phases.append(direction)
            expected.extend((abs(throws[0]-throws[1]), abs(math.dist(left_pin, right_pin)-spacing)))
            lx, ly, lw, lh = s.rect(f"link-{phase}-{i}")
            edge_clearance.append(min(lx-px, ly-py, px+pw-lx-lw, py+ph-ly-lh))
        expected.append(abs(sum(a*b for a, b in zip(*phases))))
        clip_margin.append(spacing-s.circle(f"clip-{phase}-0")[2]-s.circle(f"clip-{phase}-1")[2])
    _, zero = s.line("crank-l-0-0")
    crank_r = math.dist(zero, centers[0])
    transmission = min(max(abs(math.sin(math.radians(a))), abs(math.cos(math.radians(a))))
                       for a in range(360))
    sweep_land = min(centers[0][0]-px, px+pw-centers[1][0])-crank_r-6
    return {
        "coupler hole to pin mismatch mm": check(max(length_errors), max(length_errors) <= .15),
        "equal crank throws and 90 degree phasing": check(max(expected), max(expected) <= .01),
        "least available tangential component over 360 degrees": check(transmission, transmission >= .70),
        "link projected edge clearance mm": check(min(*edge_clearance, sweep_land),
                                                  min(*edge_clearance, sweep_land) >= 20),
        "separation between link planes mm": check(layer_gap, layer_gap >= 5),
        "clear gap between projected clip circles mm": check(min(clip_margin), min(clip_margin) >= 20),
    }


def warping_board(s):
    peg_land, joint_land, unused, tangent_error, lengths = [], [], [], [], []
    for i, active in enumerate(((0, 3), (1, 2))):
        lines = [s.line(f"yarn-{side}-{i}") for side in ("top", "bottom", "left", "right")]
        arcs = s.path(f"yarn-wrap-{i}")
        lengths.append(sum(math.dist(*line) for line in lines) +
                       sum(math.pi*float(arcs[start+4])/2 for start in range(0, len(arcs), 11)))
        for row in (0, 1):
            peg_row = [s.circle(f"peg-{i}-{row}-{j}") for j in range(4)]
            peg_land.extend(math.dist(a[:2], b[:2])-a[2]-b[2] for a, b in zip(peg_row, peg_row[1:]))
            rx, ry, rw, rh = s.rect(f"rail-{i}-{row}")
            for side in (0, 1):
                x, y, r = s.circle(f"bolt-{i}-{row}-{side}")
                sx, sy, sw, sh = s.rect(f"stile-{i}-{side}")
                joint_land.append(min(x-rx, rx+rw-x, y-ry, ry+rh-y, x-sx, sx+sw-x, y-sy, sy+sh-y)-r)
                peg = peg_row[active[side]]
                tangent_error.extend((abs(segment_distance(peg[:2], *lines[row])-peg[2]),
                                      abs(segment_distance(peg[:2], *lines[2+side])-peg[2])))
            unused.extend(min(segment_distance(peg[:2], *line)-peg[2] for line in lines[2:])
                          for j, peg in enumerate(peg_row) if j not in active)
    return {
        "peg hole edge-to-edge spacing mm": check(min(peg_land), min(peg_land) >= 20),
        "bolt edge land inside both overlapping rails mm": check(min(joint_land), min(joint_land) >= 20),
        "inactive sockets clearance from vertical runs mm": check(min(unused), min(unused) >= 20),
        "yarn line to active peg tangency error mm": check(max(tangent_error), max(tangent_error) <= .01),
        "nominal finished loop lengths mm": check([round(v, 3) for v in lengths],
                                                   all(abs(a-b) <= .1 for a, b in zip(lengths, (1850.265, 1490.265)))),
    }


CHECKERS = {
    "P232": punch_cradle, "P233": nipping_press, "P234": sewing_frame,
    "P235": spine_press, "P236": fan_clamp, "P240": punch_fence,
    "P241": dye_roller, "P246": blank_sander, "P251": radius_template,
    "P261": dividing_disc, "P263": fringe_twister, "P264": warping_board,
}
REJECTION_CRITERIA = {
    "P232": "awl exit radial clearance mm",
    "P233": "hand knob sweep clear of flat platen mm",
    "P234": "key clearance inside continuous slot mm",
    "P235": "tool clearance above both jaw tops mm",
    "P236": "rocker sweep above base mm",
    "P240": "two-point fence restraint span mm",
    "P241": "minimum bath immersion mm",
    "P246": "all blank points cross the abrasive span mm",
    "P251": "bearing to cutting radius transfer error mm",
    "P261": "centering insert radial play mm",
    "P263": "coupler hole to pin mismatch mm",
    "P264": "peg hole edge-to-edge spacing mm",
}


def replay():
    records = {}
    for product, verify in CHECKERS.items():
        candidate = verify(Sheet(HERE / product / "trial.svg"))
        rejected = verify(Sheet(HERE / product / "rejected.svg"))
        records[product] = {
            "candidate": candidate, "rejected": rejected,
            "required_rejection": REJECTION_CRITERIA[product],
            "pass": all(row["pass"] for row in candidate.values())
                    and not rejected[REJECTION_CRITERIA[product]]["pass"],
        }
    return records


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Save current measurements")
    args = parser.parse_args()
    reports = replay()
    results = json.dumps(reports, indent=2) + "\n"
    path = HERE / "results.json"
    if args.write:
        path.write_text(results, encoding="utf-8")
    elif not path.exists() or path.read_text() != results:
        raise SystemExit("Saved results differ from export replay. Use --write after reviewing edits.")
    from build import build
    with tempfile.TemporaryDirectory() as temp:
        build(Path(temp))
        for product, report in reports.items():
            for revision in ("trial", "rejected"):
                relative = Path(product) / (revision+".svg")
                if (Path(temp) / relative).read_bytes() != (HERE / relative).read_bytes():
                    raise SystemExit(f"Stale export: {relative}")
            issues = [name for name, record in report["candidate"].items() if not record["pass"]]
            negative = [name for name, record in report["rejected"].items() if not record["pass"]]
            if issues or report["required_rejection"] not in negative:
                print(product, "candidate failures:", issues, "control failures:", negative)
            else:
                print(product, f"{len(report['candidate'])} candidate checks passed; rejected on {negative}")
    raise SystemExit(0 if all(report["pass"] for report in reports.values()) else 1)
