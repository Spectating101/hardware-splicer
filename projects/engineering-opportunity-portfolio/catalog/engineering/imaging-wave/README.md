# Imaging and studio engineering trials

Eleven catalog offers have editable dimensions, a full-size baseline and revised drawing, and a product-specific digital acceptance check. The baseline runs exposed 19 failed acceptance criteria. The revised runs passed all 41 criteria. The 22 SVGs and two indexed capture CSVs rebuild byte for byte. Physical fit, hardware operation, fabrication yield, and demand remain open.

| Offer | Main question |
| --- | --- |
| [P008 35 mm camera-scanning carrier](reports/P008.md) | Can a narrow rail and mask keep edges clear after a reload? |
| [P017 Motorized indexed photo turntable](reports/P017.md) | How much position error and settle-time margin does the capture schedule leave? |
| [P018 Turntable extension platform](reports/P018.md) | Where can an eccentric payload sit while preserving tip margin? |
| [P019 Compact folding LED photo box](reports/P019.md) | Can the opposed walls stow without overlap? |
| [P020 Larger folding LED photo box](reports/P020.md) | Can a removable lintel support the modeled light panel over a 610 mm span? |
| [P195 Fold-flat field monitor sunshade](reports/P195.md) | Can a shade block an overhead ray while preserving off-axis screen visibility? |
| [P196 Lens rod support saddle](reports/P196.md) | Does saddle travel cover the desired lens sizes on 15 mm LWS rods? |
| [P199 Filter-tray matte box](reports/P199.md) | Do the three frame apertures pass a modeled 24 mm full-frame image bundle? |
| [P200 Speedlight beam grid](reports/P200.md) | How does stack depth change geometric cutoff at a fixed open area? |
| [P203 Pocket production slate](reports/P203.md) | Do the bilingual face and nominal hinge geometry clear the work requirements? |
| [P205 Smartphone cue teleprompter](reports/P205.md) | Does the beam splitter cover both the observer and camera ray bundles? |

P008 and P010 share the camera-copy carrier concept. The new acceptance criteria cover the narrow strip, perforations and feed direction. P017 and P018 cover independent subsystems of a turntable. P019 and P020 share a photo enclosure platform and test stowage and span, respectively.

## Replay and edit

Run from this directory with Python 3.9 or newer. The replay reads each released SVG and P017 capture CSV, extracts as-drawn sizes and positions, evaluates them against each job specification, validates artifact bounds and units, and checks a fresh export against the committed patterns. It runs without access to the surrounding catalog.

```bash
python3 verify.py
```

The SVG sheets use millimeters and include a 20 × 10 mm scale coupon. Use a 1:1 print or import and check the scale coupon. Red indicates nominal cut lines, dark marks indicate engrave or score operations, and blue indicates reference geometry. The product reports describe fit assumptions and where the export is a coupon from a larger assembly. Cut patterns have nominal dimensions. Add kerf and tooling compensation for the actual process.

Edit [parameters.json](parameters.json) to try new dimensions or fixture inputs. After generating the revised exports, the verifier updates the machine-readable [results](results.json) with `--write-results`. Reports and [manifest](manifest.csv) combine the notes and outcomes with catalog prices and projected results. Update [study-notes.json](study-notes.json) for any altered decision, then refresh the reports while the work is in the catalog directory.

```bash
python3 build.py
python3 verify.py --write-results
python3 document.py
```
