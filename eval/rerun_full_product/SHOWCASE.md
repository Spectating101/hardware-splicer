# Circuit-AI Real Showcase

This showcase uses real outputs from the latest rerun, not mocked demo data.

## Example 1: Image-To-Product From `assets/samples/demo_pcb.png`

Input: `assets/samples/demo_pcb.png`

Generated artifacts:
- `eval/rerun_full_product/image_demo_pcb/analysis.json`
- `eval/rerun_full_product/image_demo_pcb/workflow_report.json`
- `eval/rerun_full_product/image_demo_pcb/build_package.json`
- `eval/rerun_full_product/image_demo_pcb/README.md`

Result:
- Detected components: 10
- Component evidence: 5 connectors, 4 transistors/MOSFET-class parts, 1 inductor
- Inferred board role: motor/actuator driver
- Board-role confidence: 0.785
- OCR/marking evidence resolved: 3 components
- Machine connector candidates: 5
- AOI readiness: prototype_ready
- Best salvage/build opportunity: Robot Motor Controller
- Decision: validate_then_execute
- Build package type: salvage_project_build

Generated work order:
- reserve matched salvage assets
- run electrical validation on every reused module
- prototype interconnect between matched modules
- generate wiring/pinout checklist
- build first functional prototype
- estimate enclosure, labor, and resale price

Validation gates:
- visual inspection
- continuity power-to-ground
- current-limited first power-up
- connector pin map
- load current measurement
- flyback/protection check

What this demonstrates:
- The system is not just captioning a PCB.
- It converts visual detections into board role, machine role, reusable capabilities, opportunity score, BOM, validation plan, and commercialization positioning.
- It correctly keeps recipe suggestions separate when the known recipe does not match the observed opportunity.

## Example 2: E-Commerce/Salvage Arbitrage

Input listing:
- ESP32 BME280 OLED salvage lot
- Price: $9.00
- Shipping: $1.00
- Labor estimate: $1.00
- Failure rate: 10%
- Fee rate: 10%

Generated artifacts:
- `eval/rerun_full_product/listing_sensor_display/workflow_report.json`
- `eval/rerun_full_product/listing_sensor_display/build_package.json`

Result:
- Best opportunity: Acquire ESP32 BME280 OLED salvage lot for parts/builds
- Opportunity type: ecommerce_arbitrage
- Score: 0.827
- Estimated output value: $33.00
- Adjusted output value: $26.73
- Adjusted margin: $15.73
- Decision: execute_top_opportunity
- Generated recipe target: Energy Monitor
- Build package type: known_recipe_build
- Firmware target: ESP32
- Firmware features: WiFi, sensor read loop

Generated work order:
- verify listing photos and seller reliability
- calculate shipping/tax/labor/failure-rate adjusted margin
- buy only if adjusted margin remains positive
- test and split listing into build/resale inventory
- follow generated assembly steps

What this demonstrates:
- The engine can operate beyond PCB image scanning.
- It can combine sourcing cost, failure assumptions, parts inventory, recipe matching, and a build/commercialization plan.

## Important Limit

For weak image-only scans, the system falls back to evidence collection instead of pretending it can build. In the latest rerun, `assets/samples/test_pcb.png` produced:
- decision: inventory_and_collect_more_evidence
- package type: evidence_collection
- AOI readiness: research_preview

That is intentional behavior. It makes the system more trustworthy because it separates "enough evidence to act" from "needs more views, OCR closeups, or tests."

## Repair Encyclopedia Slice

Generated from the same image-based analysis:
- `eval/rerun_full_product/image_demo_pcb/repair_guide.json`
- `eval/rerun_full_product/image_demo_pcb/repair_guide.md`

Example symptoms:
- fan will not spin
- driver board gets hot
- works if the connector is wiggled

Result:
- Device family: small DC motor / actuator gadget
- Family confidence: 0.95
- Top fault candidate: driver stage or motor/load path fault
- Candidate likelihood: 0.90
- Secondary candidates: power input/regulator fault, connector/harness intermittency
- Safety profile: low_to_medium

Generated diagnostic flow:
- document connector orientation and wiring before touching
- unpowered visual inspection
- power path check with current limit
- output/load isolation using a dummy load
- confirm driver/load fault with resistance and isolation tests
- confirm power fault with input/regulator rail measurements
- confirm connector fault with wiggle and continuity testing

This is the first practical repair-encyclopedia lane: small low-voltage electronic gadgets and modules. It is intentionally narrower than "every machine" so the system can give concrete tests and stop conditions instead of generic advice.
