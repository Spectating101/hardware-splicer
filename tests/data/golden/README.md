# Golden S3 artifacts — real photo + manual bench capture

Committed artifacts for the **non-simulated** S3 path (`make verify-splice-real-bench`).

## Files

| File | Role |
|------|------|
| `rc_toy_motor_board.jpg` | Real donor board photo (Playmobil RC module) |
| `rc_toy_live_board_evidence.json` | **Live Qwen** `board_evidence.v1` pinned from golden photo |
| `rc_toy_live_board_evidence.meta.json` | Model, tokens, cost, image SHA256 |
| `rc_motor_manual_bench_capture.v1.json` | Hand-filled `bench_topology_capture.v1` — **not** the CI simulator |
| `ATTRIBUTION.md` | Photo license |

## Photo

**Source:** [Playmobil RC module-92464.jpg](https://commons.wikimedia.org/wiki/File:Playmobil_RC_module-92464.jpg) on Wikimedia Commons
**License:** CC BY-SA 4.0 — © Wilfried Wittkowsky
**Use:** Golden vision/bench provenance stand-in for a dead RC toy donor until project-owned junk photos are added.

## Live Qwen evidence

Pinned from `rc_toy_motor_board.jpg` via Qwen (`qwen3-vl-flash`, ~\$0.0002/call):

```bash
# Requires QWEN_API_KEY + VISION_MONTHLY_USD_LIMIT>0 in .env.local
make pin-golden-live-evidence
```

Refresh only when the photo or prompt changes. CI uses the **committed** `rc_toy_live_board_evidence.json`, not live API calls.

## Bench capture

Represents a repair-café style session: UNI-T DMM continuity/voltage, Korad supply at **0.5 A** limit, Rossmann-style ramp notes.
`simulated: false` — `run_splice_golden_real()` fails if this flag is true.

## Regenerating gate IDs

If bring-up checks change, rebuild once and update capture gate rows:

```bash
PYTHONPATH=src python3 scripts/splice_golden_loop.py \
  --intake examples/intakes/splice_robot_drive_golden_real_brief.json \
  --out /tmp/gate_probe --no-simulate-bench
# Edit BENCH_CAPTURE_TEMPLATE.json → merge into rc_motor_manual_bench_capture.v1.json
```
