# P071 · Four-wire Kelvin clamp fixture

Replay ten assumed remounts, comparing separate sense contacts with a sense lead mistakenly sharing the force contact.

**Signal path.** Two force leads supply a reference shunt → two independent sense leads measure its voltage.

| Simulated result | Value |
|---|---|
| max four wire error pct | 0.3032 |
| min shared error pct | 40.3008 |

**Bench acceptance.** Remount a reference shunt ten times, reverse the test current to assess offsets and check the separate contact positions.

Each trace is synthetic. The component values, timing and contacts are design inputs. These files exercise the specified subsystem before selecting and measuring real hardware.

[Input values](../cases.json) · [Executable models](../circuits.py) · [Trace, including control](trace.csv) · [Summary](results.json)
