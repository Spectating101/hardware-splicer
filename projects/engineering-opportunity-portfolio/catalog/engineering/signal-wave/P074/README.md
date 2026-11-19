# P074 · USB hands-free test trigger pedal

Inject switch bounce and reconnect while held, requiring a release before a new trigger.

**Signal path.** One mechanical pedal → debounced edge → keyboard trigger.

| Simulated result | Value |
|---|---|
| valid triggers | 3 |
| control triggers | 16 |

**Bench acceptance.** Record one event per stroke on the host and unplug and reconnect the USB cable with the pedal depressed.

Each trace is synthetic. The component values, timing and contacts are design inputs. These files exercise the specified subsystem before selecting and measuring real hardware.

[Input values](../cases.json) · [Executable models](../circuits.py) · [Trace, including control](trace.csv) · [Summary](results.json)
