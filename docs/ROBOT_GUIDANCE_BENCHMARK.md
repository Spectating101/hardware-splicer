# Robot Build and Modification Guidance Benchmark

Hardware Splicer should not be considered capable of guiding a robot build merely because it can classify the project or repeat instructions from a repository. This benchmark asks whether the current product can turn public references and a user's needs into a governed, project-specific engineering path.

## Reference policy

Repositories, manuals, forum posts, and YouTube videos enter as reference evidence. A URL alone does not prove dimensions, wiring, firmware revision, calibration, or physical performance.

For video-derived information to become governed evidence, a record must retain:

- source URL and stable source metadata;
- timestamp range;
- exact visible observation;
- confidence and contradiction state;
- canonical component, joint, interface, or artifact target;
- an authority ceiling no higher than `observed`.

## Guidance obligations

The benchmark scores twelve independent obligations:

1. user requirements and constraints;
2. source provenance and video evidence governance;
3. baseline robot and variant selection;
4. BOM quantities and required tooling;
5. mechanical construction or modification guidance;
6. electrical and power guidance;
7. firmware source/build/flash lineage;
8. control and middleware contracts;
9. baseline-to-candidate modification impact;
10. ordered assembly, bring-up, and calibration procedure;
11. verification and evidence gates;
12. rollback, repair, or safe recovery.

A high score is not a safety certificate. Physical measurement and supervised validation remain required.

## Scenarios

### Linorobot2 apartment mapper

Greenfield build of a low-speed differential-drive mapping rover using accessible parts, micro-ROS, SLAM Toolbox, and Nav2. This is the strongest current native robotics case because Hardware Splicer already understands a rover archetype.

Primary references:

- `linorobot/linorobot2`
- `linorobot/linorobot2_hardware`
- Linorobot2 documentation and public build videos

### OpenMANIPULATOR-X wrist-camera sorter

Modification of a five-actuator arm with a wrist depth camera, wider compliant gripper, updated URDF, MoveIt collision geometry, and perception-to-pick workflow.

This tests whether Hardware Splicer can distinguish the unmodified baseline from the candidate and propagate payload, center-of-mass, collision, transforms, cable routing, and tool changes.

### Pupper depth-camera inspection modification

Modification of a twelve-actuator quadruped with a protected forward depth camera and slow inspection behavior.

This tests repeated joint identity, payload and center-of-mass effects, power margin, calibration preservation, gait limits, and dynamic validation.

### Crazyflie custom environmental sensor deck

Modification of a Crazyflie 2.1+ with a lightweight custom sensor deck and deck driver.

This tests PCB and connector identity, weight and current limits, firmware configuration, automatic deck discovery, propeller clearance, watchdog preservation, and guarded first flight.

## Running

```bash
python scripts/benchmark_robot_guidance.py
```

Outputs:

- `.artifacts/robot_guidance/ROBOT_GUIDANCE_BENCHMARK.json`
- `.artifacts/robot_guidance/ROBOT_GUIDANCE_BENCHMARK.md`

## Verdicts

- `guided_build_ready`: all structured obligations are present; physical evidence is still required.
- `useful_with_expert_fill`: substantial plan, but an experienced builder must supply important engineering detail.
- `planning_assistant_only`: useful for requirements, architecture, and evidence gates, but not a complete build guide.
- `reference_triage_only`: mainly organizes references and identifies missing information.

## Expected current boundary

The current closure candidate should be strongest on the rover build. It should not claim that articulated, legged, or aerial modification cases are complete because native topology, explicit modification deltas, firmware/middleware lineage, ordered procedures, and governed video observations are not yet consistently represented.

The benchmark exists so those gaps can be closed one by one and the same scenarios rerun without lowering authority standards.
