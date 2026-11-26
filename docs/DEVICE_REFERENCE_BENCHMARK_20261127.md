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

## Next

1. Done: HS-ARM-A rev B (above). Still open: horn bolt circle and servo screw holes, the leader arm SO-101 pairs with.
2. Rover: HS-ROVER-A (US$263.44, 2WD, 0.79 m/s, ~5 h) and the salvage rover (built on OpenBot) against OpenBot and
   NASA-JPL's Open Source Rover, subsystem by subsystem.
3. Drone: HS-3G against the open multirotor designs once the sweep's drone results are read file by file (none passed
   the completeness floor; Crazyflie splits firmware and electronics across repositories).
4. Robot vacuum and mopping: no complete open design was found; Valetudo (Apache-2.0) is firmware for commercial
   robots. HS's junk catalogue already treats robot vacuums as donors: an open, salvage-built vacuum is uncontested.
