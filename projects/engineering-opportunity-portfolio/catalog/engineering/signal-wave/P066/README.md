# P066 · Servo characterization dial and load arm

Compute the load moment over a servo angle sweep and quantify the error from assuming a horizontal arm.

**Signal path.** Hanging mass and graduated arm → angle-corrected moment estimate.

| Simulated result | Value |
|---|---|
| max corrected pct | 2.019 |
| max uncorrected pct | 44.277 |

**Bench acceptance.** Measure lever length and angle under load, weigh the fixture and test power, holding current and safe servo limits independently.

Each trace is synthetic. The component values, timing and contacts are design inputs. These files exercise the specified subsystem before selecting and measuring real hardware.

[Input values](../cases.json) · [Executable models](../circuits.py) · [Trace, including control](trace.csv) · [Summary](results.json)
