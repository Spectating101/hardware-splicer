# Ticket: BME280 address straps and a second I2C bus, as missions demanded them

Repository: this directory, a git worktree on the new branch `agent/device-i2c-straps-buses`, cut from
`agent/mission-runtime` (PR #122). Read `CLAUDE.md`, `docs/DEVICE_PLAN.md`, `docs/DEVICE_ENGINEERING_REVIEW.md`,
`docs/AGENT_MISSION.md`, and the invariants at the end of `docs/MACHINE_PROJECT_SPINE.md` first. Run Python as
`PYTHONPATH=src .venv/bin/python -m pytest ...`. You run without a sandbox; git and TestClient work. Commit as you go
(one concern per commit, imperative mood, capitalized, no trailing period, each message ending with a blank line
and `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`). Do not push. Do not touch other branches. Leave the
git author config alone.

## Why

The device library is frozen against coverage growth. Only correctness fixes and what a real mission needs are
allowed. In the mission trial, two models (Grok 4.7, Composer 2.5) given "Raspberry Pi Pico, 2x BME280" independently
tried two fixes an engineer would use, and HS refused both:
1. strap one BME280's SDO pin to ground so it answers at 0x76 and the other at 0x77: refused as
   `unsupported_breakout_pin`;
2. move one sensor to the Pico's second I2C controller (GP6/GP7): refused as `i2c_mixed_controllers`.

There is also a real bug, reproduced: the planner tracks one bus. In `_i2c_bus_findings` the `selected` dict keeps
only the last SDA and SCL net it sees. A second sensor on GP18/GP19 (I2C1) passes with no mixed-controller error,
while the same second bus on GP6/GP7 is refused. The verdict depends on net ordering. The engineering review's
`_i2c_bus` also assumes one bus.

## The contract you must preserve

Authority is never implicitly upgraded. The planner reports; it never approves. Every new fact carries a source in
the library data, as existing pins and addresses do. `physical_correctness` stays `UNPROVEN`. A finding that was an
error stays an error unless this ticket says the planner can now check it.

## Part A: address-select pins (data plus planner)

- Library schema: a pin may carry the role `i2c_address_select` and an `address_select` map from what it is tied
  to, to the resulting address: `{"ground": "0x76", "open": "0x77"}` for the Adafruit BME280 (`adafruit-bme280-stemma-qt`)
  SDO pin. Add `i2c.default_address` (`0x77`). Cite the Adafruit pinout page (already a source of that module) and
  Bosch's datasheet "111011x" statement (already in `address_basis`). Keep `addresses` as the list of possible ones.
  Only add what the sources say. If the sources do not state that tying SDO to 3.3 V gives 0x77, do not add
  `power_3v3` to the map: "open" is enough.
- Planner: a wire from an `i2c_address_select` pin to a ground pin (on the controller or on the module itself) is
  allowed and sets that module's address. A wire to anything else (GPIO, 5 V, another signal) is an error
  `address_select_wiring`, naming the allowed targets. Unwired means "open".
- Each I2C module gets an **effective address**: from its strap, else `default_address`, else unknown (the full
  `addresses` list, as today). `i2c_address_overlap` compares effective addresses where they are known, and the
  full lists where not, so modules without straps behave exactly as today. Two straps giving one address on one bus
  is still the overlap warning.
- The plan output lists each I2C module's effective address and how it was decided (strap / default / unknown).
- When an overlap involves a module with an address-select pin whose other setting would clear it, attach a
  suggestion to the finding: `{"action": "strap_address", "module": "sensor_2", "pin": "SDO", "to_one_of": [...]}`
  (ground pins, best first). Extend `device_suggestions.apply_first_suggestions` to apply it as an added
  connection. One strap at a time, then re-plan, like `move_signal`.

## Part B: more than one I2C bus (planner plus engineering review)

- Model buses explicitly. A bus is one SDA net plus one SCL net, joined by the modules on them. On a controller
  with `electrical.i2c_pin_mux == "fixed"` (Pico), both pins of a bus must belong to one I2C controller index
  (`i2c_mixed_controllers` stays an error within a bus), and two buses must not use the same controller index (a
  new error `i2c_controller_shared`). On a controller with mux `any` (ESP32), the number of buses must not exceed
  `electrical.i2c_controller_count`. Add it to the ESP32-DevKitC entry with its source (the ESP32 datasheet lists
  two I2C controllers; cite the page or section). If you cannot cite it, refuse more than one bus on that board
  with a clear finding instead of guessing.
- A module whose SDA and SCL land on different buses is an error.
- Address overlap is checked per bus. Two BME280s at 0x77 on two different buses do not overlap.
- Fix the ordering bug: the verdict must not depend on the order of nets or connections. Add a test that permutes
  connection order and asserts identical findings.
- `device_engineering._i2c_bus`: assess each bus separately (pull-ups, capacitance, rise time). Report one result
  per bus, keeping the existing check id and shape for the single-bus case so existing tests and consumers keep
  working. Choose a backward-compatible way and say what you chose.
- The drafter (`device_draft`) keeps putting everything on the controller's default bus. It does not choose
  addresses or buses. Its assumptions text already says so.

## Part C: firmware stays honest

`device_application` already refuses more than one sensor breakout. Keep that refusal, and make sure it also
refuses (with a clear message) a plan whose single sensor sits on a non-default bus if the generated code would
not drive that bus correctly. If supporting `Wire1` on the Pico for a single sensor is a small, testable change
(arduino-pico `Wire1.setSDA/setSCL`), you may add it with a compile test like the existing ones. Otherwise refuse.
No silent wrong firmware.

## Part D: missions

- The mission store grounds `BLOCKED_NEEDS_PART_DATA` in HS's own draft of the inventory (see
  `_part_data_grounding`). Now that the planner can suggest a strap, a draft whose only findings carry suggestions
  does not show missing part data. Record in the `inventory_read` draft `plan_unrepairable`: the number of error
  and warning findings with no suggestion. Ground part data on `left_out`, `not ok` or `plan_unrepairable > 0`.
  Keep reading old `inventory_read` events (without the new field) as before.
- `tests/test_mission_gate.py`: the `address_clash` scenario ("Raspberry Pi Pico", "2x BME280") was correct as
  BLOCKED_NEEDS_PART_DATA because HS could express no repair. With the strap suggestion, the deterministic runner
  should repair and reach READY_FOR_HUMAN_BUILD. Change that one expected state and its reason string to say why
  (the planner's strap suggestion). If the runner cannot get there, report why instead of forcing it. Do not change
  any other scenario.

## Tests (write first, confirm each fails before the fix)

- Strap SDO to mcu.GND: that sensor's effective address is 0x76; with another unstrapped BME280 on the same bus,
  no overlap warning. Both unstrapped: the overlap warning, now carrying a `strap_address` suggestion.
- SDO to a GPIO or to 3V3 (unless sourced): `address_select_wiring` error. CS stays `unsupported_breakout_pin`.
- Pico, sensor A on GP4/GP5 (I2C0) and sensor B on GP6/GP7 (I2C1): no errors, no overlap. Sensor B on GP2/GP3
  (also I2C1) is the same. B on GP8/GP9 (I2C0 again, a second bus on controller 0): `i2c_controller_shared`.
  B with SDA on GP6 and SCL on GP9: `i2c_mixed_controllers`.
- The GP18/GP19 case and its permutations give identical findings.
- ESP32 with two buses on any pins: fine up to the sourced count.
- The engineering review reports per-bus results; the single-bus shape is unchanged for existing tests.
- `apply_first_suggestions` applies a strap and the re-plan is clean.
- The mission gate: address_clash reaches READY through a repair, and its evidence trail shows the strap repair.
- A mission store test that a strap-repairable inventory no longer grounds BLOCKED_NEEDS_PART_DATA.

## Docs

`docs/DEVICE_PLAN.md` (address straps, buses), `docs/DEVICE_ENGINEERING_REVIEW.md` (per-bus), and
`docs/AGENT_MISSION.md` (part-data grounding wording). Same plain style.

## Verification

1. `PYTHONPATH=src .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_device_plan.py tests/test_device_engineering*.py tests/test_device_draft*.py tests/test_device_application*.py tests/test_device_suggestions*.py tests/test_mission_*.py tests/test_device_agent_surface.py`
   (adjust names to what exists).
2. The full suite once at the end: `PYTHONPATH=src .venv/bin/python -m pytest -q -p no:cacheprovider tests`
   (about 15 minutes; run nothing else heavy alongside). Three tests fail locally before your change and pass in
   CI (KiCad environment): `test_assembly_plan.py::test_outlines_agree_with_kicads_own_geometry_for_turned_and_flipped_parts`
   and the two `test_project_intake.py` production-package tests. Report them, don't touch them.

## Final report

Write `.cache/i2c-report.md` and print a summary: commits (SHA and subject), each test and the rule it pins with
fail-before confirmation, exact pytest result lines, the backward-compatibility choice for the engineering review,
what you added to library data with its sources, and anything you think is still wrong.
