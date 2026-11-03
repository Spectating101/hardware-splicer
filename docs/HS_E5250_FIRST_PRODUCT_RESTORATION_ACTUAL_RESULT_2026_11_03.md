# First real product restoration dossier — actual result (NOT a pass)

**Case:** Dell Latitude E5250. [Technician's original source (October 5, 2026)](https://sorinelectronics.co.uk/dell-laptop-not-charging/). [Linked repair video](https://www.youtube.com/watch?v=fi-Vt34Al_A). Source evidence is an outside technician's report, not HS instrument records.

**Execution:** Actual unchanged Circuit-AI from PR #272 ran at five chronological stages, in [GitHub Actions run 41661880816](https://github.com/Spectating101/hardware-splicer/actions/runs/41661880816). [Exact raw generated dossier ZIP](https://github.com/Spectating101/hardware-splicer/actions/runs/41661880816/artifacts/13241533294).

| Source progress | What HS actually ranked first | Supported by the technician's later findings? |
| --- | --- | --- |
| T0: adapter 19.9 V unloaded but LED shuts off on connection | `battery_charge_path_fault` | No demonstrated battery fault; source points to high-load/shorted input stage |
| T1: ~2.3 A reported under board rail collapse; short persists after jack removed | `battery_charge_path_fault` | No; high-current downstream input rail short |
| T2: source isolates ceramic capacitor, false-hot current sense resistor | `battery_charge_path_fault` | No; reported input-rail capacitor short |
| T3: capacitor replaced, board 19.9 V/40 mA, button 3.3 V, still no boot | `laptop_usb_c_port_or_input_path_fault` | No; input rail recovered, new boot-state issue |
| T4: source reports RTC disconnect state changed startup | `laptop_usb_c_port_or_input_path_fault` | No; RTC/BIOS startup-state dependence is more relevant |

**Result:** HS kept `assistive_only` and blocked physical repair approval at all five stages, but **failed the actual root-cause evidence transitions**. Its top hypothesis was incorrect or failed to reflect the available physical evidence at each stage. These are **retrospective**, source-replayed observations: no numerical prospective diagnosis accuracy can be calculated.

## Actual product progress reported by original repairer

The technician reports the input short disappeared after removing a specific ceramic capacitor, a replacement capacitor from older MacBook donor stock, later 19.9 V board input and ~40 mA idle draw, a separate RTC/BIOS boot-state issue and Windows startup to BitLocker prompt. HS itself measured **zero** voltages/currents and physically replaced **zero** parts.

- **Source-reported partial functional acceptance:** 3/8 (input rail, BitLocker prompt, repeat power cycles).
- **Unproven:** safe battery charging/charge-discharge cycles, thermal runtime, all peripherals after full reassembly, RTC time retention, authenticated data access/customer sign-off.
- **HS-independent physical acceptance:** 0/8. Return-to-use, profit and resale claims: **blocked**.
- **Part procurement:** blocked. Capacitor value, dielectric, voltage derating, footprint and exact board position are unknown. No exact replacement BOM or economically defensible repair margin.

## Model-specific manufacturer reference (NEW)

The [Dell Latitude E5250 official owner's/service manual — removing coin-cell battery](https://www.dell.com/support/manuals/en-uk/latitude-e5250-laptop/dell_latitude_e5250_bdw/removing-the-coin-cell-battery?guid=guid-860392b1-5fff-4887-8f88-a91f9b86bec6&lang=en-us) describes service access, the required prior power isolation, base-cover/main battery removal and the RTC coin-cell connector. A [model-specific Dell manual for removing main battery](https://www.dell.com/support/manuals/en-my/latitude-e5250-laptop/dell_latitude_e5250_bdw?guid=guid-5b33dfcb-c074-4963-9582-689a96129261&lang=en-us) is also available. These support a **safe model-specific disassembly plan**, not the failed MLCC's unknown component rating or a live/hot RTC reconnection. The original technician's dangerous flammable-solvent and energized RTC reconnection methods are expressly NOT prescribed by HS.

## Engineering changes to make next (product capability, not a benchmark score)

A useful repair system should maintain **evidence-linked electrical state** rather than continuously choosing a stock battery/port template. An input current-protection trip with known unloaded supply must move diagnosis toward adapter-versus-board loading; short persisting without jack must exclude jack; confirming a shorted capacitor must isolate component pending ratings; recovered 19.9 V with no boot must open a *separate* boot-state diagnostic; RTC-disconnect dependence must not stay pinned to USB-C.

Implementation should attach cause/discriminator/measurement provenance to each state transition, **not grant hardware authority from heuristic text**. The E5250 case may be used for *development after failure was exposed*, but then it is NOT an untouched validation example. Future acceptance requires a fresh external real product case and ultimately a physical technician pilot with measured equipment.

This is the milestone: a traceable sourced repair episode that exposes what HS actually misses, instead of collecting more synthetic 13/13 scores.
