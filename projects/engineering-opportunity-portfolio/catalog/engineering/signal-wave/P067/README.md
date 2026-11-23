# P067 · Stepper winding identification and jog station

Recover both coil pairs under all lead permutations and reject an open coil and an intercoil bridge.

**Signal path.** Four disconnected motor leads → resistance matrix → bipolar winding pairing.

| Simulated result | Value |
|---|---|
| valid permutations | 24 |
| bad samples rejected | 48 |

**Bench acceptance.** Measure a named four-lead motor and check current-limited slow jog. Five- and six-lead motors need a separate classification.

Each trace is synthetic. The component values, timing and contacts are design inputs. These files exercise the specified subsystem before selecting and measuring real hardware.

[Input values](../cases.json) · [Executable models](../circuits.py) · [Trace, including control](trace.csv) · [Summary](results.json)
