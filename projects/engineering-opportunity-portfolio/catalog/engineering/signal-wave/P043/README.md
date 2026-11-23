# P043 · Custom four-wire harness checker

Test an exact four-wire cross-harness against every single open, output swap and pairwise bridge.

**Signal path.** One enabled source pin → unpowered harness → four observed return pins.

| Simulated result | Value |
|---|---|
| single faults detected | 16 |
| control missed | 12 |

**Bench acceptance.** Confirm the exact mating connectors and continuity on an unpowered known-good cable, then test fault plugs.

Each trace is synthetic. The component values, timing and contacts are design inputs. These files exercise the specified subsystem before selecting and measuring real hardware.

[Input values](../cases.json) · [Executable models](../circuits.py) · [Trace, including control](trace.csv) · [Summary](results.json)
