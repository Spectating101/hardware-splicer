# Virtual Ender-3 pen plotter

This digital engineering study converts the original manufacturer Ender-3 design into a pen plotter. It retains the X/Y/Z motors, belts, lead screw, controller, bed, frame, enclosed power supply and stock temperature sensors. A new two-piece adjustable clamp replaces the printing head on its documented carriage interface. Z lifts the pen between strokes. An additional parking plate supports the intact original heater, thermistor and radiator so the stock firmware can still see its temperature sensor.

**Owned inventory: zero.** The donor below is a precisely identified virtual reference. No printer, parts, pen, tools or consumables have been acquired. No fabrication, physical assembly, firmware flashing, powered motion or boot test has occurred. The G-code is a local simulation example.

The manufacturer source is [Creality3DPrinting/Ender-3 at commit 88c7758cea9d0d00a54fdb238bedb3b33425f409](https://github.com/Creality3DPrinting/Ender-3/tree/88c7758cea9d0d00a54fdb238bedb3b33425f409), dated 2019-12-11. This is the original Ender-3 open-source mechanical design, not V2, Pro, Neo, S1, V3 or an unidentified printer. The repository root license is GPLv3. Unmodified sources and exact SHA-256 hashes accompany this package.

Start with [BOM.md](BOM.md), [ASSEMBLY.md](ASSEMBLY.md) and [VALIDATION.md](VALIDATION.md). [NOTICE.md](NOTICE.md) describes attribution and changed files. `sources/manifest.json` pins the upstream files. `sources/interface.json` records measured coordinates and tool offset.

## Delivered files

- `exports/pen_adapter.step` and `.stl`: carriage adapter with rear pen saddle and captive clamp nuts.
- `exports/pen_clamp.step` and `.stl`: detachable front clamp with 0.4mm adjustment gap.
- `exports/hotend_parking_plate.step` and `.stl`: top-rail parking plate for the intact heating unit and secured fans.
- `exports/plotter.step`, `plotter.glb`, `device_render.png`: representative full-device layout. The E plate and new parts are detailed. Other retained components are explicitly named **REFERENCE_ENVELOPE** shapes. They are not detailed manufacturer replacement CAD.
- `simulation/example.svg`, `example.gcode`, `trajectory.csv`, `plotted_drawing.png`: real vector-to-linear-G-code conversion and an independently replayable drawing.
- `reports/engineering.json`, `simulation.json`, `verification.json`, `export_manifest.json`: numeric assumptions, constraints, integrity checks and byte hashes. `requirements_met` is separate from `artifact_integrity`.

## Regenerate locally

The project root is resolved from each script's location; the scripts also work on isolated package copies. Requires Python 3, CadQuery 2.6.1, numpy, trimesh, matplotlib and Pillow. The repository native environment is `.cache/hardware-splicer/digital-native-venv/bin/python`. Run from the repository root:

```bash
rtk proxy env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 taskset -c 0,3 .cache/hardware-splicer/digital-native-venv/bin/python projects/ender3-penplotter-digital/scripts/build.py
rtk proxy env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 taskset -c 0,3 .cache/hardware-splicer/digital-native-venv/bin/python projects/ender3-penplotter-digital/scripts/simulate.py
rtk proxy env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 taskset -c 0,3 .cache/hardware-splicer/digital-native-venv/bin/python projects/ender3-penplotter-digital/scripts/verify.py
```

`requirements.json` controls drawing width (60..140mm), drawing height (40..140mm), cylindrical pen grip diameter (8..12mm) and pen lift (2..5mm). Default values are 100mm, 80mm, 10mm and 3mm. Altering pen diameter changes both saddle solids. Drawing dimensions and lift alter emitted G-code and replay. Out-of-range or nonfinite inputs are rejected.

Width and height define the SVG viewport mapped onto the central paper area. The artwork has intentional internal margins, so its ink bounds are smaller than the viewport. The feed-based duration is an ideal estimate excluding acceleration and settling.

The 44.8MB original full manufacturer assembly was imported once to derive instance datums. It is provenance, not a regeneration dependency, and may be excluded from execution copies. Small, hashed E-plate/nozzle/radiator/profile/T-nut sources and extracted assembly metadata are included for independent checks.

## What the study establishes

The new adapter uses the manufacturer's two M3 hotend bores, 14mm apart, with a measured 7mm boss front and 2.5mm main plate. It clears the detailed donor plate, exports closed solids, and keeps all simulated drawing and travel within stated bed/tool bounds. The SVG becomes 12 pen-down strokes and hundreds of actual linear G-code moves. The plotted PNG is reconstructed from those emitted moves.

It does not establish print strength, clamp friction, pen force, real motor behavior, electrical safety, firmware boot, homing clearance, machine-wide collision freedom or physical plot accuracy. The new pen tip is 30.75mm lower than the original nozzle. The sample deliberately assumes a paper datum and does not home a machine. A future physical build needs its own measured acceptance before any powered operation.
