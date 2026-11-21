# AYN Thor → true 50-key split QWERTY — Hardware Splicer engineering pilot

**Research date:** 2026-11-09. **Status:** actual source-backed KiCad PCB copper + printable mechanical templates; NOT an authorized fabricated or measured physical retrofit.

## Purpose

Replace AYN Thor left/right gaming controls with two miniaturized QWERTY thumb keyboards **without replacing the Snapdragon-class processor, upper AMOLED, central lower touchscreen, hinge, cooling or battery**.

Standard QWERTY split: left QWERT/ASDFG/ZXCVB, right YUIOP/HJKL;/NM,./, ten number keys and ten control/space/function keys; **25 keys per side, 50 total**. This is an initial thumb layout: real key feel, multi-modifier operation and keycap legends have not been tested.

## Actual independent geometry source

Downloaded [HandHeldModz Thor Open STL](https://handheldmodz.com/scans/) from `https://handheldmodz.com/content/files/2025/11/Thor-Open.stl`. Binary STL 1,012,267 triangles, SHA-256 `42800c73d5e0523961f243e482732fcd2ba119c6e3aeae55659d7adee32e8402`; raw bounding extents 152.407×177.738×32.276 mm. The open scan covers **both halves**; the lower-body upper surface is manually segmented as x∈[-74.66,77.75], y∈[-74.4,-1.0]. Central lower-screen opening approximately x∈[-35.25,39.0]. The segmentation is an exterior scan *interpretation* with ~±2mm uncertainty, NOT certified device CAD or an internal cavity scan. Raw STL remains external and is **not committed or redistributed**.

### Results (2D envelope only)

| Metric | Flush 7 mm | Detachable 9 mm |
| --- | ---: | ---: |
| Per-side PCB | 36 × 57 mm | 47 × 58 mm |
| Per-side letter switches | 25 | 25 |
| Horizontal/vertical pitch | 7 / 10.5 mm | 9 / 11 mm |
| Approx keycap top rectangles | 5.5 × 7 mm | 8 × 8 mm |
| Provisional screen gap (minimum) | **1 mm** | **2 mm** |
| Provisional hinge / bottom keepout gap | 2 / 3 mm | 2 / 2 mm |
| Extension beyond actual side walls | **0 mm** | **left 9.84 / right 10.25 mm** |
| Nominal 2 mm keepout buffer | **FAIL** | **PASS in 2D only** |
| Actual internal electronics/lid clearance | **UNKNOWN** | **UNKNOWN** |
| Physical thumb typing proven | **NO** | **NO** |

**Recommendation: prototype the detachable 9 mm option FIRST**, as a standalone free-standing keyboard to establish thumb comfort and reliable input. The wings overlap regions currently occupied by the original joysticks/buttons. They **CANNOT just be laid onto an unmodified Thor**. The wings would also prevent ordinary folding unless removed or given a wholly new (unverified) stowage mechanism. The original control daughterboards and existing enclosure are not qualified for removal here.

The flush variant avoids lateral protrusion but offers just **1 mm** screen-side nominal margin—smaller than the external scan's approximate uncertainty. This is *not* viable as an approved laser-cut replacement template.

## Actual KiCad PCB result

Generated **four editable and routed KiCad 9 two-layer boards**, for left/right × flush/wing.

- Each board: **25 × C&K KMR2 tactile-switch footprints**, 25 × candidate SOD-123 1N4148W diodes, **5 column + 5 row solder test pads**. Independent 5 × 5 diode-isolated key matrix; 35 distinct electrical nets per board including per-key intermediates. The underlying KMR2 footprint has duplicated terminals; both duplicates were explicitly copper-connected.
- First attempt found **55 unconnected items**, and the generator was corrected. Native `kicad-cli pcb drc` on **all four board variants now returns 0 violations, 0 unconnected pads, 0 footprint errors**, independently replayed with `verify.py`. Four actual `.kicad_pcb` files and native layer SVG exports are under `generated/`.
- **No MCU, Bluetooth antenna, battery, charging hardware or mating cable/connector designed.** The ten test pads are for a benchtop breakout; they are NOT a finished flex connector and need strain relief.
- **No standalone KiCad schematic/ ERC parity yet.** DRC checks PCB layout/net assignments, but cannot establish manufacturer suitability or guaranteed functioning keyboard. The diode candidate and exact KMR2 switch variant must be confirmed against supply/datasheet and pin function before fabrication.
- C&K KMR2 dimensions approximately 4.6 × 2.8mm body and 1.9mm height above PCB, from [DigiKey KMR221NG LFS product specifications](https://www.digikey.tw/en/products/detail/c-k/KMR221G-LFS/550472) and the upstream [KiCad footprint library](https://kicad.github.io/footprints/Button_Switch_SMD.html). Keycap retention/height is not designed; the OpenSCAD preview uses a **1.2mm unverified cap-height stand-in**, not a build-ready button assembly.

### Firmware / input route

Prototype design: a Bluetooth split keyboard using two independent nRF52840-class microcontrollers (one on each side), ideally [ZMK's central/peripheral arrangement](https://zmk.dev/docs/features/split-keyboards). The central presents a Bluetooth HID keyboard to Android/Thor; peripheral only sends events to central. One matrix uses 5 GPIO row + 5 GPIO column connections; whether a particular XIAO MCU and board supply enough correctly routed pins, battery management, antenna clearance and charging hardware **remains unverified**. Firmware builds, actual BLE pairing, programming modifiers and real switch actuation **not yet tested**.

Do not connect any of these speculative PCBs to undocumented AYN gamepad ribbons or power rails. First test both matrix breakouts using a benign external USB/BLE development board and a known regulated development power supply, away from the Thor's battery and internals.

## Actual outputs

- [Two side-by-side envelope mockups](generated/thor_two_keyboard_options.png)
- [7mm flush printable A4 SVG, 100% scale](generated/flush_7mm/thor_flush_7mm_1to1_A4.svg)
- [9mm detachable printable A4 SVG, 100% scale](generated/detachable_9mm/thor_detachable_9mm_1to1_A4.svg)
- `generated/flush_7mm/thor_flush_7mm_{left,right}_25keys.kicad_pcb`
- `generated/detachable_9mm/thor_detachable_9mm_{left,right}_25keys.kicad_pcb`
- KiCad native copper-layer previews `generated/*/left_front_copper.svg`
- Two native OpenSCAD `generated/*/thor_*_concept.scad` files. **Imported scan and Z=28 mm are placeholders**, not real internal registration; 3D collisions **cannot** be cleared from exterior-only scan.
- [Independent native KiCad/geometry evidence receipt](evidence/verification.json)
- [Reproducible 2D fit, all 100 keys across two complete configurations](generated/fit_report.json)

## Reproduction

```bash
# Download Thor Open.stl from HandHeldModz; confirm SHA-256 above.
# Requires numpy, matplotlib and local KiCad9/pcbnew.
python3 examples/cyberdeck/thor_split_qwerty/design.py \
    --scan /tmp/hs-thor-open-reference-20261109.stl

python3 examples/cyberdeck/thor_split_qwerty/make_stencils.py
python3 examples/cyberdeck/thor_split_qwerty/verify.py \
    --out examples/cyberdeck/thor_split_qwerty/evidence/verification.json

PYTHONPATH=src python3 -m pytest -q tests/test_thor_split_qwerty.py
```

If the external scan is missing or hash mismatch, generator fails instead of substituting an invented interior model. KiCad-generated board UUIDs may vary across replays, so the native verification receipt must always be recreated for the newly generated files.

**Physical gate sequence:** printed 1:1 finger-reach tests → obtain true internal depth, screw/ribbon positions and closed-lid gap on real Thor → choose switch and keycap stack → print non-destructive unpowered dummy plates → route/mount powered two-controller prototype external to Thor → compile ZMK and verify full 50 keys and programmer shortcuts → only then redesign removable controls or install keyboard into real unit.

No purchase, destructive removal, fabricating, lithium-ion wiring, or firmware flashing of the Thor is authorized by this design study.
