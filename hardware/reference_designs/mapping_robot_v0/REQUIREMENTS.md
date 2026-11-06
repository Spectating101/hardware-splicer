# Mapping robot v0: part requirements (search criteria for Build 1)

Derived 2026-11-06 by `sizing.py` through HS `robotics_simulation`, using class-typical figures
(`typical_class.json`, every figure labelled typical) and `assumptions.json`. These are search criteria, not
properties of any chosen part. Re-run with the chosen parts in Task 9.

Targets (design spec): 0.2 m/s continuous mapping for 60 minutes with LiDAR, microcontroller and on-board computer
running; speed margin at least 1.5; fit through a 70 cm door.

HS result for the typical class: 1.10 kg robot, 16.1 W average, 86 min runtime, 58.8 rpm needed at a 65 mm wheel,
speed margin 2.36, force margin 9.1 (acceleration and rolling only).

| Part | Requirement | Where it comes from |
|---|---|---|
| Drive motor | free speed at pack voltage ≥ 88 rpm (65 mm wheel) and ≤ 350 rpm | HS: 58.76 rpm × 1.5 margin; upper bound is designer's call so encoder counts stay useful at 0.2 m/s |
| Drive motor | stall torque ≥ 0.25 N·m per motor at pack voltage | designer's call, see threshold note; HS alone asks only 0.014 N·m |
| Drive motor | quadrature encoder, counts per wheel revolution derivable | spec (odometry for SLAM) |
| Drive motor | rated voltage ≥ pack nominal voltage | `sizing.py` fails a pack above the motor rating |
| Wheel | 60-80 mm outer diameter (requirements above assume 65 mm; re-run if different) | designer's call |
| LiDAR | 2D, range ≥ 6 m, documented protocol with an open decoder | spec / plan Task 6 |
| Battery pack | finished Li-ion pack with BMS; energy ≥ 25 Wh (HS minimum 20.1 Wh + margin); ≥ 1810 mAh at 11.1 V | HS: 16.07 W × 1 h ÷ 0.8 usable |
| Battery pack | max discharge ≥ 4.5 A | 2 motor stalls (2 × 1.5 A typical) + electronics at pack voltage (0.85 A) + margin |
| Buck converter | 5 V output rated ≥ compute peak current + LiDAR current + 0.5 A | designer's call |
| Compute board | 64-bit, runs a ROS 2 tier-1 platform (Ubuntu arm64) with SLAM Toolbox and Nav2 | spec |
| Whole robot | width ≤ 350 mm (half a 70 cm door) | checked by the chassis plan, not here |

**Threshold note (designer's call).** HS's drive model has no slope or step term (logged in `GAP_LOG.md`). A 10 mm
door threshold on a 65 mm wheel needs a horizontal push of about 1.04 × the load on the driven wheels
(√(h(2r−h)) / (r−h) with h = 10 mm, r = 32.5 mm). With about 70% of 1.1 kg on the drive wheels that is 7.5 N, or
0.12 N·m per motor at the wheel radius; doubled for margin, 0.25 N·m stall torque per motor.
