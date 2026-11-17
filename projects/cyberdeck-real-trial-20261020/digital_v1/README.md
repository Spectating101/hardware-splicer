# Fielddeck 7 — engineered digital cyberdeck prototype

An editable device design for a portable **Linux terminal, offline build-reference reader, SSH machine and light coding station**. It combines a Raspberry Pi 4, 7-inch landscape touchscreen, wired keyboard, removable commercial power bank and a modular printed case. This continues the original cyberdeck goal with an actual assembly rather than another backend feature.

![Fielddeck 7 assembly](views/assembled.png)

**Digital scope:** CAD and first-order engineering calculations are complete for this revision. No physical device or booted simulation is claimed. Keyboard keys/screen content are illustrative and CAD colours distinguish parts; the selected spool is black. The assembly itself comes from the delivered geometry.

| Deliverable | Open |
| --- | --- |
| Editable solid assembly | [FIELDDECK_7.step](cad/FIELDDECK_7.step) |
| 3D viewer model | [FIELDDECK_7.glb](cad/FIELDDECK_7.glb) |
| 20 individual printable parts, STEP and STL | [cad/print](cad/print) |
| Exploded / internal / dimensioned views | [Exploded](views/exploded.png), [internal](views/internal.png), [drawing](views/dimensioned_layout.png) |
| Exact commercial modules and standard hardware | [BOM.csv](BOM.csv), [bom.json](bom.json) |
| Matching build and connection plan | [ASSEMBLY.md](ASSEMBLY.md), [CONNECTIONS.md](CONNECTIONS.md), [diagram](views/connections.svg) |
| Power/runtime and structural/airflow calculations | [calculations.json](analysis/calculations.json), [power plot](analysis/power_runtime.png) |
| OS, installation and future bring-up scripts | [software](software/README.md) |
| Actual exported geometry verification | [verification.json](analysis/verification.json) |

## The device

The case is **310 × 285 × 64 mm**, with 6 mm feet and a 2 mm fan guard outside that envelope. Four tray quarters and four face pieces fit individually on a 220 mm printer. A 7-inch Touch Display 2 uses the publisher's MIT-licensed STEP and measured mounting geometry. The keyboard and bank have purchased-part envelope models based on their published dimensions. Pi USB/Ethernet face the rear; two USB 2 ports serve keyboard/fan and two USB 3 ports remain available within the power limits. External USB service loops need rear clearance.

Selected identities: Pi **SC0193** (2GB), display **SC1635**, Adafruit keyboard **1736**, Anker **A1259**, Noctua **NF-A4x10 5V PWM**, SanDisk **SDSQXCG-032G-GN6MA0**, Adafruit **1648** display FFC and **824** power extensions, StarTech **USB2CC50CM**. Links and acquisition status are in the BOM. There is no custom PCB: this device's engineering work is integration, mounting, connections, power, service access and enclosure design.

## What the calculations say

- **Ordinary terminal scenario:** 8.25 W, estimated **2.78–3.93 h**. Light scenario: 3.53–4.98 h. Stress allocation: 1.82–2.57 h. These use assumed Pi/keyboard consumption, 36 Wh nominal cell energy, 75–90% conversion and 85–100% usable capacity. They are not measured runtime.
- **Power boundary:** the bank supplies **5 V, 3 A** per selected port. Stress allocation is 2.52 A; with a 0.5 A keyboard sensitivity it becomes 2.92 A, leaving little margin. Pi USB ports also share 1.2 A. Extra powered disks/radios need a separate budget or self-powered hub. Cable/contact resistance can cause undervoltage even below 3 A.
- **Cost reference:** approximately **$337** including a full PETG spool and explicit hardware/cable allowances, before tax, shipping, printing labour and tools. Live-observed prices are separate from allowances. The old $250 trial target was evaluator-imposed and is not met here; no user budget/country was assumed. This is a dated parts reference, not a shopping order.
- **Mechanical check:** each ideal display post carries about 1.72 N in a 2 g lateral scenario with an assumed 350 g panel; about 1.0 MPa bending stress and 0.11 mm deflection. This excludes layers, joints, screws, seams, glass and impacts; it is not FEA or a drop rating. Solid CAD PETG upper bound is about 840 g; actual sliced mass is unknown.
- **Cooling sensitivity:** at 12.6 W assumed heat, the four tested delivered-flow fractions are 5%, 10%, 20% and 40% of 8.9 m³/h free-air flow. The corresponding bulk air rises are approximately **84.5, 42.3, 21.1 and 10.6°C**. This broad range exposes the need to establish actual airflow and heat transfer; it does not prove the fan can cool the computer. CPU junction temperature and the real fan/system operating point remain unresolved.

## Verification and remaining uncertainty

The delivered CAD was iterated after actual intersections were found at keyboard supports, the rear Pi I/O fixing and a seam plate. The glass needed an underside bezel recess. The independent follow-up also found that open-top lid-nut pockets provided no axial retention: the face could lift out with its nuts. The revised bosses have side-loading captive nut pockets and a printed retaining roof. The duct now bolts into the fan stack with M3×25 screws, and the fan/duct/face subassembly is assembled outside the case before installation.

The original log is retained as `cad/iteration_01.json`; its two display-post overlap reports were identified as coincident-face artefacts, and the check now counts closed intersection solids only. Verification reopens the exported parts, checks screw/nut/head/bearing and tool-shaft envelopes, retaining roofs, exact STEP part placement and the GLB representation. Source, author, design, calculations and verified artifact bytes are bound together; changing inputs requires regeneration. Flexible cables, full tool handles, real lug threads, torque, printed strength and detailed purchased-module surfaces remain outside those rigid checks.

The largest remaining fit uncertainties are the bank's unpublished port/button placement, the keyboard underside/pad stack, nominal display lug thread engagement, and flexible leads. The GPIO extension's 28 AWG copper drop can be estimated, but its contact rating/retention remains provisional. Actual printing, input-voltage/load testing, cooling, touchscreen alignment and ARM boot were not performed because this project is digital only.

## How this relates to Hardware Splicer

This is **assistant-directed engineering using specialist CAD tools**, now also executable through HS's registered `fielddeck-7` backend case. `hs-digital cases` lists its numeric goals; `hs-digital init --case fielddeck-7` builds a fresh saved study. Changes to runtime/current goals, load assumptions, enclosure size limits or printer-bed targets generate new reports and preserve passed/failed revisions. The fixed module layout is checked explicitly; unsupported geometry changes require an authored design revision. [The backend guide](BACKEND.md) documents the shared Python/CLI/HTTP workflow.

The existing project/source/material import remains an additional traceable source record: [HS receipt](analysis/hs_receipt.json), [native STEP reading](analysis/hs_source_check.json) and [material reconciliation](analysis/hs_materials.json). The user owns no parts, so the real inventory is empty and all materials correctly remain to acquire or make. Retail availability is never treated as owned stock. This does not establish autonomous arbitrary-device design.

The old October temporary store no longer exists. `hs_project/` is a durable recovery of the same objective, with fresh revision history; the original trial's verdict is preserved. The new backend case reuses HS's existing job, revision, audit and export lifecycle. No frontend, purchase, fabrication or hardware action was performed.

## Regenerate

Use Python with `cadquery==2.6.1`, `trimesh==4.12.2`, `numpy==2.5.5`, `matplotlib==3.11.2`, `Pillow==13.0.0`, `CairoSVG==2.9.1`. The existing repository environment is `.cache/hardware-splicer/digital-native-venv/bin/python`. Run `author_cad.py`, `engineering.py`, `render_device.py`, then `verify_device.py` in that interpreter. Use the repository `.venv/bin/python save_hs_project.py` for the existing HS services, then run `package_device.py` in the CAD interpreter for the distributable ZIP and rendered connection diagram. No LLM/API credential is required. Review `design.json` and the layout constants in the authoring code together; changing a case dimension does not automatically rearrange every module.

The Raspberry Pi display STEP is redistributed with [its MIT license](sources/touch_display2_LICENSE.txt). Primary documents, source URLs and source hashes are recorded in [sources/references.json](sources/references.json); other manufacturer PDFs/HTML are local research captures, excluded from the distributable package.
