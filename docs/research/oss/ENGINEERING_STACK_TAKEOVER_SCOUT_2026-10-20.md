# Hardware Splicer: source-checked external engineering-stack scouting

2026-10-20, Taiwan/Optiplex. This is a **research and integration
triage**, not a claim that any additional integration was deployed.
The upstream SolidCraft CLI/MCP work is demonstrated separately in
PR #156. This document avoids re-implementing existing HS integrations.

## The architectural question

HS should be a source-backed autonomous engineering investigator and
build coordinator, not a parallel implementation of every specialized
CAD/electronics/repair tool. No existing package discovered here is
demonstrated to convert arbitrary e-waste into a safe working device
without a physical measurement and test environment.

**Core division:**

HS retains canonical donor identity, observations, claims, user
requirements, hardware-interface proof, verified vs hypothetical
contracts, conditional designs and independent release gates.

External packages provide CAD modeling, part/assembly packages, shop
inventory, signal acquisition/decoding, repair datasets and optional
simulation. Tool-specific PASS and a mesh export may not elevate HS
physical authority.

## HS existing capabilities — do NOT buy/rebuild them twice

The actual docs/OSS_INTEGRATION_STATUS.md already lists:

- KiCad 9 CLI/DRC/ERC/fab = core
- KiCanvas = wired browser board view
- tscircuit/circuit-json import and exports = wired
- FreeRouting and tscircuit-autorouter = opt-in
- InteractiveHtmlBom and PcbDraw = wired/best effort
- KiKit, easyeda2kicad, distributor/LCSC = opt-in or partial
- SKiDL netlist ingest, atopile netlist import = wired or partial
- ESPHome stub export = wired (NOT hardware flashed)
- KiCad MCP = documented dev sidecar
- build123d/NopSCADlib = reference only
- SolidCraft via the immediately prior PR #156 now has a genuine CLI
  + MCP CAD handshake, but no embedded GUI or measured physical donor fit.

The parent repo's products have mechanical/bench/inventory UI fragments.
No evidence that the complete frontend can be simply deleted without
replacing those non-CAD workflows.

## Recommended NEW work, ranked by immediate value

| Priority | Repo | Established capability | Proposed adapter | Maturity/readiness evidence | Caution |
| --- | --- | --- | --- | --- | --- |
| 1 | [partcad/partcad](https://github.com/partcad/partcad) | Source-controlled 3D parts, interface metadata, assemblies, parametric/mechanical/electrical BOM, manufacturing/assembly instructions, URDF/MJCF hooks, supply-chain workflow | Export SolidCraft STEP as source-referenced PartCAD part; build HS Verified vs Hypothetical-part package and conditional assembly/BOM | Apache-2.0; upstream release 0.8.220 published 2026-10-18; active developing 0.x project, **not certified fully stable** | Must validate actual pinned CLI on this host; imported STEP alone loses many parametric features and physical provenance must stay with HS |
| 2 | [inventree/InvenTree](https://github.com/inventree/InvenTree) | Mature stock/part/BOM/build records; Django REST API and plugin system | HS donor / salvaged-part inventory adapter with source condition, location, recovered count, test state and actual specimen ID | MIT; mature OSS REST integration, active updates in Oct 2026 | Do not create verified stock records directly from internet marketplace ads |
| 3 | [sigrokproject/sigrok-cli](https://github.com/sigrokproject/sigrok-cli) + [libsigrok](https://github.com/sigrokproject/libsigrok) | Capture, protocol decoding from supported scopes/logic analyzers/multimeters | Read-only device discovery and authorized bounded signal capture; attach raw capture + timestamp/instrument metadata to HS measurement receipts | Released functional project; official GitHub mirrors; supported instruments and protocol decoders listed by sigrok | No matching USB instrument observed on current host. Old released API, GPL; prefer separate subprocess/installed package. Captures require instrument calibration and provenance |
| 4 | [openrepair/data](https://github.com/openrepair/data) | Published community repair outcomes/categories/data schema | Statistical repair priors and failure taxonomy linked to externally retrievable cases | 619,873 records, data through July 2026, repo updated October 2026 | CC BY-SA 4.0 applies to dataset; repair prevalence is not an individual-device diagnosis; data may be aggregated |
| 5 | [OpenBoardView/OpenBoardView](https://github.com/OpenBoardView/OpenBoardView) | Boardview .brd visualization with component labels, nets/pins where source files exist | Open a matched boardview file alongside donor evidence and highlight evidence-backed board pin locations | Established cross-platform viewer, 1000+ commits, 1.8k stars at time of scout | Does NOT infer a PCB netlist from an arbitrary photograph; often no manufacturer boardview file is available |
| 6 | [google-deepmind/mujoco](https://github.com/google-deepmind/mujoco) | Mature multi-joint physics/contact simulation with C/Python APIs | Evaluate provisional joint/motion mechanics exported from verified CAD/PartCAD with explicit mass, friction and actuator assumptions | Apache-2.0 and Google DeepMind maintained, packaged Python wheels | Simulation is only as good as measured geometry/material/load parameters; not evidence of real-world safety |
| 7 | [flashrom/flashrom](https://github.com/flashrom/flashrom) | Flash chip discovery, read, verify and write where supported | Strict READ-FIRST firmware preservation and comparison, never uncontrolled firmware writes | GPL-2.0; official active repo, release tooling | Hardware access and voltage/programmer choices can permanently damage hardware; flash writes gated with independent authorization |
| 8 | [openocd-org/openocd](https://github.com/openocd-org/openocd) | JTAG/SWD debug and target inspection on supported devices | Optional debug probe interface through HS evidence receipts | Widely used mature external debugger | Not installed in current environment; needs supported board/probe; debug/reset/flash writes never run unsupervised |
| 9 | [openpnp/openpnp](https://github.com/openpnp/openpnp) | Stable pick-and-place camera/feed/machine controller and assembly workflow | Long-term production cell integration only once physical machines and verified stop boundaries exist | Project says stable/in wide use; GPL-3.0 | Controls actual motors and tools; high risk; out-of-scope for immediate unattended e-waste trial |
| 10 | [Part-DB/Part-DB-server](https://github.com/Part-DB/Part-DB-server) | Electronic component inventory, KiCad BOM import, datasheet/media, REST API, MCP | Alternate component-specific stock interface if InvenTree proves poorly suited | Active Oct 2026, 1.8k stars, GPL Affero-3.0 | Do NOT duplicate InvenTree unless evidence supports it; AGPL compliance and PHP stack overhead |
| 11 | [adafruit/Adafruit_CircuitPython_Bundle](https://github.com/adafruit/Adafruit_CircuitPython_Bundle) | Hundreds of published supported microcontroller peripheral driver packages | Hardware-identity-gated driver matching, not generic firmware auto-flash | Widely used and updated October 2026 | Existing HS ESPHome/firmware export partly overlaps; license varies by individual library; concrete board/MCU evidence required |
| 12 | [pyserial/pyserial](https://github.com/pyserial/pyserial) | Established cross-platform serial port library | Bounded read-only UART capture with a verified tty ID and explicit port parameters | BSD; lightweight pip install | Does not provide electrical voltage assurance or define safe device-to-host wiring |

## Actual environment and upstream checks

Optiplex verified October 20:
- ngspice is installed.
- kicad-cli is installed.
- docker is installed.
- No sigrok-cli, OpenOCD, flashrom, ROS2 or OpenSCAD command on PATH.
- Previous repo work shows SolidCraft v0.16.2 Linux native executable and
  MCP server really generated a solid STEP/native design.
- Remote git HEAD was resolvable for PartCAD, InvenTree, OpenRepair data,
  sigrok-cli, Part-DB, OpenBoardView, MuJoCo, OpenOCD and flashrom.
- PartCAD release 0.8.220 published 2026-10-18.
- OpenPnP v2.6 released 2026-03-01.
- Open Repair Alliance CSV table schema and CC BY-SA 4.0 grant verified
  directly from the dataset repository.

For complete verification beyond this scout, pin release versions,
verify package checksums, run a minimal tool probe, enforce license
review, inspect runtime permissions and perform independent integration
contract tests.

## Why SolidCraft should be HS's *mechanical* interface

The official SolidCraft release is a strong way to retire HS's own
duplicative 3D workspace, at least in a staged fashion. Its desktop/
web UI, parametric sketch/feature timeline, assembly support and MCP
surface replace much of the need for HS-owned CAD views.

Do NOT immediately delete:
- Donor intake and physical specimen identity records.
- Bench measurements, read-only instrument observations and safety gates.
- Electrical netlists/KiCad and PCB verification.
- Evidence contradiction tracking, repair decisions and release blockers.
- Hardware authorization controls and audit history.

Instead present these through a compact HS sidecar linked to the open
SolidCraft design. Only fork SolidCraft for a native embedded evidence
panel once sidecar interaction proves valuable. Its upstream WASM plugin
design documentation is not proof a native HS plugin is shipped.

## Proposed integration contract between systems

Every cross-app part or test datum should carry:

- HS case_id, donor_specimen_id (nullable for unpurchased listings).
- Vendor/model/revision and original source reference IDs.
- Physical-identity and instrument-attestation status.
- PartCAD package and source revision, optional SolidCraft document
  and feature ID, and InvenTree stock-part ID only if actual inventory
  exists.
- Partial electrical/mechanical/firmware interface contracts, units,
  tolerances and responsible test instrument.
- Test method and raw observation evidence (never only success=true).
- Current authority ceiling: HYPOTHESIS, DOC_SUPPORTED, OBSERVED,
  MEASURED_AND_CHECKED, or RELEASE_APPROVED by separate gate.

No external tool may infer a MEASURED_AND_CHECKED or RELEASE_APPROVED
status from a model, seller listing, stock database, simulator result
or self-reported test pass.

## Minimum pilot sequence and stop rules

**Pilot A: SolidCraft -> PartCAD (best immediate next experiment).**
Create a separate, attributed component/package with the explicitly
declared 120x80x25 mm test envelope from PR #156; link native SolidCraft
design, exported STEP and declared dimensions; create an assembly/BOM
with one hypothetical component; then reimport and check exact IDs,
units, geometry and source-hash continuity. No purchased donor is needed.
Fail if geometry is silently scaled, units are lost or stock is invented.

**Pilot B: InvenTree actual vs hypothetical donor distinction.**
Create synthetic/unverified inventory entries in a disposable test
database only, then show that advertised listings cannot become
available_stock or physically verified quantity without a unique intake
observation. Fail on trust-boundary promotion.

**Pilot C: Repair evidence intake.**
Import OpenRepair dataset category schema/summary into repair hypotheses,
then add sigrok offline capture replay when a safe public capture dataset
is available. Real bench proof remains open until an authorized
instrument is attached. Fail if population-level repair rates are
reported as specific specimen measurements.

**Pilot D: MuJoCo motion design.**
Only after actual verified dimensions/geometry and actuator contracts
exist; otherwise generate a clearly conditional simulation with wide
parameter bounds, not a safety claim.

**Deferred:** OpenPnP live motion, flashrom write, OpenOCD flash/reset,
unsupervised power-on, soldering/fabrication or physical actuators.

## Technical and licensing integration guidance

Pin versions. Prefer cross-process CLI/MCP/REST bridges to wholesale
vendoring of mature upstream code. Preserve original attribution and
consult each source's current LICENSE. InvenTree MIT, PartCAD
Apache-2.0, MuJoCo Apache-2.0, flashrom GPL-2.0, OpenPnP GPL-3.0,
Part-DB AGPL-3.0 and OpenRepair data CC BY-SA 4.0 have meaningfully
different obligations. Individual bundled microcontroller driver
libraries may have separate licenses.

This is a feasibility and prioritization study. **No new external
engine was installed or integrated by this scout.** The only real
native 3D CLI/MCP runtime verified so far is SolidCraft in PR #156.
