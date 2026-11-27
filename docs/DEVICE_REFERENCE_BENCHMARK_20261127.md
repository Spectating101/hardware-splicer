# Open whole-device designs as HS's benchmark (2026-11-27)

HS designs whole devices (arm, rover, drone, sub). The yardstick is the open designs other people have published and
built. `python -m hardware_splicer.device_reference_sweep` finds them by category on GitHub (keywords, topics and a few
flagship seeds), scores them like `github_data_sources`, and lists each repository's files to see whether the design is
really there. Results: `examples/device_references/sweep_20261127.json`.

## What the sweep found

| Category | Repositories found | Checked | Complete open designs (4-5 of CAD, PCB, firmware, BOM, assembly; licensed) |
|---|---|---|---|
| robot vacuum | 73 | 30 | 0 |
| mopping floor robot | 29 | 29 | 0 |
| window pool cleaner | 35 | 29 | 0 |
| lawn mower | 52 | 31 | 0 |
| multirotor drone | 72 | 32 | 0 |
| fixed wing vtol | 51 | 30 | 0 |
| underwater rov | 77 | 31 | 1: bgreig/TinkerSub |
| surface vessel | 42 | 30 | 0 |
| ground rover | 61 | 32 | 2: ob-f/OpenBot, nasa-jpl/open-source-rover |
| camera security robot | 54 | 31 | 0 |
| robot arm | 72 | 33 | 6: Source-Robotics/PAROL6-Desktop-robot-arm, roboninecom/SO-ARM100-101-102-Parallel-Gripper, roboninecom/SO-ARM102 |
| quadruped | 51 | 30 | 1: real-stanford/umi-on-legs |
| humanoid biped | 77 | 31 | 2: Roboparty/roboto_origin, menloresearch/asimov-1 |
| balance desktop robot | 67 | 31 | 1: Source-Robotics/PAROL6-Desktop-robot-arm |
| robotic hand gripper | 76 | 36 | 2: roboninecom/SO-ARM100-101-102-Parallel-Gripper, roboninecom/SO-ARM102 |
| delivery agv | 54 | 30 | 0 |
| machine 3dprinter cnc | 66 | 29 | 1: Creality3DPrinting/Ender-3 |

975 repositories found, 493 checked file by file, 13 complete and licensed.

**Complete open designs are rare.** Most repositories are software (ROS stacks, simulations, firmware for commercial
hardware such as Valetudo for robot vacuums) or a single part of a device. Categories with no complete, licensed open
design in the checked set are open ground for HS, not a sign HS is behind; but read the top results by hand before
saying so (the robot vacuum row below was wrong until OOMWOO was read).

Limits: the file check is a floor. Projects that keep hardware in git submodules (OpenMower) or sibling repositories
(OpenArm, Petoi, NASA's rover software, Stanford Pupper, OOMWOO) score low here although the design exists; their submodules are
listed. Files present show a design was published, not that it was built. An unlicensed repository (Ardumower, several
mowers) is listed, never absorbed.

## First comparison: HS-ARM-A against SO-ARM100/101 and PAROL6

| | HS-ARM-A (HS, 26 Nov) | SO-ARM101 (TheRobotStudio, Apache-2.0, 8.2k stars) | PAROL6 (Source Robotics, CERN-OHL-S) |
|---|---|---|---|
| Axes | 5 + gripper | 5 + gripper | 6 |
| Reach | 376 mm | not stated in README | 408 mm |
| Payload | 150 g (HS check: 50% of stall, safety factor 1.5) | not stated in README | 0.5-1 kg |
| Actuators | 3 x XM430-W350 + 3 x XL430 | 6 x Feetech STS3215 | steppers |
| Cost | US$1,089.50 (BOM.json) | US$229.88 for leader + follower kit (README BOM, US) | not checked |

**What the comparison changed in HS.** HS's cited servo table had the STS3215 but no mass, so the lightest-servo picker
skipped it and HS-ARM-A got three XM430s at US$269.90 each. With Feetech's listed 55 g and Waveshare's 6-12.6 V range
(cited in `data/actuators/cited_servos_20261127.json`), HS's own sizing picks the 12 V STS3215 at every HS-ARM-A joint,
each under 30% of stall, inside HS-ARM-A's own 50% rule: the three joint servos drop from about US$810 to about US$42
and from 82 g to 55 g each. The 7.4 V version is kept off 12 V supplies.

**Rev B built (same day).** `projects/hs-arm-a/rev-b`: the arm rebuilt around the STS3215, its geometry measured from
SO-ARM100's own servo model. Printed cheek bosses keep every joint clash-free over rev A's ranges. Parts US$206.49
against US$1,089.50; moving mass 0.456 kg against 0.516 (0.459 before its screw holes were cut); reach 370.5 mm against 375.9.

The full CAD check (link and bracket masses included, which the quick sizing tool leaves out) puts rev B's shoulder at
66% of stall with 150 g and safety factor 1.5: over HS's own 50% rule (about 63 g at the rule). The same method on
SO-101's published URDF gives its shoulder 80% of its 7.4 V servo's stall with no payload and 136% with 150 g, so HS's
rule is stricter than the reference that thousands of people run, and rev B keeps more margin than SO-101. HS's rule is
left as it is; the two readings are reported side by side.

## Second comparison: HS-ROVER-A against OpenBot and NASA-JPL's Open Source Rover

| | HS-ROVER-A (HS, 26 Nov) | OpenBot (MIT, 3.7k stars) | Open Source Rover (Apache-2.0, 9.8k stars) |
|---|---|---|---|
| Cost | US$263.44, all lines cited (over its US$250 target) | "about $50" body, plus a smartphone (README) | "~$1600" (README) |
| Drive | 2WD Pololu 25D MP 47:1 plus caster, sized against the maker's limits | 4 x TT gearmotors, L298N | 6 wheels, rocker-bogie, 10 motors |
| Speed / runtime | 0.79 m/s; about 5 h on 2.2 Ah cells at 4.0 W | not stated | ~1.6 m/s; "at least 3 hours" on 7.2 Ah, rough terrain |
| Brain | ESP32 + camera | the phone | Raspberry Pi |

HS-ROVER-A sits between the two: five times OpenBot's body cost for sized motors and a stated runtime, a sixth of the
OSR's for flat-floor inspection only. HS's salvage rover (HS-ROVER-SALVAGE-A) already builds on OpenBot.

**What the comparison changed in HS.** As with the arm, HS could not pick the cheap tier: its drive table held only
Pololu gearmotors. Adafruit's TT gearmotor (product 3777: 200 rpm and 0.8 kg.cm stall at 6 V, 150 mA no-load, 30.6 g)
is now in it, and passes HS-ROVER-A's speed and torque requirements. The seller publishes no torque limits, so those checks read unknown rather than passed. (This page first said no
stall current either; Adafruit's page has a one-motor bench measurement, 1.5 A at 6 V, now used.)

## Third comparison: HS-3G-B against the open multirotors

The sweep's drone category is mostly flight software (Betaflight, INAV, ExpressLRS, PX4 tooling). Read file by file, the
open whole aircraft are:

| | HS-3G-B (HS, 16 Nov) | Crazyflie 2.0/2.1 (Bitcraze) | ESP-Drone (Espressif) | Flix (okalachev, 2.6k stars) | SRD-1 (MilosRasic98) |
|---|---|---|---|---|---|
| Class | 3 in brushless, GPS, analog FPV, 137 mm | 92 mm nano, brushed coreless, 1S | ESP32-S2 nano, brushed | ESP32, 8520 brushed, printed frame | 450-class, 2212 motors, Arduino Nano FC |
| Mass | 234.9 g (model) | 27 g / 29 g; 42 g maximum takeoff | not read | not read | aim below 1.75 kg (README) |
| Flight time | 11.4 min hover (model, extrapolated below the maker's table) | 7 min with stock battery (datasheet) | not read | not read | not stated |
| Published | frame STEP/STL/DXF, BOM, wiring, partial INAV config | firmware (GPL-3.0), KiCad electronics (CC BY-NC-SA 3.0: non-commercial, not absorbed) | firmware (GPL-3.0), schematic PDF, BOM | frame STL/STEP, firmware, Gazebo simulation, assembly guide; no licence file | CAD, firmware (MIT) |
| Flight controller | bought stack (SpeedyBee F405 Mini) | own board | own board | ESP32 module + IMU breakout | Arduino Nano + MPU6050 |
| Flown | no | yes | yes | yes (videos, user builds) | yes (videos) |

No open, complete design was found in HS-3G-B's class (sub-250 g, GPS, 3 in). The open aircraft are either nano
educational quads or 450-class frames, and the open FPV designs are frames only (TBS Source One V6, DXF and STL, has no licence
file; source_micro is GPL-3.0). Against them HS-3G-B is the only package that sizes its power system against the makers' limits and
ships cut files, and the only one never flown. Three of the four reference projects design their own flight
controller; HS-3G-B buys one.

**What the comparison changed in HS.**

- *Calibration.* Bitcraze publishes its whole-aircraft bench table (thrust, current and voltage at 16 PWM steps). HS's
  propulsion check on that table predicts 7.1 min for the 27 g, 240 mAh Crazyflie 2.0 when the whole pack is used, against
  Bitcraze's 7 min, and 5.7 min with HS's default of landing at 80% of capacity. Cutting the table's low rows to force
  the extrapolation HS-3G-B relies on (up to 1.7 times below the lowest row) moves the hover power by under 12%. Both are
  now tests. A brushless aircraft agrees: the Crazyflie 2.1 Brushless (34 g, 350 mAh, "10 minutes", at least 5 g/W at
  hover by Bitcraze's own figure) comes out at 10.0 min on the whole pack and 8.0 at HS's default. The same aircraft
  shows why the check takes the more pessimistic extrapolation: the ideal 1.5-power law from its motor's peak point
  (30 g at 7.2 W) would claim about 7.8 g/W at hover, over 50% better than measured. Holybro's X500 V2 states 18 min but
  not its takeoff mass, so it cannot calibrate anything yet (`data/propulsion/calibration_aircraft_20261127.json`).
- *Rules against practice.* Bitcraze's 42 g maximum takeoff is a thrust-to-weight of 1.4; HS's default floor is 2.0, so
  HS is again stricter than the maker. HS-3G-B (5.0) is unaffected; the floor is left as it is.
- *Motor choice.* HS's four cited thrust tables sat in the proving-ground folders and the check needed one passed in.
  They are now one library (`data/propulsion/thrust_tables_20261127.json`, with Bitcraze's added), each with its motor
  mass and prop diameters, and `propulsion_check.pick` (tool `hs_pick_propulsion`) tries every motor and prop, adding each
  option's own motor mass and checking its props fit the frame. On HS-3G-B's frame only the two F1404 motors pass;
  without a frame the 58.5 g SunnySky on 9 in props would pass at 431 g, which is why the frame check matters.
- *A disagreement it exposed, and settled.* The general check refused HS-3G-B's own F1404 2900KV table: the maker
  measured it on a charged 16.8 V pack, 13% above the 4S nominal voltage, past the check's 10% limit, while HS-3G-B's
  design script used it. At a given thrust a prop needs the same speed and torque whatever the supply, so hover power
  carries over (if anything the higher-voltage figure is the larger); full-throttle thrust falls roughly with the square
  of the voltage. The check now accepts a table measured on a charged pack of the same cell count, with a warning: hover
  power from the table, full-throttle thrust scaled to nominal, full-throttle current kept at the higher bench figure. It
  then reproduces HS-3G-B's 11.4 min, 3.58 A hover and 25.8 A full throttle exactly, and corrects one claim: HS-3G-B's
  thrust-to-weight is 5.0 on a full pack and about 3.9 at nominal voltage. A table from a smaller pack (3S on 4S) is still
  refused.

## Fourth comparison: robot vacuums, and OOMWOO

**Correction.** This page first said no open robot vacuum design exists. The sweep's top vacuum result, makerspet/OOMWOO
(Apache-2.0, 13.2k stars, pushed 27 Nov), is one; it scored 3 of 5 only because its CAD (oomwoo-cad: Fusion and STEP),
boards (oomwoo-pcb: KiCad main, side, front and dock boards) and ROS2 simulation (oomwoo-one) live in sibling
repositories. Its own README says it is not buildable yet: simulation runs today, the bill of materials is rough and
awaiting validation on real hardware. Everything else in the category is software for commercial robots (Valetudo,
Home Assistant integrations, Roomba Open Interface libraries) or a teardown (remakeai, Apache-2.0).

OOMWOO's design choice is HS's: it builds the robot from robot-vacuum spare parts (Roborock drive wheel modules,
Dreame and Nidec suction fans, Xiaomi and Dreame laser scanners, Roborock battery packs), printed parts and its own I/O
board, aiming at about US$200 of parts plus a Raspberry Pi to match a US$500-600 commercial robot.

| | OOMWOO One (in development) | HS today |
|---|---|---|
| Parts route | buy each spare module (wheel pair US$24-33, fan US$10-28, scanner US$13-32, pack US$16-30) | buy one faulty LiDAR vacuum that holds all of them (Ruten, 27 Nov: NT$1,000-2,625 for a 1st-gen Xiaomi) |
| Mechanical | 3D-scanned part library, Fusion design | none for a vacuum; OOMWOO's scanned envelopes now in HS |
| Electronics | own CH32V307 + CH32L103 I/O board (KiCad) | none for a vacuum |
| Software | ROS2 / Nav2, Gazebo | none for a vacuum |
| Built | not yet | not yet |

HS should not start a rival vacuum. OOMWOO is ahead on every layer but sourcing, and its sourcing is exactly HS's
salvage step done part by part. HS's gap was that its catalogue knew a robot vacuum only as wheels, bump sensors and a
pack, with no laser scanner and no suction fan.

**What the comparison changed in HS.** OOMWOO's module list (which vacuum models each wheel module, fan, scanner and
pack fits) is in `data/third_party/oomwoo/` with its licence and pinned commits, with envelopes HS measured from
OOMWOO's scanned STEP models (wheel module 72.7 x 111.2 x 60.4 mm with a 72 mm tire; LDS02RR 107.7 x 86.5 x 54.1 mm with
a 76 mm turret; pack 44.4 x 142.8 x 43.5 mm). The junk catalogue gained `lidar_2d` and `suction_fan` and two donors:
Xiaomi/Roborock LDS vacuums and Neato, each priced on Ruten. `hs_junk_lookup` for a mapping rover (scanner, encoded
drive, pack, camera, compute) now returns two donors, a faulty Xiaomi vacuum and a cracked Android phone, listed at
NT$1,100-2,965 together. A mapping rover built from those, on OOMWOO's open software, is the build this opens.

## Next

1. Done: HS-ARM-A rev B (above), screw holes included, and its leader arm (`projects/hs-arm-a/leader`, US$125.71;
   follower plus leader US$332.20 against SO-101's US$229.88 kit).
2. Done: rover (above), and HS-ROVER-A's TT variant priced and re-checked end to end: US$187.50 against US$263.44,
   438 g, 4.7 h (`projects/hs-rover-a/tt-variant`). Adafruit does publish a one-motor stall measurement (1.5 A at 6 V),
   now in HS's table; the "no stall current" above was wrong. The OSR's rocker-bogie is now an HS tool
   (`rocker_bogie`, `hs_rocker_bogie`: wheel load split, step climb up to one wheel radius, drive ranked by step margin),
   with goBILDA's 5203 gearmotors (the OSR's drive, all nine ratios from goBILDA's pages) in the drive table; at the
   OSR's 1.6 m/s on its 144 mm wheels HS ranks the OSR's own 26.9:1 first. OSR publishes neither its mass nor fixed
   link positions, so the model is not yet checked against a measured OSR.
3. Done: drone (above), with a brushless calibration. Still open: a brushless bench table with a flown aircraft
   (the X500 V2 needs its takeoff mass), the brushed Crazyflie's motor mass, and more cited tables
   (1S brushless, 2 in, 5 in).
4. Done: robot vacuum (above); the earlier "uncontested" was wrong, OOMWOO is the open design. The mapping rover it
   opened is designed (`projects/hs-rover-vac-a`): a faulty 1st-gen Xiaomi vacuum plus a cracked phone, US$37.10 with
   Valetudo on a working board or US$46.83 with an ESP32 on a dead one, 7 h, both under the cheapest wheeled camera
   robot sold. The wheel module is in HS's drive table from OOMWOO contributor @IKsares's bench measurements. Still
   open: confirming the 1st-gen's wheel modules match the measured S5-family one. Mopping: the Xiaomi Vacuum-Mop P
   (STYJ02YM, a 3irobotix CRL-200S) is now a donor (NT$1,400 faulty): its tank, scanner, wheels and pack, rootable for
   Valetudo over micro USB, with an open driver and ROS2 bridge already written for the CRL-200S. Valetudo's page also
   shows the 1st-gen Xiaomi never got persistent maps, so the Mop P is the better donor for route A.
