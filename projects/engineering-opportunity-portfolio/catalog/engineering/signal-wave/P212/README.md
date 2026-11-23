# P212 · Headphone rehearsal splitter amplifier

Sweep simultaneous dummy loads and reject a source with insufficient per-side peak current.

**Signal path.** Two independently loaded outputs per stereo side → shared per-side current budget.

| Simulated result | Value |
|---|---|
| load pairs | 9 |
| worst per side peak mA | 39.775 |
| low current missed pairs | 3 |

**Bench acceptance.** Test both real outputs into declared dummy loads. Measure output limit, distortion, noise and heating; hearing comfort is outside the model.

Each trace is synthetic. The component values, timing and contacts are design inputs. These files exercise the specified subsystem before selecting and measuring real hardware.

[Input values](../cases.json) · [Executable models](../circuits.py) · [Trace, including control](trace.csv) · [Summary](results.json)
