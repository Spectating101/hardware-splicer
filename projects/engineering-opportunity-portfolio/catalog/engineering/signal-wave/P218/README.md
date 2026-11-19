# P218 · Large single access button

Compare center and four edge activation forces for two hinge positions at a fixed switch lever distance.

**Signal path.** Wide pivoted face → mechanical moment arm → dry-contact switch.

| Simulated result | Value |
|---|---|
| worst ideal force N | 0.695 |
| original worst N | 1.8533 |
| assumptions | Rigid face, symmetric mounting and constant bias torque; no flex, friction variation or measured accessibility. |

**Bench acceptance.** Measure activation force and travel at center and edges, inspect return, and test 500 actuations with the actual mounting and intended user.

Each trace is synthetic. The component values, timing and contacts are design inputs. These files exercise the specified subsystem before selecting and measuring real hardware.

[Input values](../cases.json) · [Executable models](../circuits.py) · [Trace, including control](trace.csv) · [Summary](results.json)
