# Five devices, five engineering decisions

These digital samples use real design files to answer questions that come up when building with existing hardware. Each device was new to the HS tracked samples when selected. The questions and predictions were committed at `3cc0adda` before opening the scoring sources. [Protocol](protocol.md) · [Exact design inputs](inputs.json) · [Sealed predictions](predictions.json)

| Device | What the sample lets a builder decide |
|---|---|
| Original Prusa i3 MK3S | A 245 × 205 × 20 mm tray fits the nominal 250 × 210 × 210 mm volume. A part 252 mm wide or 211 mm tall exceeds it in the tested orientation. Using the firmware's 255 mm X travel would give the wrong answer for the wide part. [Prusa comparison table](https://blog.prusa3d.com/original-prusa-mini-is-here-smart-and-compact-3d-printer_30887/) |
| Elephant Robotics myCobot 280 M5 | Joint 2 can reach +135° within its nominal range and exceeds it at +145°. Joint 6 allows +175°. The model alone left a 300 g tool unresolved. The manual supplies the missing 250 g payload rating. Collision clearance and loaded motion require separate checks. [M5 specifications](https://github.com/elephantrobotics/mycobot_docs/blob/468743879f4ccf9f1e727219c235310fec0d9296/mycobot_280_M5%282023%29en/1-ProductInformation/2.ProductParameter/2-ProductParameters.md) |
| Adafruit PyGamer handheld | Replacement firmware should select the SD card on D4, keep the onboard flash clock separate, and read the buttons through the shift register's latch, clock and data lines. [Board firmware](https://github.com/adafruit/ArduinoCore-samd/blob/b73ae8c05d7b9463abd40b98b88653a4eefab306/variants/pygamer_m4/variant.h) · [Button interface](https://learn.adafruit.com/adafruit-pygamer/pinouts) |
| SparkFun OpenLog Artemis v1.0 | A custom logger can read the motion sensor over SPI and control SD and Qwiic power separately. Use D23 for card select on v1.0. D10 belongs to the older v0.4 board. [Revision-specific firmware](https://github.com/sparkfun/OpenLog_Artemis/blob/f9c8e66b7da6f27a4bf9be55016c5b9231b9fb22/Firmware/OpenLog_Artemis/OpenLog_Artemis.ino#L196) |
| Adafruit MAX9744 stereo amp | Reuse a stereo line-level source through the 3.5 mm jack. Each speaker needs its own output pair, so a three-wire common-return speaker harness is incompatible. An unmarked speaker needs an impedance specification or characterization before accepting it. [Amplifier guide](https://learn.adafruit.com/adafruit-20w-stereo-audio-amplifier-class-d-max9744/overview?view=all) |

## What was verified

Of 15 questions with published answers, seven affirmative and seven negative predictions matched. The arm payload question was the one abstention. A separate missing-information case for the salvaged speaker stayed unresolved and is excluded from that denominator. Both abstentions were explicitly encoded by the sample author. An operator also selected the board revisions, component references, pins and challenge values. HS supplied the existing fit check and robot model importer. The board samples used case-specific adapters to inspect the published layouts. Several questions use the same board, so these counts describe this set of cases. [Answer key and sources](answer_key.json) · [Score by case](results.json) · [Evaluation code](predict.py)

A second check traced 18 of 20 selected pad pairs across tracks, vias and pads in the imported PCB layouts. It verified all six handheld pairs, all four logger pairs, both amplifier line-input pairs and six amplifier output pairs. The two remaining amplifier paths, FB4/1 to U1/41 and FB2/1 to U1/36, have matching net assignments and copper polygons. The track traversal leaves their filled-polygon continuity unverified. The maker's guide independently supports the speaker wiring decision. [KiCad 9.0.2 trace results](copper.json)

## Open or change the tray

The post-scoring example is an open parts tray with 2 mm walls and base. Its 245 × 205 mm footprint leaves 2.5 mm per side when centered on the nominal plate. The CAD generator reopens the STEP file and checks the solid, dimensions and material volume. Brim allowance, slicing and physical printing are outside this fit check. [Editable STEP solid](models/parts_tray.step) · [STL mesh](models/parts_tray.stl) · [Parametric source](make_tray.py)

With CadQuery 2.8 installed, this makes a 220 mm wide variant in a separate directory.

```sh
python eval/unseen_devices/make_tray.py /tmp/hs-tray --width 220
```

## Replay

Run from the repository root with the HS Python environment. The first command downloads the six pinned inputs when missing and verifies each checksum. Subsequent runs can omit `--fetch`. Grading uses the sealed prediction bytes and the manually adjudicated answer key. The optional copper check uses the system Python with KiCad 9.0.2's `pcbnew`.

```sh
cache=.cache/hardware-splicer/unseen-devices
sample=eval/unseen_devices
mkdir -p "$cache"
PYTHONPATH=src .venv/bin/python "$sample/predict.py" "$cache" --fetch > "$cache/replay.json"
diff -u "$sample/predictions.json" "$cache/replay.json"
.venv/bin/python "$sample/grade.py" > "$cache/score.json"
diff -u "$sample/results.json" "$cache/score.json"
/usr/bin/python3 "$sample/check_copper.py" "$cache" > "$cache/traces.json"
diff -u "$sample/copper.json" "$cache/traces.json"
```
