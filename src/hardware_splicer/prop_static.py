"""Static (hover) thrust and shaft power of a small propeller from the UIUC Propeller Database's measured coefficients.

    python -m hardware_splicer.prop_static UIUC-propDB.zip gwsdd_3x3 --thrust-g 55.5

The UIUC files give CT and CP against rpm, measured on a load cell (static, no forward speed). With n in rev/s and D
the diameter: T = CT rho n^2 D^4, P = CP rho n^3 D^5. The rpm where T equals the target is found by interpolating CT
over the measured range only; outside it the answer is refused rather than extrapolated. The figure of merit compares
the ideal (momentum-theory) power, T^1.5 / sqrt(2 rho A), with the shaft power.

The database is not redistributed here (its pages state no licence); download it from
https://m-selig.ae.illinois.edu/props/propDB.html and cite it as the site asks: J.B. Brandt, R.W. Deters, G.K. Ananda,
O.D. Dantsker and M.S. Selig, UIUC Propeller Database, Vols 1-4, University of Illinois at Urbana-Champaign.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import zipfile
from pathlib import Path
from typing import Any

SCHEMA = "hardware_splicer.prop_static.v1"
RHO = 1.225
G = 9.80665


def diameter_m(prop: str) -> float:
    """gwsdd_3x3 -> 3 in; apcff_4.2x4 -> 4.2 in (UIUC names are brand_DIAMETERxPITCH in inches)."""
    return float(re.search(r"_(\d+(?:\.\d+)?)x", prop).group(1)) * 0.0254


def load(zip_path: Path, prop: str) -> list[tuple[float, float, float]]:
    with zipfile.ZipFile(zip_path) as z:
        names = sorted(n for n in z.namelist() if re.search(rf"/{re.escape(prop)}_static_[^/]*\.txt$", n))
        if not names:
            raise KeyError(f"no static file for {prop}")
        text = z.read(names[0]).decode("ascii", errors="replace")
    rows = []
    for line in text.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 3:
            rows.append((float(parts[0]), float(parts[1]), float(parts[2])))
    return sorted(rows)


def hover(zip_path: Path, prop: str, thrust_g: float) -> dict[str, Any]:
    rows, d = load(zip_path, prop), diameter_m(prop)
    target = thrust_g / 1000 * G
    thrust = [(rpm, ct * RHO * (rpm / 60) ** 2 * d ** 4, ct, cp) for rpm, ct, cp in rows]
    for (r0, t0, ct0, cp0), (r1, t1, ct1, cp1) in zip(thrust, thrust[1:]):
        if t0 <= target <= t1:
            f = (target - t0) / (t1 - t0)
            rpm, cp = r0 + f * (r1 - r0), cp0 + f * (cp1 - cp0)
            power = cp * RHO * (rpm / 60) ** 3 * d ** 5
            ideal = target ** 1.5 / math.sqrt(2 * RHO * math.pi * d ** 2 / 4)
            return {"schema_version": SCHEMA, "prop": prop, "diameter_m": round(d, 4), "thrust_g": thrust_g, "rpm": round(rpm),
                    "shaft_power_w": round(power, 3), "ideal_power_w": round(ideal, 3), "figure_of_merit": round(ideal / power, 3),
                    "measured_range": {"rpm": [rows[0][0], rows[-1][0]], "thrust_g": [round(thrust[0][1] / G * 1000, 1), round(thrust[-1][1] / G * 1000, 1)]},
                    "source": "UIUC Propeller Database, Vols 1-4 (Brandt, Deters, Ananda, Dantsker, Selig), static data",
                    "claim_boundary": "Shaft power of this measured propeller; motor and ESC losses are not included."}
    raise ValueError(f"{thrust_g} g is outside {prop}'s measured range "
                     f"({thrust[0][1] / G * 1000:.1f}-{thrust[-1][1] / G * 1000:.1f} g); not extrapolated")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("zip", type=Path)
    parser.add_argument("prop")
    parser.add_argument("--thrust-g", type=float, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(hover(args.zip, args.prop, args.thrust_g), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
