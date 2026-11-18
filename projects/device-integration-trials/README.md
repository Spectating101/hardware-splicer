# Three device integrations beyond FieldDeck

## Drawing machine

The [Ender-3 trial package](ender3-route-trial.zip) contains a newly built HS registered study and a separate candidate stroke order. Revision 2 increased the pen barrel from 10 to 12 mm and the drawing viewport from 100 × 80 to 140 × 100 mm. The native audit passed. Both route measurements below use the **same revision 2 tool and drawing**.

| Result | Original order | vpype order |
| --- | ---: | ---: |
| Pen-up XY travel | 760.24 mm | 551.36 mm |
| Pen-down distance | 1,038.13 mm | 1,038.13 mm |
| Ideal feed time | 161.03 s | 150.58 s |

All 12 strokes and 268 directed ink segments were retained. Each inter-stroke move in the replay stayed at the requested 3 mm lift. [Route comparison](plotter-route.png) · [Measurements](plotter-route.json)

To repeat from this directory, unpack the trial in a separate folder. Run `plotter_route.py registered-study.zip candidate.gcode` with vpype 1.15.0. Run `check_plotter.py registered-study.zip candidate.gcode preview.png` using the repository's native digital Python. The candidate uses vpype's direction-preserving greedy sort. The original HS study remains independently auditable. Physical grip and machine timing remain unmeasured. [vpype](https://github.com/abey79/vpype)

## Bench inspection fixture

The [four-carrier fixture release](../pcb-inspection-nest/inspection-nest-v0.2.zip) adds a carrier for the Feather M4 Express. The earlier source importer missed the board's two unlabelled drills. The new profile identifies those holes by EAGLE drawing coordinates. A person still chooses the mounting features when onboarding a board. The builder now reads their actual diameters directly from the pinned drawing.

KiCad 9.0.2 imported the original EAGLE layout independently. Its PCB importer and the generated carrier agree on four positions and drill sizes. The bare board and carrier seat with zero modeled overlap, and a reversed carrier interferes with the dock by 19.223 mm³. The model has 46.524 mm² of total shoulder contact. Component clearance on a populated board remains open. [Independent comparison](feather-check.json) · [Design, licenses and regeneration](../pcb-inspection-nest/README.md)

Run `check_feather.py inspection-nest-v0.2.zip feather_m4.brd` with KiCad's Python environment. The script verifies the board digest against the release and converts KiCad's Y-axis convention before comparing the holes. Deliberately missing or duplicate mounting coordinates were separately rejected by the HS builder.

## Recovered keyboard layout

Open the [interactive assembly drawing](f60-keyboard-assembly.html) in a browser. Selecting a parts-list row highlights its footprints on the board. The example places the T, G, B, 5 and 6 keys from the f.60 study on a daughterboard. All ten modeled switch-to-header wires, twenty endpoints in total, agree between the generated viewer and the HS relocation map. Exchanging the two header pins on one key in a copy of the map produced two mismatches. Native KiCad DRC reported zero violations and zero unconnected items on the daughterboard. Donor continuity, diode polarity on an actual donor and powered key scanning remain unverified. [Source project and original designer](../../examples/arbitrage_lab/keyboard_splice/arbitrary_corpus/f60_remount_round5/README.md) · [Results and input hashes](keyboard-check.json)

To reproduce, use [InteractiveHtmlBom v2.12.0](https://github.com/openscopeproject/InteractiveHtmlBom/tree/5c192e794cd66fde04bab11810601b711bf8581b). Run its `generate_interactive_bom.py` on `key_remount/remount_keys.kicad_pcb` with `--include-nets --no-browser --no-compression`. Run `check_keyboard.py OUTPUT.html key_remount/RELOCATION_MAP.json` on the resulting file. The HTML includes the upstream viewer. Its license is in [InteractiveHtmlBom-LICENSE](InteractiveHtmlBom-LICENSE).
