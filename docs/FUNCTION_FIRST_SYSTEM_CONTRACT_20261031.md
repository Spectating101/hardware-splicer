# HS Function-First Bridge — System purpose before components

**Date:** 2026-10-31
**Authority:** Functional concept only. No measured flow, treatment capability, sensor accuracy, physical readiness, build authorization, or potable-water claims.

## Why this exists

HS can already prove isolated electrical/PCB, firmware, mechanical and simulation toolchains. The remaining architectural gap is the *entry contract*: what a machine or device must accomplish **before** selecting a circuit board, CAD form factor, filter medium, actuator or manufacturing process.

This PR **reuses** the canonical `MachineProject` model (`Requirement`, `Function`, `Subsystem`, `Interface`, `VerificationMethod`) rather than adding a competing project registry. It also complements, rather than supersedes, the existing `apps/3d-splicer/FUNCTIONALITY_FIRST.md` (which is narrowly about optimizing an enclosure). The new bridge covers *cross-domain purpose, measurable outcomes, physical input/output streams, system functions and engineering ownership*.

## First executable example — non-potable water treatment concept

The source `examples/functionality/water_filter_nonpotable_bench_001.json` states an **unbuilt bench demonstration** goal. All target values are user-style desired specifications, *not* measured product properties:

- Proposed output flow >= 0.5 L/min in a defined pressure/media condition.
- Proposed >= 70% turbidity reduction for a **specified, controlled non-potable particle challenge**. This does not assert bacteria, pathogens, arsenic, lead, PFAS, heavy metals or drinking safety.
- Zero externally visible leaks in a pressure test whose actual operating pressure must first be defined.
- No unobserved bypass of filter media, independently checked during physical assembly.
- Wet/dry separation, safe media replacement and differential-pressure monitoring.
- Explicit no-consumption labeling and no health or certification claim.

It compiles into six functional operations, five engineering subsystems and four explicit medium-carrying interfaces (wet fluid path, flow/measurement, cartridge maintenance). Every requirement maps to a function, owner and an unexecuted test. Unknown working pressure, seal compression, selected filter media, sensor range, tolerances and human-safety evidence are visible blockers.

**No architecture candidate or media is certified or selected by this step.** Further candidate generation should choose/reject real treatment mechanisms using actual inlet challenge, media performance evidence, compatible wetted material ratings, pressure loss and lifecycle economics. Do not assume a water filter can handle unspecified contaminants.

## Example run

```bash
python -m pip install -e '.[dev]'
pytest -q tests/test_function_intent_bridge.py
python scripts/compile_function_intent_001.py \
  --brief examples/functionality/water_filter_nonpotable_bench_001.json \
  --out /tmp/hs-function-water-001
```

The generated `FUNCTIONAL_INPUT.json`, `MACHINE_PROJECT.json`, `FUNCTIONAL_GATE.json` and `PACKAGE_RECEIPT.json` are source-hashed. The original functional specification determines every requirement, function, subsystem, interface and test. The bridge intentionally refuses to import “passed” or “measured” claims from a proposed brief, refuses potable/certified claims, refuses missing tests and source/graph inconsistencies, and declines to overwrite prior evidence.

The CI test also creates an unrelated **temperature-alarm device** through exactly the same bridge. This checks that the implementation is not just a hardcoded water-filter generator.

## Integration into the broader HS stack

After an external operator selects and justifies a candidate physical process and closes the unknown interfaces, downstream HS disciplines may receive a compatible slice of the existing project:

- **Process / physics:** candidate media, challenge definition, rate, residence time, hydraulic head and pressure loss — simulations only after actual parameters exist.
- **Mechanical / materials:** wetted vessel, cartridge seals, water compatibility, burst/leak evidence, service access.
- **Electronics / firmware:** optional calibrated pressure/flow instrumentation and human-readable warnings, without treating a pressure reading as a water-quality measurement.
- **Sourcing / manufacturing:** identified rated parts, exact revisions, installation and cleaning methods, compliance and operator gates.

No downstream generator is invoked *yet*. The present implementation is a tested front-end specification gate that prevents an engineering agent from optimizing the wrong design.

## Regulatory and evidence limits

See https://www.nsf.org/consumer-resources/articles/standards-water-treatment-systems and https://www.cdc.gov/drinking-water/prevention/about-choosing-home-water-filters.html for relevant distinctions between aesthetic filtration, health effects and reverse osmosis. An NSF/ANSI standard is not a certification of a hypothetical device. This bench demo must **never** be presented as a potable device; intended-use expansion requires explicit, contaminant-specific evidence, certification research and supervised expert review.

## Next acceptance milestones

1. Run the functional CI and verify its source hashes, MachineProject cross-reference integrity, zero “passed” physical tests, and refusal of corrupted claims.
2. Extend planning with alternative *process candidates* and rejection grounds tied to the explicit challenge rather than a single predetermined CAD layout.
3. Select one evidence-backed, commercially available filter cartridge and independently verify its application, pressure ratings, media service interval and contamination claims.
4. Connect one verified candidate into actual mechanical/flow analysis and optional sensor/toolchain output; preserve the exact source-intent digest across every artifact.
5. Compare functional-first HS output against a skilled domain engineer and another agent using the same non-potable design brief; record corrections, completeness, testability and time.

Do not treat this as a drinking-water treatment design, measured prototype, completed physical filter, or engineering proof of contaminant reduction.
