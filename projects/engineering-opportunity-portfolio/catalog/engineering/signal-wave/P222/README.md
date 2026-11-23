# P222 · Two-message tactile playback pad

Interrupt a replacement message at each write-operation boundary and verify recovery of the prior committed audio payload.

**Signal path.** Record buffer → two-slot nonvolatile journal → two playback selectors.

| Simulated result | Value |
|---|---|
| interruption boundaries | 33 |
| second slot preserved | True |
| completed rewrite and reopen cycles | 20 |
| bad crc recovered prior message | True |

**Bench acceptance.** Record and recover distinct audio after 20 real power cycles and verify tactile identification with the intended user.

Each trace is synthetic. The component values, timing and contacts are design inputs. These files exercise the specified subsystem before selecting and measuring real hardware.

[Input values](../cases.json) · [Executable models](../circuits.py) · [Trace, including control](trace.csv) · [Summary](results.json)
