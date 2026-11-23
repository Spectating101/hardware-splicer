# Robotics scaling benchmark

This benchmark asks a narrower question than “can Hardware Splicer build a robot?”

> How much engineering identity and closure survives as a reference project grows from a wheeled rover into a manipulator, legged robot, or aerial robot?

The suite runs public, open-reference robot profiles through the real project-intake planner. It measures structural representation only. It does not claim that Hardware Splicer reproduced, simulated, fabricated, or safely operated the reference robot.

## Reference cases

| Benchmark | Genre | Why it matters |
|---|---|---|
| `linorobot2_rover` | Differential-drive autonomous rover | Native rover baseline; motor channels, encoders, lidar, IMU, micro-ROS, SLAM and Nav2. |
| `openmanipulator_x` | Serial robotic manipulator | Joint identity, kinematic chain, smart-servo bus, URDF, MoveIt and collision-aware planning. |
| `stanford_pupper` | Twelve-actuator quadruped | Four repeated kinematic chains, joint calibration, high-current actuation and dynamic gait validation. |
| `crazyflie_2_1` | Nano aerial robot | Coupled attitude loops, dual-MCU firmware, radio/power boundaries and first-flight safety. |

Reference repositories and documentation are maintained by their respective projects. Video URLs in fixtures are discovery pointers. A search result, description, or video frame is not automatically engineering truth.

## Run

```bash
source .venv/bin/activate
PYTHONPATH=src python scripts/benchmark_robotics_scaling.py
```

Outputs:

```text
.cache/hardware-splicer/robotics_scaling/ROBOTICS_SCALING_REPORT.json
.cache/hardware-splicer/robotics_scaling/ROBOTICS_SCALING_REPORT.md
```

## What is measured

- archetype fidelity;
- multidisciplinary domain representation;
- actuator cardinality preservation;
- canonical kinematic identity;
- firmware build/flash lineage;
- ROS or middleware interface lineage;
- dynamic validation representation;
- timestamped, identity-resolved video evidence handling.

`pressure_index` estimates how strongly a robot stresses the stack. It combines actuator count, kinematic chains, sensors, control loops, power domains, external interfaces, dynamic coupling and safety criticality. It is not a safety rating.

`stack_coverage_score` measures whether the current intake plan structurally represents the required information. It is not physical correctness, fabrication readiness or authorization.

## Evidence rule for YouTube and other video

Video may establish timestamped observations such as:

- visible actuator orientation;
- assembly order;
- cable routing;
- calibration actions;
- observed motion, flex, collision or failure;
- visible tool and test setup.

Video alone must not establish hidden wiring, exact dimensions, current limits, firmware revision, material properties, structural safety or release authorization.

The future governed video artifact should retain:

```text
source URL + channel/title metadata
→ timestamp range
→ observation
→ confidence
→ candidate canonical identities
→ contradictions and unresolved references
→ observed authority ceiling
```

## Baseline interpretation

The current stack is expected to treat the rover as the strongest native case. Manipulator, quadruped and aerial profiles are expected to expose native-archetype, kinematic, firmware/ROS, video-evidence and dynamic-validation gaps rather than being silently described as complete.

That failure visibility is the purpose of the first benchmark pass. Later implementation should improve the scores without weakening evidence or authority boundaries.
