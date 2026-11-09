# Frozen actual KiCad vs plain Gemini pilot

## Provenance / no hindsight
- Original reference and experiment protocol precommitted at
  d182fb8180b82067ed8cd1909624864ab0399927.
- Gekkio schematic project, exact pinned Git revision
  032eb9c2578125b157ab88048113b2d52663b819.
- Normalized genuine KiCad netlist SHA256
  06bba923b03443c60bc37a22d0eacac1e4286d1f1caf2690944ae52e0a33bdf0.
- Both model arms use **identical** source-reported symptoms:
  no AA operation, working external DC adapter, DMG-CPU-06 label
  as stated by the publisher.
- Original video outcomes / repair steps were not loaded into the
  model; this particular case comes from a **written repair dossier**,
  not a video transcript.
- Comparison has two model inference calls and just one case. It
  cannot establish statistical fault accuracy, physical repair success,
  or superiority over Gemini across arbitrary restoration videos.

## Actual Gemini 3.8 Flash Low responses

| | Plain Gemini | HS + actual Gekkio netlist |
| --- | --- | --- |
| Model valid | Yes | Yes |
| Initial fault family | Corroded AA battery contacts | Open battery input path |
| First nonpowered check | Inspect AA terminals for corrosion | Inspect AA terminals and check continuity to board |
| Source-specific fact | None | /Power/BT+: BT1 pin 1 to DC1 pin 4 |
| Model inference runtime | 10.62 sec | 11.85 sec |

The HS arm cites source-extracted terminals that were independently
reproduced with KiCad 9.0.2. This establishes **source-grounding
capability**, not a correct outcome prediction. Plain Gemini
understood the general likely battery path from the symptoms.

### Important caught limitation
The HS arm additionally proposes unpowered DC1 pin 3-to-pin 4
continuity tests. Those pin labels are correct for the *reference
schematic*, but the actual hardware's DMG-CPU-06 revision was only
reported by the author, not verified by HS. A generic reference match
must not grant permission for pin-specific action on a physical device.

Treat the test as proposed, not authorized. The next HS gating change
must require a verified target-board revision before any practical
pin-specific test recommendation. None of these model responses
were physically executed. The separate DC converter subtype remains
unknown and its reference pinout was not supplied as a target map.

Reproducible source/results and offline hash validation:
  PYTHONPATH=src python3 examples/restoration_video_bench/real_schematic/verify_kicad_source.py --source-checkout /tmp/hs-source-gb-schematics
  PYTHONPATH=src python3 examples/restoration_video_bench/real_schematic/inspect_dmg_model_ab.py --infile examples/restoration_video_bench/real_schematic/real_dmg_kicad_model_ab.json --out /tmp/hs_real_kicad_no_gold.json
