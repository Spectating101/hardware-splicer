# HS universal compute carrier — feasibility verification (Nov 7, 2026)

**Result: achievable design methodology, real reference hardware available; NO new routed HS motherboard yet.**

The target is **one standardized product-side hardware contract** with multiple
**electrically separate compute adapters**. It is **not** a bare Snapdragon
processor replacement, and CM4 / CM5 physical size or connector pitch is NOT
proof of pin compatibility.

## Actual reusable upstream design artifacts

- **Radxa official CM4 module:** RK3576(J), 4× Cortex-A72 + 4× Cortex-A53,
  55×40mm, three 100-pin 0.4mm B2B connectors. Official product/spec:
  https://docs.radxa.com/en/som/cm/cm4
- **Radxa official CM5 module:** RK3588S2, 4× Cortex-A76 + 4× Cortex-A55,
  approximately 55×40mm, three 100-pin 0.4mm B2B connectors. Official specs:
  https://docs.radxa.com/en/som/cm/cm5
- **Official editable CM4 and CM5 IO carrier PCBs / Altium / PADS / OrCAD**
  are actually distributed at pinned
  `radxa/radxa-som-projects@cf5a4b1984fb4321233d2439320bcaea05af4817`:
  [CM4 source](https://github.com/radxa/radxa-som-projects/tree/cf5a4b1984fb4321233d2439320bcaea05af4817/cm4/radxa-cm4-io-board),
  [CM5 source](https://github.com/radxa/radxa-som-projects/tree/cf5a4b1984fb4321233d2439320bcaea05af4817/cm5/radxa-cm5-io-board).
  Those files constitute genuine manufacturer baseline engineering; check
  the exact reuse license/permission and revision for any derivative PCB.
- Independently available **MIT-licensed KiCad symbol, footprint and 3D**
  by `swdee/radxa-cm4-kicad` and `swdee/radxa-cm5-kicad`; the author notes
  **three-symbol units** and the third 100-pin section is numbered **201–300**
  rather than 1–100, hence the **minus-200** translation when comparing.
  The author reports mechanical fit of the footprints; HS has **not**
  revalidated those geometries.

These upstream resources should be reused, not reimplemented. However, the
presence of KiCad files is not proof that HS currently supports high-density
0.4mm connector routing, impedance-matched HDMI/MIPI, the PMIC reference
design or power-on sequencing.

## Upstream metadata quality incident (important)

Radxa also publishes an **agentic hardware database** in that same official
repository. Inspection of the pinned source found:

1. `hardware-db/boards/cm4/board.json` has **soc=RK3676(J)**, at odds with
   official RK3576. This is a source metadata error.
2. CM4 and CM5's `pinout.json` have **the identical Git blob SHA**
   `2409a522324d6e816fb30338d198d125ec7615fe`; many contacts are
   named `PIN_5`, `PIN_6`, etc and assigned `voltage=unknown`. These are
   **unresolved placeholders** rather than validated cross-module net
   comparisons.
3. Both `power.json` share blob SHA
   `34ec212483a5dc1cea07f04819d3821ea8ca80d9` with `unknown` input
   voltage, connector, and null power draw.

**Do not let auto-ingested database records authorize an actual PCB.**
Correct manufacturer pinout XLSX, IO carrier schematics and board revision
must override such placeholder graph data. HS gate stores source hashes and
reports provenance conflicts explicitly.

## Confirmed hazard: one socket is not universal

Radxa's [CM5 FAQ](https://docs.radxa.com/en/som/cm/cm5/faq) warns that on
an **older CM3 carrier**, third-connector pins **94/96/98** may carry 5V,
whereas CM5 uses GPIO. Moving the module without rewiring may damage it.
Radxa separately warns CM3J and CM5 are not direct substitutions.

These concrete warnings are **for CM3 and CM3J**; they do NOT prove that
CM4 necessarily has the same contact conflicts. **CM4↔CM5 remains UNVERIFIED**
until actual vendor XLSX contact-by-contact and schematic net comparisons.
Never infer safe pin matching just from both being 3×100 B2B modules.

## Practical architecture for HS

**Common device board:** interchangeable keyboard, trackpad/touch, display,
ports, housing, power protection and thermal management defined at the
**functional interface level**. This need not be one universal 300-contact
socket; a common connector or cable system may be chosen after electrical
validation. Separate adapters translate a module's voltage domains and
data links to the common device board:

| Adapter | Compute subsystem | What must actually be proven |
|---|---|---|
| CM4 adapter | RK3576 module + vendor-origin carrier design | exact CM4 pin map, boot power and termination, HDMI+USB/keyboard, thermal |
| CM5 adapter | RK3588S2 module + separate official carrier design | independent CM5 pin map, PD/USB, display routing, power, thermal |
| Salvaged phone sled | intact functional S21 subsystem | original OEM screen / safe regulated power, boot unlock and USB video, firmware support; never naked SoC |
| Other donor | e.g. certified smartphone/mini-PC board | individually proven feature/voltage/mechanical map, no invented equivalence |

Use **USB HID** for the keyboard first and the compute module's already
validated **HDMI/native display** output on a suitable carrier. Start with
an approved external 5V/12V bench supply for that specific IO board; do not
assume every compute family has the same voltage input. The common power
bus must be scoped/approved only after exact module regulator needs are
known. Integration of internal Li-ion is a separate safety program.

**Suggested fabrication strategy:** demonstrate each candidate on its
**official reference carrier** with the intended USB keyboard, screen and
Linux first. Then remove unused reference-board circuits and rerun full
pin, ERC, layout, DRC, signal-integrity, thermals, power and real boot tests.
This is a radically safer and cheaper engineering path than designing a
new 300-pin high-speed motherboard from arbitrary AI suggestions.

## What HS already has / lacks

Inspected HS's `pcb/kicad_serializer.py`, `pcb/module_registry.py`,
`pcb/safety_rules.py`, circuit synthesis IR, and existing KiCad
DRC/sidecar machinery. HS has real netlist and conventional module safety
capabilities, but its default PCB serializer has generic
**2-layer geometry** and a **2.54mm header footprint fallback**. Neither
proves correct 0.4mm 3×100 B2B footprint integration nor controlled-
impedance differential pair design. The manufacturer board should remain
source of truth until a full adapted design has been validated.

The new
`src/hardware_splicer/compute_carrier_reference_gate.py`
and `scripts/hs_compute_carrier_gate.py` expose a machine-readable fail-closed
report including these exact source conflicts, hazards and required next
verification work. The current result is **reference resources located /
research-only / not safe to fabricate or hot swap**.

**Economic caution:** a fresh RK3576/RK3588S module plus carrier, custom
screen and battery is not yet shown cheaper than a functioning used phone
(see PR #298). *Standardization* reduces engineering repetition and
improves serviceability; it does not automatically beat donor pricing.

**Next proven milestone:** pin the official CM4 and CM5 XLSX pin maps,
derive complete contact-level reports against the separate source
schematics, import one official carrier into an HS-supported ECAD workflow
without lost nets, then run independent ERC/DRC. Until then, this is not
a fab-ready KiCad project.


## Standard form factors and the cost test (additional verified sources)

- **SGET SMARC:** genuinely industry-specified **314-contact edge connector**,
  82×50mm or 82×80mm modules; multi-vendor swap opportunities, but each
  generation's supported features, power rails and thermal envelopes still
  require checks. Source: https://sget.org/standards/smarc/ . This is a
  credible alternative to a **Radxa-only high-density socket** where long
  lifecycle/replacement suppliers matter more than enclosure size.
- **SGET OSM:** standardized much smaller **solder-on BGA compute modules**.
  Attractive for production but **not field hot-swappable**. Source:
  https://sget.org/standards/osm/ .
- **Official CM5 dimension discrepancy:** CM5 product marketing states
  56×41mm (https://radxa.com/products/cm/cm5/), while CM5 docs indicate
  55×40mm (https://docs.radxa.com/en/som/cm/cm5). Actual vendor 2D/3D CAD
  and revision are mandatory, and HS records a blocking `vendor_dimension_reference_conflict`.
- **Real Taiwan price floor:** iCShop offered Radxa CM4 RK3576
  **4GB/32GB at NT$4,200**, but the listing is currently **sold out**:
  https://www.icshop.com.tw/products/368030502344 .
  The product page has an inconsistent introductory paragraph saying
  8GB/64GB; title/spec section says 4GB/32GB. Supplier qualification is
  necessary. This **module alone is more expensive** than the NT$1,600
  damaged S21 whole-phone example in PR #298, and the custom carrier,
  display, power and enclosure are additional costs.

**Engineering conclusion:** build a first *reference-carrier-based prototype*
for deterministic I/O, not claim a cheap new SoC. HS's best advantage is
integrating open carrier designs with donor-first sourcing and evidence gates.
For volume, benchmark actual delivered parts and recoverable yield before
selecting between a vendor SoM, SMARC, solderable OSM, or recovered complete
phone subsystem.
