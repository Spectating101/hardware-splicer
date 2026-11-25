# HS-ARM-A: a 5-axis desktop arm with a gripper

![HS-ARM-A at three poses](renders/HS_ARM_A_POSES.png)

An original arm designed end to end in this repository: requirement, actuator choice from cited data, printable parts,
assembly, URDF, collision sweep, workspace, power budget and a priced BOM. Nothing has been printed or built yet.

| Requirement (given) | Result | Where |
|---|---|---|
| Reach at least 300 mm | 376 mm from the yaw axis to the grasp point | `verification.json` reach_mm |
| 150 g payload, safety factor 1.5, at most 50% of stall torque (assumed derating) | shoulder 49%, elbow 29%, wrist 40% | static_torque |
| Prints on a 220 x 220 x 250 mm bed | 7 parts, all fit, each one solid, 322 g of PLA | parts |
| No self-collision | every joint swept over its limits, 0 clashes | `motion_sweep.json` |
| Pick from the table | any approach 125-365 mm out; straight down only 125-180 mm | pick_workspace |

## Parts

Joint servos (ROBOTIS e-manual figures): XM430-W350-T at base yaw, shoulder and elbow (4.1 N m stall at 12 V, 82 g);
XL430-W250-T at wrist pitch, wrist roll and gripper (1.5 N m, 57.2 g). Bus: U2D2 plus U2D2 Power Hub from a 12 V 5 A
supply, daisy-chained X3P cables. Priced in `BOM.json`: **US$1,089.50**, of which US$1,054.50 is cited from shop pages; the
three XM430s are 75% of it.

Printed in PLA (`print/*.step` and `.stl`): base housing with a support ring, turntable, upper arm, forearm, wrist,
gripper base with fixed jaw, moving jaw.

## What the checks changed in the design

* **Base bearing.** The arm's overturning moment on the base servo is 1.35 N m, 3.4x the horn's rated side load
  (40 N at 10 mm). The turntable therefore rides on a ring in the housing with a 1 mm PTFE washer, not on the servo.
* **Clamp the base.** A free-standing base (0.22 kg) cannot hold the stretched arm (0.16 N m restoring against 1.35 N m).
  Bolt it down through the four M5 holes or clamp it.
* **Wrist length.** The roll servo needs at least 68.3 mm behind the wrist-pitch axis; the build refuses anything shorter.
* **Gripper jaw.** The first jaw clashed with its own servo at 10 degrees; its bar now starts outside the servo's swing radius
  (18.2 mm) and the jaw opens 0-70 degrees clear. A first fixed jaw was a floating piece; the build now fails on any
  printed part that is not one body.
* **Joint limits** are the swept clear ranges less 5 degrees: shoulder -150..+15 (positive is down), elbow -105..+85,
  wrist pitch +/-105, yaw and roll +/-150.

## Power

Holding the stretched arm draws about 1.6 A (current scaled from the cited stall currents). All six servos stalled at once
would draw 11.1 A, over the power hub's 10 A rating and the 5 A supply; the servos' overload shutdown, not the supply, is
the protection in that case.

## Not modelled yet (check before printing)

* Horn bolt circle and servo side-screw holes: the parts have none. Take them from the real horn, or the ROBOTIS drawing
  (its download centre links were dead on 2026-11-26).
* Idler horn thickness (4 mm assumed).
* Part strength: no FEM on the links; PLA at 60% effective fill is assumed for mass only.
* Inertia is a box proxy; no dynamic or acceleration torque, no friction.
* Cable routing.

## Rebuild

```bash
NATIVE=.cache/hardware-splicer/digital-native-venv/bin/python
$NATIVE -I projects/hs-arm-a/build_arm.py                      # parts, assembly, URDF, verification.json
$NATIVE -I src/hardware_splicer/motion_sweep.py --urdf projects/hs-arm-a/urdf/hs_arm_a.urdf --steps 31 > projects/hs-arm-a/motion_sweep.json
python3 projects/hs-arm-a/workspace.py                          # pick workspace into verification.json
$NATIVE -I projects/hs-arm-a/render.py                          # renders/HS_ARM_A_POSES.png
```

Servo geometry: body dimensions from the ROBOTIS e-manual; horn diameter and its 12 mm offset measured from the XM430 in
ROBOTIS's OpenMANIPULATOR-X model (`link1.stl`, Apache-2.0). The arm itself is HS's own design, not a copy of that kit.
