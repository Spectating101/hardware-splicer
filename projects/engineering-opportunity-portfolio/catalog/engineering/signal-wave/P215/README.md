# P215 · Three-pedal stream shortcut controller

Exercise simultaneous holds and releases plus 500 strokes per pedal. Compare the reports with a one-key encoder.

**Signal path.** Three independent pedal states → HID report → host held-key set.

| Simulated result | Value |
|---|---|
| reports | 3000 |
| single key control lost chords | 500 |

**Bench acceptance.** Run a hold and release log on each supported host. Measure debounce and verify shortcut behavior inside the intended app.

Each trace is synthetic. The component values, timing and contacts are design inputs. These files exercise the specified subsystem before selecting and measuring real hardware.

[Input values](../cases.json) · [Executable models](../circuits.py) · [Trace, including control](trace.csv) · [Summary](results.json)
