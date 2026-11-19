"""Run the two full-platform decision screens offline. Neither opens a device interface."""

import argparse
import csv
import itertools
import json
import math
from pathlib import Path
import tempfile

import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation

from P049.cell import ORIENTATION, chain, forward, targets

HERE = Path(__file__).resolve().parent


def save_csv(path, headers, rows):
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)


def vehicle(p, dest):
    rows = []
    for rev, key in [
        ("small floats", "old_foam_pair_mm"),
        ("revised floats", "foam_pair_mm"),
    ]:
        for hull, mass, tether, rho, delta in itertools.product(
            p["hull_displaced_cm3"],
            p["mass_g"],
            p["effective_submerged_tether_load_g"],
            p["freshwater_g_cm3"],
            [-p["foam_dim_error_mm"], p["foam_dim_error_mm"]],
        ):
            external_float_cm3 = 2 * math.prod(n + delta for n in p[key]) / 1000
            net_g = (hull + external_float_cm3) * rho - mass - tether
            rows.append(
                (
                    rev,
                    hull,
                    mass,
                    tether,
                    rho,
                    delta,
                    round(net_g, 4),
                    round(p["assumed_down_thrust_equivalent_g"] - net_g, 4),
                )
            )
    save_csv(
        dest / "buoyancy.csv",
        [
            "revision",
            "enclosed_displacement_cm3",
            "fully_equipped_mass_g",
            "effective_tether_g",
            "density_g_cm3",
            "float_dim_error_mm",
            "net_up_equivalent_g",
            "remaining_down_authority_g",
        ],
        rows,
    )
    revised = [r for r in rows if r[0] == "revised floats"]
    small = [r for r in rows if r[0] == "small floats"]
    low = min(r[-2] for r in revised)
    old = min(r[-2] for r in small)
    down = min(r[-1] for r in revised)
    if not old < 0 < low or down <= 0:
        raise ValueError("Float budget or control failed")
    return {
        "cases": len(rows),
        "minimum_upward_reserve_g": low,
        "worst_small_float_reserve_g": old,
        "minimum_down_authority_g": down,
    }


def arm(p, dest):
    origins, bounds = chain()
    rows = []
    result = {}
    for rev, x in [("revised", p["station_x_mm"]), ("far", p["old_station_x_mm"])]:
        q = np.zeros(5)
        worst_pos = worst_ori = worst_home = 0
        for phase, point in targets(dict(station_x_mm=x, lift_mm=p["lift_mm"])):

            def error(angles):
                pose = forward(origins, angles)
                rot = Rotation.from_matrix(ORIENTATION.T @ pose[:3, :3]).as_rotvec()
                return np.r_[pose[:3, 3] - point, rot * 75]

            q = least_squares(error, q, bounds=bounds, max_nfev=60).x
            e = error(q)
            pos = float(np.linalg.norm(e[:3]))
            ori = math.degrees(float(np.linalg.norm(e[3:])) / 75)
            biased = q.copy()
            biased[0] += math.radians(p["home_error_degrees"])
            bias = float(np.linalg.norm(error(biased)[:3]))
            rows.append(
                (
                    rev,
                    phase,
                    *[round(float(v), 4) for v in point],
                    *[round(float(v), 7) for v in q],
                    round(pos, 5),
                    round(ori, 5),
                    round(bias, 5),
                )
            )
            worst_pos = max(worst_pos, pos)
            worst_ori = max(worst_ori, ori)
            worst_home = max(worst_home, bias)
        result[rev] = {
            "max_position_error_mm": round(worst_pos, 4),
            "max_orientation_error_deg": round(worst_ori, 4),
            "shoulder_home_bias_max_position_error_mm": round(worst_home, 4),
        }
    save_csv(
        dest / "cold-transfer.csv",
        [
            "layout",
            "phase",
            "target_x_mm",
            "target_y_mm",
            "target_z_mm",
            "pan_rad",
            "lift_rad",
            "elbow_rad",
            "flex_rad",
            "roll_rad",
            "error_mm",
            "orientation_deg",
            "home_error_mm",
        ],
        rows,
    )
    if not (
        result["revised"]["max_position_error_mm"] <= p["position_limit_mm"]
        and result["revised"]["max_orientation_error_deg"] <= p["orientation_limit_deg"]
        and result["far"]["max_position_error_mm"] > p["position_limit_mm"]
        and result["revised"]["shoulder_home_bias_max_position_error_mm"]
        > p["position_limit_mm"]
    ):
        raise ValueError("Arm pose or calibration control failed")
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--publish", action="store_true")
    args = p.parse_args()
    inputs = json.loads((HERE / "cases.json").read_text())
    with tempfile.TemporaryDirectory() as td:
        for ident, study in [("P031", vehicle), ("P049", arm)]:
            out = HERE / ident if args.publish else Path(td) / ident
            out.mkdir(exist_ok=True)
            data = study(inputs[ident], out)
            (out / "results.json").write_text(json.dumps(data, indent=2) + "\n")
            if not args.publish:
                for f in out.iterdir():
                    if f.read_bytes() != (HERE / ident / f.name).read_bytes():
                        raise ValueError(f"Replay differs for {ident}/{f.name}")
            print(ident, data)


if __name__ == "__main__":
    main()
