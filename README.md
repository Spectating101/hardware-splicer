# Hardware-Splicer

This folder consolidates the hardware-oriented projects behind a top-level compiler/API:

- `apps/circuit-ai/` - electronics intelligence, PCB/image analysis, BOM/DFM-style workflows, repair/reseller tooling, APIs/MCP wrappers.
- `apps/mecha-splicer/` - mechanical splicing pipeline for enclosures, brackets, fixtures, DFM/BOM bundles, proposals, and product packs.
- `apps/3d-splicer/` - parametric enclosure generator API with CadQuery/STL-style outputs.
- `apps/hardware-splicer-demo/` - frontend authority dashboard for showing intake results, deterministic margins, evidence gaps, and generated artifacts.

The production-facing path is `scripts/hardware_splicer.py` and the `hardware_splicer` Python package. It validates compile specs, starts/stops the optional local 3D-Splicer service, copies mechanical outputs into the final bundle, and writes manifest/metadata files for downstream automation.

## Doctor

Inspect local runtime readiness:

```bash
python3 scripts/hardware_splicer.py doctor
python3 scripts/hardware_splicer.py doctor --json
```

This checks app roots and key dependencies. `cadquery` is optional unless true STL rendering is required; without it, `--render-stl` can still return a CadQuery script fallback.

Validate a compile spec without running the expensive chain:

```bash
python3 scripts/hardware_splicer.py validate --spec examples/hardware_splicer_demo.json
python3 scripts/hardware_splicer.py validate --spec examples/hardware_splicer_demo.json --json
```

## Integration Smoke

Compile the canonical controller plus pan-tilt build bundle:

```bash
python3 scripts/hardware_splicer.py demo --out /tmp/hardware_splicer_demo
```

The output directory contains `SUMMARY.md`, `ENGINEERING_REPORT.md`, `MANIFEST.json`, `BUILD_METADATA.json`, `hardware_splicer.bundle.json`, extracted 3D-Splicer artifacts when present, and a copied `mecha_bundle/`. It also emits `CASEFILE.json`, `PROJECT_LOG.json`, `HARDWARE_REVIEW.md`, `ROBOTICS_ACTUATION.json`, `ROBOTICS_SIMULATION.json`, and `ROBOTICS_PLATFORM_AUTHORITY.json` so each build has a CNX-style review, Hackaday-style project log, Hackster-style build package index, deterministic robotics simulation gate, and generalized robotics/mechatronics mission authority packet.

Compile the closed mechatronics proof bundle with circuit release, mechanical measurements, robotics bench evidence, 3D-Splicer script output, and the final integration trace:

```bash
python3 scripts/hardware_splicer.py compile --spec examples/hardware_splicer_closed_mechatronics_demo.json --out /tmp/hardware_splicer_closed_mechatronics_demo
```

The generated `MECHATRONICS_AUTHORITY.json` includes an `integration_trace` that maps mechanism primitives to CAD outputs, actuator requirements, power/control coupling, bench evidence, and release closure. The generated `CASEFILE.json` reuses that trace as the normalized evidence ledger for portfolio review, competition packaging, or later frontend visualization.

Compile the generalized robotics platform proof bundle with mission, locomotion, positioning, control stack, safety case, bench evidence, field validation, and release scope:

```bash
python3 scripts/hardware_splicer.py compile --spec examples/hardware_splicer_robotics_platform_rover_demo.json --out /tmp/hardware_splicer_robotics_platform_rover_demo
```

The generated `ROBOTICS_SIMULATION.json` evaluates actuator current margin, battery runtime, differential-drive wheel speed, tractive force, pan-tilt servo payload torque, and safety-envelope blockers. Project-level robotics authority consumes this packet, so a design with impossible speed, insufficient current, weak servo torque, poor runtime, or unresolved integration gaps cannot silently pass as a scoped robotics release.

Run a full project scenario and emit one frontend/demo-ready project authority packet:

```bash
python3 scripts/hardware_splicer.py scenario --scenario examples/scenarios/rover_project.json --out /tmp/hardware_splicer_scenario_rover
python3 scripts/hardware_splicer.py scenario --scenario examples/scenarios/rover_bad_speed_project.json --out /tmp/hardware_splicer_scenario_bad_speed
```

Scenario files wrap a compile spec, optional overrides, expected authority milestones, and required artifacts. The runner writes `PROJECT_AUTHORITY.json`, `SCENARIO_SUMMARY.md`, and `SCENARIO_RESULT.json`; the clean rover scenario is claimable, while the bad-speed scenario still compiles but blocks the project claim because the declared speed exceeds the available wheel RPM.

Plan from a user-style project brief, then run the generated scenario:

```bash
python3 scripts/hardware_splicer.py intake --brief examples/intakes/plant_watering_brief.json --out /tmp/hardware_splicer_intake_plant
python3 scripts/hardware_splicer.py intake --brief examples/intakes/rover_brief.json --out /tmp/hardware_splicer_intake_rover
python3 scripts/hardware_splicer.py intake --brief examples/intakes/fan_controller_brief.json --out /tmp/hardware_splicer_intake_fan
```

The intake path detects the project archetype, normalizes available parts, creates a compile spec and scenario, then emits `PROJECT_INTAKE.json`, `PLANNED_SCENARIO.json`, `PROJECT_AUTHORITY.json`, `PRODUCTION_RELEASE_METRICS.json`, `AUTHORITY_UPGRADE_PLAN.json`, and the usual engineering artifacts. This is the backend bridge for chat-style workflows such as "I want to build an automatic plant waterer with an ESP32, soil sensor, mini pump, and $10 budget." It can claim planning/control-safety authority while leaving measured dimensions, bench evidence, and reviewed release scope as explicit next actions.

Attach physical/project evidence through `evidence` fields in the intake file to upgrade the generated package:

- `evidence.board_design_files`
- `evidence.mechanical_measurement_capture`
- `evidence.mechanical_bench_capture`
- `evidence.robotics_bench_capture`
- `evidence.integrated_bench_capture`
- `evidence.field_validation`
- `evidence.release_review`

`AUTHORITY_UPGRADE_PLAN.json` lists the next evidence requests and the exact intake fields that unlock higher authority levels, from control-safety planning toward simulation/bench, field validation, and production-ready scoped release.

`PRODUCTION_RELEASE_METRICS.json` turns the release gap into weighted gates: compile/artifacts, circuit release, mechanical release, actuation release, deterministic simulation, packaging trace, integrated bench, field validation, and reviewed scoped release. Intake examples currently land as control-safety planning packages; a closed scenario such as `examples/scenarios/rover_project.json` reaches 9/9 gates and `production_ready_project_package`.

Run the local dashboard:

```bash
cd apps/hardware-splicer-demo
npm install
npm run dev -- --port 5177
```

The dashboard currently uses seeded snapshots generated from backend intake runs, so it is suitable for portfolio/competition walkthroughs without relying on live model quota.

Run the lighter local Circuit-AI -> Mecha-Splicer -> 3D-Splicer smoke:

```bash
python3 scripts/hardware_splicer_e2e.py
```

Shortcuts:

```bash
make demo
make smoke
make test
make test-apps
```

Run the compiler API:

```bash
python3 scripts/hardware_splicer.py serve --port 8090
```

Useful API endpoints:

- `GET /health`
- `GET /v1/status`
- `POST /v1/validate`
- `POST /v1/mechanical-authority`
- `POST /v1/robotics-actuation`
- `POST /v1/robotics-simulation`
- `POST /v1/robotics-platform-authority`
- `POST /v1/mechatronics-authority`
- `POST /v1/compile`
- `POST /v1/scenario-run`
- `POST /v1/intake-run`
- `POST /v1/jobs`
- `GET /v1/jobs`
- `GET /v1/jobs/{job_id}`
- `GET /v1/jobs/{job_id}/result`
- `GET /v1/jobs/{job_id}/artifacts`
- `GET /v1/jobs/{job_id}/bundle`
- `POST /v1/jobs/{job_id}/cancel`
- `POST /v1/jobs/{job_id}/retry`

By default, API compile outputs are constrained to `HARDWARE_SPLICER_OUTPUT_ROOT` (`/tmp/hardware_splicer_api`). Set `HARDWARE_SPLICER_ALLOW_ARBITRARY_OUT_DIR=1` only for trusted local development.

Async jobs are persisted in SQLite under `HARDWARE_SPLICER_STATE_DIR` (`/tmp/hardware_splicer_state`) unless `HARDWARE_SPLICER_JOB_DB` is set. `HARDWARE_SPLICER_JOB_WORKERS` controls the in-process worker count.

See `docs/INTEGRATION.md` for the current runtime flow and environment variables.
