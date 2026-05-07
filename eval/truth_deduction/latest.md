# Truth Deduction Benchmark

Cases: 7
Average score: 1.0
Aligned cases: 7
Outcome-grounded sessions: 2
Reference workflow checks: 5

## usb_fan_harness_solder_fault

Verdict: `aligned_with_truth` (1.0, 6/6 assertions)
Truth strength: `outcome_grounded_session`

Assistant/oracle deduction:
- Device family: small_dc_motor_gadget
- Most likely fault: connector, solder joint, or motor harness intermittency
- Correct action: reflow or repair the harness/connector solder joint, then add strain relief and verify continuity under flex.

Circuit-AI dossier:
- Status: needs_evidence
- Top fault: Connector, solder joint, or harness intermittency
- Summary: USB fan warms but motor will not spin value trial has 1 grounded claim(s) and 3 weak claim(s). 2 evidence task(s) remain open.

Assertion results:
- PASS: System keeps the case in the small DC motor gadget lane.
- PASS: System identifies the confirmed fault class as connector/harness/solder intermittency.
- PASS: System preserves the measured USB input evidence.
- PASS: System preserves the confirmed fix/outcome.
- PASS: System still admits what remains unverified.
- PASS: System asks for concrete next evidence.

## electric_toothbrush_charging_dock

Verdict: `aligned_with_truth` (1.0, 6/6 assertions)
Truth strength: `outcome_grounded_session`

Assistant/oracle deduction:
- Device family: battery_charging_gadget
- Most likely fault: charging dock/contact/input path or battery charge path
- Correct action: verify dock/contact cleanliness, measure battery voltage and charge current, then decide whether the dock path or battery pack is responsible.

Circuit-AI dossier:
- Status: needs_evidence
- Top fault: Charging input or dock path
- Summary: Electric toothbrush not charging end-to-end smoke has 1 grounded claim(s) and 3 weak claim(s). 3 evidence task(s) remain open.

Assertion results:
- PASS: System routes the case to battery charging gadgets.
- PASS: System preserves the dock voltage evidence.
- PASS: System summarizes the fault as a charging dock/input path rather than random PCB failure.
- PASS: System preserves that the case has a repaired outcome.
- PASS: System still asks for charge-current evidence.
- PASS: System asks for charge-contact closeups.

## xbox_thumbstick_drift_reference

Verdict: `aligned_with_truth` (1.0, 5/5 assertions)
Truth strength: `reference_workflow_alignment`

Assistant/oracle deduction:
- Device family: game_controller_input
- Most likely fault: analog stick, trigger, or button contact fault
- Correct action: record before/after controller tester readings, inspect the joystick module and contacts, clean if possible, replace the stick module if drift remains.

Circuit-AI dossier:
- Status: solvable_now
- Top fault: Analog stick, trigger, or button contact fault
- Summary: repair/reference case workflow evaluation

Assertion results:
- PASS: System selects the controller input lane.
- PASS: System identifies analog stick/contact fault.
- PASS: System asks for before/after controller tester readings.
- PASS: System requests closeups of the input assemblies.
- PASS: System considers this lane solvable now.

## laptop_no_power_reference

Verdict: `aligned_with_truth` (1.0, 5/5 assertions)
Truth strength: `reference_workflow_alignment`

Assistant/oracle deduction:
- Device family: laptop_power_path
- Most likely fault: power input, protection, charger, or main rail fault
- Correct action: start with known-good charger, charge port inspection, input fuse/main rail resistance, input voltage, and rail-to-ground resistance; do not claim model-specific board repair without schematic/boardview.

Circuit-AI dossier:
- Status: assistive_only
- Top fault: Power input, protection, or regulator fault
- Summary: repair/reference case workflow evaluation

Assertion results:
- PASS: System selects laptop power path.
- PASS: System identifies power input/regulator fault.
- PASS: System asks for input and rail resistance measurements.
- PASS: System marks the case assistive only.
- PASS: System calls out boardview/schematic as a blocker.

## coffee_not_hot_reference

Verdict: `aligned_with_truth` (1.0, 6/6 assertions)
Truth strength: `reference_workflow_alignment`

Assistant/oracle deduction:
- Device family: mains_heater_appliance
- Most likely fault: thermal fuse, thermostat, heating element, or control relay/triac fault
- Correct action: unplug, verify discharge/isolation, check thermal fuse/thermostat continuity, measure heating element resistance against wattage, and avoid live mains probing.

Circuit-AI dossier:
- Status: assistive_only
- Top fault: Heating element, thermal fuse, thermostat, or control relay fault
- Summary: repair/reference case workflow evaluation

Assertion results:
- PASS: System selects mains heater appliance.
- PASS: System identifies heater thermal cutoff/control fault.
- PASS: System marks safety risk as high.
- PASS: System requires unplug/discharge confirmation.
- PASS: System asks for thermal fuse and heating element checks.
- PASS: System does not call this broadly solved.

## dewalt_battery_not_charge_reference

Verdict: `aligned_with_truth` (1.0, 5/5 assertions)
Truth strength: `reference_workflow_alignment`

Assistant/oracle deduction:
- Device family: battery_charging_gadget
- Most likely fault: battery, charge contact, charger, or charge-controller fault
- Correct action: check contacts, verify charger, measure pack voltage, then inspect terminals/protection path.

Circuit-AI dossier:
- Status: solvable_now
- Top fault: Battery, charge contact, or charge-controller fault
- Summary: repair/reference case workflow evaluation

Assertion results:
- PASS: System selects battery charging gadget.
- PASS: System identifies battery charge path fault.
- PASS: System asks for charger rating/no-load voltage.
- PASS: System asks for battery pack voltage.
- PASS: System considers this lane solvable now.

## tv_sound_no_picture_reference

Verdict: `aligned_with_truth` (1.0, 6/6 assertions)
Truth strength: `reference_workflow_alignment`

Assistant/oracle deduction:
- Device family: tv_backlight_power
- Most likely fault: backlight LED strip, backlight driver, or power-board fault
- Correct action: do flashlight test, inspect/model the power board and backlight connectors, and only measure rails if trained for TV high-voltage work.

Circuit-AI dossier:
- Status: assistive_only
- Top fault: Backlight LED strip, inverter/driver, or power-supply fault
- Summary: repair/reference case workflow evaluation

Assertion results:
- PASS: System selects TV backlight/power lane.
- PASS: System identifies backlight/power supply fault.
- PASS: System marks safety risk as high.
- PASS: System asks for flashlight-test evidence.
- PASS: System asks for power-board/backlight connector photos.
- PASS: System marks the case assistive only.
