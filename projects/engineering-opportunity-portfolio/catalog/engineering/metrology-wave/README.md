# Bench metrology and woodworking fit trials

Ten catalog products now have editable experiments, full-size patterns and independent artifact checks. The starting designs miss 18 digital acceptance criteria. The revised drawings and synthetic readings pass all 30 criteria. The batch includes 20 SVG patterns and six tabular reading examples.

| Product | Bench question |
| --- | --- |
| [P076 Three-face CNC work origin touch block](reports/P076.md) | Does the readout recover known stock origins after calibrating faces and adding stylus compensation? |
| [P077 Fixed-height CNC tool setter puck](reports/P077.md) | Is there spring travel after worst-case modeled trigger delay and braking? |
| [P078 Twin-indicator spindle tramming bar](reports/P078.md) | Do reversed readings cancel fixed indicator zero offsets? |
| [P086 Adjustable kerf transfer gauge](reports/P086.md) | Does subtracting the kerf from layout offset control fit across three width cases? |
| [P099 Vertical heat-set insert press](reports/P099.md) | Can the guide span and depth stop hold a useful fit envelope? |
| [P105 RC wheel balancing arbor](reports/P105.md) | Can a known small weight overcome modeled breakaway and arbor bias? |
| [P106 Bicycle wheel dish gauge](reports/P106.md) | Is there enough travel to fit two rim sizes while preserving reversal sensitivity? |
| [P107 Bicycle derailleur hanger alignment gauge](reports/P107.md) | How much does reference-shaft clearance limit a four-position comparison? |
| [P110 Guide-rail angle setting stop](reports/P110.md) | What panel-end layout error follows from the contact baseline and lock play? |
| [P245 Fretboard notched straightedge](reports/P245.md) | Do all notch edges clear the fret crowns and leave measurable straightedge lands? |

The CNC outputs are offline fixture geometry and arithmetic samples. Machine compatibility and control response need independent measurements. The wheel, calibration and woodworking trials define bench acceptance criteria. Fabrication, accuracy on a measured reference, application fit and tool approval remain open on each report. The modeled buy prices retain the catalog scope and do not establish delivered equivalence.

## Replay and editing

Use Python 3.9 or newer in this folder.

```bash
python3 verify.py
```

The independent parser reads SVG physical dimensions and the supplied CSV records, evaluates both revisions, and compares a clean export byte for byte. The SVGs use millimeters and include a 20 × 10 mm scale coupon. Red indicates a nominal cut profile, dark strokes indicate witness marks, and blue indicates reference geometry. The reports state which profiles are component patterns and which model the assembly interface.

After editing [parameters.json](parameters.json), regenerate the drawings and [results](results.json). The finished product [manifest](manifest.csv) and reports use the original catalog CSVs. Update [study-notes.json](study-notes.json) if a trial changes.

```bash
python3 build.py
python3 verify.py --write-results
python3 document.py
```
