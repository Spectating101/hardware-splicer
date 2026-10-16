# Step 4 completion: address straps and independent I2C buses

This continues `fb93c61c` from the frozen mission handover. No live agent trial,
human acceptance, physical operation, push or merge to `main` was performed.

## Integrated branch

`agent/mission-step4-integration` starts at PR #124 (`42a2b02c`), incorporates the
Step 4 work, and includes PR #122's final red-team evidence commit. The frozen
`agent/mission-runtime`, `agent/mission-delivery`, `agent/mission-feedback` and
`agent/device-i2c-straps-buses` refs were not edited.

The last red-team report was not an ancestor of #124; its handover link was
therefore missing in that checkout. The integration branch includes it through
an explicit merge of the frozen runtime branch, without rewriting that report.

| Commit in integration branch | Concern |
| --- | --- |
| `e1365a5f` | Original Step 4 WIP checkpoint, copied unchanged |
| `cd9735d5` | Explicit bus topology, effective addresses, strap suggestions and firmware/legacy compatibility checks |
| `7972e684` | Independent engineering estimates per bus |
| `226477dc` | Repairable findings versus missing mission part data |
| `cabb096f` | Selector jumpers cannot replace a module's ground return |
| `6c133afe` | End-to-end delivery regression and focused I2C CI coverage |
| `d15fd066` | Trace ground returns to the controller, retaining valid daisy chains |
| `19a45b08` | Keep the observation test's synthetic address/default/selector fixture consistent |

The three main implementation commits also exist on `agent/i2c-completion`
as `7f9609b7`, `58b115ff` and `2490d759`. Use the integration branch for the
complete result, including the later ground-return and delivery checks.

## What changed

- The planner pairs SDA/SCL nets through the peripherals on them. It no longer
  keeps just the last SDA and SCL net visited. A shared signal with different
  counterpart nets is refused; fixed pin muxes must select one controller per
  bus, and independent buses cannot reuse that controller. ESP32 bus count is
  capped by its sourced count.
- BME280 SDO-to-ground selects 0x76; unwired uses the sourced default 0x77.
  Unsupported rail/GPIO/signal straps are errors. CS remains unsupported.
  Unknown addresses retain the full declared alternatives. Overlap and stacked
  pull-ups are checked per bus.
- A conflict offers one explicit ground strap only when that setting clears the
  other modules on the same bus. The pure repair helper adds one wire, then the
  runner re-plans. The address-clash mission now reaches READY with that repair
  recorded, without dropping either sensor.
- The inventory reading records `plan_unrepairable`, counting error/warning
  findings without suggestions. A repairable strap is not missing part data.
  Historical readings without this field retain their former grounding rule.
- Engineering loading checks use each bus's own wires, devices and pull-ups.
  **Compatibility:** a single bus retains check ID `i2c_bus` and the exact old
  field shape. Multiple buses get `i2c_bus:<bus-id>` and a `bus` reference.
  Invalid topology is not assessed.
- The existing single-sensor Pico `Wire1` path remains supported. Multiple sensor
  application export is still refused. Delivery records that refusal explicitly
  while retaining the design and enclosure; it does not invent firmware success.
- Required grounds must have a ground-to-ground path to the controller. Two
  peripherals joined only to one another are not a return; an address-selector
  jumper to controller GND cannot substitute for their missing ground wiring.

## Sources checked

The WIP library additions were preserved and checked against the official pages:

- [Adafruit BME280 pinouts, I2C Address](https://learn.adafruit.com/adafruit-bme280-humidity-barometric-pressure-temperature-sensor-breakout/pinouts):
  default 0x77 and SDO-to-GND selection of 0x76. No 3V3 selector setting was added.
- [ESP32 Series Datasheet v5.3, section 4.8.4, printed page 37](https://www.espressif.com/sites/default/files/documentation/esp32_datasheet_en.pdf):
  two hardware I2C interfaces. Source membership and positive integer count are
  checked by the existing library validator.

These are catalog wiring facts, not observations of a physical unit.

## Fail-before checks

At `fb93c61c`, the prescribed core slice produced:

`20 failed, 376 passed, 4 warnings in 21.01s`

Those failures cover four ground-strap orientations/targets, the open/default
repair, four invalid straps, three independent Pico pin pairs, repeated I2C0,
split bus, ESP32 controller count, the old synthetic address fixture, per-bus
engineering, two address-clash mission checks and part-data grounding.
The synthetic library fixture now changes its default and selector map together,
instead of contradicting the newly validated possible-address list.

Additional regressions were demonstrated failing before their fixes:

- Independent BH1750 and DS3231 buses were falsely reported as stacked pull-ups.
- A self SDO-to-GND strap falsely satisfied a missing module ground return.
- Two sensors with their grounds joined only to one another could still appear
  clean, even though no ground return reached the controller. That regression
  now requires both missing-ground findings and a clean re-plan after adding
  the legitimate daisy-chain return.
- The new end-to-end strap/delivery test failed against frozen #124: it ended
  BLOCKED_NEEDS_PART_DATA instead of producing a repaired design.

Supplementary checks preserve connection-order independence, legacy grounding,
multi-sensor firmware refusal and the Pico `Wire1` generator on GP2/3, GP6/7 and
GP18/19. Existing coverage for some of those cases already passed at the WIP;
they are not all claimed as new fail-before cases.

## Package compatibility

Explicit bus/address metadata and the added ESP32 source change `DEVICE_PLAN.json`
and its hash-bound `FIRMWARE_PROPOSAL.json`. Archive member comparison against
`4e1ea762` confirmed no changes to the diagnostic source, configuration, README
or input spec. The new package goldens are intentional metadata changes, not a
claim of byte-identical old ZIPs:

| Example | Old package SHA-256 | New package SHA-256 |
| --- | --- | --- |
| ESP32/OLED | `bca8efef8c6720cb05ee3da3c6f4dcf4b511206847924860d95af1da2536265b` | `e630ecb67fd5d33236d9639b4ccfd42202c6743f180521b3adde2e1c3be4db3d` |
| ESP32/OLED/BME280 | `f9d5eefe75453894827ef7f4bc2cc8728fe05b57f4b92d90c088a8ef7a6419b1` | `eca4ea8a60ed6d05d3c29f40d4d87e6e0420175d79ff3a130752c273a3c38780` |

The old geometry/wiring/findings/steps plan hashes remain pinned after projecting
out only the explicit new metadata, ESP32 source entry and SDO role. Diagnostic
source/configuration hashes are independently pinned to their pre-Step-4 values.

## Executed compile and model check

A generated Pico/OLED/BME280 application on GP6/GP7 was run through the existing
verifier with cached pinned libraries and PlatformIO Core 6.1.18:

- Host behavior: passed.
- Actual Pico firmware compile: passed, exit code 0.
- Vendor-host adapter plus real Adafruit sources: 11/11 scenarios passed.
- The explicit-pin scenario reported `Wire1` on SDA 6/SCL 7 after boot and
  recovery, without traffic on the other controller.
- Firmware BIN SHA-256: `dc0b791de0853c92170ad301d083baf4d43edfb9ec7882f6f1f90bd7ca47cde4`.
- ELF SHA-256: `4ee69644247468fb6501c66fab5a72c6e77270d30c410f8f9c4e95423e71953b`.

Local raw verifier output is retained under the completion checkout's
`.cache/i2c-wire1/device-application-fpya0h7l/`. This is compilation and modeled
execution only, not silicon, core timing or electrical evidence. No upload ran.

## Regression results

- Core slice after primary fixes: `396 passed, 4 warnings in 19.77s`.
- Focused integration slice: `706 passed, 20 skipped, 21 warnings in 166.24s`.
  This run preceded collection of the last ground-return/delivery additions;
  those are covered in the subsequent targeted and full runs.
- Topology plus delivery/feedback slice, including those additions:
  `57 passed, 1 warning in 16.98s`.
- Ground-return, planner, observation, controller, CI and mission slice after the
  final fixes: `527 passed, 9 warnings in 39.58s`.
- Full repository suite at code commit `19a45b08`:
  `2 failed, 4146 passed, 56 skipped, 119 warnings in 799.96s (0:13:19)`.
  XML comparison confirms both failures exactly match the frozen #124 baseline:
  `test_project_intake_evidence_pack_closes_scoped_production_package` and
  `test_project_intake_extracts_notes_into_production_evidence`.
  No new failures remain in this run. The assembly-geometry test passes.

The first full run was deliberately interrupted to close the floating-ground
case. It also exposed a second old synthetic address fixture, now corrected
without relaxing validation. Its partial result was `1 failed, 1644 passed,
24 skipped, 36 warnings in 335.52s`; it is not counted as a completed full run.

The full command is `PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests
--junitxml=.cache/step4-full-suite-final.xml`, from the integration checkout, using the
repository's Python environment.

Baseline check on untouched #124: `2 failed, 1 passed, 1 warning in 19.06s` for
the three tests called out in the handover. The two production-intake failures
reproduce there; the assembly-geometry test currently passes. Do not report all
three as current baseline failures. XML: `.cache/baseline-kicad.xml`.

## Still owed

- Step 5 live cooperative and hostile trial reruns, with fresh missions explicitly
  accepted by the person. No operator token was retrieved or used here.
- The five missing hardened Grok missions remain unrun; no results are inferred.
- P4 and P5 remain designed, not implemented. Their ticket and reviewed design
  are available in this integration branch. Donor planner wiring and later
  architecture/procurement/physical automation remain frozen as the handover says.
- This tranche did not run browser specs or publish CI results for the new local
  commits. Physical correctness remains UNPROVEN, and authorization flags remain
  false. The existing FastAPI/store and authority model are preserved.
- Package byte reproducibility is scoped to a fixed code/library revision.
  This tranche does not pin a generator version into historical mission packages
  or claim unchanged package bytes across software upgrades.
