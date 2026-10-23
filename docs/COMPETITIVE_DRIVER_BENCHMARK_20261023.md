# Competitive engineering outcome benchmark — 2026-10-23

**Status:** Draft HS repair, not production, not physical buildability certification.

## Competitor-aware goal

HS should outperform generic prompt-to-hardware generation on **donor-device preservation, traceable component provenance, multi-domain engineering constraints, and correctly justified build decisions**. It should not be evaluated by number of integrations, tests, or marketing parity.

Public provider capability statements (not same-input measured outcomes):
- **Flux:** https://www.flux.ai/p and https://www.flux.ai/copilot — AI schematic/PCB design, datasheet help, SPICE, firmware, fabrication, part alternatives.
- **Cirkit Designer:** https://www.cirkitdesigner.com/ — browser-based circuit/firmware simulation, guided wiring/code and diagrams.
- **Schemr:** https://schemr.space/ — prompt→BOM/wiring/step-by-step build, advertised STEP/STL/.ino/CSV exports.
- **HS:** live software output and evidence checks are available from the repository, but **no completed same-prompt comparison against paid/closed generator exports exists**. We cannot claim winning today.

## Reproducible real artifacts: before / candidate

Ran the same three unmodified fixture inputs with `splice_and_build_from_intake` and `export_gerber=False`. Baseline SHA `35fec6b1fa6e32dc010312bc48f06536661f6383` (draft #200). Candidate `fix/competitive-rover-driver-gates-20261023` as of `5df716c1`. Offline model path consistent. Independently inspected compiled `build_graph.json`, `DESIGN_QUALITY.json`, `PROJECT_PACKAGE.json`.

| Real output measure | Baseline | Candidate |
| --- | --- | --- |
| RC donor rover graph motors and BOM | 2 / 2 | 2 / 2 |
| RC rover false-positive GND→non-GND electrical errors | **2** | **0** |
| Enabot donor-drive false-positive GND→non-GND electrical errors | **2** | **0** |
| Both rovers still blocked for actual power-on | Yes | Yes |
| Driver options with package-specific evidence | 0 | **3** |
| L298 catalog candidate without proven donor physical identity flagged | No | **Yes** |
| Sensor-logger unrelated control: electrical check + software job | Pass | Pass |
| Real motor speed, voltage, current, temperature measured | None | None |

The legacy catalog names a motor winding terminal `GND`. In a two-terminal brushed DC motor, that is a **winding lead**, not permanently chassis/common ground. An H-bridge switches either lead. New ERC interpretation treats motor leads as floating terminals, clears the fake shorts, **retains hard errors for actual MCU logic GND↔GPIO shorts and direct GPIO-driven motors**, and warns on motor current return via a controller GND pad. This improves the accuracy of the electrical analysis, not the physical power design.

## Source-backed driver tradeoff evaluated on unchanged declared motors

Fixture: 2× 6-V motors, each declared 0.9-A stall current; 7.4-V nominal battery and 2200-mAh capacity. None of these are verified measurements. The sum of declared stall currents is 1.8 A; **this is not continuous motor current or pack discharge capability**.

| Driver | Reference capability | Meaning |
| --- | --- | --- |
| **L298 bipolar bridge**, current catalog candidate | ST L298 DS0218 Rev 5 table 4: total bridge drop **1.8–3.2 V at 1 A** when VS=42 V, VSS=5 V and Tj=25°C. Logic VSS 4.5–7 V. | High-loss incumbent/salvage route, *only if physically identified and power/thermal proven*. It is not a measured drop in this 0.9 A motor. |
| **DRV8833 PWP / RTY**, proposed external alternate | TI SLVSAR1E: VM operating **2.7–10.8 V**; **1.5 A RMS/DC, 2 A peak per bridge** at VM=5 V, 25°C with proper thermal design. HS+LS typical FET path listed 360 mΩ. | Lower-loss semiconductor candidate subject to board, duty and package validation; 7.4-V nominal within VM specs does not prove full-charge pack limit or correct motor terminal voltage. |
| **DRV8833 PW** smaller TSSOP package, different thermal performance | TI: **0.5 A RMS/DC continuous** per bridge under reference, 2 A peak conditional. | Do not assume it is interchangeable with PWP/RTY. Actual continuous load current and pulse duration are unknown. |

Sources:
- https://www.st.com/resource/en/datasheet/l298.pdf (p.5 electrical characteristics)
- https://www.ti.com/lit/ds/symlink/drv8833.pdf (p.1 features and p.5 recommended conditions and package thermal data)
- https://www.ti.com/product/DRV8833

**Reference loss examples are NOT a direct same-test comparison:** L298's 1-A datasheet bridge drop implies 1.8–3.2 W dissipated per bridge at *its specific* test condition; DRV8833's nominal 360-mΩ FET path would yield an arithmetic I²R term of 0.36 W at 1 A, but that is not measured board loss or a validated calculation at the identical temperature, frequency or supply. No design has been upgraded, procured or approved by these numbers alone.

## Remaining blocking facts

1. The donor controller's H-bridge identity is not conclusively an L298. The catalog `l298n` graph node is a proposed stand-in, **not a verified physical chip**.
2. The 7.4-V nominal battery is not a measured/validated 6-V motor rail. Chemistry, peak discharge, fusing, measured current, motor stall-duration and thermal behavior remain unresolved.
3. The project is not power-on authorized and the driver alternative decision is not auto-applied. Neither DRV8833 nor L298 is verified for the physical rover.
4. No real evidence that this workflow is faster or superior to Flux, Cirkit or Schemr on a **matched export and measurement standard**. Do not score vendor claims as delivered output.

## Competitive exit criteria

Collect authorized, legally exported outputs for the **identical** prompt, constraints and hardware inventory from HS and at least one alternative generator:
- Original requested quantities preserved in BOM, connectivity graph and firmware I/O.
- Authentic donor-component identity vs ungrounded substituting of standard parts.
- Number and severity of electrical ERC/DRC issues verified by an independent tool.
- Unsupported power/thermal claims; physical measurements or explicit gaps.
- Manufacturing CAD and firmware usable without missing undocumented steps.
- Engineering intervention count, total task time, cost and repeatability.
- One independent low-voltage physical demonstration with an auditable source-to-device chain.

Fail the competitive evaluation if the rival produces an objectively better final deliverable on those dimensions. No blanket quality lead until this is done.

## Local validation

- Targeted regression suite after motor/ERC and driver-alternative corrections: **55 passed**.
- All Splice UI tests: **95 passed**, Vite production build passed.
- Same-input three-project baseline/candidate raw artifact reruns confirm above results.
- Full GH workflow is the merge gate: baseline #200 Core Diagnostics had **3,580 passes / 3 failures / 187 skipped**; current branch specifically addresses those failures and adds safety tests, but final full CI must be confirmed separately.
