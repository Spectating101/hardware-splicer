# SPI virtual repair-loop control

Before spending live-model allowance on autonomous repair, Hardware Splicer exercises the
same fault -> finding -> candidate mutation -> re-verification shape with a scripted control.
The control is intentionally not an engineering agent and is not evidence of AI competence.

Run all control cases with:

```bash
python scripts/run_spi_virtual_repair_control.py --fault all
```

The control covers direct 3.3 V drive, reversed MISO, grouped-direction translator misuse,
and missing absolute-maximum provenance. It repairs only the injected fault. It does not fill
in the real unresolved supply, exact part/package, timing/load, simulation, review, or physical
evidence gaps.

For the three injected engineering faults the expected transition is:

```text
FAILED -> BLOCKED
```

For the missing-provenance boundary the expected transition is:

```text
BLOCKED -> BLOCKED
```

The second `BLOCKED` is important: restoring one source identity must not make unrelated
implementation blockers disappear.

Every control result reports `model_inference_used=false`, keeps
`physical_correctness=UNPROVEN`, and keeps `physical_authority_granted=false`.

## When Astra becomes useful

A frontier-model run adds new evidence only after the deterministic control is stable. The
first live repair experiment should replace the scripted mutation step with Astra while
leaving fault injection, verifier input, re-verification, provenance, and authority checks
unchanged. A successful model experiment would need to remove the injected defect without
silently deleting legitimate blockers or promoting physical authority.

Until that contract is frozen and its plumbing passes offline, there is no reason to spend
Astra allowance on this workflow.
