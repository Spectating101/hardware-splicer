# Unseen build 01 · Sweep v2.2 split keyboard

The original Hardware Splicer key detector missed all 34 typing keys on this
board. It reported two cable jacks, two power switches and a logo. It had
treated a vendor library name as evidence that an item was a key. The repaired
detector recognizes all 34 typing keys on the same source file and excludes
those five items. That repair used this board and is scored separately.

## What a builder can decide

The wired design has two Pro Micro controller positions, two PJ-320A jacks
and 17 individually wired keys per half. The PCB lists a Choc V1 footprint at
each key. The published build calls for 34 compatible switches, 34 caps and one
four-contact TRRS cable. The controller choice determines the USB cable.
[Project parts list and compatibility table](https://github.com/davidphilipbarr/Sweep/blob/8ba72a256d627567660ecc0b6f51bb18fa8badb5/README.md)

| Proposed donor | Sealed decision | Project guide and findings |
| --- | --- | --- |
| Kailh Choc V1 | Accept for nominal PCB support | Supported |
| Kailh Choc V2 | Unresolved | Unsupported. The electrical contacts line up. The reference footprint calls for a 5.05 mm center hole and the PCB has a 3.429 mm hole. The probe kept recommended drill sizes separate from measured switch-body dimensions. |
| Kailh Choc Mini | Reject | Unsupported |
| Cherry MX PCB mount | Reject | Unsupported |
| Alps / Matias | Reject | Unsupported. The guide groups MX and Alps in one column. |
| Unmarked loose switch | Unresolved | Missing-information control. Its physical identity is unknown. |

The five identified donors yielded four decisions consistent with the guide
and one abstention. There were zero false accepts and zero false rejects.
There are four distinct switch-family labels in the author's table. These
results measure one assisted board assessment. The operator selected the board,
donor families and direct-wiring hypothesis. The project table covered the
Sweep2.x family, and the v2.2 instructions independently name Choc V1.
[Variant instructions](https://github.com/davidphilipbarr/Sweep/blob/8ba72a256d627567660ecc0b6f51bb18fa8badb5/Sweep%20v2.2/README.md)

## Wiring evidence after the reveal

KiCad's copper connectivity graph confirms a signal path from each of the 34
switches to its predicted controller pad. On **both controllers**, the PCB
assigns signal 15 to pad 9 and signal 1 to pad 10. The bundled schematic
labels them the other way around. The remaining 30 controller-pad labels agree.
Use the PCB trace when identifying those two pads on this revision. The
discrepancy by itself leaves actual firmware behavior open.

KiCad 9.0.2, using the author's project settings, also reported three unconnected
items involving ground, VCC and RAW, plus 14 rule errors and 105 warnings. The
board contains two halves in one panel. A maintainer's intent for a panel
boundary or an optional power path matters when interpreting these findings.
Full build operation and fabrication readiness remain unverified.
[Wiring and DRC results](wiring.json)

## Replay

The [protocol](protocol.md), [six source hashes](inputs.json) and
[predictions](predictions.json) were committed at `6b56c2f4` before the
answer row was opened. The existing native HS extractor ran first. A new
case-specific probe used the PCB and independently published donor footprints
to produce the switch map and donor decisions.

Run these commands from the HS checkout on Linux with KiCad 9.0.2 and its Python bindings.

```sh
work=$(mktemp -d)
git show 0f211aa5:src/hardware_splicer/_pcbnew_helpers/keyboard_splice_extract.py > "$work/baseline.py"
/usr/bin/python3 eval/unseen_sweep/predict.py "$work/inputs" --fetch --extractor "$work/baseline.py" > "$work/predicted.json"
cmp eval/unseen_sweep/predictions.json "$work/predicted.json"
/usr/bin/python3 eval/unseen_sweep/predict.py "$work/inputs" > "$work/repaired.json"
jq '.original_extractor_key_refs | length' "$work/repaired.json"
git clone -q https://github.com/davidphilipbarr/Sweep.git "$work/upstream"
git -C "$work/upstream" checkout -q 8ba72a256d627567660ecc0b6f51bb18fa8badb5
python3 eval/unseen_sweep/score.py "$work/upstream/README.md"
/usr/bin/python3 eval/unseen_sweep/check_wiring.py "$work/upstream/Sweep v2.2"
```

The scorer verifies the frozen prediction and answer-file hashes before reading
the outcome. The wiring audit verifies the PCB, project settings, schematic and
symbol against pinned digests. On this installation KiCad exported an empty
netlist from the legacy schematic. The audit reads the global labels directly
at the controller pins. Sheet-wide netlist parity remains unverified.
