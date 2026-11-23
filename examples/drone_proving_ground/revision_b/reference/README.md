# HS-3G-B candidate build package

This is a revised digital design for the same GPS/analog-FPV quad. No hardware was built, powered or flown. Purchase, fabrication and flight are not authorized by this package.

Native model checks: 15/15; failures: []. Independent acceptance is recorded separately in `verification.json`.

## Revised configuration

Four F1404 KV2900 motors, Gemfan PMPC3028-3 1.5 mm props, CNHL 85704G 850 mAh 4S factory-XT60 battery, matching 12AWG supply lead, and the retained SpeedyBee F405 Mini stack. GPS, receiver, camera and analog VTX remain in the BOM.
The frame has a 137 mm diagonal, 2.01 mm bottom plate and 1.02 mm top plate. Native CAD selection tried: [{'wheelbase_mm': 135.0, 'measured_mass_g': 234.76, 'min_prop_clearance_mm': 2.38, 'failed_checks': ['prop_radial_clearance']}, {'wheelbase_mm': 137.0, 'measured_mass_g': 234.9, 'min_prop_clearance_mm': 3.34, 'failed_checks': []}].

## Quantitative result

- Modeled takeoff mass: 234.90 g, including a 12 g wiring allowance. Nominal reserve to 250 g: 15.10 g. The named +5 g battery uncertainty leaves 10.10 g for other unmodeled mass. Weigh the entire finished aircraft.
- Manufacturer bench-table full-command current: 25.8 A total. A square-law voltage sensitivity assumption and 20% design factor give 31.24 A. Pack nameplate continuous rating: 59.5 A; connector rating: 35 A under its stated 12AWG/temperature-rise test conditions. Verify real sag and temperatures; these calculations are not thermal qualification.
- Full-command thrust: 1179.9 g; T/W 5.02 at modeled mass. Hover duration estimate: 11.4 min; extrapolated below the source table, not measured endurance.
- Static minimum prop radial clearance: 3.34 mm. Strap: 10 x 200 mm; required modeled wrap including overlap 176.02 mm. Battery envelope uses the conservative 62 x 33 x 33 mm interpretation of conflicting maker dimensions.
- BOM snapshot subtotal: US$346.91, including two batteries and two prop packs. Some prices and the cutting allowance are retained estimates, not current quotes; freight, tax, tools, radio and goggles are excluded.

## Manufacturing sequence

1. Confirm actual motor dimensions and usable M2 thread depth, battery envelope and controller revision/stock before ordering or machining.
2. Obtain a composite shop quote for `cutter_blanks/*.dxf` and the separate post-drilling operation. These blanks omit all 16 M2 motor holes; their minimum holes and webs pass the cited cutting screen.
3. After measurement and shop review, locate the 16 post-drilled 2.2 mm holes using `POST_DRILL_COORDINATES.csv` and the stack-hole datum. The SVG is 1:1 in millimetres; verify its 100 mm calibration line. A printed sheet does not establish machining accuracy.
4. `finished_geometry/*` describes the final drilled parts. It still fails the waterjet-only motor-hole/web rules, intentionally: those small features belong to a separately qualified drilling process. Do not submit that DXF as the cut blank.
5. Review the computed fastener stack-up in `results.json`: M2x5 motor screws have 2.99 mm nominal engagement; the actual safe thread depth remains unmeasured. Stack screws are M3x30. Use the retained M3x30 standoffs and 5 mm stack spacers.
6. Place the battery crosswise under the bottom plate at modeled x=0.84 mm, then adjust from actual balance measurements. Install GPS/receiver/FPV equipment, capacitor and strain relief. `ASSEMBLY_ENVELOPES.step` contains the editable frame and component placement envelopes, not detailed vendor solids or verified mounts.

## Firmware and wiring

`firmware/evidence.json` pins the official INAV 9.1.0 SPEEDYBEEF405MINI HEX, source commit and SHA-256 values. HS verifies the upstream binary; it does not claim to have compiled or flashed it. Upstream source files and licence accompany that evidence.
`firmware/REVIEW_ONLY.cli` is a source-checked partial starting configuration, not a tuned or flight-ready profile. Use `WIRING.csv` to review UART1 receiver/CRSF, UART2 GNSS and I2C compass; UART4 remains reserved for onboard Bluetooth. Confirm VTX protocol before allocating UART3. Complete mixer/motor mapping, receiver/GPS setup, calibration and failsafe with the actual hardware.
No electrical calculation relies on INAV throttle scaling: its mixer can add attitude corrections after scaling, and digital output is mapped to the protocol range. The revised hardware is sized against the full-command table instead.

## Remaining acceptance work

The thinner laminate and post-drilled pads need shop and structural review. Beam/arm resonance sensitivity is reported in `results.json`; measured vibration and deflection data are still required. Qualify polarity, isolation, current-sensor calibration, supply sag, lead/connector/motor heating and whole-aircraft mass before any authorized powered test. Verify controls, compass/GNSS and failsafe before considering supervised flight.
The maker marks the selected controller discontinued. The input file records a dealer stock lead; actual stock, shipping and board identity must be confirmed. This blocks a ready-to-purchase claim.

The retained build-versus-buy study favors a commercial GPS BNF on cash cost. This candidate is chosen to advance the editable engineering/operator objective; it is not a claim to be the cheapest way to acquire a flying drone.

## Source trail

- motor: https://www.ligpower.com/product/f1404-fpv-motor.html (2026-11-16)
- motor: https://www.ligpower.com/images/202408/091723192759157166.jpg (2026-11-16)
- prop: https://www.gfprops.com/products/gemfan-windancer-3028-3.html (2026-11-16)
- battery: https://chinahobbyline.com/collections/cnhl-softcase-lipo-battery/products/cnhl-ministar-series-850mah-14-8v-4s-70c-lipo-battery-with-xt60-plug (2026-11-16)
- frame_cut: https://sendcutsend.com/materials/carbon-fiber/ (2026-11-16)
- Connector rating: https://atta.szlcsc.com/upload/public/pdf/source/20240904/A35598E9EA0595B0DBCDE5A44329EFC0.pdf
- All supporting values, scope limits, source hashes and assumptions: `results.json`, `inputs/` in the revision source, and `verification.json`.
