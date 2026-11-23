# P075 · Eight-port selectable I2C sensor breakout

Prevent selecting multiple same-address channels and show how combined data can resemble a valid zero.

**Signal path.** Controller → single selected multiplexer channel → identical-address sensor.

| Simulated result | Value |
|---|---|
| correct tags | 8 |
| unsafe selections rejected | 7 |
| composite byte looks like valid port | 0 |

**Bench acceptance.** Read two marked same-address sensors on every connector and measure bus signal edges with the intended cable length.

Each trace is synthetic. The component values, timing and contacts are design inputs. These files exercise the specified subsystem before selecting and measuring real hardware.

[Input values](../cases.json) · [Executable models](../circuits.py) · [Trace, including control](trace.csv) · [Summary](results.json)
