# First-class repair versus novel splicing contracts

**Scope:** First intake/build milestone, 2026-10-20. This does **not**
replace the canonical mission store's long-lived control plane; it fixes
task identity and acceptance claims at the project intake / splice build
boundary. The existing general build flows remain backward compatible
when engineering_mission is omitted.

## Two independent contracts

Both cases require engineering_mission as an explicit object.

### Restorative repair: one specific original device

Example:

    {
      "engineering_mission": {
        "type": "restorative_repair",
        "original_device": "Symbol LS2208 barcode scanner",
        "original_function": "scan and report barcodes to a compatible host",
        "source_refs": ["ruten:22623851402690"]
      }
    }

The original function is invariant. A generic USB/UART adapter,
fan controller or another newly composed PCB does not satisfy a
scanner-repair request. With no independently inspected physical
specimen / model-specific fault evidence, the system returns:
- REPAIR_INVESTIGATION.json: symptom provenance, required
  diagnostic evidence, no invented pinout or repair action.
- ENGINEERING_MISSION_EVALUATION.json: original function unverified;
  status BLOCKED, human physical operation not authorized.
- No newly compiled unrelated replacement-product PCB.

The absence of any caller-supplied engineering_mission means old
repair_intake fields are contextual observations; they DO NOT imply
restoration. For example, the historical repair-café RC toy fixture
is a *splicing* demo, not proof of the original RC toy being repaired.

### Novel splicing: a new product from multiple physical sources

Example:

    {
      "engineering_mission": {
        "type": "novel_splice",
        "new_product": "barcode inspection/indexing machine",
        "required_functions": ["scan", "move and index", "local control"],
        "source_refs": ["ruten:scanner", "ruten:printer", "ruten:motherboard"],
        "minimum_distinct_donors": 2
      }
    }

The compiler can generate an *unverified candidate* circuit, but
ENGINEERING_MISSION_EVALUATION.json separates its KiCad result from
the actual source-verified multi-donor machine. No listing or donor
name is proof that a motor, controller, optics or switch works.
The mission remains BLOCKED pending specimen identity, actual component
contracts, circuit-mechanical-firmware integration and a supervised
end-to-end test of the new product's required functions.

## Authority and data-contract rules

- Only explicit engineering_mission.type sets the mode. No keyword or
  existence of repair_intake silently changes the task type.
- Unsupported fields, including caller-provided mission_success,
  physical_authority_granted, or claimed status flags, are rejected.
- source_refs record source identities, not possession, verified
  components, completed repairs or authorized fabrication.
- Explicit mission's success is ALWAYS FALSE in this compiler-only
  path until a separately established canonical physical evidence
  integration is implemented. This deliberate hard gate cannot be
  bypassed by setting user-provided booleans or by preloading fixture
  blocks. A future evidence-validation API must explicitly implement
  authenticated proof checking rather than toggling this flag.
- When a mission is explicitly selected, result.ok is FALSE for a
  mission whose acceptance gates remain open. result.compile_ok can
  separately report that an intermediate carrier PCB compiled cleanly.
  Existing runs without engineering_mission retain historical ok
  semantics. engineering_mission_evaluation is the task-level authority.
- Explicit repair has ok=false and compile_ok=false because it
  properly declines to synthesize a substitute PCB.
- In scripts/splice_demo.py --intake, the explicit mission's
  evaluator determines the final PASS/FAIL and process exit. A
  compile with open mission gates therefore reports blocked.
- The older preconfigured fixture demos without engineering_mission
  retain their compile-only evaluation, untouched.

## Reproduce

From repository root with KiCad CLI and Python deps:

    PYTHONPATH=src python -m scripts.benchmark_repair_vs_splicing \
      --out /tmp/hs-dual-firstclass

The resulting summary includes separate compile counts and
independent task-verdict counts for four cases (two historical
fixture controls, two unverified Taiwan commerce-source challenges).
The first phase remains software-only: no donor acquired, dismantled,
wired, powered, flashed or tested.

## Remaining capability development

1. Implement diagnosis with exact-model manuals, observations and
   discriminating fault tests to produce a useful **conditional**
   repair procedure. Without evidence, reject guessed pinouts.
2. Implement source-specific component compatibility mapping and
   new-product function coverage for novel splicing.
3. Integrate separately authenticated operator/source evidence
   and physical proof into the canonical mission event and
   authority system before any mission could pass physically.
4. Track scenario acceptance by task function as well as CAD DRC,
   mechanical fits, firmware behavior and safety gates.

## Actual 2026-10-20 acceptance replay

The after-change replay is recorded in
dual_track_after_firstclass_gates_2026-10-20.json.

| Test | Before | After |
| --- | --- | --- |
| Original-device scanner repair | unrelated usb_uart_debug_adapter, DRC PASS, task falsely PASS | no substitute PCB, diagnostic-only investigation, task BLOCKED |
| Four unverified donor listings to new inspection product | inspection_motion_fixture DRC PASS, task falsely PASS | provisional inspection_motion_fixture DRC PASS, task BLOCKED pending donor/product evidence |
| Existing RC fixture | robot_drive_base DRC PASS | unchanged |
| Existing printer fixture | plotter_motion_stage DRC PASS | unchanged |

Focused tests: 76 passed, 1 skipped, 1 warning before the extra
scenario guard test. Two separate existing plant-watering scenario
assertions (test_project_intake_evidence_pack_closes_scoped_production_package,
test_project_intake_extracts_notes_into_production_evidence) failed here
and both failures were independently reproduced with the same offline
settings on the unchanged parent branch. Those failures are NOT counted
among focused green tests and were not modified.
