# Splice demo (10 minutes)

**Product story:** dissect a donor PCB → identify reusable functional blocks → plan safe splice contracts → compile a **carrier board** that mates with what you kept.

**Canonical product reference:** [`SPLICE_PRODUCT.md`](SPLICE_PRODUCT.md) — maturity tiers, roadmap, how to proceed.

Offline-friendly. No API keys required.

## Before you start

```bash
python3 -m pip install -r requirements.txt
python3 scripts/hardware_splicer.py doctor
```

Confirm `demo_ready=True`. Node + KiCad CLI needed for carrier compile.

## One command (canonical)

```bash
make splice-demo
```

Runs case `robot_drive_from_rc_toy` from [`examples/splice/manifest.json`](../examples/splice/manifest.json).

```bash
# second canonical case — printer motion
PYTHONPATH=src python3 scripts/splice_demo.py \
  --case printer_motion_stage \
  --out /tmp/hs_splice_printer
```

## Verify all splice demos (CI bar)

```bash
make verify-splice
```

Writes `/tmp/hs_splice_verify/SPLICE_DEMO_REPORT.json`.

## Golden loop — vision junk + bench closure (S3)

Tests the **full agent loop**: donor vision evidence → splice compile → `BENCH_CAPTURE_TEMPLATE` → capture submit → `power_on_authorized`.

```bash
# single case (vision brief, simulated bench for CI)
make splice-golden-loop

# CI bar: fixture S2 + vision S3 + repair-café S3
make verify-splice-loop

# Golden real S3: Wikimedia donor photo + hand-filled bench capture (not simulator)
make verify-splice-real-bench
```

Intake: `examples/intakes/splice_robot_drive_vision_brief.json` (pinned `board_evidence` under `tests/data/` — no API keys).

Artifacts: `SPLICE_GOLDEN_LOOP_REPORT.json`, `SPLICE_GOLDEN_LOOP_STORY.md`, `SPLICE_BENCH_SESSION.json`.

For **real junk**, set `donor_board_vision.live: true` and point `board_evidence` at a photo path; bench rows must come from physical DMM/PSU, not the simulator.

See also: [`SPLICE_BEST_PRACTICES.md`](SPLICE_BEST_PRACTICES.md), [`COMPETITIVE_LANDSCAPE.md`](COMPETITIVE_LANDSCAPE.md).

## What happens

1. **Donor fixture** — JSON functional salvage (today); vision-derived blocks (roadmap)
   - `connector_reuse` — keep harness intact
   - `board_section_cut_candidate` — possible section cut, gated
2. **Splice plan** — blocks + measurements + wiring + adapter circuits
3. **Carrier compile** — `splice-build` → KiCad DRC on **new** board

## Artifacts to open

| File | What to show |
|------|----------------|
| `SPLICE_DEMO_STORY.md` | Human narrative for pitch / portfolio |
| `SPLICE_DEMO_RESULT.json` | Machine pass/fail vs manifest |
| `SPLICE_PLAN.json` | Full salvage + splice package |
| `BRINGUP_CARD.md` | Bench steps before power-on |
| `build_compilation/main_ctrl_build.kicad_pcb` | Carrier board |
| `build_compilation/DESIGN_QUALITY.json` | KiCad truth |

## Manifest cases

| case_id | Donor story | Carrier build |
|---------|-------------|---------------|
| `robot_drive_from_rc_toy` | RC toy H-bridge + motors | `robot_drive_base` |
| `robot_drive_vision_junk` | Vision/board_evidence junk path + bench (S3) | `robot_drive_base` |
| `robot_repair_cafe_s3` | Repair-café symptoms + PSU/thermal gates + bench (S3) | `robot_drive_base` |
| `printer_motion_stage` | Inkjet stepper + limits | `plotter_motion_stage` |

Fixtures: `examples/fixtures/splice_donor_*.json`
Intakes: `examples/intakes/splice_*_brief.json`

## CLI / API

```bash
python3 scripts/hardware_splicer.py splice-build \
  --brief examples/intakes/splice_robot_drive_brief.json \
  --out /tmp/hs_splice_cli --no-gerber

python3 scripts/hardware_splicer.py serve --port 8090
curl -s -X POST http://127.0.0.1:8090/v1/splice-and-build \
  -H 'Content-Type: application/json' \
  -d @examples/intakes/splice_robot_drive_brief.json
```

## What to emphasize (vs Flux)

1. **Decomposition** — donor hardware in, not catalog shopping
2. **Extractability** — harness-first vs cut-candidate is explicit
3. **Splice contracts** — pin/power gates before interconnect
4. **Carrier compile** — new board is glue; donor pieces stay physical
5. **KiCad truth** — same honest gate as catalog builds

## Related

- Product + roadmap: [`SPLICE_PRODUCT.md`](SPLICE_PRODUCT.md)
- Salvage bring-up only: `make salvage-demo`
- Authority / evidence: [`DEMO_10_MIN.md`](DEMO_10_MIN.md)
- Circuit-AI API: `apps/circuit-ai/docs/SALVAGE_TO_PRODUCT_WORKFLOW.md`
- Planner eval (29 cases): `apps/circuit-ai/eval/salvage_splice_coverage/`
