# FieldDeck 5 digital integration trial

Open `electrical/display_power.pdf` to inspect the two display power conductors. Open `fielddeck-study.zip` for the revised assembly at `revision/cad/FIELDDECK_5.step`, the changed STEP/STL files at `revision/cad/changed_parts/`, and the parts list at `revision/BOM.csv`. The study also includes the original geometry, retained print parts, source identities and vendor notices. The downloadable files are in [FieldDeck-5-integration.zip](FieldDeck-5-integration.zip).

## Device and checks

The Raspberry Pi 4 FieldDeck replaces its 7-inch SC1635 display with the 5-inch SC1975. HS built a new registered study, reopened the 47-solid assembly and repeated its native verification. It checked four nominal mounting paths and four ribbon clearance regions. The default work scenario models 7.25 W and 3.166–4.469 hours. See the calculation inputs before using that range for another workload.

Copper generated an editable KiCad schematic for the existing Adafruit 824 extension concept and supplied display lead. The two single-contact symbols represent the red and black leads, without assigning undocumented display-side connector pin numbers. J1 shows the excerpt of the Pi header that contains physical pins 2 and 6. Unused contacts in that excerpt are unconnected in this harness drawing. The pin assignments are taken from the baseline FieldDeck connection plan. KiCad 10.0.8 exported the nets and HS ran electrical rule checking with the stock connector symbols registered. All four endpoints matched, with zero ERC errors and warnings. A second schematic with the red and black ends exchanged produced two polarity mismatches against the original requirements. See `electrical/lead_check.json` for both verdicts. The released schematic is the intended wiring.

Kemerd’s enclosure mass routine consumed each reopened changed STEP file. The four revised chassis panels and four identical spacers total 466.773 g of fully dense PETG equivalent at 1.27 g/cm³. Slicer infill, supports and waste determine actual filament consumption. The calculation excludes retained chassis parts and electronics. Each input STEP hash and quantity is recorded in `mechanical/changed-parts.json`.

## Open engineering questions

- The manufacturer STEP and drawing disagree about mounting-lug depth. The model uses a 4.52 mm spacer. Actual thread engagement and screw length remain unresolved.
- The 300 mm Adafruit 1648 ribbon has space reserved in the CAD. Connector exits, permissible bends, strain relief, and the detailed DSI pin mapping and signal voltage remain open.
- The two-conductor check establishes net connectivity in the drawing. Extension contact current rating, loaded voltage at the display and physical operation remain unverified.

## Repeating the handoffs

The unmodified registered export is bundled as `fielddeck-study.zip`. Both external reports contain its SHA-256. The native HS audit is in `study-audit.json`. The two additional checks run on the exported revision as a separate integration trial. No global connector setup is required in HS.

For the electrical check use a checkout of [Copper at the tested revision](https://github.com/claynicholson/copper-kicad-mcp/tree/3d3a7628dc52a63358ad945eef224cb7c5636080), the HS checkout and KiCad CLI 10.0.8 with the stock connector symbols. Add Copper's `src` and HS's `src/hardware_splicer/pcb` to `PYTHONPATH`. Then run `python replay/check_lead.py fielddeck-study.zip electrical-replay`. The trial ran in the official kicad/kicad image with digest `sha256:3f4a01786dfbe803a65f345c3342b765db9add913f5e9448f8356793714ddc34`. The script uses a project-local symbol table. Expanded KiCad UUIDs can vary between builds.

For mechanical results use the HS digital CadQuery environment and the [Kemerd checkout at the tested revision](https://github.com/Kemerd/claude-hardware-in-the-loop/tree/e8ef234c4e63d6b13bb225430f5311f6ec60374a). Run `python replay/check_solids.py fielddeck-study.zip /path/to/checkout/skills/hardware-in-the-loop/templates/cad/examples/enclosure/build_enclosure.py changed-parts.json`.

Based on claude-hardware-in-the-loop by Kemerd (https://github.com/Kemerd/claude-hardware-in-the-loop). Copper and Kemerd license notices are included. The baseline harness description is preserved under `sources/FieldDeck-7-CONNECTIONS.md`. [Raspberry Pi display documentation](https://www.raspberrypi.com/documentation/accessories/touch-display-2.html)
