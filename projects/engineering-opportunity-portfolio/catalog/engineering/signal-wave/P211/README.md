# P211 · Passive stereo monitor level box

Bound stereo balance at six settings with finite source and load impedances.

**Signal path.** Stereo line-level source → two tapped resistive dividers → finite input load.

| Simulated result | Value |
|---|---|
| worst tracking db | 0.243 |
| control worst db | 1.522 |

**Bench acceptance.** Sweep both channels under a named load and measure tracking, residual hum, noise and mute isolation.

Each trace is synthetic. The component values, timing and contacts are design inputs. These files exercise the specified subsystem before selecting and measuring real hardware.

[Input values](../cases.json) · [Executable models](../circuits.py) · [Trace, including control](trace.csv) · [Summary](results.json)
