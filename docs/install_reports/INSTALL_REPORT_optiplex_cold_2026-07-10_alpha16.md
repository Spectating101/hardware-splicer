# Install report — optiplex public-web DMM bar (alpha.16)

| Field | Value |
|-------|-------|
| **Tester** | maintainer (software-only; Wikimedia DMM photos) |
| **Date** | 2026-07-10 |
| **Tag** | `v1.1.0-alpha.16` |
| **Machine** | optiplex |
| **Mode** | Public-web provenance bench (not this-board café) |

## What was procured online

Wikimedia Commons DMM-on-bench photos under `tests/data/golden/public_bench/`:

- `dmm_testing_5v.jpg` — LCD **5.52 V** on labeled 5 V rail (pinned)
- `dmm_voltage_3v3.jpg` — LCD **0.00 V** on 3.3 V (recorded, not pass)
- plus flyback / circuit / battery measurement photos as artifacts

## Result

```text
public_web_passed True matched 10 power_on True
policy.public_web_is_not_this_board True
```

Unit tests: `tests/test_public_web_bench.py` — 4 passed.

## Claims boundary

Real instrument displays from public photos ≠ café measurement of the current donor board.
Operator path for *this* board remains `docs/REAL_BENCH_OPERATOR.md`.
