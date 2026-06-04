# Qwen Vision Trial Report

- Created: `2026-06-02T17:12:31.063813+00:00`
- Mode: `dry_run`
- Model: `qwen3-vl-flash`
- Rows: `1`
- Live calls: `0`
- Cache hits: `0`
- Estimated preflight total: `$0.001092`
- Actual recorded total: `$0`

| Scenario | Status | Crops | Baseline | Qwen summary | Cost |
|---|---:|---:|---|---|---:|
| `single_test_pcb` | `dry_run` | 3 | controller_or_embedded_compute / conf=0.371 / det=3 / conn=0 / ocr=1 | pending | `$0` |

## Minimum Success Bar

- Valid JSON with `board_evidence.v1` on every live sampled board.
- Better markings/connectors/regions on weak baseline cases without invented pinouts.
- Total spend stays inside the configured Qwen budget.
