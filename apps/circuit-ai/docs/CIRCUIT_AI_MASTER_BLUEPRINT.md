# Circuit-AI Master Blueprint

Circuit-AI is the circuit truth layer for Hardware-Splicer. Its first production target is functional salvage: understand a board well enough to identify useful functions, prove their electrical limits, and produce a splice plan that can safely reuse those functions in another build.

## Canonical Scope

The priority order is:

1. Circuit-AI: board understanding, power/signal truth, reusable function extraction, evidence gates, and splice contracts.
2. Salvage-to-build: turn low-voltage recovered functions into useful modules, fixtures, and machines.
3. Machine composition: combine multiple verified functions into a larger product plan.
4. Mecha-Splicer and 3D-Splicer: consume verified circuit contracts later for mounting, motion, enclosures, and fabrication.

Mecha and 3D work should not drive the core architecture until circuit evidence is reliable.

## Production Contract

The core contract is `functional_salvage.v1`.

Each analyzed board can expose `functional_salvage` with:

- `FunctionalSalvageBlock`: a reusable function such as controller, wireless, sensor, power regulation, USB/UART, display, connector harness, or actuator driver.
- `ExtractabilityAssessment`: how the function can realistically be reused: connector reuse, whole-board reuse, possible board-section salvage, or not recommended.
- `ReuseEvidenceGate`: the measurement or review needed before reuse, such as rail voltage, ground continuity, logic level, current limit, or functional bring-up.
- `FunctionalReusePlan`: the salvage planner's circuit-backed splice plan, including safest entry points, required measurements, and block status.

The API must never mark a block reuse-ready only because text or inventory suggests it. Reuse-ready requires circuit-backed compatibility or closed evidence gates.

The AI contract is `circuit_ai_reasoning.v1`.

This is a backend circuit-reasoning stage, not a chat layer. It consumes the circuit graph, functional salvage blocks, connector refs, measurement gates, and the target goal. A configured LLM may propose hypotheses, missing evidence, and splice candidates, but every model claim is passed through deterministic verifier rules before it can become a proposed splice.

The required architecture is:

1. Deterministic substrate: netlist/design/image/session facts, power/signal graph, pin/connector contracts, and evidence gates.
2. Expert evidence packet: exact reusable block IDs, connector pin contracts, net neighborhoods, known part/pinout/datasheet evidence, missing gates, and allowed/forbidden claim classes.
3. AI hypothesis layer: structured JSON hypotheses about function, reuse path, missing evidence, adapter needs, and possible splices.
4. Verifier layer: blocks unsupported reuse-ready claims, blind board-section cuts, invented block IDs, wrong entry points, and unsafe power/battery/high-voltage routes.
5. Adapter synthesis: propose protected harnesses, power breakouts, load drivers, and debug/programming links only as blocked-until-evidence work packages.
6. Proof/readiness matrix: rank every reusable function by what is proven now, what is blocked, what measurement closes the block, and which adapter package is compatible.
7. Learning loop: operator accept/reject labels, measurements, pinouts, splice outcomes, and value recovered become training/eval data.

## Current Implementation Shape

- Circuit graph analysis emits board-level `functional_salvage` and top-level aggregate `functional_salvage`.
- Salvage splice planning consumes circuit-backed reusable blocks when present.
- Salvage splice planning now attaches `circuit_reasoning`, so circuit/salvage outputs include structured hypotheses and verifier results.
- Circuit reasoning includes an expert evidence packet with candidate blocks, connector pin maps, net neighborhoods, known part evidence, and adapter recommendations.
- Circuit reasoning emits a `circuit_ai_proof_matrix.v1` readiness matrix with `proof_status`, `ready_now`, `next_evidence_to_close`, `allowed_now`, `forbidden_now`, compatible adapters, a top candidate summary, and a concrete recommended first action.
- Salvage plans preserve older inventory/text behavior, but circuit-backed blocks carry priority because they include rails, connectors, evidence gates, and extractability.
- High-risk or incomplete electrical evidence keeps the result in measurement or review mode.

Primary endpoints:

- `POST /circuit/boards/analyze-design`
- `POST /circuit/sessions/{session_id}/advance`
- `POST /circuit/reasoning/assess`
- `GET /circuit/reasoning/model-status`
- `GET /vision/qwen/status`
- `POST /vision/qwen/board-evidence`
- `POST /hardware/topology-capture/template`
- `POST /hardware/topology-capture/convert`
- `POST /hardware/diy-project/plan`
- `POST /hardware/plan`
- `POST /salvage/splice-plan`
- `POST /salvage/splice-case`
- `POST /salvage/functional-workflow/golden`

The golden workflow endpoint is the practical smoke test for the whole circuit-first loop. It runs verified sensor connector reuse, blocked motor/load reuse, layout-gated regulator-section salvage, and damaged lithium safety hold scenarios through the session, circuit graph, board intelligence, salvage planner, and circuit reasoning path.

The model-status endpoint is the honest runtime check. It reports whether live model calls are actually ready: selected provider/model, whether provider keys are configured, whether the LiteLLM dependency is installed, and whether automatic model training is present. It never returns secret key values.

The Qwen vision endpoint is the native image path. Default mode is dry-run:
it redacts the uploaded image, estimates cost, and returns a request preview.
Live mode requires an explicit `live=true`, a Qwen/DashScope key, and a
positive `VISION_MONTHLY_USD_LIMIT`. Output is normalized into
`board_evidence.v1` and bridged into deterministic resources, hazards, trust,
and hardware plans. Qwen evidence remains candidate evidence and cannot clear
repair or production authority by itself.

DeepSeek can be used as a first-class model provider without LiteLLM because its API is OpenAI-compatible:

```bash
export LLM_PROVIDER=deepseek
export LLM_MODEL=deepseek-v4-flash
export DEEPSEEK_API_KEY=...
```

Then call `POST /circuit/reasoning/assess` with `use_llm_reasoner: true`. The model output remains advisory; verifier gates still decide whether a splice is allowed.

For the structured circuit contract, the DeepSeek client requests JSON output and disables thinking mode. This keeps the response in `content` as machine-parseable JSON instead of spending the whole completion budget on `reasoning_content`.

Production repair authority now emits a `production_authority_casefile.v1`.
The casefile maps each release claim to evidence and gaps: selected-resource
scope, safety authority, evidence gates, measurement coverage, measurement
provenance, terminal outcome, domain lane, release manifest, and arbitrary-board
trust where present. The regression harness is:

```bash
python3 scripts/evaluate_production_authority_regression.py
```

Arbitrary-board analysis now also emits a `bench_protocol_pack.v1`. This is the
authority-grade bench contract for the inferred board role: required equipment,
setup controls, measurement categories, pass/fail criteria, stop conditions,
required release artifacts, and record templates. Visual/model evidence can
select a protocol pack, but it cannot clear the pack. Once measured authority is
already closed, the pack remains audit guidance and does not create a fresh open
gate.

The same arbitrary-board path emits `layout_reuse_boundaries.v1`. It keeps
layout claims conservative: connector entry points are candidates until measured,
whole-board reuse is preferred when backside/geometry/topology evidence is
missing, and battery, mains/high-voltage, damaged, power-path, or load-path
regions become explicit no-cut zones.

Multi-photo visual evidence now also feeds `visual_topology_hypothesis.v1`.
This is the bridge from "what the board seems to contain" to "what the operator
should measure next": candidate connector roles, likely component-to-connector
paths, blocked pinout/net claims, and a topology measurement queue. It is not
measured topology and cannot authorize power, section cutting, or splicing by
itself.

Official schematics and product pinouts can be loaded as public reference
topology. Reference topology may map connector roles and seed the bench plan,
but the backend marks it `reference_only`; it does not create trusted
measurements, safe entry points, or ready pin-level splice contracts until the
physical board is confirmed with bench evidence.

Bench measurements now have a first-class intake path:
`bench_topology_capture.v1`. The template endpoint can seed a measurement sheet
from public reference topology or visual board evidence. The convert endpoint
turns operator-recorded connector pins, continuity, resistance, voltage, current,
and thermal readings into `topology_evidence.v1`. Production authority only
counts those rows when the capture has instrument, calibration, timestamp,
operator, and artifact provenance; template rows and public-reference seeds do
not close gates.

Visual templates also seed common non-authoritative connector references when
the evidence is strong enough: Raspberry Pi 40-pin GPIO, USB-A, USB-C logical
signals, RJ45, and HDMI. These are measurement accelerators, not truth claims.
They also expand into connector-specific bench prompts: orientation, no-short,
ground, voltage-domain, signal continuity, USB data/protection, and high-speed
reference checks. This makes the next bench step specific while preserving the
rule that real authority starts only after physical continuity, voltage,
current, thermal, and outcome evidence. A production terminal outcome is not
complete unless it records the selected resources, first-power result, thermal
result, output-function proof, cost/value/time/deviation fields, and an
`evidence_uri`, `artifact_uri`, or `test_report_uri`.

The active closure loop emits `active_evidence_closure_plan.v1`. It is the
"what would make this board knowable" coordinator above multiview evidence,
visual topology, bench protocols, trust scoring, and production authority. It
ranks the next capture, measurement, outcome, and release tasks by what they
unlock; previews the bench capture template; lists what can be claimed now; and
lists what cannot be claimed yet. It must not add open tasks for a scope that is
already closed by measured topology, trusted bench evidence, an auditable
terminal outcome, and release artifacts.

Multiview intake also emits `capture_coverage.v1`. This scores arbitrary photo
observations by reconstructive usefulness rather than by fixed top/bottom slots:
whole-board context, connector detail, marking/identity detail, safety/damage
pass, layout geometry, and optional hidden-side context. Missing lanes become
specific next capture requests.

The bench-capture regression harness is:

```bash
python3 scripts/evaluate_bench_topology_capture.py
```

Real-board corpus scoring lives at:

```bash
python3 scripts/evaluate_real_board_corpus.py
```

Cached Qwen responses can be replayed as fused multi-observation photo sets:

```bash
python3 scripts/evaluate_qwen_multiview_pipeline.py
```

Before/after evidence closure cycles are captured with:

```bash
python3 scripts/run_real_board_closure_cycle.py \
  --payload-json path/to/visual_payload.json \
  --bench-capture-json path/to/bench_topology_capture.json \
  --outcome-json path/to/outcome.json \
  --production-release-json path/to/release.json
```

New physical board sessions should enter through the intake builder:

```bash
python3 scripts/intake_real_board_case.py \
  --case-id my_board_001 \
  --goal "reuse this low-voltage board function" \
  --photo path/to/front.jpg \
  --photo path/to/closeup.jpg \
  --board-evidence-json path/to/board_evidence.json \
  --bench-capture-json path/to/bench_topology_capture.json \
  --outcome-json path/to/outcome.json \
  --production-release-json path/to/release.json \
  --required-capability connector \
  --append-manifest
```

The default manifest is `data/real_board_corpus/manifest.example.json`. Replace
the example-seed entries with real board photos, Qwen `board_evidence.v1`
artifacts, measured topology, terminal outcomes, and release manifests as those
sessions are collected.

DIY project intent now has its own backend contract:
`diy_project_engineering_plan.v1`. This is the path for "I want to build a
thing" before the operator has a clean board session or explicit capabilities.
It detects common low-voltage project profiles, such as plant watering systems,
sensor loggers, bench power adapters, fans/fume extractors, robot bases,
inspection fixtures, load controllers, and input panels. It emits required
capabilities, architecture blocks, resource strategy, build stages, evidence
gates, safety holds, and a handoff patch for `hardware_plan`.

This does not replace the board reasoning engine. It is the front door above it:
constrained/junk input means the resource pool is a premade puzzle; open
procurement means missing functions can be bought or designed; hybrid mode reuses
proven resources and buys only the gaps. In all modes, the planner remains
blocked before wiring/power/release until the existing measurement, outcome, and
authority gates close.

## First Hardening Slice

The first production slice is low-voltage board-function reuse:

1. Analyze a controller or sensor-style board from netlist/design evidence.
2. Detect reusable functions and connector-level entry points.
3. Require voltage, ground, logic, current, and functional gates before interconnect.
4. Feed those blocks into the salvage planner.
5. Produce a splice plan that says what to connect, what to measure, and what blocks reuse until proof exists.

Acceptance criteria:

- Circuit output includes reusable blocks with extractability and evidence gates.
- Salvage output includes a circuit-backed `functional_reuse_plan`.
- Salvage and reasoning output include `circuit_ai_reasoning.v1`, with model claims separated from verified splice proposals.
- Reasoning output includes connector contracts, net neighborhoods, known part evidence, adapter recommendations, proof matrix, measurement plan, and recommended first action.
- The plan does not invent blocks when explicit inventory or circuit evidence does not support them.
- Battery, mains, high-voltage, and failed measurement cases stay blocked.
- The end-to-end flow remains API-compatible with the existing board-session loop.

## Expansion Path

After the first low-voltage slice is reliable:

1. Add more function families: displays, audio, power modules, motor drivers, wireless modules, USB bridges, and sensor boards.
2. Add layout-aware extractability so board-section salvage can be assessed with geometry instead of guessed from function alone.
3. Add portfolio scoring across piles of boards: highest value, easiest proof, safest reuse, and missing adapter parts.
4. Feed verified contracts into machine composition.
5. Feed verified electrical contracts into Mecha-Splicer and 3D-Splicer for physical mounting and fabrication.
