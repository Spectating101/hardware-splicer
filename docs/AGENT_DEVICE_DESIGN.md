# Designing a device with an agent

How an AI agent (or any script) drives the device pipeline end to end: write a
spec, get a plan, repair it, review it, export a case, generate and run the
application off-hardware, and compare bench output against the plan.

Everything here is **modeled**. Nothing in this pipeline flashes a board,
powers anything, or marks a design as working. `physical_correctness` is always
`UNPROVEN`; `firmware_authorized` and `power_on_authorized` are always `false`.
An agent that reports a design as "working" because these calls succeeded is
wrong — see [MACHINE_PROJECT_SPINE.md](MACHINE_PROJECT_SPINE.md).

## Two entry points, same operations

| Surface | How |
|---------|-----|
| HTTP | `/v1/devices/*`; the OpenAPI document describes each operation and carries the spec schema on every request body that takes a spec |
| MCP | task `device_design` on the backend MCP server; it returns the ordered operation list below |

## The loop

| Step | Operation | What the agent gets |
|------|-----------|---------------------|
| 1 | `GET /v1/devices/spec-schema` | A JSON Schema for the spec, built from the module library, plus a catalogue of controllers and parts with their pins, roles and cited figures |
| 2 | `GET /v1/devices/examples` | Complete example specs to start from (ESP32 and Raspberry Pi Pico) |
| 2b | `POST /v1/devices/draft` | Optional. From `{"controller", "parts"}` (library ids) a spec wired the plain way: power, ground and the controller's default I2C bus. Returns the spec, what it assumed and the planner's findings for it |
| 3 | `POST /v1/devices/plan` | The plan: placement, wires, findings, steps, bill of materials |
| 4 | Repair | Each `error` finding may carry `suggestions`. Apply one, re-plan, repeat until no errors |
| 5 | `POST /v1/devices/engineering` | Bus, supply, heat, antenna, fit and printing review. Every number is sourced or marked as an assumption |
| 6 | `POST /v1/devices/case` | Printable case: binary STL, OpenSCAD source, mesh report |
| 7 | `POST /v1/devices/application` | Application source with host tests |
| 8 | `POST /v1/devices/application/run` | Compiles the host harness and exercises synthetic readings, faults and recovery |
| 9 | `POST /v1/devices/observations` | Compares serial output a human captured on a bench with what the plan predicts |

Steps 5 to 8 are independent of each other once the plan has no errors.

## Drafting from a parts list

When a person says "an ESP32 with a BME280 and a display", the agent maps those words to library ids
(`GET /v1/devices/spec-schema` lists them) and calls `draft`. The helper does no language processing and
invents nothing: an unknown id, a non-controller board, or a part that is not a display or I2C breakout is
refused with a reason. Two parts at one I2C address are not prevented; the planner reports
`i2c_address_overlap`, and the agent should tell the person. A draft is a starting point, so it still goes
through the plan, the repair loop and the engineering review.

## Suggestions

A suggestion is a candidate, never an applied change. The planner does not edit
the spec; the agent does, and the next plan call re-checks everything.

| `action` | Fields | Meaning |
|----------|--------|---------|
| `add_connection` | `from`, `to_one_of`, optional `joins_existing_bus` | A required pin has no wire. Connect `from` to one of the listed controller pins. When `joins_existing_bus` is true another module already wired this I2C signal, so the list holds only that pin: any other pin would split the bus, and the planner would still accept the split design |
| `replace_connection` | `wire`, `from`, `to_one_of` | A wire lands on a pin that cannot carry the signal. Replace its controller end |
| `move_signal` | `signal`, `to_one_of` | Devices share a bus but sit on different controllers' pins. Move the signal to a pin of the controller already in use |

`to_one_of` is ordered; taking the first entry is a valid strategy and is what
the test suite's reference loop does. An empty list means the planner has no
safe candidate, and the agent should say so rather than guess.

Errors without a suggestion (for example an unknown part) have no mechanical
repair; the agent should read the `message` and ask the person.

## Reading results honestly

- Engineering statuses are `exceeds_limit`, `advisory`,
  `within_limit_under_assumptions` and `not_assessed`. There is no `pass`.
  Current totals are sums of published figures, not bounds; surface temperature is a range from an assumption, not a floor.
- Assumed numbers are labelled as assumptions in the response. Report them as such.
- A clean plan means the wiring is internally consistent against the library.
  It does not mean the circuit works.
- `not_assessed` means the library has no cited figure for that part. The
  agent should list what is missing, not fill in a typical value.

## What an agent should say when it finishes

A short account of: the spec used, the findings repaired and how, the
engineering items that exceed a limit or are advisory, the assumptions the
review relied on, the modeled-run result, and the fact that nothing was
validated on hardware. Flashing and powering are decisions for a person at a
bench.

## Adding a part the agent needs

If a part is missing, follow [DEVICE_ADDING_PARTS.md](DEVICE_ADDING_PARTS.md).
Every figure needs a locator and a source, and the library validator rejects
entries without them. An agent should not invent figures to get a plan through.

## Focused tests

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/test_device_agent_surface.py tests/test_device_draft.py -q -p no:cacheprovider
```
