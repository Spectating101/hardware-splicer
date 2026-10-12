# Device fault-matrix mutation benchmark — 2026-10-12

Question: do the generated application's host fault scenarios catch bugs that a boot-only or
healthy-bus test cannot? Method: seed realistic bugs into the generated `src/app_core.h`, compile
with the production flags (`-std=c++17 -Wall -Wextra -Werror`), and record which detector notices.

```sh
PYTHONPATH=src .venv/bin/python scripts/benchmark_device_fault_matrix.py --set all --out report.json
# score an earlier harness revision:  ... --harness path/to/host_harness.cpp
```

## Detectors

| Detector | Scenarios |
|----------|-----------|
| smoke | `boot_ok` |
| healthy bus | `boot_ok`, `default_address_binding`, `read_period` (no injected fault in any of them) |
| fault matrix | all 15 host scenarios |

`serial_grammar` re-runs nine other scenarios, so it is never counted as a healthy-bus detector.

## Result

48 mutants defined, 45 scored (3 reviewed as behaviourally equivalent, 0 stillborn).

| Detector | Mutants caught |
|----------|----------------|
| smoke | 5 / 45 (11 %) |
| healthy bus | 8 / 45 (18 %) |
| fault matrix, as it stood | 41 / 45 (91 %) |
| fault matrix, after this change | 45 / 45 |

37 of the 45 are caught only by fault-injecting scenarios. By bug class, healthy-bus tests caught none of the
plausibility (6), recovery (7) or threshold (2) mutants in the primary set.

**Read the 91 % as the generalisation figure, not the 100 %.** The primary set (31/34 before tuning) and a
second set written afterwards and not used for tuning (10/11) agree at about 91 %. The 100 % includes four
mutants that exposed real gaps and were then used to strengthen the harness.

## Gaps the benchmark found, now closed

| Gap | Where it is asserted now |
|-----|--------------------------|
| A stale reading drawn under an OK headline passed (the helper accepted either headline) | `transient_read_failure` |
| Fault text drawn on a display that never answered passed (checked only on a healthy sensor) | `display_missing` |
| The failed-rebind guard was untestable: the fake bus could not fail a rebind | `sensor_missing_at_boot`, via `fail_begin_call` |
| Every scenario booted at `clock = 0`, so a boot-relative period was never checked | `clock_wrap` |

## Reviewed equivalents

Excluded only after a written reason in the script, and counted normally if ever killed:
`read_fault_backoff_not_reset`, `missing_recovery_clears_count_redundant`, `heldout_stale_state_not_tracked`.

## What this does not show

- It scores the project's own host tests against bugs its author chose. It is not a measurement of Wokwi,
  Flux or any other tool, and the smoke and healthy-bus detectors are subsets of this harness, not those tools.
- Mutants are hand-written (36 + 12) and cover application logic only. The Arduino adapter, the Adafruit
  libraries, the Wire driver, timing on silicon and electrical behaviour are untested here.
- Nothing here changes any authority flag: `physical_correctness` stays `UNPROVEN`, flashing and power-on stay closed.

Evidence: `docs/status/generated/device-fault-matrix-original-harness-2026-10-12.json` and
`docs/status/generated/device-fault-matrix-strengthened-harness-2026-10-12.json`.
