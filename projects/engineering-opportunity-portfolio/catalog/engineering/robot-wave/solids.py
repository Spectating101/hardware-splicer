"""Build and independently reopen three prototype tooling sets. Requires CadQuery 2.8."""

import argparse
import json
import math
from pathlib import Path
import tempfile
import cadquery as cq

HERE = Path(__file__).resolve().parent
D = json.loads((HERE / "designs.json").read_text())


def block(w, h, t, x=0, y=0, z=0):
    return cq.Solid.makeBox(w, h, t, cq.Vector(x, y, z))


def pin(x, y, dia, h, z=-1):
    return cq.Solid.makeCylinder(dia / 2, h, cq.Vector(x, y, z))


def throat(d):
    # Monolithic side gauge. Insert flat samples into the mouth from +X.
    def gauge(gap):
        return (
            block(36, 18, 7)
            .fuse(block(5, 18, gap, 0, 0, 7), block(36, 18, 7, 0, 0, 7 + gap))
            .clean()
        )

    return {"revised-mouth": gauge(d["gate"]), "original-mouth": gauge(d["old_gate"])}


def jaws(d):
    # Section coupon for the stationary jaw. The opposing jaw is screw-mounted on a test block.
    def shoe(gap):
        return (
            block(10 + gap, 30, 4)
            .fuse(block(5, 30, 14, 0, 0, 4), block(5, 30, 14, 5 + gap, 0, 4))
            .clean()
        )

    return {
        "max-thickness-seat": shoe(d["jaw_max_gap"]),
        "original-seat": shoe(d["old_gap"]),
    }


def corner(d):
    leg, w, t = d["leg_length"], d["rail_mm"], d["plate_thickness"]
    blank = block(leg, w, t).fuse(block(w, leg, t)).clean()
    for pitch in d["hole_pitch_from_corner"]:
        for x, y in [(pitch, w / 2), (w / 2, pitch)]:
            blank = blank.cut(pin(x, y, d["hole_diameter"], t + 2))
    return {"rail-corner-plate": blank.clean()}


def clearance_checks(i, models):
    d = D[i]
    if i == "P191":
        plate = models["rail-corner-plate"]
        w, t = d["rail_mm"], d["plate_thickness"]
        holes = 0
        for pitch in d["hole_pitch_from_corner"]:
            for x, y in [(pitch, w / 2), (w / 2, pitch)]:
                if (
                    plate.intersect(pin(x, y, d["hole_diameter"] - 0.01, t)).Volume()
                    > 1e-6
                ):
                    raise ValueError("Pierced bolt axis is obstructed")
                holes += 1
        expected = (
            2 * w * d["leg_length"]
            - w * w
            - holes * math.pi * (d["hole_diameter"] / 2) ** 2
        ) * t
        if abs(plate.Volume() - expected) > 0.001:
            raise ValueError("Rail bracket material differs from four-hole drawing")
        seat = max(d["hole_pitch_from_corner"])
        washer = pin(seat, w / 2, d["washer_diameter"], 1, z=t)
        collisions = []
        for start in [d["pad_start"], d["old_pad_start"]]:
            pad = block(
                d["leg_length"] - start + d["pad_position_error"],
                w,
                1,
                start - d["pad_position_error"],
                0,
                t,
            )
            collisions.append(washer.intersect(pad).Volume())
        if collisions[0] > 1e-6 or collisions[1] < 0.5:
            raise ValueError("Washer/pad control mismatch")
        return {
            "bolt_holes": holes,
            "plate_mm3": round(plate.Volume(), 3),
            "revised_pad_on_washer_mm3": round(collisions[0], 3),
            "old_pad_on_washer_mm3": round(collisions[1], 3),
        }
    if i == "P182":
        # Test from the open side, away from the closed wall.
        sample = block(25, 15, d["max_thick"] + d["gap_error"], 8, 1, 7)
        double = block(
            25,
            15,
            2 * d["min_thick"] * (1 - d["compression"]) - d["gap_error"],
            8,
            1,
            7,
        )
        good = models["revised-mouth"]
        old = models["original-mouth"]
        v = [
            good.intersect(sample).Volume(),
            good.intersect(double).Volume(),
            old.intersect(double).Volume(),
        ]
        if not (v[0] < 1e-6 and v[1] > 1 and v[2] < 1e-6):
            raise ValueError("Puck gauge did not distinguish tolerance coupons")
        return dict(
            zip(
                [
                    "single_overlap_mm3",
                    "revised_double_overlap_mm3",
                    "old_double_overlap_mm3",
                ],
                map(lambda x: round(x, 3), v),
            )
        )
    coupon = block(d["board_max_thick"] + d["gap_error"], 26, 12, 5, 2, 4)
    volumes = [
        models[name].intersect(coupon).Volume()
        for name in ["max-thickness-seat", "original-seat"]
    ]
    if not volumes[0] < 1e-6 or not volumes[1] > 1:
        raise ValueError("Cradle board thickness control mismatch")
    return {
        "revised_coupon_overlap_mm3": round(volumes[0], 3),
        "original_coupon_overlap_mm3": round(volumes[1], 3),
    }


def measure(path):
    solid = cq.importers.importStep(str(path)).solids().vals()
    if len(solid) != 1 or not solid[0].isValid():
        raise ValueError(f"Invalid exported solid: {path}")
    return solid[0]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--publish", action="store_true")
    args = p.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        for ident, builder in {"P182": throat, "P188": jaws, "P191": corner}.items():
            folder = HERE / ident / "solids"
            work = folder if args.publish else Path(tmp) / ident
            work.mkdir(exist_ok=True, parents=True)
            source = builder(D[ident])
            fresh = {}
            shipped = {}
            for name, model in source.items():
                file = work / (name + ".step")
                cq.exporters.export(model, str(file))
                fresh[name] = measure(file)
                shipped[name] = measure(folder / file.name)
                difference = (
                    fresh[name].cut(shipped[name]).Volume()
                    + shipped[name].cut(fresh[name]).Volume()
                )
                if difference > 1e-5:
                    raise ValueError(f"{name} differs from published geometry")
            results = clearance_checks(ident, fresh)
            saved = folder / "fit.json"
            if args.publish:
                saved.write_text(json.dumps(results, indent=2) + "\n")
            if clearance_checks(ident, shipped) != results or results != json.loads(
                saved.read_text()
            ):
                raise ValueError(f"Fit results changed for {ident}")
            print(ident, results)


if __name__ == "__main__":
    main()
