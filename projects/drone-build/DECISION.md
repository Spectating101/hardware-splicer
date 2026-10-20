# HS drone build — engineering decision, 2026-10-20

**Persistent user objective:** engineer an affordable and useful drone from obtainable components. This is an ongoing engineering project, not a benchmark or a forced kit build. See [frozen mission](../../docs/HARDWARE_SPLICER_MISSION_FREEZE.md).

## Decision: use the X500 V2 as a control design, not necessarily as the final build

The Holybro X500 V2 Pixhawk 6C development kit is the currently best-documented **reference architecture**, not an approved purchase or proven lowest-cost choice. Keep a parallel mixed-component path (S500 frame + alternative electronics + sourced powertrain) for potential lower cost or more fabrication learning. A practical custom design must outperform the integrated baseline on useful metrics or justify its additional engineering effort.

| Architecture | Known quoted starting price (USD) | Known deficiencies |
| --- | ---: | --- |
| Pixhawk 6C + X500 V2 development kit | $579 | Battery, RC and operating equipment, shipping and taxes extra; live stock and variant must be confirmed |
| X500 V2 ARF plus controller | $260.99 | ARF is currently listed as sold out; controller, power module, GPS, radio/control, battery missing |
| X500 V2 bare frame | $122.99 | Nearly entire electronics and propulsion stack still needed |
| Community S500 frame + donor electronics | Unknown | No verified material cost, printable mass/fit, flight firmware or propulsion BOM |

Manufacturer sources: [development kit](https://holybro.com/products/px4-development-kit-x500-v2?variant=43018371530941), [frame and ARF variants](https://holybro.com/collections/multicopter-kit/products/x500-v2-kits). The displayed price for the Pixhawk 6C development-kit variant is $579, distinct from the $669 Pixhawk 6X variant. Figures are point-in-time listings, not purchased or Taiwan landed prices. Never compare the $122.99 frame price against the $579 full kit as though both were complete drones.

## Engineering decisions already grounded

- Existing reference PX4 assembly includes the exact X500 power and controller integration sequence; the manufacturer specifies 500 mm wheelbase, 16×16 and 19×19 mm motor mount patterns, and a 4S 3000–5000 mAh battery recommendation. The product page's advertised approximately 18-minute flight time is **manufacturer-specific**, not a calculated or verified estimate for a custom build.
- An alternative S500 airframe *might* fit a Pixhawk-based system with a measured mounting plate, but source CAD, physical dimensions, arm geometry, propeller clearances and vibration isolation need geometry and loading checks. A claimed reference-frame incompatibility does not establish impossibility.
- The custom STM32 controller project requires a firmware and electrical redesign, not a simple board swap. Previous KiCad audit found 364 schematic and 74 PCB-rule findings in the local setup; some are missing library configuration, while others require actual design review. It is not accepted as production-ready.
- None of the candidate donor ESCs or propellers is sufficiently characterized to authorize connection or assembly.

## Next tangible outputs, not additional benchmarks

1. **Baseline geometry:** obtain, inspect and check real X500 CAD geometry; locate mass and mounting details, record actual interface dimensions. The existing source page links the manufacturer's downloadable CAD.
2. **Alternative design proposal:** choose and source a realistic hybrid build; supply exact donor geometry, components and documented specs. Calculate whether the adapter, wiring and motor/prop combination are physically and electrically workable.
3. **Cost and performance comparison:** complete vendor quotes and a real propulsion/mass calculation. Reject any claim of lower cost or adequate thrust where inputs are missing.
4. **CAD and wiring deliverables:** generate and independently inspect any required mounting adapter and the revised pin/connector map; run applicable KiCad and mechanical checks.
5. **Simulation, then supervised physical verification:** select tested PX4 configuration and exercise SITL; physical assembly, powered tests and flight require separate safety/operational approval.

**Current state:** reference architecture documented; economic choice remains provisional, hybrid design not fabricated or independently verified; no parts purchased and no flight authorization.
