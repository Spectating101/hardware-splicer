"""Regenerate dimensional drawings, replay screens, and compare them to saved evidence."""

import argparse
import base64
import csv
import json
import math
import os
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
import experiments as ex

HERE = Path(__file__).resolve().parent
DEFINITIONS = json.loads((HERE / "designs.json").read_text())
NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", NS)


class Drawing:
    def __init__(self, w, h, title):
        self.root = ET.Element(
            f"{{{NS}}}svg", width=f"{w}mm", height=f"{h}mm", viewBox=f"0 0 {w} {h}"
        )
        ET.SubElement(self.root, f"{{{NS}}}title").text = title

    def element(self, tag, **attrs):
        return ET.SubElement(
            self.root, f"{{{NS}}}{tag}", {k: str(v) for k, v in attrs.items()}
        )

    def box(self, name, x, y, w, h, color="#eceff1"):
        self.element(
            "rect",
            id=name,
            x=x,
            y=y,
            width=w,
            height=h,
            fill=color,
            stroke="#223041",
            **{"stroke-width": 0.22},
        )

    def circle(self, name, x, y, r):
        self.element(
            "circle",
            id=name,
            cx=x,
            cy=y,
            r=r,
            fill="white",
            stroke="#223041",
            **{"stroke-width": 0.22},
        )

    def write(self, dest):
        ET.ElementTree(self.root).write(dest, encoding="utf-8", xml_declaration=True)
        tree = ET.parse(dest).getroot()
        ids = [n.get("id") for n in tree if n.get("id")]
        if not ids or len(ids) != len(set(ids)):
            raise ValueError(f"Missing or duplicate geometry in {dest}")


def charuco(d, output):
    import cv2
    import numpy as np

    cv2.setNumThreads(1)
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    board = cv2.aruco.CharucoBoard(
        (d["cols"], d["rows"]), float(d["square_mm"]), float(d["marker_mm"]), dictionary
    )
    w, h = d["cols"] * d["square_mm"], d["rows"] * d["square_mm"]
    scale = d["px_per_mm"]
    b = d["border_mm"] * scale
    target = board.generateImage((w * scale, h * scale))
    raster = cv2.copyMakeBorder(target, b, b, b, b, cv2.BORDER_CONSTANT, value=255)
    path = output / "target.png"
    cv2.imwrite(str(path), raster)
    saved = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    rh, rw = saved.shape
    src = np.float32([(0, 0), (rw - 1, 0), (rw - 1, rh - 1), (0, rh - 1)])
    dst = np.float32([(70, 45), (rw - 90, 80), (rw - 45, rh - 50), (25, rh - 88)])
    perspective = cv2.warpPerspective(
        saved, cv2.getPerspectiveTransform(src, dst), (rw, rh), borderValue=255
    )
    detector = cv2.aruco.CharucoDetector(board)

    def decode(img):
        corners, ids, _, _ = detector.detectBoard(img)
        if ids is None:
            raise ValueError("No ChArUco corners found")
        return {int(i): c.ravel() for i, c in zip(ids.ravel(), corners)}

    pts = decode(saved)
    warped = decode(perspective)
    transform = cv2.getPerspectiveTransform(src, dst)
    if set(pts) != set(warped):
        raise ValueError("Perspective warp changed detected corner IDs")
    residuals = [
        float(
            np.linalg.norm(
                cv2.perspectiveTransform(np.float32([[point]]), transform)[0, 0]
                - warped[i]
            )
        )
        for i, point in pts.items()
    ]
    pitch = float(np.linalg.norm(pts[1] - pts[0]) / scale)
    # Shrink the exported page in pixel space, while the print scale bar still expects 8 px/mm.
    shrunk = decode(
        cv2.resize(saved, None, fx=0.97, fy=0.97, interpolation=cv2.INTER_AREA)
    )
    off_pitch = float(np.linalg.norm(shrunk[1] - shrunk[0]) / scale)
    expected = (d["cols"] - 1) * (d["rows"] - 1)
    results = ex.outcome(
        {
            "clean_corners": len(pts),
            "warped_corners": len(warped),
            "pitch_mm": round(pitch, 3),
            "max_warp_residual_px": round(max(residuals), 3),
            "scaled_97pct_pitch_mm": round(off_pitch, 3),
            "expected_corners": expected,
        },
        len(pts) == len(warped) == expected
        and max(residuals) < 2
        and abs(pitch - d["square_mm"]) <= d["pitch_error_limit_mm"],
        abs(off_pitch - d["square_mm"]) > d["pitch_error_limit_mm"],
    )
    drawing = Drawing(rw / scale, rh / scale, "ChArUco board; print at 100%")
    blob = base64.b64encode(path.read_bytes()).decode()
    drawing.element(
        "image",
        id="charuco-grid",
        width=rw / scale,
        height=rh / scale,
        href="data:image/png;base64," + blob,
    )
    return drawing, results


def layout(ident, d):
    s = Drawing
    n = d["name"]
    if ident == "P181":
        v = s(d["length"] + 4, d["belt_width"] + 14, n)
        v.box("belt", 2, 7, d["length"], d["belt_width"])
        v.box("sensor-axis", 2 + d["sensor_x"], 2, 0.5, d["belt_width"] + 10)
        v.box(
            "edge-buffer",
            2 + d["length"] - d["edge_buffer"],
            7,
            d["edge_buffer"],
            d["belt_width"],
            "#f0d5b1",
        )
    elif ident == "P182":
        v = s(d["frame_width"] + 4, 34, n)
        v.box("lower-rail", 2, 22, d["frame_width"], 7)
        v.box("upper-gate", 2, 22 - d["gate"] - 7, d["frame_width"], 7)
        v.box(
            "max-single-puck",
            8,
            22 - d["max_thick"],
            d["max_diameter"],
            d["max_thick"],
            "#dbb986",
        )
    elif ident == "P183":
        v = s(85, 40, n)
        v.box("chute", 2, 10, 80, 20)
        v.box("reader", 2 + d["read_x"], 7, 1, 26)
        v.box("diverter", 2 + d["gate_x"], 6, 1, 28)
    elif ident == "P184":
        v = s(60, 60, n)
        v.circle("rolling-wheel", 30, 30, d["wheel_diameter"] / 2)
        v.circle("illustrative-axle", 30, 30, 2)
        v.box("rotation-index", 29.75, 6, 0.5, 8)
    elif ident == "P185":
        v = s(58, 24, n)
        v.box("travel", 4, 8, d["guide_travel"], 8)
        for key in ["home_switch_x", "limit_x", "guide_travel"]:
            v.box(key, 4 + d[key], 3, 0.4, 18)
    elif ident == "P186":
        v = s(d["track_width"], d["track_height"] + 16, n)
        coords = []
        for i in range(361):
            a = math.radians(i)
            coords.append(
                f"{d['track_width'] * (0.5 + 0.43 * math.sin(a)):.3f},{d['track_height'] * (0.5 + 0.39 * math.sin(2 * a)):.3f}"
            )
        v.element(
            "polyline",
            id="figure-eight",
            points=" ".join(coords),
            fill="none",
            stroke="black",
            **{"stroke-width": d["line_width"]},
        )
        for i in range(d["sensors"]):
            v.circle(f"sensor-{i}", 10 + i * d["pitch"], d["track_height"] + 8, 1.5)
    elif ident == "P188":
        v = s(76, 43, n)
        v.box("base", 2, 28, 50, 7)
        v.box("fixed-jaw", 12, 10, 6, 18)
        v.box("adjustable-jaw-open", 18 + d["jaw_max_gap"], 10, 6, 18)
        v.circle("effective-friction-radius-detail", 58, 19, d["pivot_radius"])
    elif ident == "P189":
        v = s(64, 44, n)
        v.box("base", 2, 35, 59, 5)
        x, y = 32, 35 - d["pivot_height"]
        for deg in [-d["tilt_limit_deg"], 0, d["tilt_limit_deg"]]:
            v.element(
                "rect",
                id=f"tilt-{deg}",
                x=x - d["depth"] / 2,
                y=y - d["pcb_height"] / 2,
                width=d["depth"],
                height=d["pcb_height"],
                fill="none",
                stroke="#304d72",
                transform=f"rotate({deg} {x} {y})",
                **{"stroke-width": 0.25},
            )
        v.circle("pivot", x, y, 0.7)
    elif ident == "P190":
        v = s(d["length"] + 6, 24, n)
        v.box("contact-bar", 3, 4, d["length"], 4)
        for i, sign in enumerate([-1, 1]):
            v.box(
                f"switch-{i}",
                3 + (d["length"] + sign * d["switch_span"]) / 2 - 2,
                8,
                4,
                9,
            )
    elif ident == "P191":
        v = s(57, 57, n)
        leg, rail = d["leg_length"], d["rail_mm"]
        v.element(
            "polygon",
            points=f"2,2 {2 + leg},2 {2 + leg},{2 + rail} {2 + rail},{2 + rail} {2 + rail},{2 + leg} 2,{2 + leg}",
            id="l-plate",
            fill="#d4dfe5",
        )
        for i, p in enumerate(d["hole_pitch_from_corner"]):
            for j, (x, y) in enumerate([(p, rail / 2), (rail / 2, p)]):
                v.circle(f"m5-clear-{i}-{j}", 2 + x, 2 + y, d["hole_diameter"] / 2)
        for key, x, y, w, h in [
            ("x", 2 + d["pad_start"], 2, leg - d["pad_start"], rail),
            ("y", 2, 2 + d["pad_start"], rail, leg - d["pad_start"]),
        ]:
            v.box("pad-" + key, x, y, w, h, "#e3ba8e")
    elif ident == "P192":
        v = s(46, 32, n)
        v.box("throat-left", 2, 4, 11, 24)
        v.box("throat-right", 13 + d["fixture_throat"], 4, 11, 24)
        v.circle("cup", 13 + d["fixture_throat"] / 2, 16, d["cup_mm"] / 2)
    else:
        raise ValueError(ident)
    return v


CASES = {
    "P181": (
        ex.conveyor,
        "Move the stop sensor upstream",
        "A constant-speed approach, a fixed controller delay and constant braking bound the distance to the belt edge. The model omits belt slip and article sliding.",
        "Run the 80 g article through 100 passes at each speed and measure the longest stop, including a slipping belt.",
    ),
    "P182": (
        ex.singulator,
        "Set the adjustable gate with a single and a double coupon",
        "The single-piece stack and the most compressible two-piece stack must land on opposite sides of both gate tolerance limits. Bridging and friction are unmodeled.",
        "Feed 100 actual mixed pucks. Record doubles, bridge jams and single exits at the tolerance limits.",
    ),
    "P183": (
        ex.sorter,
        "Move the diverter far enough beyond the read line",
        "Three assumed color prototypes are tested under two additive lighting levels with a matched dark reading and seeded gain/noise variation. The correction uses the exact simulated dark offset. Independent illumination drift is outside this screen. Gate travel competes with transit time.",
        "Run two randomized sets of 100 real parts in the intended lighting, scoring wrong bins separately from late gate movements.",
    ),
    "P184": (
        ex.odometer,
        "Calibrate the rolling distance per encoder turn",
        "Quantized pulses are replayed for a 2 m run under three assumed slip ratios. The calibration input is synthetic. The adverse run adds 3.5% slip.",
        "Tape a 2 m baseline, measure actual loaded circumference and record forward and reverse error on three floor finishes.",
    ),
    "P185": (
        ex.pusher,
        "Place the limit before the deceleration zone",
        "One-dimensional stopping includes switch location uncertainty, controller latency and deceleration. Force, screw backlash and repeatability under load remain open.",
        "Cycle a 250 g dummy 500 times and record worst overrun, endpoint spread and home response.",
    ),
    "P186": (
        ex.tracker,
        "Check where seven reflectance sensors lose the line",
        "A single-line reflectance model tests lateral offset and lighting. The drawing includes a full-size figure-eight. A uniform dark crossing is ambiguous, so completing a lap requires additional steering logic.",
        "Replay the figure-eight for ten laps under declared lighting, including how the cart chooses its path at the crossing.",
    ),
    "P187": (
        None,
        "Detect a printed-scale ChArUco pattern after perspective distortion",
        "OpenCV renders a 4x4_50 pattern, reads the emitted image and checks the corner identities after a perspective warp. A smaller print scale yields an incorrect pitch despite remaining detectable.",
        "Measure pitch at five points per axis and both diagonal flatness readings, recording gauge uncertainty.",
    ),
    "P188": (
        ex.cradle,
        "Size the jaw opening and pivot preload",
        "A single effective friction surface balances gravity with an explicit torque factor. The drawing shows the open jaw in section and a separate effective-radius detail. Clamp force and friction are assumptions.",
        "Fit both board thicknesses and measure angular creep after 30 minutes under the maximum eccentric load.",
    ),
    "P189": (
        ex.tilt,
        "Raise the tilt pivot to clear the camera sweep",
        "An exact rectangular side envelope is checked at travel limits and its internal extremum with a reserved harness loop. The camera dimension input follows the Raspberry Pi Camera Module 3 standard-lens product brief. Connector and cable routing need a physical mockup.",
        "Sweep 250 reversals with the specified dummy module and cable, measuring clearance and return angle.",
    ),
    "P190": (
        ex.bumper,
        "Reduce trigger travel until a center press registers",
        "Static reactions distribute an applied force over two compliant switch supports. Ten equally spaced points and the exact center test the weakest location. Flex, hysteresis and release behavior require measurement.",
        "Press and release at ten positions plus center for ten cycles and record force, switch transitions and any sticking.",
    ),
    "P191": (
        ex.brackets,
        "Keep both bolt washers clear of the bumper pad",
        "A 20 mm rail and assumed pad placement tolerance set the envelope. The drawing is one corner plate used four times. The stock profile reference establishes rail width only. Hole seats, T-nuts and impact strength require verification.",
        "Fit the four corners to the named extrusion, verify nut seating and check retention after representative knocks.",
    ),
    "P192": (
        ex.pickup,
        "Size the suction cup for a nonporous coupon",
        "Pressure times cup area is derated for the assumed seal, then compared to dynamic load with a factor of three. An exponential vent trace predicts the first sample below static holding force after venting.",
        "Perform 100 lifts of a 50 g coupon in a contained bin and measure release delay, leakage and power-loss response.",
    ),
}

REFERENCES = {
    "P187": "[OpenCV ChArUco board documentation](https://docs.opencv.org/4.12.0/df/d4a/tutorial_charuco_detection.html)",
    "P189": "[Manufacturer's dimensional brief](https://pip-assets.raspberrypi.com/categories/786-raspberry-pi-camera-module-3/documents/RP-008151-DS-1-camera-module-3-product-brief.pdf)",
    "P191": "[80/20 metric 20-2020 extrusion](https://8020.net/20-2020.html)",
}


def generate(dest):
    rows = []
    for ident, (fn, decision, scope, bench) in CASES.items():
        d = DEFINITIONS[ident]
        folder = dest / ident
        folder.mkdir(exist_ok=True, parents=True)
        if fn is None:
            drawing, results = charuco(d, folder)
        else:
            drawing = layout(ident, d)
            results = fn(d)
        drawing.write(folder / "layout.svg")
        (folder / "results.json").write_text(
            json.dumps(results, indent=2, allow_nan=False) + "\n"
        )
        summary = "\n".join(
            f"| {key.replace('_', ' ')} | {display(value)} |"
            for key, value in results.items()
        )
        note = f"# {ident} · {d['name']}\n\n{decision}. {scope}\n\n[Full-scale layout](layout.svg) · [Model outputs](results.json) · [Editable design inputs](../designs.json)\n\n| Modeled quantity | Result |\n|---|---|\n{summary}\n\n**Physical acceptance.** {bench}\n"
        if ident in REFERENCES:
            note += "\n" + REFERENCES[ident] + "\n"
        solids = {
            "P182": ["revised-mouth", "original-mouth"],
            "P188": ["max-thickness-seat", "original-seat"],
            "P191": ["rail-corner-plate"],
        }.get(ident)
        if solids:
            note += (
                "\n**3D tooling.** "
                + ", ".join(
                    f"[{n.replace('-', ' ')} STEP](solids/{n}.step)" for n in solids
                )
                + ". [Fit measurements from reopened solids](solids/fit.json).\n"
            )
        (folder / "README.md").write_text(note)
        rows.append(
            [
                ident,
                d["name"],
                "Digital engineering screen. " + decision + ".",
                bench,
                f"{ident}/README.md",
            ]
        )
    with (dest / "manifest.csv").open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "title", "engineering", "physical_check", "report"])
        writer.writerows(rows)


def display(v):
    if isinstance(v, float):
        return f"{v:.4f}".rstrip("0").rstrip(".")
    if isinstance(v, dict):
        return ", ".join(f"{k} {display(value)}" for k, value in v.items())
    if isinstance(v, list):
        return ", ".join(display(n) for n in v)
    return str(v)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--publish",
        action="store_true",
        help="write the revised outputs after reviewing design changes",
    )
    args = p.parse_args()
    if args.publish:
        generate(HERE)
    with tempfile.TemporaryDirectory() as td:
        dest = Path(td)
        generate(dest)
        for f in sorted(item for item in dest.rglob("*") if item.is_file()):
            published = HERE / f.relative_to(dest)
            if f.read_bytes() != published.read_bytes():
                raise ValueError(f"Published result differs from replay: {published}")
    cad = os.environ.get(
        "HS_ROBOT_CAD_PYTHON",
        str(Path.home() / ".local/share/hardware-splicer/cad-venv/bin/python"),
    )
    subprocess.run([cad, str(HERE / "solids.py")], check=True)
    print(f"{len(CASES)} robot tooling studies regenerated with adverse controls")


if __name__ == "__main__":
    main()
