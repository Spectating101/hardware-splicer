# Cyberdeck × Hardware-Splicer Fit Experiment

**Status:** synthetic architecture/gap test only — no physical cyberdeck was built or verified in this pass.  
**Date:** 2026-08-29  
**Branch:** `design/cyberdeck-hs-fit-20260829`  
**Fixture:** `docs/design/examples/cyberdeck/machine_project.example.json`

## Decision summary

A cyberdeck is a highly natural full-machine workload for Hardware-Splicer.

Current HS can already represent and govern most of the *engineering process* needed for a multi-donor portable computer: requirements, donor/new/generated components, subsystem decomposition, interfaces, unresolved evidence, mechanical-fit gates, basic electrical/power analysis, verification methods, bench evidence, and fail-closed authority. The canonical `MachineProject` spine is broad enough that no cyberdeck-specific project model is required.

However, current HS cannot honestly claim end-to-end autonomous cyberdeck engineering. The largest missing technical capabilities are laptop-class power architecture, thermal design, high-speed-link engineering, rich enclosure/assembly geometry, and software/driver compatibility. Those should be added only as generic cross-project capabilities, not as a one-off `cyberdeck_engine.py`.

The strongest framing is therefore:

> **Cyberdeck Challenge 002 = first full-machine HS systems benchmark.**
>
> Keyboard Challenge 001 tests destructive donor transformation at small scale. Cyberdeck Challenge 002 tests multi-donor systems integration across electrical, mechanical, software, sourcing, verification, and lifecycle provenance.

---

## 1. Representative target used for the fit test

The synthetic fixture models this target:

- x86-class Linux workstation;
- integrated 13-inch-class donor display;
- donor keyboard/input assembly;
- replaceable NVMe storage;
- at least two external USB ports plus networking;
- rechargeable removable battery;
- external USB-C charging / power input;
- reusable or replaceable cooling assembly;
- generated serviceable enclosure;
- donor-first reuse where evidence makes reuse rational.

Candidate physical lineage:

```text
Donor mini-PC/laptop mainboard ─┐
Donor laptop LCD ───────────────┤
Donor keyboard ─────────────────┤
Existing/new NVMe ──────────────┤
New battery + BMS/PD ───────────┼──► HS cyberdeck output
USB hub/breakout ───────────────┤
Donor/new cooling ──────────────┤
Generated enclosure ────────────┘
```

The fixture intentionally leaves important engineering facts unresolved rather than selecting convenient answers in advance.

---

## 2. What current HS handles well

### 2.1 Cross-discipline machine representation — **STRONG**

Current `MachineProject` already has first-class domains for:

- system;
- mechanical;
- electrical;
- firmware;
- software;
- sourcing;
- assembly;
- verification.

It supports requirements, functions, subsystems, components, interfaces, constraints, verification methods, evidence and artifacts under one project identity. Components can be `NEW`, `DONOR`, `GENERATED`, `EXTERNAL`, or `UNKNOWN`.

For cyberdecks this is important: compute, display, keyboard, power, cooling, enclosure, storage and software can remain different discipline payloads while still resolving to one machine project.

**Assessment: 9/10 fit.**

### 2.2 Donor provenance and evidence-bounded reuse — **STRONG**

HS already models donor components/interfaces separately from merely similar catalog modules. Donor interfaces may remain `UNKNOWN`/`PARTIAL` until contacts, signals, voltages, protocols and completeness are evidenced.

This maps directly to cyberdeck donors such as:

- unknown laptop display panels;
- mainboard DC-input interfaces;
- reused keyboard matrices/controllers;
- speakers, fans, antennas, webcams, ports and batteries;
- salvaged daughterboards.

The right behavior is not “a laptop LCD is probably eDP”; it is “this exact panel is unresolved until identity/interface evidence closes.”

**Assessment: 8.5/10 fit.**

### 2.3 Requirements → verification → evidence traceability — **STRONG**

Cyberdecks have unusually heterogeneous success criteria. Current HS can explicitly attach requirements to components/subsystems and then bind verification methods and evidence.

Examples in the fixture:

- integrated display → panel identity/interface inspection;
- battery operation → power-interface + power-budget verification;
- serviceable enclosure → mechanical-fit verification;
- sustained workload → thermal-soak verification;
- external USB/storage → functional demonstration.

This is already a better foundation than a normal DIY build log because unresolved requirements remain visible instead of disappearing into prose.

**Assessment: 9/10 fit.**

### 2.4 Basic mechanical fit / mounting authority — **MODERATE-STRONG**

Current HS already has bounded mechanical checks for:

- declared mount-interface orientation;
- AABB clearances;
- explicit coordinate frames;
- fastener stacks;
- unresolved geometry evidence;
- blocking fit checks.

That is useful for cyberdeck questions such as:

- does the board fit under the keyboard deck?;
- do ports reach their enclosure apertures?;
- do the LCD and chassis mounting normals mate?;
- is there declared clearance between battery and mainboard?;
- is the screw/stack length plausible?;
- is geometry still unresolved?

But HS explicitly does **not** currently claim full BREP collision, structural strength, vibration endurance, deformation or full mechanical safety.

**Assessment: 6/10 fit today.**

### 2.5 Electrical carrier / glue-board generation — **MODERATE-STRONG**

The existing splice flow is naturally useful when a cyberdeck needs a small custom carrier or interconnect board rather than a full computer motherboard design.

Good candidate HS-generated hardware:

- button/status-board carrier;
- keyboard controller/bridge;
- low-speed GPIO/debug breakout;
- fan/controller board;
- sensor board;
- safe low-speed power-control logic after power contracts are verified;
- connector adaptation where electrical constraints are within current verified scope.

HS should **not** currently claim it can automatically design arbitrary laptop motherboards, eDP high-speed routing or PCIe/USB4 signal-integrity-critical boards.

**Assessment: 7/10 for bounded carrier/glue electronics; much lower for high-speed computer motherboard work.**

### 2.6 Bench / evidence gating — **STRONG**

A cyberdeck is a good match for HS's bench philosophy because many dangerous mistakes should become explicit gates:

- battery polarity unresolved;
- mainboard input voltage unresolved;
- charger/PD profile unresolved;
- display pinout unresolved;
- post-assembly short/continuity checks;
- fan operation;
- storage enumeration;
- keyboard enumeration;
- USB downstream-current test;
- sustained-load temperatures;
- charge/discharge behavior.

HS already has the principle and machinery that unresolved evidence should block stronger physical authority.

**Assessment: 8/10 fit.**

---

## 3. Where current HS is only partial

### 3.1 Power architecture — **PARTIAL**

Current HS contains an analytical power-budget / optional ngspice path, but the current implementation is optimized around a small module catalog with simple 3.3 V / 5 V / 12 V maker-electronics sources and default load estimates.

That is useful for catching obvious overloads on supported low-voltage module builds. It is not sufficient for a serious x86 cyberdeck.

A cyberdeck requires a generic power-tree model covering at least:

```text
external source / USB-C PD
          ↓
charger / power-path controller
          ↓
cell pack + BMS
          ↓
conversion rails
   ├─ compute input
   ├─ display/backlight
   ├─ USB peripherals
   ├─ storage
   └─ auxiliaries
```

Missing or under-modeled concerns include:

- USB-C PD profiles/negotiation;
- charge while operating;
- battery chemistry and series/parallel topology;
- BMS limits;
- peak/transient load;
- converter efficiency;
- startup sequencing;
- connector/cable current ratings;
- per-rail protection/fusing;
- runtime estimation;
- brownout margin;
- charge/discharge thermal constraints.

**Assessment: 4/10 for laptop-class cyberdeck power today.**

This is probably the single highest-value generic engineering capability a cyberdeck benchmark would force HS to add.

### 3.2 High-speed interfaces — **REPRESENTABLE, NOT FULLY ENGINEERED**

`MachineProject.Interface` can represent contracts for:

- eDP;
- HDMI;
- USB 3.x;
- PCIe/NVMe;
- MIPI;
- Ethernet;
- other digital links.

The donor interface system can also keep pinout/protocol/voltage fields unresolved.

What current HS does **not** provide is a proof-grade high-speed signal-integrity engine for:

- differential impedance;
- length matching;
- lane topology;
- return paths;
- connector insertion loss;
- eye margins;
- EMI/EMC.

Therefore a safe cyberdeck architecture should preferentially **reuse validated native interfaces/cables** rather than asking HS to redesign high-speed interconnects from scratch.

**Assessment: 7/10 representation and compatibility gating; 2–3/10 novel high-speed electrical design.**

### 3.3 Thermal engineering — **WEAK**

Current machine semantics can represent a thermal subsystem, requirements, constraints and physical test evidence. This is useful: HS can refuse to call sustained operation verified until measured temperature evidence exists.

But there is no mature generic thermal-design engine comparable to the electrical/mechanical authority layers.

Needed generic capability:

- declared component heat loads / TDP envelopes;
- cooling device capacity and operating state;
- inlet/exhaust definitions;
- thermal keep-outs;
- battery-temperature boundaries;
- fan curves / control state;
- measured temperatures tied to workload;
- perhaps simple lumped/empirical thermal models before any CFD ambition.

**Assessment: 2.5/10 automated engineering; 7/10 ability to represent and gate empirical validation.**

### 3.4 Full enclosure / assembly CAD — **PARTIAL**

Current fit checks can bound some placement errors, but a polished cyberdeck eventually needs richer spatial modeling:

- imported STEP/STL/mesh bodies;
- assembly hierarchy;
- articulated states (lid open/closed);
- cable paths and minimum bend radius;
- connector access volumes;
- service/removal paths;
- keep-out regions;
- fastener access;
- ventilation/open-area constraints;
- more complete collision checking.

This directly supports the planned Blender-like web frontend.

**Assessment: 5/10 current engineering backend fit; excellent future workbench driver.**

### 3.5 Operating-system / driver compatibility — **REPRESENTABLE, LIGHTLY AUTOMATED**

`MachineProject` has a software domain, so HS can represent:

- Linux distribution;
- kernel/driver requirements;
- display/input/network/storage dependencies;
- firmware versions;
- verification procedures.

But HS is not presently a full OS hardware-compatibility resolver. A real cyberdeck would need evidence around:

- suspend/resume;
- battery/charge telemetry;
- Wi-Fi/Bluetooth;
- audio;
- display brightness;
- hotplug;
- sleep/wake input;
- fan control;
- firmware updates;
- device-tree/ACPI quirks depending architecture.

**Assessment: 4/10 automation, 8/10 traceability representation.**

---

## 4. Current HS fit score

These scores measure different things and should not be collapsed into a fake universal percentage.

| Cyberdeck engineering dimension | Current HS fit |
|---|---:|
| Machine/system decomposition | 9/10 |
| Requirements + traceability | 9/10 |
| Donor provenance / reuse governance | 8.5/10 |
| Interface evidence contracts | 8/10 |
| Bench / authority gating | 8/10 |
| Low/medium-speed glue electronics | 7/10 |
| Mechanical fit / mounting | 6/10 |
| Whole-system power | 4/10 |
| OS / driver integration | 4/10 |
| Detailed enclosure / cable-routing CAD | 5/10 |
| Thermal design automation | 2.5/10 |
| Novel high-speed-link design | 2–3/10 |
| Lifecycle/passport runtime | design only today |

### Practical interpretation

**HS is already credible as the cyberdeck project's engineering coordinator / evidence authority.**

It can structure the machine, manage donor identity, expose unknown interfaces, track constraints, generate bounded electronics, run some mechanical/electrical checks, define bench gates and produce an auditable project package.

**HS is not yet credible as a push-button cyberdeck generator.**

A human/agent still has to perform substantial engineering around power, thermal, high-speed compatibility and enclosure integration.

That distinction is valuable rather than embarrassing: cyberdeck work identifies exactly which generic capabilities must mature next.

---

## 5. What HS could realistically do on Cyberdeck #001 with no new core subsystem

Given real donor hardware and photos/specs, current HS should already be able to drive this sequence:

1. **Create one MachineProject** with target requirements.
2. **Register each donor/new component** and provenance state.
3. **Create subsystem graph** for compute/display/input/power/storage/IO/enclosure/thermal/software.
4. **Create explicit interfaces** and leave unsupported assumptions unresolved.
5. **Request donor identity evidence** for LCD, board, keyboard, fan, connectors, etc.
6. **Decide REUSE / REUSE-PENDING / REPLACE / NEW-GLUE** at component/interface level.
7. **Use existing interface-contract machinery** for accessible donor electrical interfaces.
8. **Generate bounded low-speed carrier/glue PCBs** where current compiler/catalog capability is appropriate.
9. **Use mechanical geometry/fit gates** for known mount/clearance questions.
10. **Run current electrical budget analysis** only where supported and explicitly mark cyberdeck-class power facts still unresolved.
11. **Generate bench gates** before power-on and after integration.
12. **Capture real measurements** and update evidence state.
13. **Produce final project/casefile package** with remaining nonclaims.
14. Later, **project that evidence into the lifecycle/passport layer** once a real transformed output exists.

That is already a meaningful amount of the project.

---

## 6. Generic HS capabilities cyberdecks justify adding later

Do **not** add a cyberdeck-specific engine. Add reusable machinery capabilities:

### P0 — Power Tree v2

General purpose portable-device power model:

- source / battery / BMS / charger / converter / load graph;
- voltage/current/power envelopes;
- transient and startup budget;
- protection;
- efficiency;
- energy/runtime budget;
- bench validation hooks.

Useful later for robots, drones, portable instruments, vehicles, UPS systems and edge devices.

### P1 — Spatial Assembly Workbench / Geometry v2

Backend concepts supporting the planned Blender-like frontend:

- assembly tree;
- measured/imported geometry;
- transforms;
- articulated states;
- clearance/keepout volumes;
- service access;
- connector/cable routing;
- evidence state rendered spatially.

### P2 — Thermal Envelope

Start empirical/bounded:

- heat-source declarations;
- cooling components;
- thermal constraints;
- sensor locations;
- workload-bound temperature evidence;
- pass/fail envelopes.

### P3 — High-Speed Interface Policy

Not a full SI solver initially.

At minimum distinguish:

- direct reuse of manufacturer-validated cable/interface;
- passive adapter with known constraints;
- custom carrier requiring controlled-impedance design;
- unsupported high-speed redesign.

This lets HS fail closed instead of treating all `Interface` objects as electrically equivalent complexity.

### P4 — Software/Platform Verification

Generic hardware-software bring-up matrix:

- device enumeration;
- drivers;
- firmware;
- suspend/resume;
- power telemetry;
- thermal/fan control;
- workload tests.

---

## 7. Passport/lifecycle fit

Cyberdecks are unusually strong lifecycle objects because they have no single manufacturer's authoritative final configuration.

For a finished deck, the lifecycle record could preserve:

```text
Donor A mainboard ─┐
Donor B display ───┤
Donor C keyboard ──┤
New power system ──┼─► Deck-001 R1
Generated chassis ─┘

R2: battery replaced
R3: compute board upgraded
R4: display cable repaired
R5: carrier-board revision changed
```

Every revision can selectively invalidate affected evidence and require retesting.

This is arguably a *better* demonstration of HS Passport than an ordinary refurbished stock product, because manufacturer documentation stops being sufficient once several donor systems become one new machine.

Cyberdeck therefore connects four HS theses in one object:

1. donor reuse / splicing;
2. bounded physical engineering authority;
3. reusable transformation recipes;
4. persistent lifecycle/passport evidence.

---

## 8. Frontend consequence

Cyberdeck testing reinforces the need for a spatial web workbench.

A future HS interface should allow the operator/agent to work against one visible machine rather than a collection of forms:

```text
Asset / assembly tree  |       3D workspace       | Evidence inspector
-----------------------|----------------------------|-------------------
Compute                |  board / display / case   | identity
Display                |  positions + constraints  | interface state
Keyboard               |  collisions / keepouts    | measurements
Power                  |  cable/connector routes   | authority
Cooling                |  selected component       | blockers
Enclosure              |                            | history
```

Important HS-specific rendering semantics:

- verified/measured geometry distinct from estimated geometry;
- unresolved interface regions visually explicit;
- blocking collisions/constraints visible;
- donor provenance inspectable from the object;
- evidence and lifecycle history reachable from the selected physical component;
- no drag/drop action silently changes engineering authority.

This is **not Blender-in-browser for its own sake**. It is a spatial frontend for `MachineProject` + evidence + authority.

---

## 9. Recommended benchmark sequence

### Challenge 001 — Monolith → Split Keyboard

Focus:

- destructive donor modification;
- matrix/interface reverse engineering;
- firmware;
- evidence-gated cut/rebuild;
- small physical artifact.

### Challenge 002 — Multi-Donor Cyberdeck

Focus:

- full-machine requirements;
- multi-donor provenance;
- display/input/compute integration;
- power + thermal;
- enclosure/assembly;
- software bring-up;
- lifecycle passport.

### Challenge 003 — Electromechanical Machine

Example inspection gantry / rover.

Focus:

- motion;
- higher-current actuation;
- sensing;
- mechanics;
- controls;
- field safety.

That sequence grows HS's physical scope without jumping immediately from small electronics to high-risk machinery.

---

## 10. Final verdict

**Cyberdeck fit: high at the systems/evidence level, moderate at current automated engineering depth.**

The current project does not need a conceptual rewrite to support cyberdecks. The existing `MachineProject`, donor-interface, splice, electrical, mechanical, bench and evidence-authority foundations are already pointed in the right direction.

The cyberdeck is valuable precisely because it stresses the weak domains that HS eventually needs for many other products:

- portable power;
- thermal management;
- rich spatial assembly;
- high-speed interface policy;
- hardware/software bring-up.

Therefore the recommendation is:

> Keep cyberdeck as **Hardware-Splicer Challenge 002 / first full-machine benchmark**, and let it drive generic capability growth only when a real donor build begins.

Do not start a large cyberdeck-specific implementation before Challenge 001 or before real hardware is available.
