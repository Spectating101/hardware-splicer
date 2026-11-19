# DC measurement station

This HS capability specifies a small measurement station and provides an actual Linux I2C acquisition program for its primary INA228 channel. It produces wiring, parts and numerical sizing artifacts. It has no dependency on a policy engine.

The default working envelope is an externally isolated 24 V, 120 W DC bench source: 5 A nominal current, with a primary monitor range that accommodates at least 7.5 A. The equipment remains an **unbuilt candidate**. No component has been selected, procured, assembled, calibrated or physically tested by this package.

## Electrical architecture and measurement boundary

The positive power path is source → DC fuse/disconnect → primary four-terminal shunt RSH1 → independent reference four-terminal shunt RSH2 → load positive. The return conductor runs from load negative to source negative. All load current traverses both shunts. Load energy is measured after both shunts and excludes their losses.

The INA228 IN+/IN− inputs use a separate Kelvin pair at RSH1. Its VBUS input measures load positive; its ground references load negative. A separate reference instrument measures both the voltage across RSH2 and the load voltage at the same load terminals. Its two measurements need paired inputs or documented scan timing, and the shunt inputs must tolerate the high-side common-mode voltage. No reference instrument driver or simultaneous-input capability is assumed.

INA228 is **not galvanically isolated**. A direct host I2C connection shares the measurement ground and can earth a previously floating DC circuit. The source must have independently verified isolation; a floating host boundary additionally needs a specified isolator and isolated supply. This design includes no mains wiring, battery storage, solar input or grid connection.

The INA228 pin assignments, input ranges, current scaling and register formats come from the [TI INA228 datasheet, SLYS021A revision A](https://www.ti.com/lit/ds/symlink/ina228.pdf), sections 5, 6.3, 7.6, 8.1.2 and 10.1. The external shunt and reference values are explicit design assumptions, not TI part recommendations.

## Default sizing

| Quantity | Primary | Independent reference |
|---|---:|---:|
| Candidate four-terminal shunt | 5 mΩ | 10 mΩ |
| Stated candidate power rating | 2 W | 2 W |
| Stated tolerance | 0.1% | 0.1% |
| Allowed dissipation at 50% design derating | 1 W | 1 W |
| Worst-tolerance dissipation at 7.5 A | 0.28153125 W | 0.5630625 W |

Nominal source current is `120 / 24 = 5 A`. With both shunts at their high tolerance, their total drop at 5 A is 75.075 mV and total loss is 0.375375 W. A 24 V source would then supply about 23.924925 V and 119.624625 W to the load, before conductor and contact losses. The 120 W source ceiling does not guarantee 120 W delivered at the load.

The primary uses INA228's ±163.84 mV range (`ADCRANGE=0`), a requested 10 A current-register full scale, and `SHUNT_CAL=1250`. The effective current LSB is derived from the actual rounded calibration register; quantization is not silently discarded. The ADC range, current-register range, both shunt dissipations and 1.5× nominal-current headroom are checked independently.

Configure exact measured resistance and documented ratings in a `StationSpec` JSON file. The exported parts table retains unresolved fuse coordination, source limits, connectors, conductor sizing, common-mode capability, calibration and temperature effects. Mechanical work requires measured module/shunt dimensions, strain relief, covered terminals and thermal separation; this package does not invent mounting holes or a fabrication-ready PCB.

## Generate the equipment package

From the repository root:

```bash
PYTHONPATH=src python -m hardware_splicer.dc_measurement_cli design --out /absolute/new/station-design
```

The new directory contains `station-design.json`, `parts.csv`, `wiring.csv` and a short README. To replace assumptions, pass `--spec /absolute/spec.json`. The spec supports the fields of `hardware_splicer.dc_measurement_station.StationSpec`; unknown fields and non-finite numbers are rejected. A failed numerical check is retained in the design artifact and returns exit status 2. It does not become a success by changing a readiness flag.

## Primary acquisition program

This is host software, not generated MCU firmware. It uses Linux `i2c-dev` combined pointer-write/read transactions. The adapter must support `I2C_FUNC_I2C`; the selected address is checked without force-binding over an existing kernel driver. Adapter numbers can change after reboot: inspect the actual adapter before choosing the explicit bus and address. See [Linux userspace I2C documentation](https://docs.kernel.org/i2c/dev-interface.html). Transport imports were checked with `smbus2==0.5.0`; install that optional package only on the acquisition host.

After actual hardware, source limits and connections have been checked, a manually invoked capture looks like:

```bash
PYTHONPATH=src python -m hardware_splicer.dc_measurement_cli capture \
  --spec /absolute/actual-station-spec.json \
  --bus 1 --address 0x40 --samples 183 --period-seconds 1 \
  --clock-source 'actual configured host UTC source' --out /absolute/new/capture
```

This command writes sensor configuration registers and reads the connected bus. It does not switch, fuse or disconnect the load. Its software checks apply to measured J2 load voltage and power. They do not enforce the upstream 24 V/120 W source ceiling, because both shunt losses and conductor losses lie upstream. Source current/power limits and fault protection must be independently configured and verified. No hardware command was run while developing this capability.

At initialization the program checks manufacturer/device identity, resets the INA228 and sets explicit configuration. Each sample checks static configuration and identity, triggers a fresh bus/shunt conversion pair, waits for conversion-ready with a finite timeout, and checks memory/diagnostic flags. It decodes the three-byte, MSB-first measurement registers and retains their raw bytes. Shorts, bus errors, ID/configuration changes, negative current, range/power violations and inconsistent shunt/current values stop acquisition; no zeros or previous values are substituted.

The trigger uses 1052 µs per bus/shunt conversion and 16 averages, nominally 33.664 ms per pair. These are consecutive measurements, not an assertion of simultaneous voltage and current sampling. The program targets steady or slowly varying bench loads; it does not observe every transient between one-second samples. INA228's accumulated energy/charge registers are invalid in triggered mode, so the program does not use them. Integrating sample power over time is a separately stated numerical approximation.

Outputs:

- `samples.csv`: exact columns `timestamp_utc,voltage_v,current_a`, with actual UTC read-completion timestamps.
- `registers.jsonl`: raw measurement words, decoded values, diagnostic flags, elapsed conversion time and monotonic elapsed time.
- `session.json`: source kind, configuration and shunt basis, device ID, declared UTC source, completion/failure, sample coverage and exact file hashes.
- `station-design.json`: the design and assumptions used by this run.

UTC is checked against a monotonic clock to detect jumps; synchronization to an external clock is still unverified. Schedule delays and coverage gaps stop the run and preserve partial data with `status=FAILED`. CSV rows are never resampled or given scheduled timestamps. Acquire a little beyond both ends of an intended integration window: 183 one-second samples normally bracket a complete three-minute window aligned to whole seconds, while 181 arbitrarily timed samples may not.

## Reproducible software verification

The fixture encodes a constant 23.925 V, 5 A load into fake INA228 registers. The real decoder and capture loop produce the CSV using a deterministic clock with no waiting:

```bash
PYTHONPATH=src python -m hardware_splicer.ina228_fixture \
  --start-utc 2026-01-01T00:00:00Z --samples 183 --out /absolute/new/register-fixture
PYTHONPATH=src python -m pytest -q tests/test_dc_measurement_station.py
```

Its session is always `capture_kind=TEST_FIXTURE`, `source_kind=register_fixture`. No hardware or instrument observation is claimed. Tests cover signed decoding and exact register vectors, calibration quantization, undersized shunts, insufficient current range, identity/configuration changes, missing conversion-ready, diagnostic flags, short reads, negative/out-of-envelope signals and clock-step failure. They do not validate a physical INA228, Linux adapter timing, the shunts, temperature rise or instrument calibration.
