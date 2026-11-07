# HS cyberdeck value engineering — complete architecture re-evaluation

**Date:** 2026-11-08
**Owner's goal:** one highly useful, genuinely cost-efficient **dual-touchscreen** pocketable programming device, *not* launching a consumer-electronics company. HS is also expected to prove engineering decision quality by doing a reproducible comparison. This study does **not** authorize a purchase, PCB fabrication, product launch, or battery wiring.

## Requirements and authority

- TWO independent rigid touchscreens, no built-in physical keyboard.
- SSH and remote editing of an authorized Optiplex should be productive, not merely technically possible; native Linux is preferred, not mandatory when SSH works well.
- Closed body benchmark 155 x 80 x <=18 mm, with actual mechanical and thermal fit (the 18 mm gate is preserved from HS PR #307).
- Research cost target NT$8,000 **was proposed by the assistant; owner did not separately approve it**. No fabricated purchase decisions may silently relax or lock the budget.
- Actual cost excludes marketing, brand, distribution and running a company. It DOES include full physical BOM, carrier fabrication, shipping, assembly and reasonable rework when eventually substantiated.
- Security (SSH host identity) and lithium-ion protection remain hard engineering gates.
- Source readings are Taiwan seller asks and published vendor drawings; not delivered supplier quotations. No hardware bought or tested.

## HS result

| Architecture | Taiwan source subtotal | Independent geometry and value finding |
| --- | ---: | --- |
| CM4 wireless 2GB/32GB + 2 x Waveshare 5in DSI LCD **(B)** 800x480 | **NT$6,324** | **Reject:** panel 127.7 x 87.45 mm. Bare panel is wider than 80 mm enclosure, before FDM wall. Local Waveshare price NT$1,298 each. |
| CM4 + 2 x Waveshare **4.3in DSI** 800x480 | **NT$5,724** | **Reject as-sold:** vendor reports **14.05 mm total module depth each**, already **28.1 mm** for two before enclosure or hinge. NT$998 each. |
| CM4 + 2 x narrow Waveshare **5in DSI LCD (D)** 720x1280 | **NT$8,366** | XY matches (126.9 x 70.7 mm), but price **already >8k** before carrier, battery, hinge, fabrication or other cost. DSI LCD (D) is made-to-order (lead time unknown). Full depth is not qualified; side-view drawing includes protruding driver PCB, not simply a naked 3 mm panel. |
| CM4 + 2 x thin Winstar **WF50DTYA3MNG10-000** 720x1280 | **NT$3,728 compute-only** | **Technical investigation ONLY:** panels are 127.6 x 73.3 mm x 3.45 mm, physically plausible front face; exact Taiwanese delivered panel pricing absent and no Linux panel driver / power board / two-screen touch proof. **Do not interpret NT$3,728 as the build cost.** |
| 2 x Waveshare ESP32-S3-Touch-LCD-4.3 SKU25948 + RS485 hinge | **NT$3,300 contingent for screens/MCUs** | Strongest cheap remote-terminal lab trial, no native Linux. Original HS shell **29.6 mm**, not 18 mm. Ruten NT$1,650 is mixed-variant upper ask and the cheaper iCShop NT$1,250 listing was sold out in prior HS snapshot. Actual secure SSH / dual touch / battery not verified. |
| Radxa CM5 + 2 x thin Winstar DSI | **No complete NTD module+panel quote** | HS-native PR #307 rejected 18 mm at **-0.735 mm** nominal clearance when using its FDM floor. 20 mm would give 1.265 mm research margin but violates hard 18 mm requirement. Higher computing performance isn't needed to SSH into Optiplex. |
| Intact used Galaxy S23 + external touch display | **NT$7,200 phone alone** | Strong performance-per-dollar baseline; Samsung DeX supports S23, but additional display/hub makes it an unqualified second-screen portable solution, not a pocket clamshell. |
| Intact used Fold4 | **NT$10,000 used listing** | Price/lifecycle benchmark only: flexible OLED/unknown hinge history, not the dual independent rigid-screen topology. |
| Donor extracted phone motherboard | **unquoted** | Reject as plug-and-play shortcut: OEM display interfaces and power/boot thermistors are non-generic; removing original phone erases much of its cost advantage. |

**All prices above are seller asking prices multiplied by the stated count, NOT complete manufactured-unit prices.** Source citations are directly in `candidates.json`. Manufacturer / reseller facts used: Raspberry Pi CM4 IO docs; Taiwan Meiya CM4102032 NT$3728; Meiya 5in DSI B NT$1298; RobotShop manufacturer part full dimension 127.70 x 87.45; Meiya Waveshare 4.3 DSI NT$998/14.05mm; iCShop 5in DSI D NT$2319 made-to-order; Waveshare 5in DSI D drawing 126.90 x 70.70; Taiwan mixed-variant Waveshare ESP32 SKU25948; Samsung Taiwan DeX; local Yahoo used phone adverts. Vendor documentation supports DSI0/DSI1 independently, but two SAME touch panels at once remains a required test. No camera/video to display adapter may be assumed just because it has similar connectors.

## What HS did rather than the assistant

The native reproducible `hardware_splicer.cyberdeck_architecture_value` runtime:

1. Fails closed on wrong dual-touch/keyboard constraints, absent URLs for priced items, fabricated delivered quote and ID collisions.
2. Computes **seller asking-price subtotals** and never fills unknown cost rows with zero to claim a complete product price.
3. Computes rotated full-component XY rectangles against HS's actual **1.6 mm FDM enclosure wall** in a 155 x 80 mm case (usable 151.8 x 76.8).
4. Screens two unmodified full display-module depths against the 18 mm closed envelope, separate from fragile bare-panel assumptions.
5. Loads actual **PR #307 native MechanicalFit output** for the CM5 candidate and checks the same hard limit before reusing its result.
6. Uses canonical HS **MachineProject** authority checks; every candidate retains planned but **unexecuted** real device fit/thermal/power/SSH/serviceability/cost tests. None can pass build or use authority.
7. Preserves a commercial-engineering decision without injecting any product company, marketing, sales or distribution requirement.

The computed decision: **no verified, source-priced Linux architecture meets both the pocket geometry and NT$8k target.** CM4 + bare narrow panel is the **highest information-gain unquoted study**, not a selected design or cost win; the dual ESP32 is the cheapest plausible remote terminal software trial but not a native Linux PC nor proven ≤18mm. Current CM5 package remains no-go.

## Most efficient next move (no large parts purchase)

**Software / electrical first**: on documented existing CM4 IO schematics, map DSI0/DSI1 and separate I2C/touch lines; request a vendor-confirmed concurrent 2-panel pairing and a complete thin-panel driver/backlight/FPC quotation. For a stronger real product, require an interactive 30-minute remote code-editing test: SSH known-host verification, tmux Ctrl-B/Esc/Tab/arrow combos, code navigation, keyboard layout, reconnect and latency. First test via an existing tablet/phone display or borrowed dev kit before procuring a second panel.

**Mechanical second**: if the panel supplier proves reliable dual displays, measure the actual module including connector, protection, heat spreader and FPC hinge bend. Print a cheap 155 x 80 x 18 dummy from HS geometry and test pocket fit/comfort. Use native 3D step/orientation outputs rather than unsupported AABB assumptions.

**Cost third**: obtain real Taiwan delivered quotes for screen pair, carrier PCB+assembly, battery/charging, enclosure/hinge, shipping; reject if the total is uncompetitive without an obvious functional advantage.

No buying two displays, custom PCB fabrication or placing a battery into this shell until these gates close.

## Reproduce

```bash
PYTHONPATH=src python3 -m hardware_splicer.cyberdeck_architecture_value \
  --candidates examples/cyberdeck/architecture_value/candidates.json \
  --out examples/cyberdeck/architecture_value/hs_decision.json
PYTHONPATH=src python3 -m pytest -q tests/test_cyberdeck_architecture_value.py
```

Outputs: `hs_decision.json` and `tests/test_cyberdeck_architecture_value.py`. All source-linked item identities, price kinds, availability qualifiers, unknowns and machine-release authority records retained for further R&D.
