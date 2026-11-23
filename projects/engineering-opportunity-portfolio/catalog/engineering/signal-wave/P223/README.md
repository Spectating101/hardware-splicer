# P223 · Dry-contact switch latch and timer

Replay both modes on a discrete clock including a press during an active interval and simulated power loss.

**Signal path.** Switch edge → toggle or timed state → low-voltage dry-contact output.

| Simulated result | Value |
|---|---|
| timed cycles | 300 |
| toggle edges | 100 |
| maximum late ms | 3 |
| loss of power closes contact | False |

**Bench acceptance.** Compare each preset with a reference timer for 100 cycles, verify relay release and confirm default open after power loss.

Each trace is synthetic. The component values, timing and contacts are design inputs. These files exercise the specified subsystem before selecting and measuring real hardware.

[Input values](../cases.json) · [Executable models](../circuits.py) · [Trace, including control](trace.csv) · [Summary](results.json)
