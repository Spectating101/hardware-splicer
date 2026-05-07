# Salvage Splice Coverage Evaluation

- Cases: 29
- Strong: 29
- Partial: 0
- Weak: 0
- Safety holds caught: 8/8
- Reuse-ready or ready-after-measurements: 21/21
- Average score: 1.0

## Cases

### usb_fan

- Category: `low_voltage_air_mover`
- Verdict: `ready_after_measurements`
- Coverage: `strong` score `1.0`
- Target: `usb_fume_extractor` / USB fume extractor or bench cooling fan
- Blocks: `5`, measurements: `7`, adapters: `2`
- Top measurements: unpowered resistance between power and ground, continuity from connector ground to exposed ground, input voltage and polarity, current draw under current-limited supply

### pc_fan

- Category: `low_voltage_air_mover`
- Verdict: `ready_after_measurements`
- Coverage: `strong` score `1.0`
- Target: `usb_fume_extractor` / USB fume extractor or bench cooling fan
- Blocks: `4`, measurements: `7`, adapters: `2`
- Top measurements: unpowered resistance between power and ground, continuity from connector ground to exposed ground, input voltage and polarity, current draw under current-limited supply

### toy_rc_car

- Category: `motors_mechanics`
- Verdict: `ready_after_measurements`
- Coverage: `strong` score `1.0`
- Target: `low_voltage_motor_test_jig` / Low-voltage motor/load test jig
- Blocks: `6`, measurements: `7`, adapters: `2`
- Top measurements: unpowered resistance between power and ground, continuity from connector ground to exposed ground, input voltage and polarity, current draw under current-limited supply

### inkjet_printer_motion

- Category: `motors_mechanics`
- Verdict: `ready_after_measurements`
- Coverage: `strong` score `1.0`
- Target: `plotter_motion_stage` / Printer/scanner motion stage
- Blocks: `6`, measurements: `7`, adapters: `3`
- Top measurements: unpowered resistance between power and ground, continuity from connector ground to exposed ground, input voltage and polarity, current draw under current-limited supply

### flatbed_scanner

- Category: `motors_sensors_lighting`
- Verdict: `ready_after_measurements`
- Coverage: `strong` score `1.0`
- Target: `inspection_motion_fixture` / Inspection light and motion fixture
- Blocks: `6`, measurements: `7`, adapters: `4`
- Top measurements: unpowered resistance between power and ground, continuity from connector ground to exposed ground, input voltage and polarity, current draw under current-limited supply

### document_camera_slider

- Category: `inspection_fixture`
- Verdict: `ready_after_measurements`
- Coverage: `strong` score `1.0`
- Target: `inspection_motion_fixture` / Inspection light and motion fixture
- Blocks: `7`, measurements: `7`, adapters: `5`
- Top measurements: unpowered resistance between power and ground, continuity from connector ground to exposed ground, input voltage and polarity, current draw under current-limited supply

### dvd_drive_motion

- Category: `small_motion_stage`
- Verdict: `ready_after_measurements`
- Coverage: `strong` score `1.0`
- Target: `low_voltage_motor_test_jig` / Low-voltage motor/load test jig
- Blocks: `5`, measurements: `7`, adapters: `2`
- Top measurements: unpowered resistance between power and ground, continuity from connector ground to exposed ground, input voltage and polarity, current draw under current-limited supply

### laser_printer_mains

- Category: `mains_laser_printer`
- Verdict: `unsafe_hold`
- Coverage: `strong` score `1.0`
- Target: `safety_hold` / Safety hold before salvage
- Blocks: `6`, measurements: `5`, adapters: `2`
- Top measurements: unpowered resistance between power and ground, continuity from connector ground to exposed ground, motor/load resistance, startup current estimate

### wifi_router

- Category: `network_modules`
- Verdict: `ready_after_measurements`
- Coverage: `strong` score `1.0`
- Target: `network_status_indicator` / Network status light or WiFi indicator
- Blocks: `5`, measurements: `4`, adapters: `1`
- Top measurements: unpowered resistance between power and ground, continuity from connector ground to exposed ground, input voltage and polarity, current draw under current-limited supply

### bluetooth_speaker

- Category: `audio_modules`
- Verdict: `ready_after_measurements`
- Coverage: `strong` score `1.0`
- Target: `small_audio_amp_box` / Small powered speaker or alert box
- Blocks: `6`, measurements: `7`, adapters: `2`
- Top measurements: unpowered resistance between power and ground, continuity from connector ground to exposed ground, input voltage and polarity, current draw under current-limited supply

### car_radio_speaker

- Category: `audio_modules`
- Verdict: `ready_after_measurements`
- Coverage: `strong` score `1.0`
- Target: `small_audio_amp_box` / Small powered speaker or alert box
- Blocks: `5`, measurements: `4`, adapters: `2`
- Top measurements: unpowered resistance between power and ground, continuity from connector ground to exposed ground, input voltage and polarity, current draw under current-limited supply

### led_desk_lamp

- Category: `lighting`
- Verdict: `ready_after_measurements`
- Coverage: `strong` score `1.0`
- Target: `indicator_or_task_light` / Indicator light or small task lamp
- Blocks: `4`, measurements: `4`, adapters: `1`
- Top measurements: unpowered resistance between power and ground, continuity from connector ground to exposed ground, input voltage and polarity, current draw under current-limited supply

### led_strip_controller

- Category: `lighting_control`
- Verdict: `ready_after_measurements`
- Coverage: `strong` score `1.0`
- Target: `smart_relay_box` / Smart relay or low-voltage load controller
- Blocks: `6`, measurements: `10`, adapters: `2`
- Top measurements: unpowered resistance between power and ground, continuity from connector ground to exposed ground, input voltage and polarity, current draw under current-limited supply

### power_bank_normal

- Category: `battery_power`
- Verdict: `ready_after_measurements`
- Coverage: `strong` score `1.0`
- Target: `bench_power_adapter` / Bench power adapter or breakout
- Blocks: `4`, measurements: `4`, adapters: `1`
- Top measurements: unpowered resistance between power and ground, continuity from connector ground to exposed ground, input voltage and polarity, current draw under current-limited supply

### electric_toothbrush

- Category: `battery_motor_gadget`
- Verdict: `ready_after_measurements`
- Coverage: `strong` score `1.0`
- Target: `low_voltage_motor_test_jig` / Low-voltage motor/load test jig
- Blocks: `5`, measurements: `7`, adapters: `2`
- Top measurements: unpowered resistance between power and ground, continuity from connector ground to exposed ground, input voltage and polarity, current draw under current-limited supply

### game_controller

- Category: `input_devices`
- Verdict: `ready_after_measurements`
- Coverage: `strong` score `1.0`
- Target: `salvaged_input_panel` / Input panel, macro pad, mouse, or controller tester
- Blocks: `5`, measurements: `7`, adapters: `2`
- Top measurements: unpowered resistance between power and ground, continuity from connector ground to exposed ground, input voltage and polarity, current draw under current-limited supply

### keyboard

- Category: `input_devices`
- Verdict: `ready_after_measurements`
- Coverage: `strong` score `1.0`
- Target: `salvaged_input_panel` / Input panel, macro pad, mouse, or controller tester
- Blocks: `5`, measurements: `7`, adapters: `1`
- Top measurements: unpowered resistance between power and ground, continuity from connector ground to exposed ground, input voltage and polarity, current draw under current-limited supply

### mouse

- Category: `input_devices`
- Verdict: `ready_after_measurements`
- Coverage: `strong` score `1.0`
- Target: `salvaged_input_panel` / Input panel, macro pad, mouse, or controller tester
- Blocks: `5`, measurements: `4`, adapters: `2`
- Top measurements: unpowered resistance between power and ground, continuity from connector ground to exposed ground, input voltage and polarity, current draw under current-limited supply

### security_camera

- Category: `camera_sensor`
- Verdict: `ready_after_measurements`
- Coverage: `strong` score `1.0`
- Target: `network_status_indicator` / Network status light or WiFi indicator
- Blocks: `5`, measurements: `4`, adapters: `4`
- Top measurements: unpowered resistance between power and ground, continuity from connector ground to exposed ground, input voltage and polarity, current draw under current-limited supply

### hard_drive

- Category: `motors_mechanics`
- Verdict: `ready_after_measurements`
- Coverage: `strong` score `1.0`
- Target: `bench_power_adapter` / Bench power adapter or breakout
- Blocks: `5`, measurements: `7`, adapters: `2`
- Top measurements: unpowered resistance between power and ground, continuity from connector ground to exposed ground, input voltage and polarity, current draw under current-limited supply

### laptop_parts

- Category: `mixed_modules`
- Verdict: `ready_after_measurements`
- Coverage: `strong` score `1.0`
- Target: `camera_ir_light_or_sensor_mount` / Camera/IR light or sensor mount
- Blocks: `6`, measurements: `7`, adapters: `5`
- Top measurements: unpowered resistance between power and ground, continuity from connector ground to exposed ground, input voltage and polarity, current draw under current-limited supply

### phone_parts

- Category: `mixed_modules`
- Verdict: `ready_after_measurements`
- Coverage: `strong` score `1.0`
- Target: `small_audio_amp_box` / Small powered speaker or alert box
- Blocks: `6`, measurements: `7`, adapters: `5`
- Top measurements: unpowered resistance between power and ground, continuity from connector ground to exposed ground, input voltage and polarity, current draw under current-limited supply

### power_bank_swollen

- Category: `battery_hazard`
- Verdict: `unsafe_hold`
- Coverage: `strong` score `1.0`
- Target: `safety_hold` / Safety hold before salvage
- Blocks: `3`, measurements: `4`, adapters: `1`
- Top measurements: unpowered resistance between power and ground, continuity from connector ground to exposed ground, input voltage and polarity, current draw under current-limited supply

### coffee_maker_mains

- Category: `mains_appliance`
- Verdict: `unsafe_hold`
- Coverage: `strong` score `1.0`
- Target: `safety_hold` / Safety hold before salvage
- Blocks: `5`, measurements: `5`, adapters: `1`
- Top measurements: unpowered resistance between power and ground, continuity from connector ground to exposed ground, motor/load resistance, startup current estimate

### microwave_hv

- Category: `high_voltage_appliance`
- Verdict: `unsafe_hold`
- Coverage: `strong` score `1.0`
- Target: `safety_hold` / Safety hold before salvage
- Blocks: `5`, measurements: `5`, adapters: `1`
- Top measurements: unpowered resistance between power and ground, continuity from connector ground to exposed ground, motor/load resistance, startup current estimate

### smart_bulb_mains

- Category: `mains_lighting`
- Verdict: `unsafe_hold`
- Coverage: `strong` score `1.0`
- Target: `safety_hold` / Safety hold before salvage
- Blocks: `4`, measurements: `8`, adapters: `1`
- Top measurements: unpowered resistance between power and ground, continuity from connector ground to exposed ground, MOSFET/transistor short check, flyback/protection diode continuity

### pc_power_supply

- Category: `mains_power`
- Verdict: `unsafe_hold`
- Coverage: `strong` score `1.0`
- Target: `safety_hold` / Safety hold before salvage
- Blocks: `6`, measurements: `7`, adapters: `2`
- Top measurements: unpowered resistance between power and ground, continuity from connector ground to exposed ground, input voltage and polarity, current draw under current-limited supply

### ebike_battery

- Category: `high_energy_battery`
- Verdict: `unsafe_hold`
- Coverage: `strong` score `1.0`
- Target: `safety_hold` / Safety hold before salvage
- Blocks: `4`, measurements: `4`, adapters: `1`
- Top measurements: unpowered resistance between power and ground, continuity from connector ground to exposed ground, input voltage and polarity, current draw under current-limited supply

### crt_tv

- Category: `high_voltage_display`
- Verdict: `unsafe_hold`
- Coverage: `strong` score `1.0`
- Target: `safety_hold` / Safety hold before salvage
- Blocks: `5`, measurements: `2`, adapters: `1`
- Top measurements: unpowered resistance between power and ground, continuity from connector ground to exposed ground

## Interpretation

- Strong means the planner identified useful blocks, routed to a plausible build or safety hold, and produced measurement/adapter gates.
- Partial means it found reusable material but the target or proof path still needs sharper domain knowledge.
- Weak means the item needs more evidence, new capability vocabulary, or a dedicated safety/reuse pack.
