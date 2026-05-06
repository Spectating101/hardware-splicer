# Repair Market Coverage

This matrix answers a practical product question: do common repair/restoration video items overlap with what Circuit-AI can support well enough for customers?

Latest generated data:
- `eval/rerun_full_product/repair_market_coverage.json`

Summary from the latest run:
- Weighted coverage: 0.518
- Strong fit classes: 4
- Partial fit classes: 3
- Weak fit classes: 3

## Strong Fit Now

These are worth building into customer-facing workflows first.

### Retro Handheld Consoles

Examples:
- Game Boy
- Game Boy Color
- Game Gear
- PS Vita

Why it fits:
- Common restoration videos include cleaning, corrosion, battery terminals, contacts, buttons, screens, speakers, and simple boards.
- Circuit-AI can help with visual evidence, PCB scan, corrosion/defect candidates, connector labels, cleaning checklist, and validation.

Needed next:
- model-specific parts catalog
- revision/reference photo library
- button/contact resistance workflow

### Small USB Powered Gadgets

Examples:
- USB fan
- LED gadget
- desk toy
- small pump
- powered hub

Why it fits:
- Low-voltage, board-level, connector, regulator, driver, and load faults fit the current repair encyclopedia.
- Current-limited testing and dummy-load isolation can be made very reproducible.

Needed next:
- motor/fan/pump/load test library
- enclosure/mechanical replacement notes

### Sensor/Display Modules

Examples:
- weather monitor
- meter
- thermostat module
- panel display

Why it fits:
- Board understanding, OCR, connector mapping, recipe matching, and firmware smoke-test planning are already useful.

Needed next:
- calibration procedure database
- display ribbon/backlight guides

### Game Controllers

Examples:
- DualSense
- Xbox controller
- Joy-Con
- retro controller

Why it fits:
- High customer demand.
- Cleaning, contacts, USB, battery, button, flex, connector, and resale workflows are relevant.

Needed next:
- stick-drift decision tree
- calibration software workflow
- part compatibility catalog

## Partial Fit

These are valuable, but not safe to market as fully covered yet.

### Modern Game Consoles

Examples:
- Nintendo Switch
- PlayStation 5
- Xbox Series
- Steam Deck

What works:
- cleaning/thermal service
- visual board triage
- connector/corrosion evidence
- fan/power path hints
- resale/salvage economics

Gaps:
- HDMI/USB-C microsoldering workflows
- boardview/schematic integration
- BGA/APU/storage faults
- console revision-specific part pairing and firmware constraints

### Audio And Retro Electronics

Examples:
- cassette player
- radio
- speaker amp
- VCR accessory

What works:
- cleaning and visual PCB triage
- power/connector faults

Gaps:
- analog audio signal-path diagnosis
- belts/gears/head alignment
- oscilloscope/audio injection workflows

### Phones And Tablets

Examples:
- iPhone
- Samsung phone
- iPad
- Android tablet

What works:
- symptom intake
- older repair-guide scaffolding
- safety warnings

Gaps:
- model-specific teardown
- adhesive/battery workflows
- paired parts and calibration
- microsoldering and boardview workflows

## Weak Fit For Now

Do not sell these as covered yet.

### Mains Appliances

Examples:
- microwave
- coffee maker
- vacuum
- washing machine
- power supply

Why weak:
- high-voltage and mains safety
- mechanical/plumbing/heater/compressor diagnostics
- certification/liability boundaries

### Mostly Mechanical Restoration

Examples:
- rusty tools
- lighters
- locks
- bicycles
- non-electronic mechanisms

Why weak:
- useful for documentation/checklists only
- little overlap with PCB intelligence unless the item has electronics, motors, or control boards

## Product Recommendation

The best first customer-facing repair vertical is:

1. retro handheld consoles and controllers
2. small USB powered gadgets and small actuator devices
3. sensor/display modules and simple smart gadgets
4. modern console triage, but only as cleaning/thermal/basic diagnostic guidance at first

Avoid claiming broad coverage for:
- phones
- laptops
- mains appliances
- mostly mechanical restoration

Those can become later verticals after adding model-specific parts, teardown, safety, schematic/boardview, and measurement workflows.
