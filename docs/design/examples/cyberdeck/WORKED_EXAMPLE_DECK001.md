# Worked Example — DECK-001 Modular Linux Cyberdeck

> **SYNTHETIC DESIGN WALKTHROUGH ONLY.** This file demonstrates how current Hardware-Splicer should reason through one plausible cyberdeck project. No hardware was physically built, measured, powered, or verified by this document.

## 1. Mission

Build one serviceable portable x86 Linux workstation using donor hardware where reuse is defensible, while avoiding unnecessary redesign of high-speed interfaces.

Target requirements:

- x86-class Linux compute suitable for normal development workloads;
- integrated 13-inch-class display;
- integrated keyboard;
- replaceable NVMe storage;
- at least two external USB ports and networking;
- rechargeable removable battery;
- USB-C charging / external power;
- serviceable cooling;
- enclosure that can be opened without destructive disassembly;
- explicit donor provenance and revision-bound validation.

The goal is **not** maximum reuse at any cost. The goal is maximum *rational* reuse under evidence.

---

## 2. Candidate donor set

### Donor A — x86 mini-PC / laptop mainboard

Candidate reuse:

- mainboard;
- original cooling assembly if mechanically compatible;
- Wi-Fi card / antennas if reusable;
- original DC-input or USB-C power path if documented and practical.

Initial HS state: `REUSE_PENDING`.

Required evidence:

- exact board identity / revision;
- CPU/RAM configuration;
- supported storage interface;
- display outputs;
- power-input requirements;
- mounting geometry;
- cooling attachment and fan interface;
- Linux enumeration / boot evidence.

### Donor B — broken portable monitor or laptop display assembly

Candidate reuse:

- LCD panel;
- display controller if a portable monitor donor exposes native HDMI/USB-C input;
- speakers only if convenient.

Initial HS state: `REUSE_PENDING`.

HS preference: **reuse a manufacturer-validated display controller/cable path rather than designing a new eDP link.**

If the donor is only a raw unidentified laptop panel, keep it `REUSE_PENDING` until panel identity, pinout, voltage, backlight power, connector and cable topology are evidenced.

### Donor C — commodity USB keyboard

Candidate reuse:

- complete USB HID controller + matrix if physically adaptable;
- switches/keycaps/plate if a deeper transformation is justified.

Initial HS state: `REUSE_PENDING`, likely low-risk compared with display/power.

### New / external modules

- known-good NVMe SSD;
- USB hub / breakout if required;
- removable rechargeable battery system;
- USB-C PD / charger / power-path subsystem;
- generated enclosure, mounts and low-speed carrier boards.

### Explicit donor rejection candidate — old unknown lithium battery

Default HS decision: `REJECT` unless provenance, chemistry, health, BMS/protection and safe operating envelope are all established.

For DECK-001 the economically rational path is a known battery solution rather than maximizing battery reuse.

---

## 3. HS architecture decision

After donor intake, the preferred architecture is deliberately conservative:

```text
                   ┌────────────────────────────┐
                   │       DONOR A x86 board    │
                   │ Linux + NVMe + networking  │
                   └───────┬─────────┬──────────┘
                           │         │
                 native video      USB
                           │         │
                           ▼         ▼
             ┌────────────────┐  ┌──────────────┐
             │ Donor B display│  │ Donor C input│
             │ + validated I/O│  │ USB HID path │
             └────────────────┘  └──────────────┘
                           │
                           │
             ┌─────────────┴────────────────────┐
             │                                  │
             ▼                                  ▼
      known battery / PD                 USB hub / aux I/O
      power subsystem                          │
             │                                 │
             └──────────────┬──────────────────┘
                            ▼
                  generated serviceable
                       enclosure
```

The key HS decision is **not** to custom-route eDP/PCIe/USB3 unless no lower-risk architecture exists.

Use native manufacturer-validated high-speed interfaces; reserve HS-generated electronics for low/medium-speed glue, control, status, keyboard adaptation, fan control, sensing and safe connector breakout where current authority is adequate.

---

## 4. What HS asks before committing to the architecture

### Gate D1 — compute identity

HS requests:

- board markings / model;
- photos of both sides;
- port inventory;
- original power adapter label or board documentation;
- Linux boot / `lspci` / `lsusb`-class inventory if the board still functions;
- board dimensions and mounting points.

Outcome required: compute board identity and basic interfaces at least `OBSERVED`, critical power facts stronger than assumption.

### Gate D2 — display path

HS asks:

- exact panel/controller identity;
- whether donor display exposes HDMI/DisplayPort/USB-C/eDP directly;
- connector and cable identity;
- required voltage / power;
- physical dimensions and mount points.

Decision branches:

1. **Portable-monitor donor with native HDMI/USB-C controller:** prefer direct reuse.
2. **Raw laptop panel with fully evidenced compatible controller path:** allow reuse pending bench verification.
3. **Raw panel still electrically ambiguous:** do not connect; source another display/controller.

### Gate D3 — input path

HS asks:

- whether keyboard donor already enumerates as standard USB HID;
- physical dimensions;
- whether controller can remain attached after mechanical adaptation;
- if not, matrix/interface characterization required.

Preferred DECK-001 branch: preserve donor USB HID controller and avoid matrix redesign unless the form factor forces it.

### Gate D4 — power architecture

This is the primary blocker.

HS needs:

- compute board input voltage profile;
- measured/authoritative steady-state and peak demand;
- display power;
- storage + USB auxiliary budget;
- selected battery chemistry/capacity;
- BMS current limits;
- PD input/output profiles;
- charger/power-path behavior while operating;
- connector/cable ratings;
- protection/fusing;
- thermal constraints.

Current HS can represent and gate this information, but today it cannot independently prove a laptop-class battery/PD architecture from its existing simple maker-board power catalog.

Therefore DECK-001 remains **power-blocked** until those facts come from component documentation, accepted measurements, or a human/external engineering calculation that HS records as evidence.

### Gate D5 — mechanical layout

HS obtains measured/imported geometry for:

- mainboard;
- cooling assembly;
- display;
- keyboard;
- battery;
- USB/IO boards;
- hinge / lid envelope if hinged.

Current HS can already check bounded mount orientation, AABB clearance and fastener-stack conditions, while explicitly not claiming structural/vibration/lifecycle proof.

---

## 5. Synthetic resolution of the first design pass

For this walkthrough, assume the evidence closes as follows:

| Object | Synthetic evidence result | HS decision |
|---|---|---|
| Donor A x86 board | exact identity found; Linux boots; native HDMI/USB available; original cooling reusable | `REUSE` |
| Donor B raw laptop panel | identity incomplete; eDP pinout/backlight unresolved | `REJECT FOR DECK-001` |
| Donor B portable-monitor controller/display alternative | native HDMI input documented and bench-testable | `REUSE` |
| Donor C keyboard | enumerates as USB HID; controller survives enclosure modification | `REUSE` |
| old donor lithium pack | health/BMS/provenance insufficient | `REJECT` |
| known battery + PD subsystem | documentation available; still requires system-level power validation | `NEW / VERIFY` |
| NVMe | native board slot verified | `REUSE/EXTERNAL` |
| enclosure | generated around measured component envelopes | `GENERATE` |

This result is important because HS **does not maximize donor count**. It rejects the ambiguous raw panel and battery because the cost/risk of establishing safe reuse exceeds the value for the first deck.

---

## 6. Resulting DECK-001 build candidate

```text
DECK-001 R0

REUSED
- x86 donor mainboard
- donor cooling assembly
- donor portable display assembly/controller
- donor USB keyboard/controller
- Wi-Fi / networking from compute donor where supported

EXTERNAL / NEW
- known NVMe SSD
- known battery + BMS / power subsystem
- USB-C PD / charging system
- small USB hub if board ports require redistribution

GENERATED BY / THROUGH HS
- machine project + traceability graph
- low-speed carrier / breakout boards if required
- mount and clearance requirements
- enclosure geometry inputs / generated parts where supported
- bench plan
- evidence package
- later lifecycle/passport projection
```

No claim is made here that current HS can automatically generate the entire enclosure or power system from first principles.

---

## 7. Pre-power authority gates

DECK-001 must remain physically unauthorized until at minimum:

1. no unresolved polarity on powered interfaces;
2. compute input voltage/profile verified;
3. selected PD/power subsystem provides the required profile;
4. battery/BMS continuous and peak current exceed verified demand with defined margin;
5. display power/interface verified;
6. no short between primary rails and ground after assembly;
7. cooling assembly correctly mounted and fan path verified;
8. no known enclosure collision compromising power, cooling or connector access.

The first battery-powered boot must itself be a controlled bench event, not proof of full readiness.

---

## 8. Validation ladder

### V1 — subsystem bench

- compute board boots from approved bench supply / known original supply;
- display works over native validated interface;
- keyboard enumerates and all required keys test;
- NVMe enumerates;
- networking works;
- fan/cooling control operates.

### V2 — integrated external-power test

Before battery operation:

- complete system powered from verified external source;
- idle and workload current captured;
- USB load behavior captured;
- display brightness states exercised;
- no brownout / unexpected reset;
- temperature sensors/measurement points established.

### V3 — battery / PD test

- charge while off;
- charge while operating;
- battery-only boot;
- sustained workload;
- USB peripheral load;
- low-battery behavior;
- charger disconnect/reconnect;
- protection behavior checked within safe, non-destructive procedure.

### V4 — thermal soak

Defined workload for a defined duration with measurements at:

- compute hotspot / heatsink;
- exhaust;
- battery-adjacent enclosure;
- charging/power-conversion region.

HS records the workload and exact revision with the evidence. A later enclosure/fan/power change selectively invalidates this thermal result.

### V5 — usability / software

- cold boot;
- reboot;
- suspend/resume where supported;
- display brightness/control;
- input after resume;
- Wi-Fi/network reconnect;
- storage health/enumeration;
- external USB hotplug;
- battery telemetry if available.

---

## 9. Lifecycle/passport projection after a real build

Only after physical evidence exists would the lifecycle layer emit something like:

```text
HS UNIT: DECK-001
revision: R1
state: physically validated prototype

lineage:
- compute: donor A, retained
- cooling: donor A, retained
- display: donor B2 portable display assembly, retained
- keyboard: donor C, modified / retained
- battery: new
- power-path: new
- enclosure: generated

verified capabilities:
- Linux boot
- integrated display
- integrated keyboard
- NVMe storage
- networking
- external USB
- battery operation
- external charging

known limitations:
- no claim of regulatory product certification
- no claim of structural/drop/vibration certification
- thermal evidence applies only to revision R1 and defined workload
- battery life claim valid only for installed battery and R1 configuration
```

A later battery, board, fan or enclosure change creates a new revision rather than silently rewriting the history.

---

## 10. What this example demonstrates about HS

### Current HS genuinely contributes

- machine-level decomposition;
- donor provenance;
- reuse / reject / pending decisions;
- interface contracts;
- unknown-field management;
- requirements and constraints;
- verification planning;
- bounded mechanical fit checks;
- bounded electrical/carrier work;
- evidence capture;
- fail-closed physical authority;
- revision-bound final package.

### Current HS still needs external/human engineering for

- laptop-class USB-C PD / battery power architecture;
- meaningful thermal design before empirical validation;
- rich articulated enclosure and cable-routing CAD;
- novel eDP/PCIe/USB3 signal-integrity work;
- OS/driver edge cases.

### Design verdict

**DECK-001 is feasible as an HS-governed project today, but not as a push-button HS-generated computer.**

The strongest first real build would deliberately choose donor parts with native compatible high-speed interfaces and let HS own the evidence, reuse decisions, low-speed glue, mechanical constraints, bench process and lifecycle package.

That is enough to make Cyberdeck Challenge 002 a legitimate full-machine benchmark without overstating current capability.
