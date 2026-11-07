# Hardware Splicer CM4 Lite ultra-thin dual-touch feasibility replay

**2026-11-08.** Test of **HS** running its own technical design study, not another assistant-made standalone CAD. Builds on PR #308 and PR #307; target is a useful and economically rational personal product, NOT starting a business. **Research-only; no buying or fabrication authority.**

## Critical result

A *different* CM4 device, the **wireless 2GB Compute Module 4 Lite CM4102000**, is listed in Taiwan by element14 for **NT$2,238.43 (before VAT)**, but lead time is currently indicated as **26 weeks**. This is a component quotation, **not a delivered prototype**. Unlike the earlier CM4102032 at NT$3,728, it has **no on-module eMMC**; a correctly routed microSD card/SDIO path, safe boot power, and RF antenna keepout are required.

We evaluated the two **exact** Winstar **WF50DTYA3MNG10-000** 720x1280, capacitive, **2-lane** MIPI DSI units. DigiKey US listed a vendor price **US$29.88 each**, excluding shipping/taxes/NTD conversion; **WF50DTYA3MNG10** without **-000** is the **4-lane** different variant and must not be substituted. The parent Winstar product family page shows the 4-lane model, so the exact distributor part / underlying 2-lane data sheet must control the interface. Parent manufacturer mechanical outline (127.6 x 73.3 x 3.45mm) is treated nominally; verify on the exact -000 mechanical drawing before manufacturing.

Official Raspberry Pi **CM4 datasheet** reports the 1.5mm connector option gives **5.078mm mated module height above carrier**, and a 40x55mm board. The CM4 Lite needs an SD path. Raspberry Pi documents DSI0 (2 lanes) and DSI1 (4 lanes); use only 2 of DSI1's 4 available lane positions with suitable custom wiring. **No dual Winstar panels have been powered or tested.** Full Linux display initialization and two separate touch-controller I2C paths need source-compatible engineering, not mere pin matching.

## Nominal HS calculation at the strict 155 x 80 x 18 mm CLOSED target

Assumptions: lower shell 1.6mm FDM floor; 0.8mm custom carrier PCB; 5.078mm mated CM4 stack; 6.0mm **naked / unprotected** battery placeholder; Winstar capacitive module 3.45mm; closed glass-to-glass gap 0.8mm; >=1mm *research* clearance in lower half; upper lid shell floor 1.6mm.

There is **no verified tolerance budget, no battery protection, no fully constrained mounting / rear FPC**. The dimensional *nominal* layer experiment is:

| Upper lid height | CM4/lower LCD clearance | Bare battery/lower LCD clearance | Native HS MechanicalFit |
| --- | ---: | ---: | --- |
| 5.05mm | 1.222mm | 1.100mm | *nominal* research pass |
| **5.10mm** | **1.172mm** | **1.050mm** | *nominal* research pass |
| 5.15mm | 1.122mm | 1.000mm | *nominal* research pass |
| 5.20mm | 1.072mm | 0.950mm | FAIL |
| 5.30mm | 0.972mm | 0.850mm | FAIL |
| 5.80mm | 0.472mm | 0.350mm | FAIL |

The selected 5.10mm lid contains a **3.45mm panel + 1.60mm shell**, leaving **0.05mm** nominal additional space for actual LCD retention / backing. This does **not** meet viable manufacturing margins. Nearby variations (cell +0.3mm; CM4 package +0.25mm; lid +0.2mm; panel +0.15mm) **all cause the native HS nominal fit to fail**.

**Whole-device envelope failure:** Native OpenSCAD's external 6.8mm hinge is centered 1.2mm behind the 80mm shell, projecting another **4.6mm**. The resulting closed device is **155 x 84.6 x 18mm**, not 155 x 80 x 18mm. The 80mm "case body" figure must NEVER be substituted for the complete assembly. Even reducing this existing barrel to a *valid* nominal 5.8mm outer diameter and 0.5mm rear offset still produces **83.4mm** outer depth on an 80mm shell. An inset, differently positioned, or redesigned hinge is required; shell XY clearances around the 73.3mm display are already narrow.

Therefore the finding is **not** '18mm viable'; it is: **a highly constrained, sensitivity-fragile nominal 18mm internal stack exists but the external hinge violates the strict pocket footprint**. This is a useful counterexample to the idea that CM4 always needs >20mm, but tells us exactly what to resolve with real components or redesign.

### Unresolved engineering gates

- The 4.6mm rear hinge projection **fails the external 80mm limit**, despite valid shell meshes. Real inset hinge with preserved strength and FPC bend path is required.
- The exact 2-lane panel's kernel DSI timing/init sequences and dual GT928 controller bus address / IRQ/reset topology.
- DSI0 and DSI1 simultaneous display output on exact CM4 carrier (Raspberry Pi IO board supports separate DSI connections, but the specific pair is untested).
- Actual panel FPC tail routed across hinge with correct high-speed impedance, bending radius and lifetime; a long MIPI extension is not inherently safe.
- Rigid LCD retention, cover glass, backlight boost power, ESD, thermal heatsink and CM4 antennas.
- Mated connector footprint, bottom clearance, PCB fab / DRC, SD connector, protected single-cell pack & charge management.
- A real pocket test with a printed thickness dummy and a target 30-minute remote editing workflow.
- All-in Taiwan delivered price including both screens, full PCB/carrier, assembly, shipping, battery, hinge, and rework.

The **exact two screens' NTD delivered cost is absent**. Do not invent an FX rate, declare a 'NT$ price' from a USD seller ask or represent the NT$2,238 CM4 as an entire product cost.

## Reproduce THROUGH Hardware Splicer

```bash
PYTHONPATH=src:apps/mecha-splicer/src python3 -m hardware_splicer.cyberdeck_cm4_stack \
  --requirements examples/cyberdeck/cm4_thin_stack/requirements.json \
  --out examples/cyberdeck/cm4_thin_stack/evidence
PYTHONPATH=src:apps/mecha-splicer:apps/mecha-splicer/src python3 -m pytest -q \
  tests/test_cyberdeck_cm4_stack.py \
  tests/test_cyberdeck_architecture_value.py \
  tests/test_cyberdeck_packaging_workflow.py \
  examples/cyberdeck/dual_touch/tests/test_dual_touch.py \
  apps/mecha-splicer/tests/test_bundle.py
```

The native workflow combines **HS MechanicalFit** bounding-box reports, **existing Mecha-Splicer** shell generator + correct CM4+2 Winstar BOM, and **canonical MachineProject** safety/authority gates. The OpenSCAD binary STLs and sampled hinge CGAL collisions, when present, were generated via HS's existing `produce_terminal.py` using the current `native_project_spec.json` after the nominal selected scenario.

**This is an engineering study, not a physical artifact. Nothing was purchased or powered, and HS is prohibited from releasing the design as fabrication-ready.**

### Suggested next experiment

Qualify a *real* protected battery (including connector and swelling allowance), a proper mated CM4 carrier board outline, and supplier-confirmed exact -000 Winstar panel/FPC stack. If any part violates these sub-millimetre margins, **change the architecture or dimensions**—do not simply erase protection, thickness or tolerance requirements to make the CAD fit. If acceptable assembly space requires 19–21 mm, record that as a separate design trade-off, not a silent change to the 18mm user specification.
