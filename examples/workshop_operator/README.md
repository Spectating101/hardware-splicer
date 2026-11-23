# Hardware Splicer — first consolidated engineering operator

**Status: bounded software operator pilot, not a new HS subsystem and not physical product validation.**

This work unifies two **existing** HS engineering routes behind one executable
work order. It is based directly on `main`, not the long cyberdeck PR stack.
This fixes an operational problem: a DRC-clean **generic board** can be produced
even when an unrelated donor repair has not been identified.

## The single interface

```bash
# Show exactly the workflows this operator can safely route
python3 scripts/hs_workshop_operator.py --list

# No side effects by default; one machine-readable plan and handoff
python3 scripts/hs_workshop_operator.py --case robot_repair_cafe_s3 \
  --out /tmp/hs-operator-preview

# Execute approved SOFTWARE tools, with a new directory for every attempt
python3 scripts/hs_workshop_operator.py --case spi_flash_adapter_reference \
  --out /tmp/hs-operator-spi-run --execute

python3 scripts/hs_workshop_operator.py --case robot_repair_cafe_s3 \
  --out /tmp/hs-operator-repair-run --execute
```

The repair command exits **2** when it cannot complete the registered
engineering case. It is not a crash. A source/test/tool error is also a
failure, never an automatic fallback. A successful native design run exits 0;
no command grants power-on or manufacturing authority.

Each run writes `HS_OPERATOR_RESULT.json` and `ENGINEERING_HANDOFF.md`.
The report records exact registered source SHA-256, chosen native engine, stage
status, evidence/artifact SHA-256, unresolved blockers, and the **canonical
MachineProject** release assessment. It has no path for arbitrary shell
commands, third-party repo installation, device access, or LLM-derived authority.

## Actual current Optiplex observations

| Case | Execution and independent evidence | Outcome |
|---|---|---|
| SPI flash adapter source review | **Original** `verify_design.py` ran in a separate staging directory using KiCad 9.0.2 and pcbnew, checking ERC, DRC, schematic/pad parity, BOM, ground zones, pin nets and more; every independent verification category reported **0 problems**. All **9 source-input hashes** matched the new verifier receipt, and the design source stayed unchanged | `verified_design_only_physical_blocked` |
| RC toy repair-café donor | Existing `load_project_intake`, board vision evidence and salvage planner ran. In the captured run, **no source-backed non-generic drive base** or reusable donor functional block was resolved; the workflow refused to generate a generic placeholder board | `blocked_unresolved_donor_architecture` |

These are *runtime observations*, not artificial success stubs. The compact
[recorded receipts](pilot/) and human handoffs are committed for independent
inspection, with source identity hashes retained.

### Another important RC failure found during development

Running the legacy `splice_demo.py` directly could produce a **DRC-clean
generic_low_voltage_build** despite the target requiring
`robot_drive_base`. Its case-level evaluation correctly failed, but the
large generated package could look deceptively complete.

During another operator trial, the existing planner did choose
`robot_drive_base` and found reusable blocks, and the case-level evaluator
passed. However the compiler's **manufacturing reconciliation still failed**:
the compiled board graph contained components absent from the BOM.
The operator rejected that outcome as well. This difference is why the
operator validates independently across *intent, source identity,
actual artifact, manufacturing reconciliation and bench authority*.

These RC outcomes are not deterministic because the installed planner/model
path may vary with environment. The tests inject precise adversarial cases and
require **both** failure modes to remain blocking. A correct repair is never
claimed on the strength of its internal DRC alone.

## Why native tool reuse matters

- **SPI**: stages the *complete original source*, including local symbol
  library and KiCad project rules. Stripping to just `.kicad_sch` and
  `.kicad_pcb` can produce dozens of false ERC violations; the real
  published verifier correctly checks project-specific context.
- **Repair**: uses `project_intake.plan_project_from_intake` rather than
  implementing another donor/vision model. Only if a non-generic architecture
  and donor blocks are resolved does it call the existing
  `splice_manifest.run_splice_case` compiler.
- **Release**: uses `MachineProject.assess_release`. A passed KiCad design
  has **software evidence only**, no physical measurement and no authorization.
- **Tool selection**: two explicit, reviewed routes. Arbitrary natural-language
  task execution, GitHub source-native tool dispatch and new model-driven
  route selection are **not claimed**. The already-merged worker controller
  remains separate until a reviewed adapter proves it can add value.

## Reproduce and verify

```bash
# Tests include actual native KiCad verification when KiCad/pcbnew is present;
# deterministic negative/adversarial tests run without those optional tools.
PYTHONPATH=src python3 -m pytest -q tests/test_workshop_operator.py

# Reuse the actual existing case scripts for comparison.
python3 scripts/splice_demo.py --case robot_repair_cafe_s3 \
  --out /tmp/hs-existing-repair-replay
```

The SPI case source identity is computed from **Git-tracked files** in the
registered reference directory. Native KiCad and unrelated tests may generate
ignored/untracked artifacts there; those files neither pollute the recorded
source SHA nor get staged into the verifier. Every tracked input is still
hashed and checked for modifications, and paths are restricted to the
registered source tree. This repairs a full-suite CI hash mismatch without
loosening the actual KiCad/verifier acceptance criteria.

Tests reject stale green receipts, modified source hashes, a missing source
file, wrong path/case, unregistered execution, unverified donor identity,
manufacturing/BOM inconsistency, and forged power authorization.

## Concrete next acceptance milestone

This operator's first proven value is **not passing everything**. It is
executing an actual existing design verification **and** refusing a wrong
design for a damaged donor. Next, integrate one independent externally
documented repair case with traceable source-to-measurement evidence, without
tailoring a fixture to its answer. Then extend the approved capability registry
to existing mechanical and remote GitHub worker routes *only when* the case
needs those tools.

**Not done:** no damaged device was acquired or repaired; no SPI board was
fabricated; no independent technician performed measurements; no unattended
general-purpose design agent has been validated.
