# Robot Reference End-to-End Validation

This tranche tests whether Hardware Splicer can turn a large, heterogeneous robotics reference corpus into one governed and actionable custom-rover plan.

It is intentionally broader than a YouTube workflow. Repositories, official manuals, CAD indexes, firmware, middleware contracts, papers, simulation resources and videos enter the same source graph. Video is retained as observed evidence and never upgrades a candidate to measured, verified or authorized state.

## Corpus

The catalog at `examples/robot_reference_corpus/robot_reference_catalog.json` contains 11 robot families and 51 source records:

- Linorobot2
- TurtleBot3
- OpenMANIPULATOR-X
- Stanford Pupper
- Mini Pupper
- SpotMicroAI
- ODRI Solo12
- Crazyflie
- ArduPilot Rover
- PX4 Multicopter
- Reachy

Each source records:

- stable source identity;
- source type and URI;
- authority ceiling;
- revision-capture policy;
- intended evidence use;
- structured claims;
- explicit limitations.

Search-result pages and embedded video indexes are discovery sources only. A media observation becomes usable evidence only after one concrete media item and timestamp range are selected and mapped to a canonical target identity.

## End-to-end case

The case at `examples/robot_reference_e2e/reference_rich_indoor_inspection_rover.json` asks Hardware Splicer to prepare a custom two-wheel indoor inspection rover with:

- 90-minute target runtime;
- 500 g sensor payload;
- 15 mm threshold requirement;
- 500 mm maximum width;
- ROS 2 mapping and navigation;
- emergency motor-power isolation;
- current-limited first motion.

The case selects public Linorobot2, TurtleBot3 and ArduPilot sources for baseline, comparison, safety and observed-media roles. It also provides a fixture URDF, firmware manifest, ROS interface contract, electrical/firmware pin identity, connectors, harnesses, BOM, physical instances, assembly steps, CAD identity and revision-pinned artifact hashes.

The fixture identifiers exercise traceability. They are not claims that a real chassis, firmware image or wiring package has been fabricated or physically verified.

## What the run executes

`src/hardware_splicer/robot_reference_e2e.py` performs the following sequence:

1. Load and validate the reference catalog.
2. Resolve selected source identities.
3. Adapt public, media, URDF, firmware and ROS sources into the engineering source graph.
4. Run the complete guided engineering planner.
5. Import and project the selected robot model.
6. Run bounded quantitative analysis.
7. Reconcile manufacturing relationships.
8. Compile bounded execution previews.
9. Generate the ordered operator guide.
10. Build unified engineering status.
11. Prepare the highest-ranked next-action packet.
12. Confirm that fabrication, flashing, power, motion and release authority remain false.

## Running it

```bash
PYTHONPATH=src python scripts/run_robot_reference_e2e.py \
  --strict \
  --out /tmp/robot-reference-e2e
```

Focused tests:

```bash
PYTHONPATH=src python -m pytest -q tests/test_robot_reference_e2e.py
```

The dedicated `Robot Reference E2E` GitHub Actions workflow runs both commands and uploads:

- `ROBOT_REFERENCE_E2E.json`
- `ROBOT_REFERENCE_E2E.md`

## Pass interpretation

A passing report means:

- the large corpus is identity-safe and source-diverse;
- selected references survive into the source graph;
- the custom rover receives native topology;
- the planner produces analysis, manufacturing closure, execution previews, an operator guide and a ranked action packet;
- video remains one evidence type among several;
- no physical authority is created.

It does **not** mean:

- remote source content was fully mirrored and content-hashed;
- CAD underwent full BREP collision or structural analysis;
- firmware was compiled or flashed on real target hardware;
- the robot was powered, moved or field tested;
- a human release decision was made.

Those require materialized artifacts, installed toolchains, calibrated instruments, physical evidence and an authorization decision scoped to the exact candidate revision and artifact hashes.
