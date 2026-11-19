# Physical readiness and fabrication HOLD — HS witness v0

**Verdict: HOLD.** A clean KiCad ERC, zero-unconnected-pad PCB DRC and passing ngspice / INA228-register fixture are **not** assembly validation or authority to power on.

## Blocking items (must be resolved with actual physical evidence)

| ID | Blocker | What closes it |
|---|---|---|
| PHY-01 | No parts or board actually assembled or measured | Exact BOM, as-delivered identification and inspected assembly |
| PHY-02 | Vishay 4-terminal WSK2512R0100FEA Taiwan stock zero; no approved replacement | Exact same four-terminal/shunt pad geometry, rating and tolerance, independently inspected |
| PHY-03 | INA228 carrier rev/shunt true tolerance and shunt power rating unknown; guide says 0.1%, schematic elsewhere said 1% | Actual manufacturer revision/part evidence and independent calibration against selected reference |
| PHY-04 | No DC-qualified fuse-link selected or prospective fault-current analysis | Compatible fuse-link DC interrupt rating and full source/connector/fuse fault coordination review |
| PHY-05 | No actually isolated current-limited source, earth topology or I2C host chosen | Named source, current-limit behavior, measured isolation/common-mode and fault handling |
| PHY-06 | No high-side differential reference instrument or independent logger | Actual exact reference channels, high-side rated inputs, timestamp pairing, native exports, calibration and uncertainty |
| PHY-07 | Mechanical and thermal of screw terminals, load mounting, shunt, cables uninspected | Mechanical drawing/fitted enclosure, standoffs, load thermal mounting, cable strain relief and temperature checks |
| PHY-08 | No independent operator or genuine recorded bench run | Controlled, permitted physical commissioning with true source identity and independent repeat |
| PHY-09 | This 5 V fixture has no authority for 24 V / 120 W | New higher-power design with independently reviewed ratings, protection and measured validation |

## Hardware selection ledger

- **Adafruit INA228 #5832**: real product with onboard 15 mΩ current shunt; separate external board, not fabricated into this PCB. A J3 open circuit is an intentional *carrier insertion* connection. Adafruit board VBUS-to-VIN+ jumper stays open so separately sensed VBUS observes J2 after BOTH shunts. Real carrier MUST match those pin labels.
- **Vishay WSK2512R0100FEA**: 4-terminal 10 mΩ ±1%, 1 W. Footprint KiCad 4 pads, verified in generated board. Taiwan distributor reports no stock in current listing. No substitution without actual four-pad equivalence.
- **Phoenix Contact 1715022 (5mm pitch 2-way)**: candidate for J1, J2 and J3. Exact geometry must be verified to native KiCad footprint prior to assembly.
- **SCHURTER 0031.3551**: candidate capped 5×20 mm PCB fuse holder (straight pins). **No fuse-link yet.** Holder's 250 VAC catalog rating does NOT establish a suitable fuse cartridge DC interrupt rating.
- **External load**: 10 Ω, ≥10 W (part and insulated mounting unselected). Simulation's `R_FUSE=0.05Ω` is a modeling assumption; nominal contact DCR of holder + fuse is NOT established.
- **External reference**: not selected. J5/J6 separate header networks are not independent measurements by themselves.
- **External source and I2C**: not selected. Optiplex has no identified suitable laboratory USB power meter; its internal /dev/i2c-* adapters are **not** an invitation to probe motherboard buses.

## Status boundary

| Layer | State |
|---|---|
| Editable schematic, netlist, PCB | Built in software |
| KiCad9 ERC, PCB DRC, netlist/pad agreement | Pass |
| Candidate Gerbers, STEP bare-board shape | Exported for review; **hold fabrication** |
| SPICE steady-state equivalent | Pass mathematically under assumptions |
| Actual HS INA228 decoder run | Run against **fake I2C registers**, not a sensor |
| Policy Lab PLRS-6 receipt | `TEST_FIXTURE_STRUCTURALLY_INGESTED_NO_PHYSICAL_CLAIMS` |
| Hardware procured or constructed | No |
| Calibration / actual independent reference capture | No |
| Operator energization / power-on | Not authorized |
| Real-world research statement | Not established |

**Stop condition:** If the selected part dimensions, pin naming, breakout shunt, power fuse or reference instrument are incompatible, revise schematic and PCB and repeat ERC/DRC. Never silently reclassify the candidate as safe/fabrication-ready because an electronic check returns zero violations.
