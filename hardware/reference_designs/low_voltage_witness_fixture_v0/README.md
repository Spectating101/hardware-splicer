# HS / Policy Lab — 5 V independent DC witness fixture v0

**Status:** Native KiCad schematic and routed PCB pass KiCad 9 ERC / DRC / schematic parity. Analog DC simulation and the original HS INA228 decoder → Policy Lab frozen PLRS-6 intake replay pass **software fixtures only**. **No hardware has been purchased, built, connected, energized, calibrated, or tested. This design is NOT released for fabrication or power-on.**

## Purpose and physical boundary

A deliberately low-energy commissioning prototype for the question: *Can two separately acquired measurement paths agree about the energy delivered to the same DC load, and can that evidence support a bounded engineering decision?*

Working experiment: **5.0 V nominal, ≤0.5 A / approximately 2.5 W**, an isolated current-limited external bench source (proposed current limit no higher than 0.65 A), external 10 Ω resistive load (select a ≥10 W part with mounting/thermal clearance). The 5.25 V spec maximum is a **planning envelope**, not permission to raise the supply setting. No grid, PV panel, battery, mains, or 24 V operation. The *real* output depends on physical component and cable resistance.

Electrical topology in the KiCad schematic:

```text
SOURCE+ J1.1 → F1 fuse holder → J3.1 → [external Adafruit INA228 VIN+ shunt VIN−]
                                             J3.2 → R1.1 (WSK2512 10mΩ)
                                                     R1.4 → LOAD+ J2.1
SOURCE− J1.2 ─────────────────────────────────────────────────→ LOAD− J2.2

R1.2 → J5.1, TP1  independent reference shunt + Kelvin measurement
R1.3 → J5.2, TP2  independent reference shunt − Kelvin measurement
LOAD+ J2.1 → J4.1 (Adafruit VBUS) and J6.1 (reference VBUS)
LOAD− J2.2 → J4.2 (Adafruit ground) and J6.2 (reference ground)
```

**J3 pins are deliberately separate nets.** They MUST NOT be shorted by a jumper; the complete load current is intended to pass through the *external* INA228 carrier's actual VIN+ / VIN− onboard 15 mΩ shunt. Adafruit's VBUS-to-VIN+ jumper should remain **OPEN** (the guide's default), and its VBUS connected separately to J2 LOAD+ via J4 to preserve the same downstream measurement boundary as the reference path. Confirm the carrier's actual revision and pin labels on delivery; **INA228 does not provide galvanic isolation**. Independently review the supply, USB host earth, 3.3 V I2C domain and reference instrument grounding before wiring anything.

R1 is a proposed **genuine four-terminal** Vishay WSK2512R0100FEA. KiCad footprint pad numbers **1,4** carry the main current; **2,3** are Kelvin-only sensing. Replacing it with a similar-looking ordinary two-terminal 2512 resistor would invalidate the designed reference. **As of 20 November 2026, Taiwan DigiKey lists 0 on-hand**, so this selection is a procurement blocker. No automatic replacement is authorized.

## Actual design assets

- `low_voltage_witness_fixture_v0.kicad_sch` — native editable schematic, 12 components, seven named nets, measured current topology.
- `low_voltage_witness_fixture_v0.kicad_pcb` — native KiCad 9 board, 2 layers; routed without unconnected pads, **125 × 58 mm outline** nominal (PCB API includes 0.05 mm edge stroke in bbox).
- `low_voltage_witness_fixture_v0.kicad_pro`, `sym-lib-table` — tracked project/library metadata. `netlist.xml` is **generated** from the editable schematic on each run and deliberately not committed because KiCad embeds checkout-sensitive data. Design generators use installed KiCad symbols and native footprint geometry.
- `generate_schematic.py`, `generate_pcb.py` — source regenerators. Board geometry is validated semantically rather than claiming byte-identical KiCad UUIDs.
- `erc.txt`, `drc.txt`, `pad-map.txt` — native reports. Both have zero violations; DRC has zero unconnected pads and zero schematic/PCB parity errors.
- `board-geometry-preview.step` — actual KiCad board-only geometric export (no modeled populated assembly).
- `fabrication_preview/` — manufacturing file *preview* for review; **NOT released to fabrication**.
- `preview/` — native KiCad SVG exports of editable schematic and front copper/silkscreen layout.
- `evidence/fixture-replay-20261120/` — complete pinned software fixture and Policy Lab receipt, not real measurements.
- `spice_low_voltage_witness.cir`, `spice-simulation.txt` — ngspice DC electrical model with explicit hypothetical resistance assumptions.
- `BOM_candidate.csv`, `station-spec-5v.json`, `BUILD_HOLD.md` — sourcing requirements and unresolved safety/physical questions.
- `verify_and_replay.py` — repeats KiCad ERC/DRC, schematic-netlist-to-PCB pad parity, SPICE cross-check, actual HS INA228 register-decoder simulated acquisition, and optional frozen Policy Lab intake.

## Software validation (NO hardware)

From this directory, with an HS checkout containing `hardware_splicer.ina228_logger` and a Policy Lab checkout containing the existing `scripts/equipment/dc_bench_capture.mjs`:

```sh
python3 verify_and_replay.py \
  --pl-root /absolute/path/to/solarpunk-coin \
  --out /absolute/PREVIOUSLY_NONEXISTENT_DIRECTORY
```

Output includes `verification.json`, native ERC and DRC reports, a `station/` candidate design, actual INA228 decoding of 183 simulated register samples, an independently computed reference-shunt fixture, and `policy-lab-intake/` with the **unchanged frozen** PLRS-6 receipt.

Focused self-check: `python3 -m unittest -v test_verify_fixture.py` (needs KiCad 9, ngspice and pcbnew).

The reference model is **5.0 V source, 0.05 Ω assumed fuse/contact resistance, 0.015 Ω Adafruit shunt, 0.010 Ω reference shunt, 10 Ω load**. Ngspice's nominal result:

| Model output | Value |
|---|---:|
| DC current | 0.496278 A |
| Output voltage at J2 | 4.962779 V |
| Load power at J2 | 2.462918 W |
| Three-minute load energy | 0.1231459 Wh |

Those are **numerical model outputs**, not measurements. The *independently written* reference fixture and HS register simulator agree with the modeled power within defined quantization limits; PL returns `TEST_FIXTURE_STRUCTURALLY_INGESTED_NO_PHYSICAL_CLAIMS`, with `physical_ready:false`.

## Physical commissioning gates — all still OPEN

1. **Parts and mechanical:** acquire exact fuse holder/terminator/shunt parts; verify data sheets against footprints and the actual board, count connector pins, polarity, screw orientation, 4-terminal pad map, solderability and contact strain relief. R1 stock availability is unresolved.
2. **Protection:** choose a fuse link with a documented DC breaking rating suitable for the supply's prospective fault current, not simply a 1 A marking. Validate source current limiting and off/short behavior. The source limit is the primary bounded-power measure; the fuse must not be presented as verified protection.
3. **Grounding/isolation:** qualified operator reviews the actual isolated supply, USB/I2C host connection, high-side instrument common-mode and all shared grounds; verify no unexpected earth or shorts.
4. **Instrument integration:** acquire/connect the actual INA228 carrier + a separately characterized reference DMM/logger (paired shunt and bus readings). Record serials, original raw bytes, actual UTC/monotonic times, calibration status and uncertainty. A single DMM scan does not automatically provide synchronized voltage/current.
5. **Thermal and structural:** mount the load off-board with thermal clearance; inspect board/cable heating, contact resistance, screw terminal and mounting standoffs. Confirm clear labels and fuse holder fit in the *assembled* enclosure; STEP currently describes only an unpopulated board.
6. **Operator-controlled bench steps:** after review, work from supply OFF, verify connectivity and shunt polarity with suitable instruments, begin with a tightly current-limited low-voltage bring-up, then run predefined steady-current profiles; watch for unexpected heat/current and shut down manually on faults. No remotely commanded energization was implemented here.
7. **Independent repeat:** second operator repeats three independently timed capture intervals, reference compares, and records blind/negative-control cases. A correct result or a recorded disagreement can be a valid outcome, but physical data cannot be replaced with synthetic data.

**Nothing in the software reports closes these gates.** The v0 board is not a ready-to-order product and absolutely must not be extrapolated to the old 24 V / 120 W station. Any higher-power revision requires new part selection, current-carrying design and separate review.

## Vendor leads and caveats

[Adafruit #5832 INA228](https://www.adafruit.com/product/5832), [Adafruit VBUS jumper/pins](https://learn.adafruit.com/adafruit-ina228-i2c-power-monitor/pinouts), [TI INA228](https://www.ti.com/product/INA228), [Schurter FAB fuse holder 0031.3551](https://www.schurter.com/en/part/0031.3551), [Vishay WSK2512R0100FEA listing](https://www.digikey.tw/zh/products/detail/vishay-dale/WSK2512R0100FEA/12142494), [Phoenix 1715022 5 mm terminal block](https://www.phoenixcontact.com/us/products/1715022).

Adafruit's guide describes **15 mΩ ±0.1%**, while an official carrier schematic previously examined indicated a **1%** resistor. Actual populated revision must be resolved; `station-spec-5v.json` explicitly uses a conservative unverified 1% assumption. Schurter's **holder** lists 250 VAC; that is *not* a fuse-link DC interrupt certification.

The largest remaining obstacle to real physical credibility is **physical instrumentation and independently retained reference measurements**, not another software or CAD feature.
