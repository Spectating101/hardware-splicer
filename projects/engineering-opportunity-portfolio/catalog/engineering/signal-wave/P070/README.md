# P070 · Bench resistance substitution box

Compute the tolerance envelope for all 1,000 settings and identify when the two-wire contacts dominate.

**Signal path.** Three decade switches → series resistors → test terminals.

| Simulated result | Value |
|---|---|
| settings | 1000 |
| uncorrected settings outside budget | 72 |
| assumed contact change each ohm | 0.02 |

**Bench acceptance.** Measure every switch position at the terminals on a calibrated meter. Repeat low-ohm settings after operating the switches.

Each trace is synthetic. The component values, timing and contacts are design inputs. These files exercise the specified subsystem before selecting and measuring real hardware.

[Input values](../cases.json) · [Executable models](../circuits.py) · [Trace, including control](trace.csv) · [Summary](results.json)
