# Hardware Splicer — full-stack engineering ecosystem freeze

**Frozen:** 2026-10-27 (Asia/Taipei)
**Freeze class:** research and decision baseline, **not** a runtime dependency pin, product claim or integration approval.
**Scope:** Electrical/PCB; parametric and generative 3D; mechanical mechanisms; embedded firmware/HIL; physical simulation, materials and chemical properties; robotics and motion; fabrication agents and machine interfaces; model orchestration.
**Policy:** Prefer reusing interoperable specialist tools, then validate on actual HS artifacts. Do not clone another CAD, EDA, FEM, firmware or printer stack without a measured unmet need.

## Executive decision

HS's intended differentiator is **cross-domain engineering orchestration and evidence**: a shared design revision binds electronics, firmware, mechanical geometry, real materials, toolpaths, machine profile and observed physical results. The individual engines need not be written in HS. Today this is a *target architecture*, not an end-to-end demonstrated product.

Separate five authority levels:

1. **Candidate:** natural-language/model suggestion, sketch, mesh, topology or generated code.
2. **Compiler/static validated:** actual CAD/EDA/firmware artifacts compile and format/net/fit checks pass.
3. **Model tested:** reproducible, correctly parameterized simulator/FEA/CFD/control results, with applicability limits.
4. **Manufacturing prepared:** exact fab package, qualified parts/material/profile, verified device capabilities and operator-approved job.
5. **Physically validated:** independent bench/measurement/inspection records for the exact built revision. Software tests never imply level 5.

No model leaderboard, vendor screenshot, generated STL, electrical SPICE run or printer API response may be substituted for level 5.

## Frozen landscape matrix

| Discipline | Reusable tools / candidate systems | Established capability and target HS role | Maturity / warning | Integration priority |
|---|---|---|---|---|
| Electrical design | KiCad CLI, SKiDL, atopile, tscircuit, KiCad MCP/EDA agents | Native schematic/PCB/netlist sources and edit/verification loops; expand existing HS adapters | Exact KiCad version, symbol/pin identity, component values, real ERC/DRC, footprint/net parity required | **P0** |
| PCB layout + fab | KiCad ERC/DRC/exports, FreeRouting, tscircuit autorouter, KiBot, LCSC/JLC tools | Reuse existing bridges instead of inventing copper router; authoritative fab outputs | Router success != manufacturability; source licenses & services vary | **P0/P1** |
| AI model coding/engineering | Kimi K3.1 Pro, Claude, GPT, Gemini in agent harnesses | Parameterized CAD/EDA/firmware code and design-repair agents | Kimi released Oct 2026; Moonshot BenchCAD is vendor-reported; test same harness, tasks and run budgets; hosted access ≠ local weights | **P0 benchmark** |
| Parametric CAD | text-to-cad, agentcad, CadQuery/build123d, FreeCAD; newer SOMA/SolidCraft/Procedura | Editable STEP-based solids, dimensioned assemblies, feature/script history | Early agent apps need reproducible geometry/exports/actual tolerance validation; some license terms not audited | **P0/P1** |
| Visual/model 3D | Meshy/Tripo/Seed3D/TRELLIS.2/Hunyuan | Reference reconstruction, concepts and irregular enclosure surfaces | Mesh realism ≠ engineering CAD; provenance, dimensions and topology remain unverified | **P2** |
| Mechanical design | Existing Mecha Splicer, FreeCAD assembly and FEM, text-to-cad DfAM/DFM, CAD-agent | Hinges, brackets, bearings, joints, fits, DFM and editable assemblies | Printability heuristics ≠ strength, lifetime or measured fit | **P0** |
| Structural mechanics | FreeCAD FEM + CalculiX; Elmer, MOOSE for heavier multiphysics | Stress, deformation, thermal-structural, contact/loads, sensitivity | Inputs, loads, mesh independence, constitutive/material data and real tests essential; don't over-claim solver validity | **P1** |
| Thermal/fluids/electromagnetics | Elmer FEM, OpenFOAM, MOOSE; domain-specific solvers | Enclosure heat, heatsinks, airflow, board/module thermals, coupled effects | Full simulation expensive; start with analytical/low-order screens and accepted solver examples | **P1/P2** |
| Chemistry/materials | thermo (ChEDL), pymatgen, PyBaMM | Source-grounded density, conductivity, heat capacity, expansion/chemical properties, battery models | Property at given T/P/phase not universal or always experimentally measured; do not extrapolate beyond validity | **P1** |
| Firmware authoring | PlatformIO, ESP-IDF, Zephyr, ESPHome, Renode/Wokwi where supported | Compile + pin/driver contracts + emulation/firmware tests; enhance existing HS scaffold | Compiler pass != hardware behavior, incompatible GPIO or power safety | **P0** |
| Agentic firmware/HIL | agentic-hil, Firment, Boardex, esp-agentic-dev, TuyaOpen IDE, Zephyr Workbench | Agent build→flash→observe→repair with bounded probe/UART/CAN/logic-analyzer receipts | Emerging tool maturity varies; *flash only within trusted board authorization* | **P0 targeted spike** |
| Robotic dynamics/control | MuJoCo, Gazebo, ROS 2 / ros2_control, MoveIt 2, LeRobot; Isaac Sim/Lab if GPU resources | Kinematics, contact, actuators, control simulation and guarded real-device I/O | Simulation ≠ real stability; GPU/system requirements vary; robotics broadening after basic hardware case | **P1/P2** |
| Manufacturing desktop agents | Kiln, OctoPrint/Moonraker, PrusaSlicer/OrcaSlicer, CAD→G-code | Reuse fleet/device adapters, slicer profiles, job monitoring; benchmark Kiln instead of proliferating bespoke drivers | Kiln AGPL-3.0; advertised coverage ≠ actual individual printer acceptance; never silently allow agent start | **P1** |
| Cross-domain hardware agents | vibe-hardware, Form/Form-OSS, next.BREP/openIE CAD, experimental Kerf | Potential PLM/parts/geometry/electrical/firmware joins | Some are early or broad claims; audit code, license, output files and runnable demos before adoption | **P0 comparative audit** |

## Findings by discipline

### Electrical and PCB — preserve existing integration before expanding

Current HS repo already includes `src/hardware_splicer/backends/tscircuit.py`, Circuit JSON intake, `freerouting_bridge.py`, `spice_runner.py`, KiCad CLI verification and documentation for optional KiCad MCP and atopile ingest. `docs/CIRCUIT_LOGIC_AUDIT.md` accurately calls its synthesis *bounded*, not arbitrary. Work to close is **real new schematic authorship** from a candidate and complete native-layout feedback, with independent simulation, selection of real parts, ERC/DRC, net parity and manufacturable BOM.

- atopile: https://github.com/atopile/atopile
- tscircuit: https://github.com/tscircuit/tscircuit
- KiCad: https://www.kicad.org/
- FreeRouting: https://github.com/freerouting/freerouting
- SKiDL: https://github.com/devbisme/skidl

### Mechanical and 3D — two distinct lanes

**Engineering geometry** is parametric CAD, assembly constraints and edit history (FreeCAD, CadQuery/build123d, text-to-cad, agentcad). New tools such as SOMA, SolidCraft and Procedura may help but require reproducible evaluation. **Generative meshes** (Meshy, Tripo, TRELLIS.2, Hunyuan, etc.) are candidates for shapes and reconstruction, not by themselves tolerance-controlled manufactured parts.

Existing `apps/mecha-splicer/docs/STATUS.md` explicitly lists OpenSCAD, fit/DFM heuristics, brackets and several mechanism primitives, but real CAD kernel/STEP and geometry validation are still missing. Existing `apps/3d-splicer` should remain reusable, not be replaced without a matched benchmark.

- text-to-cad: https://github.com/earthtojake/text-to-cad — parametric CAD, DfAM/DFM, STEP parts, printer toolpath skills.
- agentcad: https://agentcad.dev/ — build123d-based CLI/MCP CAD.
- CAD agent: https://github.com/bloodreaper005/cad-agent — published-standards sizing and FreeCAD checks; early.
- Procedura: https://github.com/SpatiaOS/Procedura
- FreeCAD FEM: https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/FEM_Workbench.md

### Firmware — stronger opportunities than another code generator

HS currently has a deterministic `device_firmware.py` and `firmware_scaffold.py`, PlatformIO compile-only verification, a pin/wire proposal with strict authorization boundaries, and `docs/DEVICE_FIRMWARE.md`. That is valuable but not a general real-hardware agent.

New HIL candidates can offer a genuine **compile → flash under operator policy → UART/CAN/logic-analyzer/debug → correct** loop.

- Agentic HIL: https://github.com/agentic-hil/agentic-hil — Apache-2.0, local bounded MCP, OpenOCD/pyOCD/STM32 support; claims first real-board example.
- Firment: https://github.com/MoRiv447/Firment — embedded-focused Rust coding agent, on-board observation and partially executed 2026 HIL benchmark. Check incomplete tests and platform constraints.
- Boardex: https://github.com/ankayca/boardex — early firmware/logic analyzer agent with an approval gate.
- ESP JTAG agent loop: https://github.com/ccattuto/esp-agentic-dev — ESP32-specific debug/flash/inspect.
- TuyaOpen: https://tuyaopen.ai/ — cross-chip AI/IoT tooling, firmware + cloud/app toolchain; review supported targets and cloud dependencies.
- Zephyr Workbench HIL tutorial: https://z-workbench.com/docs/tutorials/ai-agent-hardware-in-the-loop/

**Best first firmware proof:** HS supplies a pinned ESP32 design and produces firmware with GPIO/timing contract, compiles it, measures PWM/I2C over a real probe, and distinguishes host mocks from real measurements. Do not expose unrestricted flashing to an agent.

### Physical simulation / structural / materials / chemistry

These should be legitimate **independent discipline gates**, not another AI-generated confidence score.

- FreeCAD FEM with external CalculiX: https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/FEM_Install.md
- Elmer FEM (stress, heat, fluids and EM): https://github.com/ElmerCSC/elmerfem
- MOOSE multiphysics: https://github.com/idaholab/moose
- `thermo` chemical/T/P dependent properties: https://github.com/CalebBell/thermo
- `pymatgen` materials and structure analysis: https://github.com/materialsproject/pymatgen
- `PyBaMM` electrochemical battery models: https://github.com/pybamm-team/PyBaMM

Example: if HS designs a printed motor bracket, it must declare material, process anisotropy, loads, boundary conditions, minimum wall, mating tolerances and mounting geometry; then run independent fit checks and an appropriate structural model **only when input quality supports it**. Validation still requires a physical loaded coupon/part when failure matters. For an electronics enclosure, add measured dissipation, ventilation and temperature boundaries, rather than assuming a mesh is thermally safe.

### Robotics, actuation and motion

HS already has `robotics_simulation.py` and `docs/ROBOTICS_SCALING_BENCHMARK.md`. The latter explicitly benchmarks structural representation and **not** real robot simulation or actuation. Avoid labeling an estimated speed or torque budget as validated dynamics.

- MuJoCo: https://github.com/google-deepmind/mujoco — dynamic/contact physics; version **3.17.0 released Oct 22, 2026**. Pin version for repeatability.
- ROS 2 hardware control: https://github.com/ros-controls/ros2_control
- MoveIt 2: https://github.com/moveit/moveit2
- LeRobot: https://github.com/huggingface/lerobot
- Isaac Sim: https://developer.nvidia.com/isaac/sim — heavier GPU/software requirements.
- Real-machine motion always needs device-resident safety limits, homing and stop behavior; LLM does not control a real-time servo loop.

### Manufacturing agents and cross-discipline products

- Kiln: https://github.com/codeofaxel/Kiln — cross-brand agent-facing slicing/fleet control, claims numerous machine protocols; **AGPL-3.0** and some paid closed capabilities. First evaluate external interoperability rather than embedding/redistributing source.
- vibe-hardware: https://github.com/luckiday/vibe-hardware — plain-English firmware + KiCad + enclosure + fabrication-agent skills, includes shared product/fit-number manifest; explicitly early and its flagship custom PCB/enclosure are still stubs.
- Form / Form-OSS: https://github.com/caid-technologies/Form-OSS — early unified designs, model previews, BOM, wiring and assembly; license and accuracy checks required.
- agent-wide CAD/physical suites: https://github.com/vul-os/kerf and https://github.com/ai-cad-labs — broad self-reported feature sets, treat as **discovery candidates**, not proven engines.
- See existing HS `apps/mecha-splicer`, `apps/3d-splicer`, `hardware_splicer/firmware_scaffold.py` and cross-discipline contract guidance before adopting overlapping platforms.

## Model claims at freeze time

Kimi K3.1 Pro is real and available via hosted Kimi surfaces as of October 2026. Official model blog: https://www.kimi.ai/blog/kimi-k3-1-pro. Full weights *promised* by Nov 4, 2026 (future as of freeze). Its BenchCAD performance is **Moonshot-reported and benchmark-specific**. No Kimi result proves physical safety, native KiCad electrical correctness, FEA accuracy or manufacturing reliability. Evaluate Kimi/Claude/GPT/Gemini on **identical HS design tasks** and **same CAD/EDA/HIL harness and limits**. Do not rank by unrelated benchmark numbers.

## HS freeze: existing vs missing vs unmerged

**Verified by repository review** at freeze:

- Electrical: bounded synthesis, imported netlists and real KiCad/DRC/PCB bridges exist; arbitrary native design generation remains incomplete.
- Mechanical: OpenSCAD, templates, assembly/mate metadata and heuristics exist; real validated STEP/parametric kernel and load/fit proof are incomplete.
- Firmware: deterministic ESP32 proposals and compile-only PlatformIO path exist; onboard HIL feedback not generally deployed.
- Robotics: engineering-envelope checks exist; not independent dynamics/physical robot completion.
- Manufacturing: PR #225 creates an OctoPrint stage-only adapter and CAD→slicer pipeline (GitHub workflows passed); PR #226 expands fleet/Moonraker as draft; no physical print validation or universal driver coverage.
- Build challenge: PR #224 is draft with a topology-only candidate and a **CI-blocking Python SyntaxError** in `scripts/generate_hs_build_candidate_001.py` (`reference_design_reused` literal escaped newline). Fix separately before interpreting its hardware gate; its failing CI is a *syntax/collection defect*, not an electrical failure.

**None of PRs #224/#225/#226 were merged as of freeze**. An open draft branch is not a product feature on main.

## Frozen priorities — no further implementation before evaluation

| Step | Test | Success evidence | Fallback |
|---|---|---|---|
| **0. Repair baseline** | Fix #224 syntax, re-run strict CI; check #225/#226 PR stack | Green targeted/full suites; accurate feature claims | Keep draft and block promotion |
| **1. Cross-domain identity** | One pinned board + enclosure + firmware shared revision | Exact connector/PCB geometry/pinout/fastener/material tied across artifacts | Explicit mismatch finding |
| **2. EE agent benchmark** | atopile/tscircuit/KiCad native generation on 24→5 V 0.5 A fixture | Native `.kicad_sch`, PCB, real BOM, simulation checks, net parity, ERC/DRC | Bounded design-review product only |
| **3. Mechanical benchmark** | Hinged enclosure from same PCB dimensions; model Kimi/text-to-cad vs HS | Editability, STEP+assembly, measured holes/tolerances, mesh validation, appropriate loads | Degrade to static enclosure advice |
| **4. Firmware benchmark** | Pinned ESP32 I2C/PWM fixture with policy-gated HIL | Compile logs plus actual probe/UART/logic captures and exact firmware hash | Compile-only authority |
| **5. Multiphysics** | Thermal dissipation + bracket strain for exact case | Solver input, mesh/refinement and defensible property ranges; results distinguished from empirical | Analytical screen with explicit uncertainty |
| **6. Manufacturing** | Supervised small low-risk part and low-voltage PCB case | Profile-bound toolpath, local approval, telemetry, finished part inspection, bench measurements | No auto-start or fabricated claim |
| **7. Reevaluate external agents** | Kiln, vibe-hardware, Form and others on same files/tests | Consistent artifacts, license/ops/security review, measured effort saved | Continue minimal local bridges |

### Go / no-go questions for every external integration

1. Can it accept and return our source artifacts without destroying references and editability?
2. Does it produce independently checkable engineering data, not just a plausible render?
3. Can a mismatched connector, wrong pin voltage, collision, invalid mesh, bad print profile and unsafe actuator state cause a reproducible failure?
4. Can we pin version/model/source, record input and output hashes, and reproduce results offline or with a stable service contract?
5. Does its license permit the specific distribution and deployment we intend?
6. Does it respect local approval for flashing, power, heating, printing, motion and external fabrication orders?
7. Does it improve our actual success rate or developer time vs current HS with the same acceptance test?

## Freeze maintenance

Treat this file as **immutable dated evidence**, not a live catalog. For subsequent breakthroughs, create a new dated delta (e.g. `HS_ENGINEERING_LANDSCAPE_DELTA_YYYYMMDD.md`), link here and cite exact upstream release/commit and benchmark artifacts. Do not silently rewrite old rankings or promote claims without observed tests.

**What is frozen:** research choices, current HS limits, evaluation tasks, primary source pointers and success criteria. **What is not frozen:** dependency versions, API surface compatibility, license interpretation or proven physical operation. Those all need independent checks at implementation time.
