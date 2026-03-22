# Circuit-AI Value And Workflows

This is the canonical product-level map of what Circuit-AI currently provides, where it creates value, and which workflows the backend can already support.

It is intentionally different from route-by-route API docs. The purpose here is to answer:

- what users can bring into the system
- what the system can do with that evidence
- what outputs or decisions it can generate
- which use cases are already strong
- where the current boundaries still are

## Core Value

Circuit-AI provides value in five concrete ways:

1. It turns raw board artifacts into engineering structure.
   A board image, KiCad netlist, or PCB file can become connectors, rails, regulators, controller hints, interfaces, and bring-up guidance instead of just a file upload.

2. It turns electrical designs into manufacturing-ready packages.
   A board can move from validation to BOM, Gerber, PnP, DFM, and packaging workflows inside one backend.

3. It turns messy engineering intent into actionable readiness.
   Requirements, incomplete specs, and project context can be converted into questions, assumptions, risks, capability checks, and SOW-like planning outputs.

4. It turns several boards into one machine or system view.
   The backend can infer candidate interconnects, candidate power trees, board ordering, and a machine compile preview across several boards.

5. It turns visual evidence into learning, repair, reuse, or triage outputs.
   Images can drive analysis, component context, educational outputs, repair guidance, and reuse-oriented workflows.

## Inputs The System Can Work With

Current backend value is organized around a small set of input types:

- board image or PCB photo
- KiCad netlist
- KiCad PCB
- requirements/specification JSON
- project and revision metadata
- machine definition spanning several boards
- optional mechanism context for machine engineering

## Primary Workflow Families

These are the main workflow families already implied by the backend.

### 1. Board Extraction And Reconstruction

Input:

- KiCad netlist
- KiCad PCB

What the system does:

- extracts connectors and semantic connector roles
- extracts rails and regulator relationships
- infers interfaces such as I2C, UART, SPI, SWD, and power links
- identifies controller/runtime clues when evidence exists
- emits a firmware-facing surface describing flash/debug strategy, external interfaces, signal inventory, runtime role, and likely firmware functions
- emits bring-up guidance and open questions

Value:

- makes an unknown board legible
- supports reverse engineering and system reconstruction
- gives the frontend a real artifact graph to visualize

### 2. Board Validation And Manufacturing Packaging

Input:

- KiCad board artifacts
- optional project or revision context

What the system does:

- validates design files
- generates BOM
- generates Gerbers
- generates PnP
- generates DFM and EE-quality outputs
- packages deliverables for manufacturing

Value:

- shortens the path from design state to fabrication handoff
- gives one continuous workflow instead of several disconnected exports

### 3. Requirements To Engineering Readiness

Input:

- requirements/specification payload
- optional evidence files

What the system does:

- compiles readiness
- enumerates questions and assumptions
- flags risks
- builds capability and lane checks
- emits SOW-style planning outputs

Value:

- helps when the design is not clean yet
- provides structure before schematic or PCB completion
- supports consulting, planning, and engineering intake workflows

### 4. Project And Revision Management

Input:

- project identity
- revisions
- optional requirements or board artifacts

What the system does:

- creates and stores project state
- creates revisions
- compares revisions
- emits build-package outputs from revision state
- preserves readiness and continuity over time

Value:

- gives engineering continuity instead of one-off board runs
- supports iteration, comparison, and traceability

### 5. Power And Control Analysis

Input:

- extracted board structure from KiCad artifacts

What the system does:

- identifies regulator stages
- surfaces protection findings
- classifies power stages such as buck, boost, and LDO-like stages
- classifies motor-driver or gate-driver stages where supported
- phase-links BLDC gate-driver and current-feedback stages where evidence supports it
- identifies firmware-visible control channels such as PWM, current-sense, CAN-ish, and analog feedback nets when the MCU pinout database is thin but raw net evidence exists

Value:

- moves the system beyond "file parser" into electrically meaningful judgment
- helps distinguish plain controller boards from real power/control boards

### 6. Multi-Board And Machine Engineering

Input:

- several extracted boards
- machine definition
- interconnect and power context
- optional mechanism context

What the system does:

- infers candidate interconnects
- infers candidate power tree
- builds a system graph
- orders board bring-up
- compiles a machine preview
- emits a `motor_control_pack` summarizing actuation boards, control links, power feeds, and actuation-focused bring-up context
- supports machine engineering and full-simulate flows

Value:

- makes the system useful for robotics, mechatronics, and distributed board systems
- lifts the product out of "single PCB utility" territory

### 7. Mechatronic Context And 3D Bridge

Input:

- machine workflows with board files
- optional mechanism information

What the system does:

- preserves PCB outline and mount information
- preserves ports and electronics anchors
- carries prototype3d packaging context into machine flows

Value:

- keeps the electrical and mechanical story connected
- supports the broader Circuit-AI / Mecha-Splicer / 3D-Splicer stack direction

### 8. Visual Analysis, Repair, And Education

Input:

- board image

What the system does:

- analyzes the board image
- routes into component/project/educational/repair outputs
- supports lighter-weight discovery and interpretation flows

Value:

- gives an easier entry point than full EDA files
- supports education, repair, triage, and top-of-funnel product use

### 9. Reuse, Salvage, Inspection, And Triage

Input:

- image evidence
- board artifacts
- partial legacy evidence

What the system does:

- helps surface reusable modules or interesting board regions
- supports fault and inspection-style workflows
- supports board-level extraction even on older external projects

Value:

- useful for reuse, refurbishment, e-waste, and practical hardware triage
- supports the repo's historical product variants such as salvage, inspection, and education

## High-Value Use Cases

These are the user-facing use cases the current backend can already assist with in a meaningful way.

### Students, Makers, And Learners

- find viable builds from available parts
- get build instructions and learning-path outputs
- understand what a board is doing
- move from curiosity into guided electronics work

### PCB Engineers And Hardware Startups

- validate designs before fabrication
- generate manufacturing outputs
- compare revisions
- preserve project continuity
- reason about power and controller structure on real boards

### Reverse Engineering And Legacy Hardware Work

- recover connectors, rails, interfaces, and power structure from older boards
- reconstruct likely board-to-board links
- establish bring-up order and open questions

### Robotics, Machines, And Mechatronics

- organize several boards as one machine
- infer interconnects and power links
- carry electrical context into machine engineering and simulation
- preserve board geometry and anchor context for mechanical follow-on work

### Repair, Diagnostic, And Bring-Up Work

- generate bring-up plans
- identify suspicious power/control structure
- route image-based analysis into repair and educational assistance

### Manufacturing And Operations

- take a validated board into BOM, Gerber, PnP, DFM, and packaging flows
- use project/revision state to control what gets built

### Reuse, Appraisal, And Inspection

- inspect boards for reusable structures
- use image and board evidence to support salvage or triage decisions
- support AOI-like comparison and inspection-adjacent workflows through the broader repo stack

## Concrete Outputs The Frontend Should Surface

If the frontend is built around the real backend, it should be able to surface:

- active board or machine context
- extracted connectors and rails
- regulator and power-stage relationships
- controller/runtime facts and programming hints
- firmware-facing runtime surface and likely firmware functions
- bring-up plan
- validation issues
- manufacturing artifacts
- project/revision state
- candidate interconnects and power tree
- machine compile preview and system graph
- questions, assumptions, and risks
- educational, repair, and reuse outputs from visual analysis

## Where The Current Backend Is Strongest

Current strongest value areas:

- board extraction from KiCad artifacts
- board validation and manufacturing packaging
- project and revision continuity
- requirements/readiness workflows
- multi-board machine/system framing
- first-pass power/control reasoning
- firmware-aware hardware reasoning over controller surfaces and raw MCU net evidence
- machine-level motor/control pack extraction for actuation-oriented systems
- benchmarked compatibility with real outside hardware such as Tardygrade, MotCtrl, and Paul

## Current Boundaries

The backend is strong enough to anchor a serious workbench, but it still has boundaries.

It is not yet:

- a full RF or EMC signoff system
- a full inverter-grade motor-control signoff system
- a full firmware semantic analyzer
- a full CAD authoring replacement
- a complete hardware-in-loop lab

Those are expansion directions, not the current baseline.

## Practical Product Summary

Circuit-AI is best understood as a deterministic engineering substrate for:

- board understanding
- board validation
- manufacturing preparation
- revision continuity
- multi-board machine framing
- visual analysis and interpretation

That is already enough to support a serious integrated frontend workbench.
