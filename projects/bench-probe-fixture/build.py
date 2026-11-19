"""Build and inspect a passive two-plate fixture concept from an HS board revision."""

import argparse
import hashlib
import json
from math import dist
from pathlib import Path
import subprocess

import cadquery as cq
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle


HERE = Path(__file__).resolve().parent
BOARD = HERE.parents[1] / "hardware/reference_designs/spi_flash_adapter_v1/spi_flash_adapter_v1.kicad_pcb"
POSTS = [(-6, 0), (96, 4), (-6, 47)]
PROBE_BORE = 0.9
POST_BORE = 3.1


def plate(thickness):
    return cq.Workplane("XY").center(45, 25).rect(112, 62).extrude(thickness)


def cylinders(points, diameter, height, z=0):
    return (cq.Workplane("XY").workplane(offset=z).pushPoints(points)
            .circle(diameter / 2).extrude(height, combine=False))


def exported_centres(path, diameter, z):
    model = cq.importers.importStep(str(path))
    if len(model.solids().vals()) != 1 or not model.val().isValid():
        raise ValueError(f"Invalid STEP solid in {path.name}")
    centres = []
    for edge in model.edges().vals():
        if edge.geomType() == "CIRCLE" and abs(2 * edge.radius() - diameter) < 1e-5:
            center = edge.arcCenter()
            if abs(center.z - z) < 1e-5:
                centres.append((center.x, center.y))
    return centres


def match(centres, targets):
    return (len(centres) == len(targets) and
            all(sum(dist(c, target) < 1e-5 for c in centres) == 1 for target in targets))


def draw_preview(layout, output):
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.add_patch(Rectangle((-11, -6), 112, 62, facecolor="#e5eced", edgecolor="#42535d"))
    ax.add_patch(Rectangle((0, 0), layout["width"], layout["height"],
                           facecolor="#c7e2d8", edgecolor="#2d6757"))
    for x, y in POSTS:
        ax.add_patch(Circle((x, y), POST_BORE / 2, color="#42535d"))
    for point in layout["points"]:
        x, y = point["x"], point["y"]
        probe = point["ref"].startswith("TP")
        ax.add_patch(Circle((x, y), point["diameter"] / 2, color="#9a4400" if probe else "white",
                            ec="#9a4400" if probe else "#52615d"))
        ax.annotate(point["ref"], (x, y), xytext=(0, 6), textcoords="offset points",
                    ha="center", fontsize=8)
    ax.set(xlim=(-13, 103), ylim=(-8, 58), aspect="equal", xlabel="mm", ylabel="mm")
    ax.set_title("SPI adapter specimen  •  top view, component side up", loc="left")
    fig.text(.5,.025,"Orange = probe targets     White = PCB mounting holes     Gray dots = fixture guide posts",
             ha="center")
    fig.tight_layout(rect=(0,.05,1,1))
    fig.savefig(output, dpi=140)
    plt.close(fig)


def build(board, output, kicad_python):
    output.mkdir(parents=True, exist_ok=True)
    layout = json.loads(subprocess.check_output([kicad_python, HERE / "read_board.py", board]))
    probes = [p for p in layout["points"] if p["ref"].startswith("TP")]
    mounts = {p["ref"]: p for p in layout["points"] if p["ref"].startswith("H")}
    if not probes or set(mounts) != {"H1", "H2", "H3", "H4"}:
        raise ValueError("Expected front-side probes and mounting holes H1 through H4")
    if layout["width"] > 90 or layout["height"] > 50:
        raise ValueError("Board exceeds the common plate envelope")
    positions = [(p["x"], p["y"]) for p in probes]
    mounting = [(p["x"], p["y"]) for p in mounts.values()]
    locators = [(mounts[r]["x"], mounts[r]["y"]) for r in ("H1", "H4")]
    if any(abs(p["diameter"] - 3.2) > 1e-5 for p in mounts.values()):
        raise ValueError("Carrier geometry expects 3.2 mm mounting holes")
    guide = plate(4).cut(cylinders(positions, PROBE_BORE, 4)).cut(cylinders(POSTS, POST_BORE, 4))
    carrier = (plate(3).cut(cylinders(POSTS, POST_BORE, 3))
               .union(cylinders(mounting, 6, 2, 3)).union(cylinders(locators, 3, 1, 5)))
    guide_path, carrier_path = output / "probe-guide.step", output / "board-carrier.step"
    for model, path in ((guide, guide_path), (carrier, carrier_path)):
        cq.exporters.export(model, str(path))
    for path, z in ((guide_path, 4), (carrier_path, 3)):
        if not match(exported_centres(path, POST_BORE, z), POSTS):
            raise ValueError(f"Missing guide-post geometry in {path.name}")
    if not match(exported_centres(carrier_path, 3, 6), locators):
        raise ValueError("Exported carrier lost a board locator")
    for z in (0, 4):
        if not match(exported_centres(guide_path, PROBE_BORE, z), positions):
            raise ValueError("Exported guide does not match the board probe coordinates")

    # Sensitivity scenario. The radial allowance includes all locating errors at the pad.
    tip_radius, radial_error = 0.25, 0.40
    worst_margin = min(p["diameter"] / 2 - tip_radius - radial_error for p in probes)
    shifted_margin = min(p["diameter"] / 2 - tip_radius - 0.80 for p in probes)
    if worst_margin <= 0 or shifted_margin >= 0:
        raise ValueError("Pad coverage or displaced-guide control failed")
    report = dict(board=board.name, board_sha256=hashlib.sha256(board.read_bytes()).hexdigest(),
                  frame="component side up; lower-left board corner is (0,0); mm",
                  contacts=len(probes), distinct_nets=len({p["net"] for p in probes}),
                  reopened_step_through_bores=len(positions), common_post_positions_mm=POSTS,
                  assumed_tip_diameter_mm=2*tip_radius, assumed_radial_error_mm=radial_error,
                  minimum_pad_margin_mm=round(worst_margin, 4),
                  margin_at_0_8_mm_displacement_mm=round(shifted_margin, 4), board_layout=layout)
    (output / "geometry.json").write_text(json.dumps(report, indent=2) + "\n")
    draw_preview(layout, output / "contact-map.png")
    print(f"{len(probes)} through-bores and {len(POSTS)} post positions verified from STEP")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--board", type=Path, default=BOARD)
    parser.add_argument("--output", type=Path, default=HERE)
    parser.add_argument("--kicad-python", default="/usr/bin/python3")
    args = parser.parse_args()
    build(args.board, args.output, args.kicad_python)
