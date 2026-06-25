# Circuit Logic Audit

Date: 2026-06-20

Scope: audit whether Hardware-Splicer currently contains a true circuit-algebra /
schematic-synthesis core, or whether it is primarily a readiness-checking and
carrier-build spine around known modules, manifests, donor evidence, and checks.

## Executive Conclusion

Hardware-Splicer already has real structured circuit representation, but it is
not yet a full component-level circuit algebra or general schematic synthesis
engine.

The current system is best described as:

```text
CircuitIntent + bounded topology planners
  -> SynthesisCandidate
  -> known modules / manifests / donor evidence / simple netlist IR
  -> BuildGraph or CircuitNetlist
  -> KiCad carrier/build package
  -> ERC/DRC/fabrication/bench/readiness checks
```

It does contain the outer spine needed for a future synthesis system:
structured intake, module metadata, ports, wires, netlist lowering, ERC, build
graph compilation, fabrication inspection, casefiles, bench gates, SDK/MCP/HTTP
surfaces, repeatable verification paths, and a first bounded topology-planning
layer for selected battery-power, power-rail, level-shift, analog-conditioning,
sensor/interface, relay-switch, H-bridge, and motor-driver cases.

It does not yet contain:

- a general first-class topology algebra for arbitrary series, parallel,
  high-side/low-side switching, filters, protection, biasing, drivers, or
  dividers beyond the bounded operators already implemented;
- general from-scratch schematic synthesis from arbitrary functional goals;
- behavioral simulation-based design selection;
- analog, power integrity, signal integrity, thermal, or derating optimization;
- arbitrary-board engineering from photos or free text without human evidence
  and bounded assumptions.

The honest claim today is: Hardware-Splicer can plan a small set of bounded
topologies, assemble/check bounded module/netlist/build paths, and preserve
evidence. It is moving from a pre-fabrication readiness and splice/build system
toward circuit synthesis, but it is not a general ECAD synthesis engine.

## Verification Status Observed

These commands were run before writing this audit.

| Command | Status | Notes |
|---|---:|---|
| `make setup` | PASS | Environment and doctor checks completed. |
| `make verify-engine` | PASS | `18/18` catalog builds compiled and passed KiCad DRC. |
| `make verify-tier-c` | PASS | Functional delivery audit reported average `100.0`; pytest `5 passed`. |
| `make verify-geometry` | PASS | Geometry checks passed for listed build cases. |
| `make verify-splice` | PASS | `4/4` splice demo cases passed. |
| `make verify-splice-loop` | PASS | `3/3` golden loop cases passed. |
| `make verify-splice-real-bench` | PASS | Golden real bench replay now syncs a fresh template and closes the power-on gate. |
| `make verify` | PASS | Full verification passed after the offline tier-score and golden-real-bench fixes. |

Important audit findings from verification:

- The S2 splice carrier path is currently strong.
- The simulated/golden bench loop passes.
- The real manual bench replay path now passes on the committed golden capture.
- The top-level `make verify` target now runs offline-safe tier scoring in this
  environment.

Update 2026-06-22:

- `make test` passes: `556 passed, 4 skipped`.
- `make verify-engine` passes: `18/18` catalog builds compile and pass KiCad
  DRC.
- `make verify-netlist-engine` passes: `fixtures=18 drc_clean=18`.
- `make verify-catalog` passes and exports frontend catalog JSON.
- `make verify` passes end-to-end after hardening default verification against
  live Qwen salvage calls, JLC enrichment calls, and native KiCad STEP export in
  tier scoring.
- `make verify-splice-real-bench` now passes after forcing golden-real replay to
  open a fresh bench session and sync a current capture template before applying
  the committed manual capture.
- `make score-intake-tiers` now runs with explicit offline LLM flags in the
  Makefile, so tier scoring no longer reaches the Qwen workshop path during
  default verification. It also disables Qwen salvage resolution and native
  KiCad board STEP export for the scorecard path.
- Circuit synthesis gained a safe arbitrary dispatcher and compile bridge:
  supported battery-power, power-rail, level-shift, analog-conditioning,
  sensor/interface, relay-switch, H-bridge, and motor/pump/fan/solenoid intents
  route to bounded planners, while unsupported arbitrary goals produce a
  structured blocked candidate instead of a generated schematic.
- Ready bounded synthesis candidates now compile through a strict
  selected-module graph-to-netlist path instead of the scratch composer, so the
  bridge does not silently add unrelated modules.

Update 2026-06-23:

- Focused synthesis regression passed: `26 passed` across
  `tests/test_circuit_synthesis_ir.py`,
  `tests/test_circuit_synthesis_bridge.py`,
  `tests/test_motor_driver_planner.py`, and
  `tests/test_circuit_synthesis_planners.py`.
- The bounded synthesis dispatcher now routes eight families:
  battery power, power rail, level shift, analog conditioning,
  sensor/interface, relay switch, H-bridge motor drive, and low-side
  motor/pump/fan/solenoid drive.
- New direct SDK/API surfaces were added for H-bridge, relay switch, analog
  conditioning, and battery power planning.
- The auto-wire layer was tightened for motor-driver and relay cases. A barrel
  supply now remains available as the motor/load rail, relay variants get
  explicit control/power wiring, and H-bridge motor loads are not generically
  tied to common ground.
- Earlier H-bridge load modules were kept as topology/bench evidence because
  the safety checker treated motor load pins named `GND` as literal ground,
  while H-bridge motor terminals are floating outputs.

Update 2026-06-23 later:

- A first operator-lowering layer now exists in
  `src/hardware_splicer/circuit_synthesis/operator_lowering.py`.
- `compile_synthesis_candidate` applies topology lowering before graph-to-netlist
  conversion and preserves the lowering report in the compile payload.
- BuildGraph/netlist round-trips now preserve `terminal_semantics` and
  `topology_lowering` metadata.
- The electrical safety checker now honors effective terminal roles before
  applying GND/power/digital rules.
- H-bridge motor loads can now stay in the strict compile graph: motor pins
  behind the bridge are marked `floating_motor_terminal`, so a catalog pin named
  `GND` no longer becomes common ground by accident.
- A second lowering step now emits virtual `support_components` and
  `topology_nets` for voltage dividers, RC filters, pull-up networks,
  transient/clamp protection, battery charger paths, and regulator paths.
- Selected support items now lower further into physical synthetic graph nodes:
  analog voltage-divider resistors, ADC RC-filter resistor/capacitor parts, and
  I2C pull-up resistors get refs such as `R1`, `R2`, `R3`, `C1`, footprints,
  graph wiring, netlist components, schematic footprint properties, and BOM
  lines marked `synthetic_support`.
- Ambiguous items such as ADC clamps, TVS/snubbers, protected cells, and battery
  protection boards remain review-required support evidence rather than fake
  placed parts.
- A topology primitive library now defines the trusted backend synthesis
  ceiling: low-voltage mechatronics primitives such as low-side switch, motor
  driver, H-bridge, relay driver, voltage divider, RC filter, pull-up/pull-down,
  sensor interface, level shifter, regulators, battery charger path, and
  review-limited protection.
- `topology_authority` reports are now attached to synthesis compile payloads.
  They state whether the candidate is inside the trusted ceiling, which
  operators are planned-only or review-limited, how many physical support parts
  were inserted, and the next authority gap.
- This does not make general synthesis complete. It is the first real bridge
  from topology operators into compile semantics and explicit support-part
  requirements.

## Current Internal Representation

The repo uses a mixture of representations rather than one complete circuit
algebra.

| Representation | Evidence | What it means |
|---|---|---|
| Module library | `src/hardware_splicer/pcb/module_registry.py`, `data/engine_pcb_data.json` | Known hardware modules with IDs, labels, categories, capability tags, pins, voltage/current notes, and geometry hints. |
| BuildGraph | `src/hardware_splicer/auto_wire.py`, `src/hardware_splicer/plan_to_graph.py`, `src/hardware_splicer/compile_stages.py` | Nodes are module instances; wires connect module pins. This is the main compile input for carrier generation. |
| Catalog recipes | `data/catalog_recipes.json`, `src/hardware_splicer/plan_to_graph.py` | Named build archetypes and role/wire recipes. |
| CircuitNetlist IR | `src/hardware_splicer/netlist/ir.py`, `src/hardware_splicer/netlist/lower.py`, `src/hardware_splicer/build_compiler.py` | Components and nets with pin references. It can lower between BuildGraph and netlist form and compile netlists. |
| Circuit synthesis IR | `src/hardware_splicer/circuit_synthesis/` | Bounded `CircuitIntent`, `TopologyOperator`, `Constraint`, and `SynthesisCandidate` layer for selected battery-power, power-rail, level-shift, analog-conditioning, sensor/interface, relay-switch, H-bridge, and motor-driver cases. |
| Canvas / scratch compose | `src/hardware_splicer/compose_dispatch.py`, `src/hardware_splicer/scratch_pipeline.py` | User/module/canvas input routed through one compose spine. |
| Splice / donor case data | `examples/splice/manifest.json`, `src/hardware_splicer/salvage_bridge.py`, `src/hardware_splicer/project_intake.py`, `src/hardware_splicer/board_vision_salvage.py` | Donor evidence becomes functional salvage candidates, splice plans, and build inputs. |
| Evidence / casefiles / gates | `src/hardware_splicer/casefile.py`, `src/hardware_splicer/compile_casefile.py`, `src/hardware_splicer/splice_bench.py`, `src/hardware_splicer/bench_capture_bridge.py` | Success and failure are recorded as auditable artifacts rather than only chat responses. |

Answer to the core question:

Hardware function is partially represented as components + ports + topology +
constraints + evidence. The strongest pieces are components, ports, selected
bounded topology operators, net connections, physical outputs, DRC/fabrication
checks, and bench gates. The weak piece is still general electrical/topology
reasoning: the system can plan a few bounded circuit families, but it does not
yet synthesize arbitrary circuits from operators and constraints.

## Component Knowledge

Current component knowledge is real but uneven.

Present:

- module ID and label;
- category and capability tags;
- pin IDs and pin roles;
- some voltage/current metadata in module pins;
- logic voltage hints for some modules;
- body dimensions, footprint names, pad geometry or synthetic pad placement;
- limited default current estimates for power-budget simulation;
- module-specific heuristics in auto-wire and safety rules.

Partial or missing:

- first-class behavior classes;
- required support components as explicit structured requirements;
- thermal derating curves;
- full current limits per path and trace;
- regulator dropout/efficiency models;
- analog behavior;
- motor transient/stall modeling;
- protection requirements as formal constraints;
- tolerance, frequency, EMI, impedance, and signal integrity models.

Primary evidence:

- `src/hardware_splicer/pcb/module_registry.py`
- `data/engine_pcb_data.json`
- `src/hardware_splicer/electrical_simulation.py`
- `src/hardware_splicer/pcb/safety_rules.py`

## Topology Knowledge

Topology exists today mostly as wires and heuristic composition.

Present:

- explicit net/pin connectivity through BuildGraph wires;
- explicit component/nets through `CircuitNetlist`;
- BuildGraph-to-netlist lowering and netlist-to-BuildGraph import;
- catalog recipe graphs;
- scratch auto-wiring for common module sets;
- power rail and ground connection heuristics;
- bounded handling for I2C, PWM, MOSFETs, relays, L298N, A4988, servos,
  ultrasonic sensors, OLEDs, ESP32-CAM, and similar known modules;
- explicit bounded topology operators for buck regulators, LDO regulators,
  pull-ups, voltage dividers, low-side switches, motor drivers, level shifters,
  sensor interfaces, relay drivers, H-bridges, analog conditioning, ADC
  interfaces, boost regulators, and battery chargers;
- safety checks for power-source conflicts, missing power, GND-to-non-GND,
  rough voltage mismatch, logic-level mismatch, I2C pull-up reminders, and
  weak MOSFET drive warnings.

Partial or missing:

- no general solver for arbitrary `series`, `parallel`, `RC filter`,
  `high-side switch`, protection, biasing, or analog-stage operators;
- no optimizer that chooses among broad alternate topologies from constraints;
- only bounded support-component insertion for selected cases;
- no formal power/signal direction propagation beyond local pin roles;
- no analog stage composition;
- no optimization loop over alternate topologies.

Primary evidence:

- `src/hardware_splicer/auto_wire.py`
- `src/hardware_splicer/plan_to_graph.py`
- `src/hardware_splicer/netlist/lower.py`
- `src/hardware_splicer/netlist/erc.py`
- `src/hardware_splicer/pcb/safety_rules.py`
- `src/hardware_splicer/circuit_synthesis/`

## What The System Currently Synthesizes

Current synthesis is bounded assembly, not general schematic invention.

It can synthesize/generate:

- bounded topology candidates for power rails, logic-level translation,
  analog sensor-to-ADC conditioning, sensor/display interfaces, relay-switched
  loads, single-cell battery/charger paths, H-bridge motor drive paths, and
  MCU-controlled DC motor/pump/fan/solenoid drivers;
- module selections from a natural-language goal in bounded cases;
- BuildGraph module graphs from catalog recipes, module IDs, inventory, canvas
  nodes, or splice plans;
- netlist IR from module graphs and optional LLM netlist composition;
- strict candidate graph-to-netlist compile for ready bounded synthesis
  candidates;
- carrier PCB artifacts from BuildGraph or CircuitNetlist input;
- BOM, firmware scaffold, KiCad PCB, design-quality reports, and optional fab
  bundles;
- splice build packages from donor/intake evidence;
- bench gate sessions and bench capture templates;
- casefiles for compile/check failures.

It does not yet synthesize:

- complete arbitrary schematics with unrestricted discrete support networks;
- analog filters/amplifiers/power stages from equations;
- general greenfield schematic hierarchy;
- proven topology alternatives selected by simulation;
- arbitrary board reconstruction from photos;
- final production-certified designs.

Primary evidence:

- `src/hardware_splicer/sdk.py`
- `src/hardware_splicer/compose_dispatch.py`
- `src/hardware_splicer/scratch_pipeline.py`
- `src/hardware_splicer/build_compiler.py`
- `src/hardware_splicer/circuit_synthesis/candidate_bridge.py`
- `src/hardware_splicer/integrations/qwen_netlist_compose.py`
- `src/hardware_splicer/project_intake.py`
- `examples/splice/manifest.json`

## What The System Currently Verifies

Current verification is stronger than current synthesis.

Present:

- schema/structure checks for graph and netlist paths;
- ERC on netlist IR;
- graph safety checks for obvious wiring hazards;
- KiCad DRC through compile paths;
- design-quality gate;
- BOM/Gerber/fab package inspection;
- fabrication readiness scoring and blockers;
- bench gate opening/status/submission;
- bench capture conversion into splice measurements;
- simulated golden bench closure;
- casefiles for blocked or failed paths.

Partial:

- power-domain simulation exists as analytical load budgeting plus optional
  ngspice DC operating-point cross-check. This is useful, but it is not full
  behavioral simulation.
- robotics/mechatronics simulation exists elsewhere in the repo, but it does
  not make the circuit layer a general electrical behavior solver.
- committed golden real bench replay now passes, but this is still replayed
  evidence rather than broad external field validation.

Missing:

- SPICE-grade behavioral coverage for the arbitrary output design;
- measured field validation across real donor boards;
- production certification;
- analog/power/signal integrity verification;
- formal proof of arbitrary topology correctness.

Primary evidence:

- `src/hardware_splicer/netlist/erc.py`
- `src/hardware_splicer/electrical_simulation.py`
- `src/hardware_splicer/design_quality.py`
- `src/hardware_splicer/fabrication_inspection.py`
- `src/hardware_splicer/splice_bench.py`
- `src/hardware_splicer/bench_capture_bridge.py`
- `src/hardware_splicer/standard_bench_gates.py`
- `src/hardware_splicer/golden_loop.py`
- `src/hardware_splicer/golden_real_bench.py`
- `scripts/verify_splice_demos.py`
- `scripts/verify_splice_golden_loop.py`
- `scripts/verify_splice_real_bench.py`

## Design Generation vs Readiness Checking

The current line is clear:

- Design generation today means producing bounded topology candidates, choosing
  or composing known modules, converting them into a graph/netlist, and
  compiling a carrier/build package.
- Readiness checking means checking that package with ERC, safety rules, KiCad
  DRC, fabrication inspection, casefiles, and bench gates.

The readiness/checking side is still more mature. The design-generation side is
bounded and useful, and now includes explicit topology operators for selected
families, but it is not yet the original full vision of "hardware as
algebra/graph/constraints" with broad behavioral selection.

## What Should Not Be Claimed Yet

Do not claim:

- full arbitrary schematic synthesis;
- arbitrary board repair from photos alone;
- production certification or formal safety certification;
- engineer replacement;
- complete component-level electrical algebra;
- analog/power/signal-integrity optimization;
- verified support for any random PCB or unknown donor board;
- that model output can approve readiness;
- that vision evidence can close gates without bench capture;
- that bounded topology candidates are certified final schematics.

Appropriate claim:

Hardware-Splicer is a backend-first hardware Agent spine that can convert
bounded module/intake/donor evidence into auditable build packages and readiness
checks. It now has a first bounded intent/part/port/topology/constraint layer
for selected circuit families, with a credible path to expand toward broader
circuit synthesis.

## Layer Classification

| Layer | Status | Evidence | Notes |
|---|---|---|---|
| Layer 0 - Inventory / intake | present | `src/hardware_splicer/project_intake.py`, `src/hardware_splicer/repair_intake.py`, `src/hardware_splicer/salvage_bridge.py`, `examples/intakes/` | Intakes, repair-style notes, donor evidence, and part/module rows are supported. |
| Layer 1 - Module selection / module graph | present | `src/hardware_splicer/module_picker.py`, `src/hardware_splicer/module_resolver.py`, `src/hardware_splicer/auto_wire.py`, `src/hardware_splicer/plan_to_graph.py` | Works for known module families and catalog/scratch paths. Not a general topology solver. |
| Layer 2 - Netlist or graph compile | present | `src/hardware_splicer/netlist/ir.py`, `src/hardware_splicer/netlist/lower.py`, `src/hardware_splicer/netlist/erc.py`, `src/hardware_splicer/build_compiler.py`, `tests/test_netlist_engine.py` | Netlist IR and graph lowering are real. Electrical semantics are limited. |
| Layer 3 - PCB / carrier / output generation | present | `src/hardware_splicer/build_compiler.py`, `src/hardware_splicer/compile_stages.py`, `src/hardware_splicer/pcb/`, `make verify-engine`, `make verify-splice` | Carrier/build package generation is one of the strongest layers. |
| Layer 4 - DRC / fabrication readiness check | present | `src/hardware_splicer/design_quality.py`, `src/hardware_splicer/fabrication_inspection.py`, `make verify-tier-c` | DRC/fab/readiness checks are mature for bounded outputs. |
| Layer 5 - Bench / measurement gate | partial | `src/hardware_splicer/splice_bench.py`, `src/hardware_splicer/bench_capture_bridge.py`, `src/hardware_splicer/standard_bench_gates.py`, `make verify-splice-loop`, `make verify-splice-real-bench` | Gate model exists, simulated golden loop passes, and committed golden real bench replay now passes. External field validation remains future work. |
| Layer 6 - Electrical behavior simulation | partial | `src/hardware_splicer/electrical_simulation.py`, `src/hardware_splicer/spice_runner.py`, `tests/test_electrical_trust_loop.py` | Analytical power budget and optional ngspice `.op` exist. No full behavioral simulation or topology selection. |
| Layer 7 - Bounded topology synthesis | partial | `src/hardware_splicer/auto_wire.py`, `src/hardware_splicer/scratch_pipeline.py`, `src/hardware_splicer/integrations/qwen_netlist_compose.py`, `src/hardware_splicer/circuit_synthesis/` | Heuristic module composition, optional LLM netlist compose, bounded planners for power rails, level shifting, sensor/interface hookup, and motor/pump/fan/solenoid drivers, safe arbitrary dispatch, and ready-candidate compile bridge exist. This is still not a general topology solver. |
| Layer 8 - General from-scratch schematic synthesis | missing | N/A | No general schematic synthesis engine, no full component algebra, no arbitrary goal-to-schematic solver. |

## Bottom Line

The repo has more than "just readiness checking"; it has a real structured
module/netlist/build/check spine. But the central design intelligence is still
bounded: it composes and verifies known module-level hardware far better than it
invents arbitrary circuits.

The next honest upgrade is not a rewrite. The first bounded synthesis layer now
exists; the next step is to widen it carefully with more bounded planners,
better component electrical metadata, and optional simulation evidence while
keeping unsupported goals blocked.
