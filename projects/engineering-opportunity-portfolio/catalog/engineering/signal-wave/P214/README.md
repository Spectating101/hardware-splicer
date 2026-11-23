# P214 · Four-pad USB MIDI trigger box

Replay light and hard strikes with coupled adjacent signals and compare false notes across two thresholds.

**Signal path.** Four strike envelopes → per-pad threshold → MIDI note and velocity.

| Simulated result | Value |
|---|---|
| synthetic strikes | 240 |
| control extra notes | 360 |

**Bench acceptance.** Measure missed and doubled notes and velocity response from 30 light and hard strikes on each actual pad.

Each trace is synthetic. The component values, timing and contacts are design inputs. These files exercise the specified subsystem before selecting and measuring real hardware.

[Input values](../cases.json) · [Executable models](../circuits.py) · [Trace, including control](trace.csv) · [Summary](results.json)
