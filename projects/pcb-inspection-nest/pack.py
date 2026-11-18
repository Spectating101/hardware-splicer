"""Generate, audit and package the HS fixture and its source for standalone use."""

import argparse
from contextlib import redirect_stdout
from hashlib import sha256
from math import pi, radians, tan
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from xml.etree import ElementTree as ET
from zipfile import ZipFile, ZIP_DEFLATED
import io
import json
import shutil

import cadquery as cq
import trimesh

import build


def board_outline(profile, raw, holes):
    board = ET.fromstring(raw).find("drawing/board")
    cx, cy = profile["board_center_mm"]
    edges = []
    for wire in board.findall("plain/wire[@layer='20']"):
        x1, y1, x2, y2 = (float(wire.get(k)) for k in ("x1", "y1", "x2", "y2"))
        a, b = cq.Vector(x1 - cx, y1 - cy, 0), cq.Vector(x2 - cx, y2 - cy, 0)
        angle = float(wire.get("curve", 0))
        if angle:
            sag = tan(radians(angle) / 4) / 2
            middle = (a + b) * 0.5 + cq.Vector((y2 - y1) * sag, -(x2 - x1) * sag, 0)
            edges.append(cq.Edge.makeThreePointArc(a, middle, b))
        else:
            edges.append(cq.Edge.makeLine(a, b))
    (loop,) = cq.Wire.combine(edges)
    if not loop.IsClosed():
        raise ValueError("Expected a closed external PCB contour")
    board = cq.Solid.extrudeLinear(loop, [], cq.Vector(0, 0, 1.6))
    for x, y, d in holes:
        board = board.cut(build.cylinder(x, y, -1, d, 4))
    box = board.BoundingBox()
    if (
        max(
            abs(v - w)
            for v, w in zip([box.xlen, box.ylen], profile["board_envelope_mm"])
        )
        > 0.001
    ):
        raise ValueError("External contour differs from declared board envelope")
    return board


def check_shoulders(seated, board, holes):
    # A thin slice just below the PCB must support its full designed annulus.
    delta = 0.05
    area = seated.intersect(board.translate((0, 0, -delta))).Volume() / delta
    expected = sum(pi * (4.6**2 - d**2) / 4 for _, _, d in holes)
    if abs(area - expected) > 0.01 or seated.intersect(board).Volume() > 1e-5:
        raise ValueError("Board outline collides or a support misses the board")
    return round(area, 3)


def preview(solids, path):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    import numpy as np

    fig = plt.figure(figsize=(4 * len(solids), 4.2))
    for index, (name, parts) in enumerate(solids.items(), 1):
        ax = fig.add_subplot(
            1, len(solids), index, projection="3d", proj_type="ortho", computed_zorder=False
        )
        direction = np.array(
            [
                np.cos(np.deg2rad(26)) * np.cos(np.deg2rad(-68)),
                np.cos(np.deg2rad(26)) * np.sin(np.deg2rad(-68)),
                np.sin(np.deg2rad(26)),
            ]
        )
        for level, (solid, color) in enumerate(
            zip(parts, ("#929dac", "#e3a039", "#318e83"))
        ):
            pts, idx = solid.tessellate(0.07)
            pts = np.array([p.toTuple() for p in pts])
            triangles = pts[np.array(idx)]
            normals = np.cross(
                triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]
            )
            collection = Poly3DCollection(
                triangles[normals @ direction > 0],
                facecolors=color,
                linewidths=0,
                shade=True,
                zorder=level + 1,
            )
            ax.add_collection3d(collection)
        title = {
            "pygamer": "PyGamer",
            "max9744": "MAX9744",
            "openlog": "OpenLog Artemis",
            "feather-m4-express": "Feather M4 Express",
        }.get(name, name)
        ax.set(xlim=(-62, 62), ylim=(-42, 42), zlim=(0, 46), title=title)
        ax.set_box_aspect((124, 84, 46))
        ax.view_init(elev=26, azim=-68)
        ax.set_axis_off()
    fig.suptitle(
        "Inspection nest · common dock, interchangeable carriers, bare PCB outlines"
    )
    fig.tight_layout()
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def package(cache, destination, fetch):
    started = perf_counter()
    destination.mkdir(parents=True, exist_ok=True)
    profiles = json.loads((build.HERE / "boards.json").read_text())
    with TemporaryDirectory() as temp:
        root = Path(temp)
        models = root / "models"
        with redirect_stdout(io.StringIO()):
            build.build(cache, models, fetch, list(profiles))
        report_file = models / "verification.json"
        report = json.loads(report_file.read_text())
        dock = cq.importers.importStep(str(models / "dock.step")).val()
        panels = {}
        for stl in models.glob("*.stl"):
            mesh = trimesh.load_mesh(stl)
            if not mesh.is_volume or len(mesh.split()) != 1:
                raise ValueError(f"Invalid delivery mesh {stl.name}")
        for name, profile in profiles.items():
            raw = (cache / profile["file"]).read_bytes()
            if sha256(raw).hexdigest() != profile["source"]["sha256"]:
                raise ValueError("Unexpected PCB revision during assembly audit")
            holes = report[name]["reference_xy_and_drill_mm"]
            pcb = board_outline(profile, raw, holes).translate(
                (0, 0, build.BASE_H + build.PLATE_H + build.STAND_H)
            )
            carrier = (
                cq.importers.importStep(str(models / f"{name}.step"))
                .val()
                .translate((0, 0, build.BASE_H))
            )
            report[name]["support_contact_area_mm2"] = check_shoulders(
                carrier, pcb, holes
            )
            assy = cq.Assembly()
            assy.add(dock, name="dock", color=cq.Color("gray"))
            assy.add(carrier, name="carrier", color=cq.Color("orange"))
            assy.add(pcb, name="bare_board_reference", color=cq.Color("seagreen"))
            assy.export(str(models / f"{name}-assembly.step"))
            reopened = cq.importers.importStep(str(models / f"{name}-assembly.step"))
            if len(reopened.solids().vals()) != 3:
                raise ValueError("Incomplete STEP assembly")
            panels[name] = [
                dock,
                carrier.translate((0, 0, 12)),
                pcb.translate((0, 0, 26)),
            ]
        report_file.write_text(json.dumps(report, indent=2) + "\n")
        preview(panels, root / "preview.png")
        for name in (
            "README.md",
            "build.py",
            "pack.py",
            "boards.json",
            "LICENSE",
            "requirements.txt",
        ):
            shutil.copyfile(build.HERE / name, root / name)
        shutil.copytree(build.HERE / "notices", root / "notices")
        archive = destination / "inspection-nest-v0.2.zip"
        with ZipFile(archive, "w", compression=ZIP_DEFLATED) as z:
            for path in sorted(root.rglob("*")):
                if path.is_file():
                    z.write(path, path.relative_to(root))
        with ZipFile(archive) as z:
            if z.testzip() is not None:
                raise ValueError("Archive failed its integrity check")
        shutil.copyfile(root / "preview.png", destination / "preview.png")
        print(
            json.dumps(
                {
                    "package_sha256": sha256(archive.read_bytes()).hexdigest(),
                    "seconds_after_imports": round(perf_counter() - started, 3),
                    "checks": report,
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--fetch", action="store_true")
    args = parser.parse_args()
    package(args.cache, args.destination, args.fetch)
