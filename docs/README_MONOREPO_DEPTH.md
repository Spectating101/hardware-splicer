# Monorepo depth — engine, intake, and full API

**Purpose:** Technical depth for engineers working beyond the **Splice Agent v1** product SKU.

**Product quick start:** [`../README.md`](../README.md) · [`QUICKSTART_SPLICE_v1.md`](QUICKSTART_SPLICE_v1.md)

---

## Production path

The production-facing entry is `scripts/hardware_splicer.py` and the `hardware_splicer` Python package under `src/hardware_splicer/`.

Engine completion gates: [`ENGINE_DONE.md`](ENGINE_DONE.md)

---

## Doctor & validate

```bash
python3 scripts/hardware_splicer.py doctor
python3 scripts/hardware_splicer.py doctor --json
python3 scripts/hardware_splicer.py validate --spec examples/hardware_splicer_demo.json
```

`cadquery` is optional unless true STL rendering is required.

---

## Splice path (canonical v1)

```bash
make splice-demo
make verify-splice
make verify-splice-loop
make verify-splice-v1
```

```bash
python3 scripts/hardware_splicer.py splice-build \
  --brief examples/intakes/splice_robot_drive_brief.json \
  --out /tmp/hs_splice_build --no-gerber
```

See [`DEMO_SPLICE.md`](DEMO_SPLICE.md). Donor fixtures: `examples/fixtures/splice_donor_*.json`.

---

## Integration demo & mechatronics (beyond v1 SKU)

Canonical controller + pan-tilt bundle:

```bash
python3 scripts/hardware_splicer.py demo --out /tmp/hardware_splicer_demo
```

Closed mechatronics proof:

```bash
python3 scripts/hardware_splicer.py compile \
  --spec examples/hardware_splicer_closed_mechatronics_demo.json \
  --out /tmp/hardware_splicer_closed_mechatronics_demo
```

Robotics platform rover:

```bash
python3 scripts/hardware_splicer.py compile \
  --spec examples/hardware_splicer_robotics_platform_rover_demo.json \
  --out /tmp/hardware_splicer_robotics_platform_rover_demo
```

Scenarios:

```bash
python3 scripts/hardware_splicer.py scenario \
  --scenario examples/scenarios/rover_project.json \
  --out /tmp/hardware_splicer_scenario_rover
```

---

## Intake & authority (chat-style workflows)

```bash
python3 scripts/hardware_splicer.py intake \
  --brief examples/intakes/plant_watering_brief.json \
  --out /tmp/hardware_splicer_intake_plant
```

Emits `PROJECT_INTAKE.json`, `PROJECT_AUTHORITY.json`, `PRODUCTION_RELEASE_METRICS.json`, evidence reports, and related artifacts. See [`LLM_OPS.md`](LLM_OPS.md) for vision/text LLM providers.

```bash
make plant-qwen-pipeline    # live vision (API key)
make score-intake-tiers     # offline tier scoring
```

---

## Catalog build & benchmark

```bash
python3 scripts/hardware_splicer.py build --build-id automatic_plant_watering --out /tmp/plant_build
node scripts/compile_build_graph.cjs --build-id automatic_plant_watering --out /tmp/plant_build
make benchmark-backend
```

When `kicad-cli` is installed, `build` emits Gerber packages under `build_compilation/`.

---

## Full compiler API (monorepo)

```bash
python3 scripts/hardware_splicer.py serve --port 8090
```

Endpoints include compile, intake-run, scenario-run, mechanical/robotics authority, and async jobs. Splice Agent v1 HTTP surface is documented in [`AGENT_HANDOFF.md`](AGENT_HANDOFF.md).

Environment: [`INTEGRATION.md`](INTEGRATION.md) — `HARDWARE_SPLICER_OUTPUT_ROOT`, `HARDWARE_SPLICER_STATE_DIR`, job workers.

---

## Other demos

| Demo | Command |
|------|---------|
| Authority dashboard | `cd apps/hardware-splicer-demo && npm run dev` |
| E2E smoke | `python3 scripts/hardware_splicer_e2e.py` |
| 10-min authority | [`DEMO_10_MIN.md`](DEMO_10_MIN.md) |

---

## Make targets (full dev)

```bash
make setup
make doctor
make test
make verify          # full monorepo bar — heavier than verify-splice-v1
make refresh-demo-data
```

**v1 product bar only:** `make verify-splice-v1`
