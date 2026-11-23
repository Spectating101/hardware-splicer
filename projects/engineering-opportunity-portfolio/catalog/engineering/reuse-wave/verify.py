"""Inspect the two frozen HS design releases without connecting to hardware."""

import argparse
import json
from importlib.util import find_spec
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from zipfile import ZipFile

HERE = Path(__file__).resolve().parent


def check_dock(work):
    import cadquery as cq
    from trimesh import load_mesh

    root = work / "models"
    profiles = json.loads((work / "boards.json").read_text())
    saved = json.loads((root / "verification.json").read_text())
    records = {}
    for ident in profiles:
        solids = (
            cq.importers.importStep(str(root / f"{ident}-assembly.step"))
            .solids()
            .vals()
        )
        dock, carrier, pcb = sorted(solids, key=lambda v: v.BoundingBox().zmin)
        seated = max(dock.intersect(carrier).Volume(), carrier.intersect(pcb).Volume())
        reverse = carrier.rotate((0, 0, 0), (0, 0, 1), 180).intersect(dock).Volume()
        support = carrier.intersect(pcb.translate((0, 0, -0.05))).Volume() / 0.05
        mesh = load_mesh(root / f"{ident}.stl")
        if not (
            mesh.is_volume
            and abs(mesh.volume - carrier.Volume()) < carrier.Volume() * 0.002
            and seated < 1e-5
            and reverse > 10
            and abs(support - saved[ident]["support_contact_area_mm2"]) < 0.002
        ):
            raise ValueError(
                f"Carrier assembly {ident} failed. Seated {seated}; reversed {reverse}; support {support}"
            )
        records[ident] = {
            "seated_intersection_mm3": round(seated, 5),
            "reversed_intersection_mm3": round(reverse, 3),
            "support_mm2": round(support, 3),
        }
    return records


def check_plotter(work):
    verifier = [sys.executable, "scripts/verify.py"]

    def run():
        proc = subprocess.run(verifier, cwd=work, text=True, capture_output=True)
        result = json.loads((work / "reports/verification.json").read_text())
        return proc.returncode, result

    status, accepted = run()
    if status or not accepted["artifact_integrity"] or not accepted["requirements_met"]:
        raise ValueError("Supplied plotter failed replay")
    # Change the command stream independently of the published CSV trajectory.
    path = work / "simulation/example.gcode"
    with path.open("a") as f:
        f.write("\nG1 X999.000 Y999.000 Z0.000 F1000\n")
    status, rejected = run()
    if not status or rejected["artifact_integrity"]:
        raise ValueError("Deliberate command/trajectory mismatch was accepted")
    return {
        "accepted_checks": len(accepted["checks"]),
        "drawing_area_mm": [100, 80],
        "mount_pitch_mm": accepted["metrics"]["mount_pitch_mm"],
        "adverse_control": "Extra out-of-envelope move in temporary command stream",
        "rejecting_checks": [r["name"] for r in rejected["checks"] if not r["passed"]],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--publish", action="store_true")
    args = p.parse_args()
    if not all(find_spec(name) for name in ("cadquery", "trimesh")):
        local = next(
            (
                root / ".cache/hardware-splicer/digital-native-venv/bin/python"
                for root in HERE.parents
                if root.parent != root
                if (
                    root / ".cache/hardware-splicer/digital-native-venv/bin/python"
                ).is_file()
            ),
            None,
        )
        cad = os.environ.get("HS_CAD_PYTHON", str(local or ""))
        if (
            Path(cad).absolute() == Path(sys.executable).absolute()
            or not Path(cad).is_file()
        ):
            raise SystemExit("Set HS_CAD_PYTHON to a Python with CadQuery and trimesh.")
        os.execv(cad, [cad, __file__, *sys.argv[1:]])
    with tempfile.TemporaryDirectory() as td:
        for ident, check in [("P001", check_dock), ("P002", check_plotter)]:
            folder = HERE / ident
            work = Path(td) / ident
            with ZipFile(folder / "design-release.zip") as release:
                release.extractall(work)
            result = check(work)
            saved = folder / "trial.json"
            if args.publish:
                saved.write_text(json.dumps(result, indent=2) + "\n")
            if result != json.loads(saved.read_text()):
                raise ValueError(f"{ident} changed on replay")
            print(ident, "release and adverse control verified")


if __name__ == "__main__":
    main()
