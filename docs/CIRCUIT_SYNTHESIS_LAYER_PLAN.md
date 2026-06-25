# Circuit Synthesis Layer Plan

Date: 2026-06-20

Implementation update: 2026-06-22

Implementation update: 2026-06-23

Goal: add the smallest useful layer that moves Hardware-Splicer from bounded
module/readiness checking toward the original "hardware as components + ports +
topology + constraints + evidence" model.

This is not a plan for full arbitrary schematic synthesis. It is a bounded
extension that should fit the current spine and preserve the existing
guardrails.

## Design Target

Add a circuit-planning layer between natural-language/module input and the
existing BuildGraph/CircuitNetlist/build/check paths.

```text
CircuitIntent
  -> candidate FunctionalPart set
  -> explicit TopologyOperator plan
  -> Constraint and evidence gates
  -> SynthesisCandidate
  -> existing compose/build/check/bench pipeline
```

The first implementation should produce candidates and blockers. It should not
claim certified correctness.

## Current Implementation Status

The first bounded layer now exists:

- `src/hardware_splicer/circuit_synthesis/ir.py`
  - `CircuitIntent`
  - `FunctionalPart`
  - `Port`
  - `TopologyOperator`
  - `Constraint`
  - `SynthesisCandidate`
- `src/hardware_splicer/circuit_synthesis/motor_driver_planner.py`
  - deterministic DC motor / pump driver planner;
  - chooses bounded `motor_driver` or `low_side_switch` topology when possible;
  - blocks missing load current, undersized supply, missing inductive-load
    protection, and incompatible logic levels;
  - emits PSU ramp, thermal, and inductive-protection bench gates.
- `src/hardware_splicer/circuit_synthesis/power_rail_planner.py`
  - deterministic regulator planner for bounded step-down rails;
  - selects known buck/LDO modules from the catalog;
  - blocks missing input/output voltage, missing load-current estimate,
    regulator input/output mismatch, current-margin failure, and unsafe LDO
    thermal dissipation;
  - emits no-load voltage, loaded voltage/current, and thermal bench gates.
- `src/hardware_splicer/circuit_synthesis/level_shift_planner.py`
  - deterministic logic-level translation planner;
  - handles explicit 3.3V/5V mismatches and known controller/peripheral logic
    voltages;
  - blocks missing level shifter or insufficient shifted channels;
  - emits rail-reference and channel-mapping bench gates.
- `src/hardware_splicer/circuit_synthesis/sensor_interface_planner.py`
  - deterministic MCU sensor/display interface planner;
  - handles I2C, OneWire, digital, and analog module interfaces from the
    existing module catalog;
  - blocks missing pull-up evidence, 5V-to-3.3V logic hazards, and analog ADC
    over-voltage hazards;
  - emits sensor supply, bus idle, and first-readout bench gates.
- `src/hardware_splicer/circuit_synthesis/h_bridge_planner.py`
  - deterministic reversible DC motor H-bridge planner;
  - selects known H-bridge modules such as L298N, DRV8833, TB6612FNG, L9110S,
    or BTS7960 when available and rated;
  - blocks missing motor current/voltage, missing controller logic voltage,
    undersized drivers, and incompatible logic levels;
  - emits direction/brake, current-limit ramp, and thermal gates.
- `src/hardware_splicer/circuit_synthesis/relay_switch_planner.py`
  - deterministic relay-controlled load planner;
  - treats low-voltage relay loads as reviewable candidates;
  - blocks mains/high-voltage switching instead of pretending to certify it;
  - requires suppression evidence for inductive loads.
- `src/hardware_splicer/circuit_synthesis/analog_conditioning_planner.py`
  - deterministic analog sensor-to-ADC conditioning planner;
  - generates voltage-divider and optional RC-filter topology operators;
  - blocks missing source/ADC voltage range evidence;
  - emits ADC range and calibration gates.
- `src/hardware_splicer/circuit_synthesis/battery_power_planner.py`
  - deterministic single-cell battery/charger planner;
  - handles TP4056-style charge paths, boost output rails, 3.3V regulators,
    and optional fuel gauge modules;
  - blocks Li-ion/LiPo use without protected-cell/protection-board evidence;
  - emits battery protection, charge-current, and loaded-rail gates.
- `src/hardware_splicer/circuit_synthesis/planner.py`
  - safe arbitrary synthesis dispatcher;
  - routes supported battery-power, power-rail, level-shift,
    analog-conditioning, sensor/interface, relay-switch, H-bridge, and
    motor/pump/fan/solenoid intents to bounded planners;
  - returns a structured blocked candidate for unsupported arbitrary goals.
- `src/hardware_splicer/circuit_synthesis/candidate_bridge.py`
  - refuses blocked candidates;
  - compiles ready-for-review candidates through a strict selected-module graph
    and `CircuitNetlist` path, avoiding scratch composer module expansion;
  - applies topology-operator lowering before graph-to-netlist conversion;
  - preserves the candidate and claim boundary in the compile payload.
- `src/hardware_splicer/circuit_synthesis/operator_lowering.py`
  - adds the first operator-to-graph semantic bridge;
  - writes `terminal_semantics`, `support_components`, `topology_nets`, and
    `topology_lowering` metadata onto the graph;
  - marks H-bridge motor terminals as `floating_motor_terminal` so motor load
    pins are not mistaken for common ground;
  - records relay contact terminals as isolated switched-load terminals;
  - lowers voltage dividers, RC filters, pull-up networks, protection/clamp
    items, battery charger paths, and regulator paths into reviewable virtual
    support-component IR;
  - physically lowers safe two-terminal resistor/capacitor support items for
    analog divider/filter and I2C pull-up patterns into synthetic graph nodes,
    netlist components, schematic footprint properties, and BOM lines.
- `src/hardware_splicer/circuit_synthesis/topology_library.py`
  - defines the trusted low-voltage mechatronics synthesis ceiling as registered
    topology primitives;
  - classifies primitives by implementation status: module graph, terminal
    semantics, physical support, review evidence, or planned only;
  - evaluates every synthesis candidate into a `topology_authority` report with
    authority tier, score, review-limited operators, physical support counts,
    and next gap.
- `src/hardware_splicer/netlist/lower.py`
  - preserves synthetic support refs, values, footprints, terminal semantics,
    `support_components`, `topology_nets`, `physical_support_lowering`, and
    `topology_lowering` through graph/netlist round-trips.
- `src/hardware_splicer/bom_generator.py`
  - emits synthetic physical support passives using their real refs, values,
    footprints, support-component IDs, and operator IDs.
- `src/hardware_splicer/pcb/safety_rules.py`
  - reads effective terminal roles before applying GND, power-source, digital,
    unpowered-module, and no-ground checks;
  - recognizes explicit pull-up support components so inserted I2C pull-up
    resistors close the old generic pull-up warning.
- SDK entry points:
  - `hardware_splicer.sdk.circuit_synthesis_capability`
  - `hardware_splicer.sdk.plan_motor_driver_circuit`
  - `hardware_splicer.sdk.plan_power_rail_circuit`
  - `hardware_splicer.sdk.plan_level_shift_circuit`
  - `hardware_splicer.sdk.plan_sensor_interface_circuit`
  - `hardware_splicer.sdk.plan_h_bridge_circuit`
  - `hardware_splicer.sdk.plan_relay_switch_circuit`
  - `hardware_splicer.sdk.plan_analog_conditioning_circuit`
  - `hardware_splicer.sdk.plan_battery_power_circuit`
- SDK entry points: `hardware_splicer.sdk.plan_circuit_synthesis`,
  `hardware_splicer.sdk.synthesize_circuit`
- HTTP endpoint: `POST /v1/circuit-synthesis/motor-driver`
- HTTP endpoint: `GET /v1/circuit-synthesis/capability`
- HTTP endpoints:
  - `POST /v1/circuit-synthesis/power-rail`
  - `POST /v1/circuit-synthesis/level-shift`
  - `POST /v1/circuit-synthesis/sensor-interface`
  - `POST /v1/circuit-synthesis/h-bridge`
  - `POST /v1/circuit-synthesis/relay-switch`
  - `POST /v1/circuit-synthesis/analog-conditioning`
  - `POST /v1/circuit-synthesis/battery-power`
- HTTP endpoints: `POST /v1/circuit-synthesis/plan`,
  `POST /v1/circuit-synthesis/compile`
- Tests:
  - `tests/test_circuit_synthesis_ir.py`
  - `tests/test_motor_driver_planner.py`
  - `tests/test_circuit_synthesis_bridge.py`
  - `tests/test_circuit_synthesis_planners.py`
  - `tests/test_topology_operator_lowering.py`
  - `tests/test_topology_library.py`

This is still bounded topology planning, not general schematic synthesis.
However, H-bridge load modules now compile with actual motor modules included
because operator lowering gives the graph a terminal model beyond pin names.
Analog and battery-power candidates also now expose explicit virtual support
items such as divider resistors, RC filter components, bus pull-ups, protection
items, and protected-cell evidence instead of leaving those requirements only in
operator notes. Analog divider/filter parts and I2C pull-ups now go one step
further and physically appear in the compiled graph/netlist/BOM as synthetic
passives when their endpoints are unambiguous. Each compiled synthesis result
now also carries a topology-authority report that says whether it is inside the
trusted low-voltage mechatronics ceiling.

## Non-Goals

- Do not build a general schematic solver yet.
- Do not require Qwen, DeepSeek, or any paid model in default verification.
- Do not let model output approve readiness.
- Do not replace KiCad DRC, fabrication inspection, or bench capture.
- Do not rewrite `compose_dispatch`, `build_compiler`, or the splice pipeline.
- Do not make SPICE/ngspice a required dependency for normal tests.

## Proposed Objects

### CircuitIntent

Purpose: describe the user's requested hardware function in a structured form.

Fields:

- `goal`
- `supply_rails`
- `load_requirements`
- `signal_requirements`
- `current_constraints`
- `voltage_constraints`
- `frequency_constraints`
- `allowed_parts`
- `allowed_modules`
- `required_evidence`
- `notes`

Example:

```json
{
  "goal": "drive a small DC pump from an ESP32 GPIO",
  "supply_rails": [{"name": "+5V", "voltage_v": 5.0, "max_current_a": 1.0}],
  "load_requirements": [{"name": "pump", "type": "dc_motor", "current_a": 0.55}],
  "signal_requirements": [{"name": "control", "type": "pwm", "voltage_v": 3.3}],
  "allowed_modules": ["esp32-devkit", "mini-pump", "mosfet-irlz44n", "usb-power-5v"],
  "required_evidence": ["load_current_estimate", "supply_current_limit", "flyback_or_driver_protection"]
}
```

### FunctionalPart

Purpose: describe a module/component in terms of electrical function, not only
catalog identity.

Fields:

- `id`
- `type`
- `module_id`
- `ports`
- `voltage_range`
- `current_range`
- `function_tags`
- `behavior_class`
- `required_support_components`
- `thermal_notes`
- `current_notes`
- `verification_requirements`

### Port

Purpose: make pin semantics first-class.

Fields:

- `name`
- `direction`: `input`, `output`, `bidirectional`, `power`, `ground`
- `signal_type`: `analog`, `digital`, `power`, `pwm`, `i2c`, `spi`, `uart`, etc.
- `voltage_range`
- `current_limit`
- `required`
- `notes`

### TopologyOperator

Purpose: represent reusable electrical relationships that are currently mostly
implicit in `auto_wire.py`.

Initial operator set:

- `buck_regulator`
- `boost_regulator`
- `ldo_regulator`
- `series`
- `parallel`
- `voltage_divider`
- `pull_up`
- `pull_down`
- `low_side_switch`
- `high_side_switch`
- `rc_filter`
- `decoupling`
- `protection_diode`
- `h_bridge`
- `relay_driver`
- `sensor_interface`
- `analog_conditioning`
- `adc_interface`
- `motor_driver`
- `battery_charger`
- `level_shifter`

Each operator should declare:

- required part types;
- required ports;
- input constraints;
- output nets;
- missing-evidence conditions;
- required bench gates.

### Constraint

Purpose: make readiness blockers explicit before build.

Types:

- `voltage`
- `current`
- `frequency`
- `thermal`
- `trace_current`
- `isolation`
- `measurement_required`
- `fabrication_requirement`
- `evidence_required`

### SynthesisCandidate

Purpose: represent one possible plan without pretending it is final.

Fields:

- `selected_parts`
- `selected_modules`
- `generated_topology`
- `assumptions`
- `missing_evidence`
- `constraints`
- `verification_gates`
- `recommended_build_path`
- `result`: `candidate`, `blocked`, `ready_for_review`

## Minimal Demo Case

First bounded case:

```text
Goal: drive a small DC motor or pump from a microcontroller control signal.
```

Inputs:

- supply voltage;
- estimated load current;
- control signal voltage;
- available modules/components;
- optional donor evidence;
- optional bench evidence.

Expected output:

- selected candidate driver topology or module;
- required constraints;
- required protection/support assumptions;
- build/check plan;
- bench gate requirements;
- blocked result if current rating, supply budget, protection, or measurement
  evidence is missing.

This case is valuable because it touches real hardware relationships:

- microcontroller signal cannot directly drive the motor load;
- motor supply current must be budgeted;
- low-side switching or motor-driver topology is required;
- inductive load protection must be present or explicitly delegated to a module;

## Additional Bounded Cases Now Implemented

These cases are still bounded topology planning, not general synthesis.

### Power rail

```text
Goal: generate a regulated rail from a known source.
```

Checks:

- input/source voltage;
- target output voltage;
- load-current estimate;
- regulator input range;
- regulator current margin;
- LDO thermal dissipation.

Output:

- `buck_regulator` or `ldo_regulator` topology operator;
- DMM no-load voltage, loaded voltage/current, and thermal gates;
- strict compile bridge into the selected-module graph when enough known
  modules are present and auto-wire can connect them.

### Level shifting

```text
Goal: safely translate a 3.3V controller signal to/from a 5V peripheral.
```

Checks:

- both logic voltages are declared or inferable;
- known level-shifter module is available;
- required shifted channel count fits the bounded shifter.

Output:

- `level_shifter` topology operator;
- rail-reference and channel-mapping gates.

### Sensor interface

```text
Goal: connect a known MCU to a known sensor/display/interface module.
```

Checks:

- controller and peripheral modules;
- sensor supply range;
- I2C/OneWire pull-up evidence;
- 5V peripheral logic into 3.3V controller hazards;
- analog output scaling for ADC safety.

Output:

- `sensor_interface` topology operator;
- optional `pull_up`, `level_shifter`, or `voltage_divider` support operators;
- supply voltage, bus idle, and first-readout gates.
- bench current-limit ramp should gate first power-on.

### H-bridge motor drive

```text
Goal: drive a reversible brushed DC motor from MCU direction/PWM signals.
```

Checks:

- known controller module;
- motor voltage and run/stall current;
- H-bridge module current rating and voltage range;
- controller logic compatibility or level-shift availability;
- thermal review for higher-current drivers.

Output:

- `h_bridge` topology operator;
- direction/brake no-load test, PSU current-limit ramp, and driver thermal
  gates;
- strict compile bridge for controller/driver/power modules. The motor load is
  retained as topology and bench evidence until floating motor terminals are
  represented distinctly from common-ground pins.

### Relay switch

```text
Goal: switch a low-voltage external load from a controller signal.
```

Checks:

- controller and relay module availability;
- load voltage/current declaration;
- low-voltage boundary;
- hard block for mains/high-voltage load switching;
- flyback/TVS/snubber evidence for inductive relay loads.

Output:

- `relay_driver` topology operator;
- optional `protection_diode`/suppression topology operator;
- relay coil current, contact continuity, low-voltage first-power, and
  inductive-suppression gates.

### Analog conditioning

```text
Goal: condition an analog sensor/source into a controller ADC.
```

Checks:

- controller with ADC-capable pin;
- analog source/sensor module;
- maximum source voltage;
- ADC maximum input voltage;
- optional sample-rate/noise-filter requirement.

Output:

- `adc_interface` for direct-safe inputs;
- `voltage_divider` when source voltage exceeds ADC maximum;
- optional `rc_filter` for noisy/smoothed inputs;
- ADC range measurement and firmware calibration gates.

### Battery power

```text
Goal: create a single-cell Li-ion/LiPo charger and output rail path.
```

Checks:

- 5V charge input and charger module;
- protected-cell/protection-board evidence;
- target output voltage and expected load current;
- boost/regulator availability and current margin;
- optional cell capacity for runtime/charge-rate review.

Output:

- `battery_charger` topology operator;
- `boost_regulator`, `ldo_regulator`, or raw battery rail review path;
- optional fuel-gauge `sensor_interface`;
- battery protection, charge-current, and loaded-rail gates.

## Candidate Decision Rules For First Planner

The first planner can be deterministic.

Inputs:

- `control_signal_voltage_v`
- `load_voltage_v`
- `load_current_a`
- `available_modules`
- `available_parts`
- `evidence`

Rules:

1. If a rated motor-driver module is available and its current rating covers the
   load with margin, prefer `motor_driver`.
2. Else if a logic-level MOSFET path is available, propose `low_side_switch`.
3. If the load is inductive and no driver/protection module is selected, require
   `protection_diode` evidence or block.
4. If `load_current_a` is missing, block with `measurement_required`.
5. If supply max current is missing or below load current, block.
6. If control voltage cannot drive the selected switch/driver, require
   `level_shifter` or block.
7. Always require a current-limited bench ramp gate before power-on.

Output statuses:

- `blocked`: missing current, supply, protection, or incompatible control.
- `candidate`: topology is plausible but requires human review/bench evidence.
- `ready_for_review`: all static constraints are satisfied and required bench
  gates are created, but not production-certified.

## Integration Path

### Phase 1 - Audit only

Status: this document and `docs/CIRCUIT_LOGIC_AUDIT.md`.

No behavior changes.

### Phase 2 - Schema only

Add:

```text
src/hardware_splicer/circuit_synthesis/
  __init__.py
  ir.py
```

Add tests:

```text
tests/test_circuit_synthesis_ir.py
```

Acceptance:

- objects serialize to/from dicts;
- one motor/pump `CircuitIntent` fixture validates;
- no existing flow changes;
- no live model calls;
- existing verify targets still pass or fail exactly as before.

Status: implemented for the first bounded IR.

### Phase 3 - Bounded planner

Add:

```text
src/hardware_splicer/circuit_synthesis/motor_driver_planner.py
```

Add tests:

```text
tests/test_motor_driver_planner.py
```

Acceptance:

- chooses `motor_driver` when rated driver module is available;
- chooses `low_side_switch` when MOSFET path is available and constraints pass;
- blocks missing load current;
- blocks insufficient supply current;
- blocks missing inductive-load protection;
- emits bench gates for PSU current-limit ramp and thermal baseline;
- returns `SynthesisCandidate`, not a final PASS.

Status: implemented for MCU-controlled DC motor / pump cases.

### Phase 4 - Hook Into Existing Flow

Bridge `SynthesisCandidate` to the current spine:

```text
SynthesisCandidate
  -> module_ids / graph hints / constraints
  -> strict selected-module graph
  -> CircuitNetlist compile
  -> build package
  -> design_quality / fabrication / bench gates
```

Likely integration files:

- `src/hardware_splicer/circuit_synthesis/candidate_bridge.py`
- `src/hardware_splicer/auto_wire.py`
- `src/hardware_splicer/netlist/lower.py`
- `src/hardware_splicer/build_compiler.py`
- `src/hardware_splicer/splice_bench.py`
- `src/hardware_splicer/standard_bench_gates.py`
- `src/hardware_splicer/sdk.py`

Acceptance:

- new SDK entry point can produce a candidate plan and compile only when enough
  evidence exists;
- blocked candidates write casefile-style failure output;
- no model output directly approves readiness.

Status: implemented for ready-for-review bounded candidates through
`compile_synthesis_candidate` and `synthesize_circuit`. Blocked candidates
return a structured no-compile payload.

Phase 4.5 - Operator lowering and terminal semantics

Status: implemented as graph/netlist metadata IR, with bounded physical
discrete-footprint lowering for safe resistor/capacitor support patterns.

Current coverage:

- registered topology primitive library for the current low-voltage
  mechatronics ceiling;
- candidate authority report with tier/score, supported/planned/review-limited
  primitive classification, support-part counts, and next authority gap;
- H-bridge floating motor terminals;
- relay isolated contact terminals as semantic metadata;
- virtual support components for voltage dividers, RC filters, pull-up
  networks, protection/clamp items, battery charger safety evidence, and
  regulator power-path segments;
- physical synthetic passives for analog divider/filter paths and I2C pull-up
  networks;
- topology nets for scaled analog signals, filtered ADC paths, bus idle levels,
  protected transient paths, and battery/regulator power paths;
- metadata, support ref, value, and footprint preservation through graph/netlist
  round-trip;
- safety checker honors terminal overrides.

Still missing:

- physical lowering for ambiguous protection devices such as ADC clamp networks,
  flyback/TVS/snubber choices, and battery protection hardware;
- explicit relay contact/load-side graph generation;
- deeper battery cell/protection board terminal modeling beyond review evidence
  items;
- generalized topology search/composition across multiple independent
  subsystems beyond the registered primitive ceiling.

### Phase 5 - Optional Simulation Later

After the IR and bounded planner are stable:

- add optional SPICE export for simple operator patterns;
- keep simulation optional;
- use analytical checks first;
- never require ngspice for default tests unless the project later makes it a
  documented dependency.

## Guardrails

Preserve these principles:

- No fake PASS.
- No model-output-only approval.
- Vision evidence can suggest candidates only.
- Bench capture closes gates.
- KiCad/DRC/fabrication checks remain external evidence, not model confidence.
- Existing SDK/MCP/HTTP entry points must keep working.
- Default verification must not require paid-model calls.
- Competition/runtime model use should stay compatible with OpenAI,
  Anthropic, or Google if needed.

## Lowest-Risk Next Implementation Step

Original lowest-risk step was Phase 2:

1. Add schema/dataclasses for `CircuitIntent`, `FunctionalPart`, `Port`,
   `TopologyOperator`, `Constraint`, and `SynthesisCandidate`.
2. Add one fixture for the motor/pump driver case.
3. Add serialization tests.
4. Do not connect it to build output yet.

This gives the repo a real place to put the circuit-algebra idea without
destabilizing the existing compile/check spine.

Current next implementation step:

1. Add physical lowering for the next safe patterns: relay low-voltage contact
   loads, flyback/TVS/snubber choices when the load type and polarity are
   known, and ADC clamp networks only when rail ownership is explicit.
2. Add richer terminal semantics beyond H-bridge and relay: protected battery
   cell terminals, analog ADC input limits, switched contacts, and common ground
   should not all be inferred from pin names alone.
3. Add a small evaluated topology-library table for each bounded family:
   expected inputs, required support parts, static constraints, bench gates,
   and compile limitations.
4. Add optional simulation/export only after the operator lowering and terminal
   model are stable.
5. Keep unsupported arbitrary goals blocked until they have a bounded planner or
   a reviewed topology-library entry.

## Why This Is The Right Next Layer

The current system already has enough compiler/check infrastructure. The
missing layer is not another KiCad exporter or another model integration. The
missing layer is a stable internal language for the electrical relationship the
agent is trying to reason about.

Once that language exists, model calls can be used safely as optional parsers or
candidate generators, while deterministic rules, KiCad, fabrication inspection,
and bench gates remain the authority.
