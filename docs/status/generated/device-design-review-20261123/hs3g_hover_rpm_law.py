"""Cross-check the HS-3G-B hover point against the propeller's own measured thrust/RPM law.

The maker's table (examples/drone_proving_ground/digital/reference/thrust-table.json) starts at
50% throttle. Thrust scales with RPM^2 for a fixed propeller; if the measured rows follow that law,
hover RPM and power can be estimated from the law instead of from the throttle curve.
"""
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
ref = ROOT / "examples/drone_proving_ground/digital/reference"
rows = np.array(json.loads((ref / "thrust-table.json").read_text())["props"]["GF3028-3"])
mass_g = json.loads((ref / "model.json").read_text())["mass_kg"] * 1000
thrust, volts, rpm, power = rows[:, 1], rows[:, 2], rows[:, 4], rows[:, 5]
k = thrust / rpm**2
b, la = np.polyfit(np.log(rpm), np.log(thrust), 1)
bp, lp = np.polyfit(np.log(rpm), np.log(power), 1)
hover = mass_g / 4
r_h = (hover / np.exp(la)) ** (1 / b)
p_h = np.exp(lp) * r_h**bp
print(json.dumps({
    "mass_g": round(mass_g, 1), "hover_thrust_per_motor_g": round(hover, 1),
    "lowest_measured_row": {"throttle_pct": rows[0, 0], "thrust_g": rows[0, 1], "rpm": rows[0, 4]},
    "thrust_per_rpm2_spread_pct": round(float((k.max() - k.min()) / k.mean() * 100), 1),
    "fitted_thrust_exponent": round(float(b), 2), "fitted_power_exponent": round(float(bp), 2),
    "hover_rpm_estimate": round(float(r_h)), "hover_rpm_fraction_of_lowest_measured": round(float(r_h / rows[0, 4]), 2),
    "hover_power_per_motor_w": round(float(p_h), 1),
    "hover_current_total_a_at_measured_voltage": round(float(4 * p_h / volts.mean()), 2),
}, indent=1))
