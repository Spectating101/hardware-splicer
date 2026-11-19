# P065 · Buffered digital timing capture pod

Determine which capture interval can see the shortest specified pulse at every sampled phase.

**Signal path.** Eight square-wave inputs → buffer → common sample clock → edge records.

| Simulated result | Value |
|---|---|
| phase channel cases | 800 |
| slow misses | 416 |
| input pulse ns | 240 |

**Bench acceptance.** Measure input thresholds, shortest detectable pulse width, interchannel skew and crosstalk on the populated pod.

Each trace is synthetic. The component values, timing and contacts are design inputs. These files exercise the specified subsystem before selecting and measuring real hardware.

[Input values](../cases.json) · [Executable models](../circuits.py) · [Trace, including control](trace.csv) · [Summary](results.json)
