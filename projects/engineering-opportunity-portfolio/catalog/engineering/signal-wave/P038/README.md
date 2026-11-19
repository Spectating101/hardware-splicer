# P038 · USB dry-cabinet environmental logger

Distinguish new samples, carried-forward readings, startup without data and expired readings.

**Signal path.** RH, temperature and sample age → validated record → host CSV.

| Simulated result | Value |
|---|---|
| boot without sensor | unavailable |
| cached rows labelled | 2 |
| expired rows suppressed | 2 |

**Bench acceptance.** Compare against a reference humidity instrument and log a real USB disconnect and reconnect.

Each trace is synthetic. The component values, timing and contacts are design inputs. These files exercise the specified subsystem before selecting and measuring real hardware.

[Input values](../cases.json) · [Executable models](../circuits.py) · [Trace, including control](trace.csv) · [Summary](results.json)
