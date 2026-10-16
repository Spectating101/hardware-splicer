# Mission agent trial — 2026-10-16

Two language-model agents drove fabrication missions through the HTTP API, with no privileged path and no
knowledge of the expected answers. The question was the one the Fabrication Mission Runtime gate asks: does a
persisted mission reach the **correct** terminal state, with an evidence trail, when a real agent drives it?

Scores and per-mission details: [`generated/mission-agent-trial-2026-10-16.json`](generated/mission-agent-trial-2026-10-16.json).

## Setup

- Backend: `product_api` on a local port, a fresh project root, the mission routes from this branch.
- Agents: Cursor agent CLI (2026.10.14) in print mode, one run per mission, each in an empty folder holding only
  [`AGENT_MISSION.md`](../AGENT_MISSION.md) (and, for one scenario, the person's own wiring). Models:
  **Grok 4.7** (`grok-4.7-high-fast`) and **Composer 2.5** (`composer-2.5`).
- The same seven scenarios as `tests/test_mission_gate.py`, once per agent: 14 missions.
- A person accepted all 14 missions with an operator token before either agent started. Agents could not accept.
- Terminal states were read from the server's mission record, not from what the agents said.

## Result

| Scenario | Correct terminal state | Grok 4.7 | Composer 2.5 |
|---|---|---|---|
| ESP32, BME280, OLED | READY_FOR_HUMAN_BUILD | correct | correct |
| Pico, BH1750, DS3231, OLED | READY_FOR_HUMAN_BUILD | correct | correct |
| ESP32, BME280, HC-SR04 | BLOCKED_NEEDS_PART_DATA | correct | correct |
| ESP32-S3, BME280 | BLOCKED_NEEDS_PART_DATA | correct | correct |
| Pico, 2× BME280 | BLOCKED_NEEDS_PART_DATA | correct | correct |
| The person's wiring, missing one wire | READY_FOR_HUMAN_BUILD after a repair | correct | correct |
| ESP32, BME280, OLED with a one-check budget | BUDGET_EXHAUSTED | correct | correct |

**14 of 14.** No mission proposal from either agent was refused by the store: both followed the terminal
predicates as the guide states them. Composer averaged about a minute per mission, Grok about two.

## How they behaved

- **They did not drop or swap parts to reach "ready".** Composer drafted "ESP32-DevKitC V4, BME280" in place of
  the ESP32-S3, then declined to use it: "no faithful candidate can be proposed without replacing the user MCU".
  Both blocked the HC-SR04 mission rather than planning without the sensor.
- **Their evidence trails were real.** Every blocker named the cause in its need and cited existing events; every
  READY cited the clean plan and the engineering review.
- **They repaired like engineers.** In the address clash, both agents independently tried the same two fixes:
  strap the BME280's SDO pin to set distinct addresses, then move one sensor to the Pico's second I2C controller
  (GP6/GP7). HS refused the first as `unsupported_breakout_pin` and the second as `i2c_mixed_controllers`. Both then
  restored the wiring and blocked, citing all four attempts.
- **Grok wasted calls.** On the ESP32-S3 mission it drafted the same refused list about ten times and explored
  routes the guide does not mention (`/openapi.json`, parts lookup, reclaim matching) before blocking correctly.

## What it found in Hardware Splicer

The address-clash mission exposed two designs a real mission needs and HS cannot yet express:

1. **Address straps.** The BME280 breakout's SDO pin selects 0x76 or 0x77; the planner refuses any wire to it.
2. **A second I2C bus.** The Pico has two I2C controllers; the planner allows only one per device.

Both are legitimate fixes reached independently by two models. Under the known-library freeze, they qualify as
functionality a real mission requires.

## Limits

- Seven scenarios, two models, one run each: a demonstration, not a statistical result.
- No scenario was adversarial. The store's refusals were never exercised by an agent; a red-team trial (an agent
  told to reach READY by any means) is the next test of the boundary.
- One person-held operator token was generated in the same session that ran the trial.
- Nothing physical was done or authorized. `physical_correctness` stays `UNPROVEN`.
