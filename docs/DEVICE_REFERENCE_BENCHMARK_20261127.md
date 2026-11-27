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
design in the checked set are open ground for HS, not a sign HS is behind.

Limits: the file check is a floor. Projects that keep hardware in git submodules (OpenMower) or sibling repositories
(OpenArm, Petoi, NASA's rover software, Stanford Pupper) score low here although the design exists; their submodules are
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
against US$1,089.50; moving mass 0.459 kg against 0.516; reach 370.5 mm against 375.9.

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
is now in it, and passes HS-ROVER-A's speed and torque requirements. The seller publishes no stall current or torque
limits, so those checks read unknown rather than passed, and a TT option is listed after every option with a known
current.

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
  now tests. One aircraft, brushed motors: a brushless calibration is still to find.
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

## Next

1. Done: HS-ARM-A rev B (above). Still open: horn bolt circle and servo screw holes, the leader arm SO-101 pairs with.
2. Done: rover (above). Still open: a TT-motor variant of HS-ROVER-A priced and re-checked end to end; the OSR's
   rocker-bogie (Apache-2.0) as HS's rough-terrain option.
3. Done: drone (above). Still open: a brushless calibration aircraft, Crazyflie's motor mass, and more cited tables
   (1S brushless, 2 in, 5 in).
4. Robot vacuum and mopping: no complete open design was found; Valetudo (Apache-2.0) is firmware for commercial
   robots. HS's junk catalogue already treats robot vacuums as donors: an open, salvage-built vacuum is uncontested.
