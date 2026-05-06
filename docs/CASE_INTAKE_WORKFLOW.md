# Case Intake Workflow

Circuit-AI should feel like one guided assistant, not a drawer of separate tools.
The primary user entrypoint is:

```text
show the item -> create a case file -> choose the next action
```

The frontend route for this is:

```text
/start
```

## What The Intake Does

The intake accepts:

- a device, PCB, label, corrosion, connector, or listing photo
- a plain-language description
- symptoms or observed repair actions
- sourcing/listing context

It then creates a case file with:

- the best workflow route
- confidence
- evidence captured
- evidence still needed
- safety gates
- repair, salvage, build, source/sell, and advanced actions

## Routing Model

The case file can route to:

- repair: symptoms, faults, corrosion, heat, intermittent behavior, or no-power cases
- salvage: useful visual component evidence from a board/device photo
- build: typed parts, recovered modules, or project intent
- source/sell: listing, price, lot, margin, resale, or sourcing context
- safety: mains, high voltage, lithium, CRT, microwave, inverter, or other hazard signals
- evidence: not enough reliable evidence to act

The route is intentionally a recommendation, not a hard lock. A repair case can
still expose build and source actions when useful.

## Product Direction

Specialist routes remain available:

- `/scan`
- `/repair`
- `/parts`
- `/build`
- `/workspace`

But they should be reached from the case file whenever possible. A new user
should not need to decide whether their problem is a scan, repair, salvage,
parts-bin, or build problem before the system has seen the evidence.

## Current Limits

The intake is strongest for low-voltage electronics:

- retro handhelds and controllers
- USB gadgets
- simple motor/actuator devices
- sensor and display modules
- simple smart gadgets
- visible PCB corrosion, connectors, power, driver, and load faults

It should remain conservative for:

- mains appliances
- phones/tablets requiring model-specific teardown
- BGA or microsoldering workflows
- mostly mechanical restoration
- high-voltage, lithium, CRT, EV, and microwave repairs
