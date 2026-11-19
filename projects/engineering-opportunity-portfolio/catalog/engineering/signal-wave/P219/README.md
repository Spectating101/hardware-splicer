# P219 · Two-switch wired USB interface

Replay independent, simultaneous and reconfigured holds, including unplug recovery when a key is still down.

**Signal path.** Two dry-contact sockets → configurable key usages → HID held-key set.

| Simulated result | Value |
|---|---|
| reports | 1000 |
| single key control lost chords | 200 |
| reset while pressed | held input inhibited until release |
| remap and reset transitions | 10 |

**Bench acceptance.** Repeat on the two named hosts with the user's actual switches. Verify socket fit, accessibility and release handling.

Each trace is synthetic. The component values, timing and contacts are design inputs. These files exercise the specified subsystem before selecting and measuring real hardware.

[Input values](../cases.json) · [Executable models](../circuits.py) · [Trace, including control](trace.csv) · [Summary](results.json)
