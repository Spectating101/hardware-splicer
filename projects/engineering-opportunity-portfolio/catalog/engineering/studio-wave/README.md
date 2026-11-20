# Camera, focus and studio fixture engineering trials

Fourteen product trials cover optical positioning, mechanical motion, cable and body clearance, grip, stability and studio accessories. Eighteen individual criteria failed the starting designs. All 48 revised criteria pass. The 28 full-size SVGs and two focus schedule CSVs replay from editable input and are checked against the stored artifacts.

| Product | Engineering question |
| --- | --- |
| [P036 Motorized macro focus rail](reports/P036.md) | Can same-direction pre-roll and a 6 µm schedule preserve macro focus overlap? |
| [P037 Manual XY specimen stage](reports/P037.md) | Does a square slide at commanded travel keep the specimen inside the viewing aperture? |
| [P193 Hand-pushed tabletop camera dolly](reports/P193.md) | Does the steering plate give the desired orbit without consuming static support margin? |
| [P194 Camera cable strain relief](reports/P194.md) | Will the pad stack grip the cable while preserving its minimum modeled bend radius? |
| [P197 Camera half cage](reports/P197.md) | Can the operator access ports, hot shoe and door once the rails are installed? |
| [P198 Manual lens follow-focus wheel](reports/P198.md) | Can reducing center distance improve backlash and retain adequate tooth contact? |
| [P201 Portable reflector sail](reports/P201.md) | How much does a centered ballast improve the modeled moment ratio? |
| [P202 Single-roll tabletop backdrop winder](reports/P202.md) | Does the brake contact radius control paper tension while keeping hand force low? |
| [P204 Collapsible chroma panel](reports/P204.md) | Can the same strap cut length handle both chair attachment routes? |
| [P206 Low-profile desk microphone arm](reports/P206.md) | Does moving the spring anchor reduce residual moment across the working travel? |
| [P207 Clip-on speech pop screen](reports/P207.md) | Can the two layers cover the modeled source envelope without crowding the mic? |
| [P208 Microphone suspension cradle](reports/P208.md) | Can softer elastic reduce modeled vibration transfer with remaining mechanical travel? |
| [P209 Folding vocal reflection screen](reports/P209.md) | How much behind-and-side area is intercepted by the modeled panel arrangement? |
| [P210 Monitor-speaker isolation wedges](reports/P210.md) | Do a matched pair of 1:1 profiles give the intended tilt and seating margin? |

P036 and P037 use different macro hypotheses. P036 tests axial capture scheduling under backlash and a modeled depth of field. P037 tests cross-axis drift and the usable specimen field. The audio accessories assess separate failure modes of an arm, mesh, suspension, reflection screen and listening wedge. Reports separate geometric and dynamic models from the physical audio or optical check.

## Replay and edit

Use Python 3.9 or newer from this directory.

```bash
python3 verify.py
```

Replay extracts geometry from the supplied drawings, reads the focus schedule, runs the product criterion models, and compares fresh exports byte for byte. SVG uses 1:1 millimeters and includes a 20 × 10 mm reference coupon. Red indicates cut geometry, dark indicates engrave or score, and blue indicates references. Each report explains how to use the measured pattern and lists the first physical check.

After changing [parameters.json](parameters.json), regenerate the artifacts and [results](results.json). Reports and the [manifest](manifest.csv) also use the original parent catalog pricing files. Update [study-notes.json](study-notes.json) if decisions change.

```bash
python3 build.py
python3 verify.py --write-results
python3 document.py
```
