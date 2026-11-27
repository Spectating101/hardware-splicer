# Leads from Cite-Refinery's atlas for Hardware Splicer (28 Nov 2026)

Cite-Refinery's atlas maps about 4,900 open-source products from the Signals feed to what each one does, takes and
gives. Of those, 172 match HS's hardware topics; 169 were new to HS's landscape register, which now reads the atlas every
week (`landscape_watch.atlas`). These are the ones that change something in HS. Licences were read from GitHub on
28 Nov 2026; "none" means HS may read and cite the project but not copy its files.

| Project | Licence | What it is | What HS does with it |
|---|---|---|---|
| [schlae/cm5-reveng](https://github.com/schlae/cm5-reveng) (1.1k stars) | none | Reverse-engineered KiCad schematic and layout of the Raspberry Pi CM5, with its PMIC, DDR, RP1 and Wi-Fi module; "not meant to be fabricated" | Reference for HS's CM5 carrier work (which pins are which rail) and for salvage: the author notes a dead CM5's PMIC can be reused over I2C. Read and cite only |
| [Adam-CAD/CADAM](https://github.com/Adam-CAD/CADAM) (5.5k) | GPL-3.0 | Text and image to parametric OpenSCAD | Compare against HS's CadQuery generation on the same briefs; may run as a separate program, code not copied |
| [ForgeCAD/forgecad-public-kit](https://github.com/ForgeCAD/forgecad-public-kit) (956) | MIT | MCP server for agents to author simulation-ready CAD | Candidate outside CAD tool, like Copper for routing |
| [Sandflow-ai/sand3d](https://github.com/Sandflow-ai/sand3d) (2.4k) | Apache-2.0 | Deterministic Python 3D modelling over Blender, built for LLMs | Compare with CadQuery for agent-written parts |
| [ferdous-alam/GenCAD](https://github.com/ferdous-alam/GenCAD) (3.9k) | none | Research models generating CAD from images | Read only; a benchmark reference |
| [dorianborian/sesame-robot](https://github.com/dorianborian/sesame-robot) (5.2k) | Apache-2.0 | ESP32 mini quadruped, eight servos, printable | A new device class for HS's reference benchmark (legged robot) |
| [SIGRobotics-UIUC/LeKiwi](https://github.com/SIGRobotics-UIUC/LeKiwi) (1.5k) | Apache-2.0 | Low-cost mobile manipulator for LeRobot | Benchmark for an HS rover plus HS-ARM-A combination |
| [ace-trump-tech/MindPaw](https://github.com/ace-trump-tech/MindPaw) (2.8k) | not stated (NOASSERTION) | ESP8266 desktop robot dog | Benchmark only until its licence is clear |
| [m5stack/StackChan](https://github.com/m5stack/StackChan) (1.6k) | none | Desk companion robot firmware and apps | Read only |
| [arpanghosh8453/open-dronelog](https://github.com/arpanghosh8453/open-dronelog) (1.6k) | AGPL-3.0 | Drone flight-log analyser with battery tracking | Possible source of flown battery data for the next hover back-test; run separately, code not copied |
| [Gathin23/cleanyourtv](https://github.com/Gathin23/cleanyourtv) (61k, listed as tv-vibehack) | not stated | Debloats Android and Google TV boxes | Salvage lead: old TV boxes as kiosks or controllers, the atlas's "pre-configured devices" line |

## What the atlas ranks that HS has already tested

The atlas's top hardware chain, "AI-drafted PCB with independent KiCad check, engineering review and supplier order files"
(Copper, a KiCad checker, kicad-happy), is marked there as not yet shown to work end to end. HS has run it:
`examples/atlas_feedback/pcb_chain_tested_20261128.json` holds the results for the atlas to attach.
