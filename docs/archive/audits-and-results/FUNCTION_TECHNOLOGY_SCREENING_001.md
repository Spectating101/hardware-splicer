# Technology-Option Screening 001 — Functionality → candidate process → engineering study

**2026-10-31** · Extends draft PR #236, reuses the existing `MachineProject` model.
**Authority:** preliminary engineering-screening hypothesis only. No selected commercial filter medium, verified treated-water quality, qualified wetted materials, actual CAD/CFD output, or physical-build authorization.

## What changed

Instead of immediately choosing a board or drawing an enclosure, the function-first source package feeds a **separate, testable technology comparison**. The input consists of the exact source-hashed `FUNCTIONAL_INPUT.json`, `MACHINE_PROJECT.json`, `FUNCTIONAL_GATE.json`, `DISCIPLINE_WORK_PACKAGES.json` and their receipt (produced by the already green PR #236 workflow). The technology catalog is a second, versioned proposal, not a hidden LLM decision.

The new `function_technology_selection.py`:

1. Recomputes the original MachineProject, function gate and work packages from `FUNCTIONAL_INPUT.json`. Hash and byte mismatch, even against a resealed upstream artifact, is fatal.
2. Checks every proposed technology against **all seven mandatory requirements** (flow, challenge-specific particle removal, leakage, bypass isolation, service, instrumentation and explicit non-potable labelling).
3. Every purported mechanism-to-requirement link must include a concrete proposed design operation and `unverified_hypothesis` status. If a mandatory requirement is omitted, an explicit engineering incompatibility reason is required before rejecting the option.
4. For conceptually eligible alternatives, the stated **study-order heuristic** uses fewer newly introduced subsystems, then fewer open parameter assumptions, then candidate ID. This is only a reproducible comparison of investigation complexity; **not** measured treatment efficacy, cost, power use, performance or engineering superiority.
5. Produces a `PROVISIONAL_ARCHITECTURE_HANDOFF.json` mapping the *preferred study* mechanism to the original five engineering assignments, tests, interfaces and missing measurements.

## Initial non-potable demonstration options

| Candidate | Requirement coverage | Screening outcome | Why |
|---|---|---|---|
| Passive replaceable depth-media cartridge | 7/7 proposed functional mappings | **Provisional first design study** | Requires fewer new subsystems, but inlet head, media performance, seal integrity and instrument specification are all unknown |
| Pump-assisted membrane cartridge | 7/7 proposed functional mappings | Eligible second study | Additional pump, motor-power and control subsystems; pressure, fouling and power evidence missing |
| Coarse strainer **alone** | 6/7 | Reject | This proposal has not established a justified process for the defined particulate turbidity challenge |
| Activated-carbon adsorption **alone** | 6/7 | Reject | This proposal addresses an unspecified dissolved constituent rather than the stated suspended-particle challenge |

**These are engineering hypotheses.** Even 7/7 proposed mappings are not 7/7 completed tests or verified water treatment. The scenario's 0.5 L/min and 70% turbidity targets are *design requests*, never measured device outputs.

## Reproduce locally or in CI

```bash
python -m pip install -e '.[dev]'
python scripts/compile_function_intent_001.py \
  --brief examples/functionality/water_filter_nonpotable_bench_001.json \
  --out /tmp/hs-water-function
pytest -q tests/test_function_technology_selection.py
python scripts/compare_function_technologies_001.py \
  --functional-package /tmp/hs-water-function \
  --options examples/functionality/water_filter_technology_options_001.json \
  --out /tmp/hs-water-study
```

CI runs two jobs: upstream function traceability first; the new option-screening job downloads the **same-run** function package and independently verifies source hashes, alternatives, deterministic screening decision and closed authority. Outputs:
- `FUNCTIONAL_SOURCE_RECEIPT.json`
- `TECHNOLOGY_OPTIONS.json`
- `TECHNOLOGY_DECISION.json`
- `PROVISIONAL_ARCHITECTURE_HANDOFF.json`
- `TECHNOLOGY_STUDY_RECEIPT.json`

Adversarial tests cover unsatisfied mandatory requirements hidden without rejection reasons, different project identity, altered functional intent even with updated digest, false physical treatment claims, fabricated measurements, forged manufacturing authority, unknown subsystem identities, deterministic revision change and no-eligible-option behavior.

## Boundary and next actual engineering step

No candidate is a certified product or commissioned treatment process. All outcomes remain `PROVISIONAL_FOR_DESIGN_STUDY_ONLY` or `NO_CANDIDATE_COVERS_REQUIRED_FUNCTIONS`. All engineering discipline verification stays `not_executed`. This concept example explicitly forbids drinking-water claims.

For the preferred passive-media concept, **before CAD or equipment**, determine the nature and size distribution of non-potable test particles, characterize available feed pressure/head, identify one exact manufacturer-rated cartridge and housing, obtain pressure-flow and media/seal compatibility evidence, and design repeatable challenge testing. Then reuse HS's native CAD and inspection stack on a physically justified, source-bound design. The next gate is not just prettier geometry: it is a testable **separation process and compatible fluid path**.

Do not publish water-quality, filtration effectiveness, product pricing, suitability-for-drinking or physical-system safety claims from these outputs.
