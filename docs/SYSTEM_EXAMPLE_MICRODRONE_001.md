# HS System Example 001 — Crazyflie 2.1+ environmental deck

**Status:** Executable offline **design-review** system example; not a new flight controller, KiCad design, firmware release, flight simulator run, manufactured hardware, or authorized flight.

## Why a microdrone?

A quadcopter is a useful cross-domain engineering benchmark because a seemingly small change affects electronics and battery current, airframe mass and center of gravity, control-loop behavior, flight software, manufacturing, and real-world safety. Hardware Splicer already has a Crazyflie reference in `examples/robotics_benchmarks/crazyflie_2_1.json` and an expansion-deck change request in `examples/robotics_guidance/crazyflie_custom_sensor_deck.json`. **Do not create a disconnected new drone ontology:** this system example reuses that guidance source with identity checks.

The actual selected baseline is the **Crazyflie 2.1+**, not the earlier Crazyflie 2.1 or the more powerful 2.1 Brushless; their electronics, motors, thrust and payload assumptions are not interchangeable.

## Manufacturer-sourced baseline

Official source: https://www.bitcraze.io/products/crazyflie-2-1-plus/

- Baseline takeoff weight: **29 g**; chassis extent described by Bitcraze as **92 × 92 × 29 mm**. This is not an independently calibrated rotor-center geometry.
- Four brushed motors, STM32F405 application MCU, nRF51822 radio/power MCU, BMI088 IMU and BMP388 barometer.
- Expansion VCC: **3.0 V, max 100 mA**; expansion includes I2C, SPI, UART and 1-Wire deck identification.
- Maximum **recommended** payload mass **15 g**; official stock flight time **7 min**, which **does not predict** flight time after modification.
- Firmware reference: https://github.com/bitcraze/crazyflie-firmware
- Independent simulation / research options cataloged by Bitcraze: https://www.bitcraze.io/development/external-projects/
- Bitcraze simulation overview: https://www.bitcraze.io/documentation/repository/

The existing HS Crazyflie custom-deck scenario adds **user-project** limits of 3 g added deck mass, 80 mA peak deck current, prop guards, watchdog/disarm preservation and supervised initial tests. Those limits are *scenario constraints*, **not** manufacturer values.

## The example modification

A hypothetical *environmental-sensing expansion deck* comprising BME688 sensor, DS28E05 deck identification, local bypass capacitors, and expansion connector. The initial design file records **2.4 g and 54 mA as illustrative, unmeasured engineering estimates**, not a selected BOM's verified characteristics.

Run with no drone, no external network or simulation:

```bash
python -m pip install -e '.[dev]'
python scripts/generate_microdrone_system_001.py --output .cache/hs-system-microdrone-001
pytest -q tests/test_system_example_microdrone.py
```

Outputs:

| Artifact | Evidence |
|---|---|
| `DESIGN_INPUT.json` | Complete reviewed baseline and unmeasured proposal |
| `GUIDANCE_REFERENCE.json` | Existing HS Crazyflie change-request source |
| `MICRODRONE_ASSESSMENT.json` | Whole-system constraints, static-load and power estimates, explicit blockers |
| `ARCHITECTURE_CONTRACT.json` | Components, functional interfaces and source pointers (not real PCB pinout) |
| `PHYSICAL_EVIDENCE_GATE.json` | Independent evidence obligations and all physical authority disabled |
| `PACKAGE_RECEIPT.json` | Hashes of every input and derived output, no overwrite |

## Executed engineering calculations, not invented physical evidence

- Total proposed takeoff mass = stock 29 g + proposed 2.4 g = **31.4 g**, assuming stock baseline remains otherwise unchanged.
- Within this particular project's 3 g added-deck limit: **0.6 g declared headroom**; within Bitcraze's 15 g recommended payload by a wider margin. Neither establishes rotor capability, dynamic control, mechanical fit or battery endurance.
- 54 mA *proposed peak* is 26 mA below the 80 mA user project cap and 46 mA below the official expansion 100 mA VCC cap. **No real rail current or sensor/die voltage has been measured.**
- At 3.0 V, proposed deck electrical power is 0.162 W. This is an illustrative input, not a verified maximum.
- Four equal motors require approximately 0.07698 N of force each for static gravity equilibrium at 31.4 g. **This is not a thrust test, available thrust margin, stability proof or flight dynamics simulation.**
- Flight-time change and usable lift margin are deliberately `null` because mass, rotor, battery and current/thrust curves are unverified.

Change any deck mass, current, VCC or safety constraint to make the intended budget fail, and the corresponding blockers must appear. Source hashes change on each altered scenario.

## Next artifact milestones

1. **Native electrical:** reuse real Crazyflie deck KiCad template, choose a specific compatible board/part revision, audit power rail and I2C/1-Wire pin assignments; produce real schematic/PCB/BOM and independently run ERC/DRC. Zero unmeasured pin assumptions.
2. **Firmware:** pin compatible Bitcraze firmware source commits, compile the deck driver and platform-specific host tests, preserve watchdog and emergency-disarm behavior. Never flash hardware simply because compilation succeeded.
3. **Mechanical:** independently measure a real deck, mounting and propeller-guard clearances, mass distribution and battery placement; generate source-linked PCB mechanical envelope, not guessed bolt holes.
4. **Physical modelling:** launch a pinned Crazyflie simulation backend and compare available telemetry/behaviour against scenario acceptance tests. Current report does not run one; do not claim dynamic accuracy from static hover force arithmetic.
5. **Physical evidence:** operator-gated power, current/voltage instrument readings, props-off checks, link-loss/failsafe, prop guards and controlled supervised tests under applicable local rules. No automated flight command or motor motion is in this branch.
6. **Generalize:** run a second non-aerial system (e.g. a low-speed differential-drive rover) through the *same* schema and evidence tiers so HS proves a reusable system workflow rather than one drone-specific demo.

## No false authority

Manufacturer documentation is source evidence. A repository URL is **not** a cloned or executed firmware tree; a model name is **not** a simulator run. Input flags marked `true` cannot promote a physical release; this example hardcodes all physical authorization to false pending independent, reviewed observations. This example deliberately exposes technical gaps to be closed by subsequent integrations.
