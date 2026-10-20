# Hardware Splicer robotic-arm splicing and fabrication-tool handoff

Date: 2026-10-20. Conditional engineering benchmark: NOT a physically approved arm.

## Two robotics pathways

1. Construct a robot arm from salvaged electronics, motors, joints, recovered mechanical hardware and printed support elements.
2. Use an existing robot arm as a fabrication/assembly tool to pick, position, inspect and place the previously SolidCraft-designed casing parts.

Both need a central AI agent for design decisions, a robotics engine for planning, CAD/BOM for physical parts, controller/firmware interfaces and separate motion authorization.

## Assumptions that permit research without claiming real measurements

- Reach requirement: 400 mm; carried-part payload up to 0.15 kg.
- Gripper mass: assumed interval 0.08–0.20 kg.
- Structural link mass: assumed 0.06–0.24 kg per segment.
- Continuous gearbox output torque reduced to 65% for pessimistic sizing.
- Preliminary acceleration amplification 1.0–1.8, separate torque factor 1.5.
- Backlash and stiffness are entered as intervals but NOT structurally qualified.
- These are scenario-input priors, NOT surveyed industry averages or actual donor readings.
- Higher-torque geared motors can weigh more: the link-mass interval MUST be revisited when actual motor choices emerge.

## Live Codex designs and validation outcomes

Codex first proposed an arm using lower-torque assumed classes. An earlier proposal with zero-length joints was rejected by HS's typed schema; the input contract was clarified and a new real model proposal obtained.

Initial design: four degrees of freedom, total 450 mm proposed chain. PyBullet 3.2.7 genuine URDF and inverse kinematics completed, but pessimistic motor comparison found:
- Shoulder: assumed available 3.25 N m versus modeled worst demand 8.5974 N m: FAIL.
- Elbow: 1.95 versus 3.8181 N m: FAIL.
- Wrist: 0.78 versus 0.6222 N m: tentative static pass.
- Base yaw: zero gravity moment in vertical rotation does NOT establish inertia, drive friction, cable safety, speed or braking.

An improved Codex design was tested using additional unowned HYPOTHETICAL geared motor classes rated at 20 N m shoulder and 12 N m elbow continuous. Result: total chain 420 mm and static pessimistic sizing passes for shoulder/elbow/wrist under the unchanged selected mass interval.

PyBullet does not certify the robot. The revised candidate's generic IK error was 5.035 mm against 5.000 mm acceptance, slightly failing. Its abstract five-step lid pick-place positions were reachable but proxy self-collision with base was identified. Arm load inertia, real collision meshes, gripper rotation/orientation, actual fixture dimensions and all inter-waypoint collision sweeps remain unproven.

## Actual printed mechanical parts for an arm

SolidCraft 0.16.2 generated two parametric finger inserts, left and right; 45 x 12 x 8 mm with two nominal 3.2 mm holes per finger. Each was exported to STEP/STL with closed-manifold audit; a 2-body 3MF was produced. PartCAD 0.8.220 read both parts and returned a BOM with one of each.

PrusaSlicer 2.9.2, assumed Original Prusa MK4S 0.4 mm and Prusament PLA 0.20mm STRUCTURAL settings, actually generated:
- G-code for two inserts; 40 layers, 5.43 g estimated filament.
- 17 min 59 sec estimated duration.
- No real printer, robot gripper or actual components were connected.
The hole pattern is NOT matched to any purchased arm or real gripper.

## How to bring the robotic splicing design to reality

1. Specify arm task, target grip force, actual payload mass, reach, repeatability, workspace, hazards and cycle rate.
2. Acquire or inspect actual motors and gearboxes: joint-output continuous torque, measured current, rated voltage, reduction ratio, drive type, feedback, motor/driver connector pinouts and braking. Never connect an unknown harness from a guessed color code.
3. Redo HS interval calculations for exact actuator choices, real motor/link/gripper mass, centers of gravity, duty cycle and thermal derating, including moment of inertia and acceleration. If worst-case fails, adapt torque/reach/material before proceeding.
4. CAD the full load-bearing structure in SolidCraft, including joint mounts, bearings, couplers, printed brackets, gripper adapters, cable routing and reachable workspace; reference each part in PartCAD. The delivered simple finger inserts alone are not a complete arm.
5. Export actual inertial/collision geometry to URDF and run PyBullet or equivalent path planning with a modeled table, fixtures, arm, cable envelopes and limits. Clear current base collision, generic IK residual, orientation and intermediate trajectory before physical motion.
6. For physical fabrication, identify a real printer and real material; confirm exact machine profile, check purge movements beyond nominal bed, inspect G-code, print coupon and check dimensions and mechanical strength. 3D-printed plastic alone does not establish strength for a moving load-bearing joint.
7. Wire and assemble with power isolated using documented controller and motor driver ratings. Independently verify joint limits, homing, E-stop, guards and loss-of-command response.
8. After human approval and qualified review, bring up a single joint at very low power/motion; record current, position/encoder response, torque, heat and limit response. Verify all protective paths.
9. Calibrate the whole arm, inspect dynamic loads, and perform one guarded light-object pickup and place trial. Measure actual pose error, torque, gripper slip and collisions, then revise HS models.
10. For use as an assembly tool, require safe gripper-force/current control, actual enclosure-part measurement, fixture collision clearance, repeatable grasp and verified release before manipulating physical components.

Physical printing, wiring, motor power, motion, firmware flash and real assembly remain BLOCKED until equipment exists and authorization is granted.

Reproducibility bundle: examples/assumption_robot_arm/HS_ROBOT_ARM_SPLICE_BENCHMARK_20261020.zip
