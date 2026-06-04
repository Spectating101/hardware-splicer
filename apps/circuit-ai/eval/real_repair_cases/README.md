# Real Repair Case Functional Evaluation

- Cases: 7
- Solvable now: 4
- Assistive only: 3
- Not ready: 0
- Average workflow score: 0.725

## Cases

### Xbox One wireless controller has malfunctioning thumbstick

- Source: https://www.ifixit.com/Troubleshooting/Xbox_One_Controller/Xbox%2BOne%2BWireless%2BController%2BHas%2BMalfunctioning%2BThumbstick/444889
- Verdict: `solvable_now` score `0.768`
- Lane: `game_controller_input` / top fault `analog_stick_or_button_contact_fault`
- Coverage: `usable_with_gaps`
- Safety: `low_to_medium`
- Session tasks: `5`, captures `1`, measurements `2`
- Blockers: none
- First task: [measurement] before/after controller tester readings for stick center, axis range, triggers, and buttons
- First task: [measurement] measure input connector polarity and voltage
- First task: [evidence] connector closeups with wire colors and labels

### Laptop will not turn on

- Source: https://www.ifixit.com/Troubleshooting/PC_Laptop/Laptop%2BWill%2BNot%2BTurn%2BOn/505262
- Verdict: `assistive_only` score `0.718`
- Lane: `laptop_power_path` / top fault `power_input_or_regulator_fault`
- Coverage: `usable_with_gaps`
- Safety: `low_to_medium`
- Session tasks: `6`, captures `1`, measurements `3`
- Blockers: boardview/schematic and model-specific teardown needed for deeper board repair
- First task: [measurement] input fuse or main-rail resistance with power disconnected
- First task: [measurement] input voltage measurement
- First task: [measurement] rail-to-ground resistance before power-up

### Coffee maker not hot enough

- Source: https://www.ifixit.com/Troubleshooting/Coffee_Maker/Not%2BHot%2BEnough/483047
- Verdict: `assistive_only` score `0.703`
- Lane: `mains_heater_appliance` / top fault `heater_thermal_cutoff_or_control_fault`
- Coverage: `partial`
- Safety: `high`
- Session tasks: `6`, captures `1`, measurements `3`
- Blockers: model-specific knowledge required before customer-facing claim, trained safety workflow required for high-voltage or mains portions
- First task: [measurement] confirm appliance is unplugged and capacitors are discharged before continuity checks
- First task: [measurement] thermal fuse and thermostat continuity readings
- First task: [measurement] heating element resistance compared with expected wattage

### Electric toothbrush not charging

- Source: https://www.ifixit.com/Troubleshooting/Electric_Toothbrush/Not%2BCharging/564390
- Verdict: `solvable_now` score `0.723`
- Lane: `battery_charging_gadget` / top fault `battery_charge_path_fault`
- Coverage: `usable_with_gaps`
- Safety: `low_to_medium`
- Session tasks: `6`, captures `1`, measurements `3`
- Blockers: none
- First task: [measurement] charger rating and no-load output voltage
- First task: [measurement] battery pack voltage compared with nominal rating
- First task: [measurement] charge current or dock current draw during safe charging test

### DeWalt DC970 battery will not charge

- Source: https://www.ifixit.com/Wiki/DeWalt_DC970_Troubleshooting
- Verdict: `solvable_now` score `0.747`
- Lane: `battery_charging_gadget` / top fault `battery_charge_path_fault`
- Coverage: `usable_with_gaps`
- Safety: `low_to_medium`
- Session tasks: `6`, captures `1`, measurements `3`
- Blockers: none
- First task: [measurement] charger rating and no-load output voltage
- First task: [measurement] battery pack voltage compared with nominal rating
- First task: [measurement] charge current or dock current draw during safe charging test

### TV has sound but no picture

- Source: https://www.ifixit.com/Troubleshooting/Television/TV%2BHas%2BSound%2BBut%2BNo%2BPicture/493422
- Verdict: `assistive_only` score `0.689`
- Lane: `tv_backlight_power` / top fault `display_backlight_or_power_supply_fault`
- Coverage: `partial`
- Safety: `high`
- Session tasks: `8`, captures `3`, measurements `3`
- Blockers: model-specific knowledge required before customer-facing claim, trained safety workflow required for high-voltage or mains portions
- First task: [measurement] standby/main rail readings only if trained for high-voltage TV work
- First task: [capture] flashlight-test result showing whether a faint image is present
- First task: [capture] power-board and backlight connector photos with model labels

### USB fan warms but motor will not spin

- Source: local sample assets/samples/test_pcb.png
- Verdict: `solvable_now` score `0.727`
- Lane: `small_dc_motor_gadget` / top fault `driver_stage_or_load_fault`
- Coverage: `usable_with_gaps`
- Safety: `low_to_medium`
- Session tasks: `5`, captures `1`, measurements `3`
- Blockers: none
- First task: [measurement] motor/load resistance and isolation reading
- First task: [measurement] connector continuity while gently flexing the harness
- First task: [measurement] driver output voltage with current limit and dummy load

## Next Builds
- battery chemistry, pack safety, and replacement compatibility workflow
- collect board photos, measurements, and outcome data for this lane
- controller calibration and stick-module compatibility database
- TV model rail/backlight LED-strip reference library
- laptop boardview/schematic connector for power-path diagnosis
- mains heater appliance safety pack with thermal fuse/element rating tables
