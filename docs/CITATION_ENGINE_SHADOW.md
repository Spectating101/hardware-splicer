# Citation Engine shadow integration

**Status:** bounded consumer candidate on branch `citation-engine-shadow`.

Hardware-Splicer remains the authority for electrical evidence and physical bring-up. Citation Engine records the already-evaluated golden-real authorization path; it does not decide whether a voltage, contract, DRC result, firmware state, or power-on gate is valid.

## Live seam

`scripts/verify_splice_real_bench.py` runs the real golden S3 path and receives `SPLICE_GOLDEN_REAL_REPORT.json` from `run_splice_golden_real()`.

Only after Hardware-Splicer has computed that report does the bridge call:

```python
record_golden_real_report(report)
```

The bridge maps the existing pass condition into six inspectable neutral gates:

1. `drc_pass`
2. `contract_updates_ok`
3. `firmware_authorized`
4. `bench_submission_ok`
5. `power_on_authorized`
6. `not_simulated`

Each gate gets its own canonical evidence artifact. Citation Engine then records the already-computed Hardware decision, mirrors an authority transition only for an authorized run, issues a receipt, and exports a rooted bundle fingerprint.

## Important boundary

Hardware-Splicer currently defines `report.passed` as the conjunction of the same six conditions. The bridge checks that the declared result and the mapped gates agree.

If they disagree, strict mode raises rather than creating a misleading clean receipt:

```bash
HARDWARE_SPLICER_CITATION_ENGINE_STRICT=1
```

This is a consistency guard, not a second electrical calculation.

## Runtime modes

Default shadow mode is enabled and fail-open. To disable independently:

```bash
HARDWARE_SPLICER_CITATION_ENGINE=off
```

Optional durable canonical log:

```bash
HARDWARE_SPLICER_CITATION_ENGINE_STORE=/path/to/hardware-citation-engine.jsonl
```

The normal Hardware-Splicer install path pins Citation Engine to reviewed commit `01066927ce2949ccbee40a1245d81421ef517906`.

## Trace shape

The golden-real verification summary gains a `citation_engine` object containing:

- `runRef`
- `decisionRef`
- `decisionDigest`
- `authorityRef` or `null`
- `receiptRef`
- `receiptDigest`
- `bundleSchema`
- `bundleFingerprint`
- `bundleObjectCount`
- store mode/path

The original Hardware report fields are unchanged.

## Validation

Focused bridge tests cover:

- authorized report → decision + authority + receipt;
- blocked report → decision + receipt, no authority transition;
- contradictory `report.passed` vs gate evidence is rejected in strict mode;
- independent kill switch;
- JSONL persistence is idempotent for repeated identical reports.

Local reconstructed result against the exact Phase-3 Citation Engine source:

```text
5 passed
```

## Promotion posture

This remains shadow evidence infrastructure. Citation Engine is not yet allowed to override Hardware-Splicer's native bench authority. A future enforcement step would require an explicit statement of which Hardware transition the kernel may block and why.
