# Small AI hardware tools: references and benchmark candidates (25 Nov 2026)

These are small, published products that turn a plain-language idea into a hardware build (wiring, parts list, firmware, sometimes a PCB or a robot kit). They are the tools a maker would try instead of HS, so they set the bar HS has to clear. Everything below comes from the products' own pages and GitHub on 25 Nov 2026. No tool was run, and none of their claims was tested.

**Common pattern.** Every one of them generates. A few check that the firmware compiles or that pins exist on the board. None publishes how often its designs are right.

## Prompt to wiring, parts and firmware (Arduino, ESP32, Pico)

| Tool | Maker | Output | What it says it checks | Open/price | Evidence it is real |
|---|---|---|---|---|---|
| [Schematik](https://www.schematik.io/) | Schematik (Amsterdam), founder Sam Beek | Code, wiring, pin assignments, assembly steps, browser simulator, web flasher, desktop app, MCP server | Compiles and flashes; no design checks stated | Closed; pricing not shown | $4.6M pre-seed led by Lightspeed (its own company page); press in WIRED; updated 3 Nov 2026 |
| [Banana Board](https://bananaboard.app/ai-circuit-generator) | not stated | Firmware, wiring and pin map, parts list with distributor links, routed 2-layer PCB, Gerbers or KiCad | "validates every connection against the board's real pin map"; ERC; power budget; compiles with arduino-cli | Closed; free tier, paid price not shown | Live sign-up; demo board only |
| [sensbench AI Project Builder](https://sensbench.com/ai-project-builder/) | sensbench (a parts shop) | Parts list from its own stock, pin-by-pin wiring table, Arduino firmware | "Compile Verified" badge on the real arduino-esp32 toolchain; says it does not check behaviour | Closed; 1 free build a day, credit packs | Beta |
| [Tinkered](https://www.tinkered.ai/) | not stated | Schematic, PCB with fab files, firmware, printable enclosure, 3D simulator | "Checked against physics before it's built"; firmware run on an emulated chip; heat and tolerance checks shown | Closed; free to start | Claims "350K+ builders" (no source) |
| [Schemr](https://schemr.space/) | not stated | Parts list with prices, wiring, 3D layout, starter firmware, build guide; also CNC, SCARA arms, drones, rovers | "validated for power budget, GPIO assignment and electrical safety", plus a build-confidence score (method not described) | Closed; 1 free generation | Pricing page empty |
| [JotWare](https://jotware.vercel.app/) | "SHAJ" | Firmware, wiring, connection table, parts list (live prices on Pro), build guide; 10 boards | "checks your design for mistakes" (checks not listed) | Closed; free 3 a month, Pro $12 a month | Beta; homepage counters read "0 boards" |
| [Cirkit Designer](https://www.cirkitdesigner.com/) | Cirkit Design LLC | Wiring diagram, AI-written code, firmware simulation, flashing | No checks stated | Closed; free to start | Live web app |
| [Circuit Forge](https://uas-forge.com/circuit-forge/) | Midwest Nice UAS LLC | Prompt to output (format not shown); drone parts matched to its own catalogue with prices | "ERC VALIDATED"; "canonical pinouts" | Closed; bring your own API key | Output panel and cost page empty |
| [Blueprint](https://www.blueprint.io/) | 3E8 Robotics (per directory listings) | Wiring diagrams, parts list, assembly guides (per directory listings) | Not stated | Not stated | Site renders only its title |
| TronicsAI | not stated | Schematic, live simulation, firmware for 16 boards (search listing only) | Not stated | Not stated | Site renders only its title |

## Open source, runnable locally (can be benchmarked directly)

| Tool | Licence | Stars, activity | Output | Checks |
|---|---|---|---|---|
| [WireStudio](https://github.com/moellere/WireStudio) | MIT | 29, active | One design file to ESPHome/Tasmota/WLED and other firmware, KiCad, JLCPCB bundle, enclosure | Pin solver and validator (strapping, ADC2, voltage). Already absorbed into HS. |
| [esp-labs](https://github.com/agharsallah/esp-labs-web) | MIT | 1,003, active | ESP32-S3 lessons with simulators and an honest per-lab status | Lab status from real hardware. Already absorbed into HS. |
| [Circuitiny](https://github.com/mfranzon/circuitiny) | MIT | 56, last push May 2026 | 3D wiring, agent-written firmware, simulation; Claude, OpenAI or local Ollama | Runs DRC; simulates firmware before hardware |
| [boardsmith](https://github.com/ForestHubAI/boardsmith) | AGPL-3.0 | 38, one push (Mar 2026) | Prompt to KiCad schematic, parts list, firmware | "computed values" |

## Robots

| Tool | Maker | What it is | Checks | Status |
|---|---|---|---|---|
| [Tnkr](https://tnkr.ai/) | Tnkr AI (CEO Seun Akinbode) | Hosting and sharing for robot projects (CAD, parts lists, wiring, firmware, models), an AI agent builder and a teleoperation data marketplace. Hosts SO-101, Open Duck Mini, XLeRobot, Aero Hand. | Only "is it connected" checks in its desktop app; no design checks | Live; free public projects, Pro $20 a month |
| [Orcamaker](https://orcamaker.com/) | Soohoo Robotics (Spencer Soohoo) | Robot kits with a validated parts list, wiring diagram, power budget and architecture | "Human-validated … every point checked on reference hardware"; power budget and motor-driver headroom marked verified | Pre-order; checkout link is a placeholder |
| [BuildRobot.ai](https://www.buildrobot.ai/) | not stated | Robot description to parts list, Gerbers, firmware, assembly and test procedures | "100% engineer-reviewed before delivery"; claims "7 days" to a hardware package and "6x faster" (no method given) | Page has unrendered template text; changelog link goes nowhere |
| [Vanika](https://vanika.ai/) | Vanika.ai | "Engineering intelligence platform" for robots and drones | Links tests and simulation results to decisions (roadmap) | Private beta; most features marked planned |

Also seen: [ESP-Mosaico](https://www.producthunt.com/products/esp-mosaico) (an ESP32-S31 modular board built for AI coding agents; hardware, not a design tool), and TechBench (an electronics repair app with a camera board scanner; its listing could not be read).

## What this means for HS

1. **None of them publishes accuracy.** The strongest checks on offer are "it compiles" (Schematik, Banana Board, sensbench), "every pin exists on the board" (Banana Board, Circuit Forge) and an unspecified power budget (Banana Board, Schemr, Orcamaker). HS's measured benchmark (`examples/schematic_bug_benchmark/`) and its cited engineering checks remain the differentiator, but only if HS can show the others getting things wrong.
2. **The bar to clear is the brief, not the schematic.** A user of these tools types a project idea and gets a build. The fair comparison is the same brief in every tool, with the output graded on known traps:
   - 5 V logic into a 3.3 V pin (HC-SR04 echo, WS2812 data);
   - a strapping or boot pin used for a sensor;
   - missing I2C pull-ups;
   - a supply too small for servo stall or motor current;
   - battery runtime;
   - a missing USB-C CC pull-down.
3. **Orcamaker's published Room-Nav numbers are a small worked case.** It quotes 2.1 h runtime from a 5.2 Ah 11.1 V pack at 18 W peak and 14 W average. That holds only with roughly 80% depth of discharge and about 80% converter efficiency at peak load, and the page states neither. HS's runtime model makes that assumption explicit.
4. **Robots are a separate track.** Tnkr's projects are off-the-shelf builds (bus servos, adapter boards, a Pi or Jetson) with no KiCad files, except Aero Hand. The test there is HS's wiring and power checks against the problems builders report on GitHub (brownouts, servo resets).

## Mechanisms in 3D: AnyMachine

[AnyMachine](https://github.com/apekshik/anymachine) (MIT, 1,205 stars, created 4 Nov 2026, by Apekshik Panigrahi) has an AI agent (Claude in Claude Code) build moving machines in Blender with a person approving each stage. Its sister projects are AnyScene, AnyKit and AnyShot; anymachine.ai is only a "coming soon" page.

Its outputs are game and film assets, not engineering: the "hydraulics" are animation, with no masses, forces, materials or electronics.

What is worth taking, all of it MIT:

1. **Range-of-motion clash sweep.** Every joint becomes a 0-1 control with limits. Each control, and listed pairs of controls, is swept in small steps, and the sweep reports overlapping triangles, penetration depth and minimum clearance. Parts that touch by design (a strap on fabric) pass if they penetrate no more than a set tolerance. Reported results: laptop lid 0 overlaps over 0-135°, minimum clearance 0.32 mm; quadruped 0 overlaps and 0.014 mm foot slip.
2. **Export round trip.** The GLB is re-imported and checked against the Blender pose.
3. **Reference beside model.** Every stage is rendered next to its reference image, with a second pass where the model came out plainer, and a per-experiment status that says plainly what only partly works.

HS already measures static interference (`scene_fit.py`) and imports URDF/SDF/MJCF joints (`robot_model_import.py`), but it never moves the joints. Combining the two gives the missing check: sweep each joint of a robot's own model through its limits and report clashes and minimum clearance. SO-101, Open Duck Mini and other Tnkr-hosted robots publish URDFs, and FieldDeck's clamshell lid and the pan-tilt head are the same problem.

## Small open-source agent projects on the physical side (GitHub sweep, 26 Nov 2026)

The sweep ran 42 GitHub searches for repositories created in 2026 and found 491; about 150 are on the physical side. Excluded:
- eight near-identical `blender-ai-copilot-*` repositories, all created 12 Nov 2026 by throwaway-looking accounts with about 500 stars each, which looks like star farming;
- ESP32 desk gadgets that display Claude usage.

Stars, licences and dates are from the GitHub API on 26 Nov 2026. The descriptions come from each project's README; nothing was run.

**Whole things from a sentence, with gates (closest to HS):**

| Project | Licence, stars | What it does | What it checks |
|---|---|---|---|
| [Formwright](https://github.com/Romanok2805/formwright) (Axo) | not stated, 27; built 27 Oct-4 Nov 2026 for a Meta hackathon; [live app](https://formwright.axo.kz) | Sentence, photo, caliper readings or voice to a device: real LCSC parts wired in a node editor, a placed and routed board, a printed case, firmware, then an order; also spare parts | Electrical and design rules; the firmware runs against its own circuit on a virtual board; each printed part passes a slicer-like check and an independent critic; dimensions come from measurement, standards and specs; "done" is refused until the checks pass |
| [claude-hardware-in-the-loop](https://github.com/Kemerd/claude-hardware-in-the-loop), now [Nihil.sh](https://nihil.sh) | not stated, 98 | Boards written as Python scripts and generated into KiCad, plus CAD and firmware, under a Claude Code skill | ERC and DRC at KiCad defaults; a live distributor check of every part (it caught an 0603 part sold under a code assumed to be 0402); a "no-shortcut" audit that fails on stubs and admitted guesses; it says green gates are not an engineer's review |
| [Replicator](https://github.com/T-Crypt/replicator) | MIT, 25 | Sentence to a validated build program on the manifold3d kernel: buildings, boards, machines (involute gears, nozzles); exports STEP, URDF, MJCF and Blender | Thirteen measured checks (floating or loose parts, missing planned parts, whether it stands); mass and centre of gravity; a MuJoCo check; Reverse mode keeps a ledger of what was measured, inferred or unknown |
| [Cadex](https://github.com/ayutaz/cadex) | LGPL-2.1, 0; 0.2.0 pre-release | Headless CAD engine for robots and mechanisms driven by your agent: exact OCCT geometry, renders, exports, MuJoCo simulation, trained control policies | Checks geometry and verifies trained policies before playing them |
| [machine-cad-agent](https://github.com/dylanstechmann/machine-cad-agent) | MIT, 0 | Mechanical CAD an agent can edit, measure and inspect with a vision model; a humanoid concept with a full motion storyboard | Measurement and vision inspection; the author says it is a digital concept only |

**Agent-written mechanical CAD:**
- [text-to-cad](https://github.com/earthtojake/text-to-cad) (MIT, 27,435 stars, [texttocad.dev](https://www.texttocad.dev)): the agent writes a Python model, the `cad` command builds it, a viewer shows it; installs into 20+ agent apps.
- [SOMA](https://github.com/Kai-Jungsthoefel/SOMA) (GPL-3.0, 564): a CadQuery desktop app for makers' cases and brackets.
- [AgentSCAD](https://github.com/Kevoyuan/AgentSCAD) (MIT, 26):
  - writes OpenSCAD and checks manifoldness, wall thickness, bounds, hole connectivity and clearance with code rather than a model;
  - asks when a request has two readings;
  - keeps "delivered" separate from "accepted".
- [Prompt2Product](https://github.com/atechdotdev/prompt-to-product) (GPL-3.0, 33, by Atech): FreeCAD; sizes and volumes are measured off the solid; it knows its maker's own boards for enclosures.
- [Varen CAD](https://github.com/vanyu0710/Varen-AI-CAD) (66, closed beta):
  - the BOM plan needs approval before modelling;
  - a result does not count as delivered unless the geometry and collision checks pass;
  - it published gearboxes with 0 hard collisions;
  - the source was withdrawn in Oct 2026, and older AGPL forks exist.
- [mesh2cad](https://github.com/emirmrkaljevic/mesh2cad) (MIT, 153, covered by Hackaday): STL to parametric STEP, CadQuery or OpenSCAD, with the deviation reported.

**Electronics, firmware and review skills:**
- [pcb-skill](https://github.com/daishuge/pcb-skill) (MIT, 191):
  - takes an idea to an orderable board through EasyEDA Pro, stopping at the payment page;
  - its gates each come from a real board failure, such as a socket rotated so the display cannot plug in, a capacitor under a module, or a keep-out drawn on the wrong layer; see its case study.
- [agentic-hil](https://github.com/agentic-hil/agentic-hil) (Apache-2.0, 33): the agent develops firmware on a real board, which acts as the gate.
- [claude-code-eyes](https://github.com/fcavalcantirj/claude-code-eyes) (MIT, 52): a camera skill so the agent checks the real display and wiring.
- [datasheet-cli](https://github.com/akiselev/datasheet-cli) (GPL-3.0, 32): datasheet PDF to JSON pinouts and footprints, with Mouser, DigiKey and JLCPCB search.
- [Mechanical-AI-Skill](https://github.com/almightyshui/Mechanical-AI-Skill) (MIT, 34): engineering review of a STEP assembly (risks, DFM, DFA); the mechanical counterpart of HS's schematic review.
- [claude-for-hardware](https://github.com/LilithSemi/claude-for-hardware) (Apache-2.0, 26): HDL, FPGA and SoC bring-up skills.

**Robots:**
- [robium](https://github.com/robium-ai/robium) (MIT, 111): robotics skills and runnable reference robots for coding agents.
- [Hebbian RUA](https://github.com/Hebbian-Robotics/rua) (MIT, 123): an LLM observes and acts through a real arm.

**A published benchmark:** [PCB-Bench](https://github.com/digailab/PCB-Bench) (ICLR 2026, no licence): about 3,700 PCB placement and routing questions, plus layout tasks, for grading language models. It tests layout knowledge, not schematic checking.

### What HS should take

Only MIT, Apache or BSD code can be copied into HS; for GPL, AGPL, LGPL and unlicensed projects take the idea only.

1. **Gates that refuse "done".** Formwright and Nihil will not accept the agent's word that something is finished:
   - the firmware has to run against its own circuit;
   - every part has to resolve at a distributor to the package that was assumed;
   - stubs and guesses fail the build.
   HS has the authority rules but not the distributor-resolution gate or the firmware-on-circuit gate.
2. **A real-failure rule list.** pcb-skill's gates (rotated socket, part under a module, keep-out on a drawing layer) are layout bugs HS does not check yet and are candidate benchmark cases.
3. **Measured mechanical checks.**
   - From AgentSCAD and Replicator: wall thickness, clearance, floating or loose parts, whether it stands, mass and centre of gravity.
   - From AnyMachine and Cadex: a joint-range sweep.
   HS's `scene_fit.py` covers static clearance only.
4. **One evidence ledger.** Replicator's measured, inferred and unknown, and AgentSCAD's delivered versus accepted, match HS's authority states. Using the same words would make HS easier to compare.
5. **Same-brief benchmark.** Formwright's live app, Replicator, AgentSCAD and text-to-cad can take the same briefs as the hosted tools above, graded on the same traps.
