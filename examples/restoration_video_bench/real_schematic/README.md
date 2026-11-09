# Real schematic evidence pilot: original Game Boy DMG-CPU-06

This is HS's first restoration diagnostic intervention backed by
**real exported electrical connectivity**, not a generic prompt or a
hand-coded fault classification. It uses the native
engineering_source_graph and repair_intake adapters already in HS.

## Source and attribution

Reference author: Gekkio, Game Boy -related schematics,
https://github.com/Gekkio/gb-schematics,
CC BY 4.0. Exact source revision:
032eb9c2578125b157ab88048113b2d52663b819.
These are **reverse-engineered** KiCad 2023 files, not Nintendo official
service documentation or independently measured target-device truth.

KiCad CLI 9.0.2 produced source-backed electrical netlists:
- Original Game Boy DMG-CPU-06 mainboard: 50 components, 108 nets;
- Separate DC-CONV-DMG-A/B converter *reference*: 19 components, 15 nets.

The exact source file hashes, commit, license and resulting
normalized source-netlist SHA-256 are in source_gb_dmg_manifest.json.
No time/date/path-dependent raw export is committed. The normalized
dmg_netlist_snapshot.json is an attributed source-derived snapshot,
NOT hand-authored synthetic PCB data.

Real mainboard extracted power connections include:
- /Power/BT+: BT1 pin 1, DC1 pin 4;
- /Power/SW1-VCC: DC1 pin 3, D1 pin 1, SW1 pin 1;
- VCC: SW1 pin 2 and J1 pin 4;
- VDD: J1 pin 1;
- GND: BT1 pin 2, DC1 pin 1, J1 pin 3, SW1 pin 4;
These are separate **KiCad electrical nets**; they do not establish
tested conductivity *through* the diode/jack/switch, or the actual
voltage present in any repair device.

## Revision matching and conservative authority

Pilot repair report:
https://revamp.top/gameboy/gameboy-dmg-no-power-battery-contact/
The account says a Game Boy DMG-01 does not start from four AA cells,
but works from an external DC adapter; author labels mainboard
DMG-CPU-06. This is a **publisher report**, not an independently
confirmed board label or instrument observation.

- If the reported mainboard revision is NOT an exact DMG-CPU-06 match,
  HS withholds **all pin-specific electrical reference claims**.
- Even if the author says DMG-CPU-06, HS distinguishes
  "reported revision match" from "physically verified revision".
- The separate converter-board subtype is UNKNOWN. Its netlist and
  connector mapping are withheld from pin-specific target advice even
  though a separate public converter reference can be extracted.
- Every source graph net claim is capped at DECLARED authority, not
  MEASURED, VERIFIED or AUTHORIZED.
- No internal mains PSU, hardware operation, physical bench test,
  component replacement, actual repair, or model video frame analysis.
- No safe operation is automatically authorized. No outcomes are
  imported from the rest of the repair article.

## Pre-specified matched pilot

Use Gemini 3.8 Flash Low (same model, one call each, fixed order):
1. Plain model with same native HS repair-intake observations.
2. Same model, same E1..E3 symptom evidence, augmented by actual
   timestamp-independent KiCad net claims and provenance plus explicit
   revision uncertainty and safe non-powered-test restrictions.

The comparison is **one case**, not a statistical performance result.
Source graph plus extra instructions means a longer prompt; the
treatment effect includes prompt structure as well as actual hardware
facts. Outputs must be frozen before any outcome comparisons. Do not
label a plausible mechanism as a proven component failure.

Reproducible engineering-source check using a pinned checkout:

    PYTHONPATH=src python3 examples/restoration_video_bench/real_schematic/verify_kicad_source.py \
      --source-checkout /tmp/hs-source-gb-schematics

A/B model run after source check:

    PYTHONPATH=src python3 examples/restoration_video_bench/real_schematic/run_dmg_real_schematic_ab.py \
      --source-checkout /tmp/hs-source-gb-schematics \
      --out /tmp/hs_dmg_real_kicad_ab.json

The model uses the existing user's Antigravity CLI connection, no
direct paid API charge. Results are append-saved per arm; failed runs
are not silently rerolled.

## Next acceptance gates

1. Source-backed electrical advice must reference *correct* terminals
   rather than hallucinated test points, and avoid claiming observed
   voltage where none has been independently measured.
2. Have an independent operator photograph and confirm the exact PCB
   revision and collect signed safe meter readings, then use the
   same audited path to update the differential.
3. Expand from one public DMG dossier to actual, *unseen* repair videos
   with confirmed matching board revisions and accessible schematics.
4. Separate visual PCB registration, validated boardview mapping,
   source retrieval, test-selection accuracy and repair outcome checks.

A verified KiCad source file does **not** by itself prove an actual
repair. This pilot tests the first real engineering-data connection.
