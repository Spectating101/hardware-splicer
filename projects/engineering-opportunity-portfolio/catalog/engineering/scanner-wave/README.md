# Scanner accessories and camera-copy lighting

Seven engineering trials yielded fourteen full-size SVG patterns. The initial drawings missed twelve digital criteria. The revised drawings pass all 34 criteria. The experiments cover different media constraints and share some host assumptions.

| Product | Trial question |
| --- | --- |
| [P009 35 mm carrier with CS-LITE](reports/P009.md) | Can an opaque baffle match the vendor illumination footprint and reduce the unintended bright field? |
| [P011 Kodak Disc adapter](reports/P011.md) | Will the index shoe register a radial frame while preserving the aperture margin? |
| [P012 127 flatbed adapter](reports/P012.md) | How far can edge clamps sit apart before modeled curl exceeds the height limit? |
| [P013 126 flatbed adapter](reports/P013.md) | Will a single perforation key align the strip and reject the reflected side? |
| [P014 120 holder for V600](reports/P014.md) | Does an adjustable shim kit bracket enough height to support a focus sweep? |
| [P015 110 holder for 4870](reports/P015.md) | Will four narrow crop apertures preserve image margins and opaque separator land? |
| [P016 8 mm inspection holder](reports/P016.md) | Can an offset window isolate one frame under a pose tolerance? |

V600 studies share a synthetic 112 × 198 mm transparency test area and a 24 mm placeholder keepout. The 4870 quick reference expressly requires leaving top calibration space uncovered. The 4870 study models that region with a separate 30 mm placeholder. These dimensions exercise the placement logic. Epson’s manuals document the workflow and hardware markings. Actual interface dimensions and focus planes require hand measurements. The CS-LITE study uses published body and illuminated-area dimensions. The trial metric for that product describes illuminated geometry. Optical uniformity remains a physical fixture test.

## Replay and edit

Run this command from the folder with Python 3.9 or newer.

```bash
python3 verify.py
```

Replay independently reads the saved SVG geometry and compares newly generated files byte for byte. The SVG patterns are physically dimensioned in millimeters. Verify the 20 × 10 mm coupon when printing or importing. Red denotes cut paths, blue shows references or stock envelopes and dark strokes represent score or engraving operations. The production host dimensions, kerf compensation, working depth, fastener or clip geometry and focus need the stated physical checks.

Edit dimensions and constraints in [parameters.json](parameters.json) and update [study-notes.json](study-notes.json) for altered decisions. Regenerate the patterns and [results](results.json) in place. Building the reports and [manifest](manifest.csv) uses the catalog CSVs in their original layout.

```bash
python3 build.py
python3 verify.py --write-results
python3 document.py
```
