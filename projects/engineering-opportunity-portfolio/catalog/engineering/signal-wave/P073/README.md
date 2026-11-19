# P073 · USB-UART service adapter with keyed leads

Check alternating and boundary bit patterns across three declared rates and injected clock skew.

**Signal path.** Synthetic 8N1 transmitter → sampled loopback waveform → decoded bytes.

| Simulated result | Value |
|---|---|
| frames accepted | 36 |
| outside skew faults | 33 |

**Bench acceptance.** Loop back on the populated board and measure actual logic voltage in each keyed position. Test supported hosts.

Each trace is synthetic. The component values, timing and contacts are design inputs. These files exercise the specified subsystem before selecting and measuring real hardware.

[Input values](../cases.json) · [Executable models](../circuits.py) · [Trace, including control](trace.csv) · [Summary](results.json)
