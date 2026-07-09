# Operator real-bench capture

**Purpose:** Close gates with **instrument-backed** `bench_topology_capture.v1` — not `simulate_bench`.

**Related:** [`BENCH_LOOP_AGENT.md`](BENCH_LOOP_AGENT.md) · [`AGENT_DRY_RUN_CHECKLIST.md`](AGENT_DRY_RUN_CHECKLIST.md)

---

## Boundary

| Path | Closes gates? |
|------|----------------|
| `simulate_bench: true` | Yes — **CI/demo only** |
| `vision-assist` / photo draft | **No** |
| Golden-real committed JSON | Yes — provenance fixture, not live café |
| **Public-web DMM photos** (`public_web_bench_capture.py`) | Yes for cold-run — **real meter LCDs from Wikimedia**, labeled `public_web_is_not_this_board` |
| This operator path | Yes — when you fill real DMM/PSU readings on **this** board |

### Public-web path (no café required)

```bash
PYTHONPATH=src python3 scripts/public_web_bench_capture.py --build-dir "$OUT"
# optional: --live  (Qwen VL on the public photos)
```

Photos live under `tests/data/golden/public_bench/` (CC from Wikimedia).

---

## Steps

1. Compose or splice-build with `finalize_package: true` → note `out_dir`.
2. Status + template:

```bash
PYTHONPATH=src python3 scripts/operator_bench_capture.py \
  --build-dir "$OUT" --status
```

3. Optional camera draft (gates stay open):

```bash
PYTHONPATH=src python3 scripts/operator_bench_capture.py \
  --build-dir "$OUT" \
  --vision-photo tests/data/golden/rc_toy_motor_board.jpg
```

4. Copy `BENCH_CAPTURE_TEMPLATE.json` (or vision draft), fill:
   - `operator_id`, `recorded_at`, instrument IDs
   - each measurement `status` / `value` from DMM or PSU
   - set `"simulated": false`
5. Submit:

```bash
PYTHONPATH=src python3 scripts/operator_bench_capture.py \
  --build-dir "$OUT" \
  --submit path/to/filled_capture.json
```

6. Confirm `power_on_authorized=true` via `hs_splice_bench_status` or `--status`.

---

## Claims

- Do **not** cite simulated or vision-only runs as field evidence.
- Copper may still be `cosmetic_preview` — DRC 0 ≠ fab-ready.
