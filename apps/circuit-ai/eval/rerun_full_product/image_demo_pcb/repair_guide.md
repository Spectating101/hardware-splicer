# Repair Encyclopedia Guide

Quick summary: Small DC motor / actuator gadget: start with Document before touching; top candidate is Driver stage or motor/load path fault.

## Device Family
- Family: Small DC motor / actuator gadget (`small_dc_motor_gadget`)
- Confidence: 0.95
- Evidence: board role: motor_or_actuator_driver, multiple switching devices detected, multiple connectors/harness points detected, symptom/device hint: fan, motor, spin, capabilities: actuator_driver

## Scan Evidence
- Board type: motor_or_actuator_driver
- Board confidence: 0.785
- Components detected: 10
- Components by type: {"connector": 5, "inductor": 1, "transistor": 4}
- Connector candidates: 5
- AOI readiness: prototype_ready

## Safety
- Risk level: low_to_medium
- disconnect power before inspection
- start every powered test with a current-limited supply when possible
- label connector polarity and voltage before reconnecting loads
- treat unexpected heating as a fault; power only briefly under current limit while measuring
- test inductive loads with flyback/protection in place

## Top Fault Candidates
- Driver stage or motor/load path fault (`driver_stage_or_load_fault`), likelihood 0.9
  - evidence: actuator-driver family selected
  - evidence: reported output/motor symptom
  - evidence: reported motorized gadget symptom
- Power input, protection, or regulator fault (`power_input_or_regulator_fault`), likelihood 0.68
  - evidence: reported power symptom
- Connector, solder joint, or harness intermittency (`connector_or_harness_fault`), likelihood 0.62
  - evidence: 5 connector candidate(s)
  - evidence: intermittent/connection symptom

## Diagnostic Flow
1. Document before touching
   - Purpose: Preserve connector orientation, labels, screws, and cable routing.
   - Pass: device state and wiring are reproducible
   - If fail: capture more evidence before disassembly
2. Unpowered inspection
   - Purpose: Find obvious mechanical, thermal, liquid, or solder damage without adding risk.
   - Pass: no immediate stop-condition damage found
   - If fail: repair visible damage or quarantine unsafe battery/high-voltage assembly first
3. Power path check
   - Purpose: Confirm that input power reaches the board and regulated rails are not shorted.
   - Pass: rails are present, stable, and not current-limited
   - If fail: follow power_input_or_regulator_fault playbook
4. Output/load isolation
   - Purpose: Separate a bad board driver from a bad motor, relay, solenoid, cable, or load.
   - Pass: dummy load switches correctly and real load measures sane resistance
   - If fail: follow driver_stage_or_load_fault or connector_or_harness_fault playbook
5. Confirm candidate: Driver stage or motor/load path fault
   - Purpose: Confirm the suspected fault before replacing parts.
   - Pass: Finite winding/load resistance and no short to ground unless designed that way.
   - If fail: Near-zero resistance, open circuit, or unexpected ground short.
6. Confirm candidate: Power input, protection, or regulator fault
   - Purpose: Confirm the suspected fault before replacing parts.
   - Pass: Input and regulated rails match expected voltages within tolerance.
   - If fail: Shorted rail, zero regulator output, excessive current draw, or unstable rail.
7. Confirm candidate: Connector, solder joint, or harness intermittency
   - Purpose: Confirm the suspected fault before replacing parts.
   - Pass: Stable continuity with no visual cracking.
   - If fail: Continuity drops, joint ring cracks are visible, or cable movement changes behavior.

## Parts And Tools
- Tools: ESD-safe tweezers, clip leads, current-limited bench supply, dummy load, flux, magnification, multimeter, soldering iron, thermal camera or IR thermometer
- Likely parts: MOSFET/transistor with matching rating, flyback diode, heat shrink, input/output capacitors, replacement connector, voltage regulator, wire/crimp terminals

## Evidence To Collect Next
- input voltage measurement
- rail-to-ground resistance before power-up
- current draw at startup under current limit
