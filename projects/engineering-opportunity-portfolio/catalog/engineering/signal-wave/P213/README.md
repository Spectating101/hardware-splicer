# P213 · Wired director tally lamp

Check all contact combinations, transition latency and loss of both closures.

**Signal path.** Two isolated contact inputs → program priority → red / green tally.

| Simulated result | Value |
|---|---|
| max delay ms | 3.5 |
| slow control max ms | 17.5 |
| open contacts output | off |

**Bench acceptance.** Verify dark state on unplug and time 100 mixer-contact transitions including simultaneous program and preview.

Each trace is synthetic. The component values, timing and contacts are design inputs. These files exercise the specified subsystem before selecting and measuring real hardware.

[Input values](../cases.json) · [Executable models](../circuits.py) · [Trace, including control](trace.csv) · [Summary](results.json)
