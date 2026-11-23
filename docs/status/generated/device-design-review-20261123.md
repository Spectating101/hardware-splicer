# Device design review (23 November 2026)

The owner asked whether the product designs themselves are good, not only the interface. This review uses the committed models, the fit engine (`scene_fit.py`), KiCad's own checks and the digital studies' records.

Every number here is software evidence from CAD, KiCad or simulation. Nothing was built, printed, powered or flown. A proposal is not a revision until its CAD is authored and re-measured.

## 1. Pan-tilt demo: "production ready" with a board that fails DRC

**Finding.** The closed pan-tilt scenario (`examples/scenarios/closed_pan_tilt_mechatronics_project.json`) is asserted by `tests/test_scenario_runner.py` to reach:

- `production_ready_project_package`;
- `claimable: true`;
- 9 of 9 gates.

Its main controller board is `examples/main_ctrl_esp32_servo.kicad_pcb`, which HS itself generated in June 2026 (`generator hardware_splicer`). KiCad 9.0.2 DRC on that file reports 92 errors and 51 warnings, including:

- 14 shorts between nets, among them USB_D+ to USB_D- at J1, GND to VBUS at U2, and +3V3 to VBUS at U3;
- 10 crossing tracks;
- 12 clearance violations.

**Cause.** The attached `.kicad_pcb` reaches the release decision through two paths:

- `_simulate_board_design_file` in `apps/circuit-ai/src/engines/machine_system_engineering.py`: netlist compile, a power-tree solve and ngspice;
- `mechatronics_authority.py`, which counts `board_design_files`.

Neither path runs KiCad DRC on the attached board. A board with shorts therefore counts as release evidence. This is an implicit authority upgrade.

**Proposal.** When an attached board design is a `.kicad_pcb`, run native KiCad DRC on that file and block the release on any DRC error. The pan-tilt test must then stop reporting production ready until the board is fixed. That is the intended outcome. This goes in its own draft PR, separate from the device workspace.

## 2. ESP32 servo board: rerouting needed

**Finding.** The board has 23 track segments, 21 of them single diagonal runs from pad to pad, crossing other nets' pads and tracks. This is consistent with the June generator drawing connections rather than routing them. The device workspace now shows each short on the board's copper, with both nets highlighted.

**Proposal.**

1. Re-route the board, with Freerouting or HS's own autoroute path, from the same netlist.
2. Re-run KiCad DRC and ERC.
3. Replace the file only when DRC reports no errors.

Not done here: it changes a design file that other tests and the pan-tilt demo depend on. It should follow the authority fix above, so that the fix is visible as a gate turning from blocked to clear on real evidence.

## 3. Fielddeck 5-inch: 21 mm of empty air in the rear bay

**Finding.** The case is 310 × 285 × 64 mm, and its height is set by the front stack. There the 26 mm power bank (z 4–30) sits directly under the 22 mm keyboard (z 40–62). In the rear, between the top of the Pi (z 24.6) and the underside of the display (z 46.1), the bay is empty over most of its area. The contents cover 61% of the case footprint.

**Layout probe.** This is a probe, not authored CAD (`device-design-review-20261123/probe.py`):

1. Move the power bank into the rear bay. A collision search (`search.py`) found 484 clear positions. The chosen one is x 213–265, y 171–275, on the floor.
2. Lower the keyboard, display, fan and faceplates by 11.6 mm.
3. Shorten the fan duct by 11.6 mm.
4. Trim the trays by 11.6 mm.

Re-measured with the fit engine:

| | Current 5-inch | Compact probe |
|---|---|---|
| Case height | 64 mm | 52.4 mm (−18%) |
| Overall height including feet and fan guard | 72.0 mm | 60.4 mm |
| Case bounding volume | 5.65 L | 4.63 L |
| Tray wall material (solid volume) | 544.2 cm³ | 495.1 cm³ (−49.1 cm³, about 62 g of solid PETG; printed mass depends on infill) |
| Real collisions | 0 | 0 |
| Power bank clearance | touching the front-left tray nest | 0.5 mm from the rear-right tray; 5.0 mm under the display |

The probe's remaining overlaps are exactly the supports a real revision would shorten:

- the keyboard support ribs in both front trays (top at z 38 → 26.4);
- the four display bosses in the rear trays (top at z 40 → 28.4).

**What the probe does not settle:**

- the bank's ports, button and built-in cable are not dimensioned (an existing recorded blocker), so cable access from the new position is unknown;
- moving 180 g of battery rearward shifts the centre of mass;
- the bank now sits beside the Pi and the fan intake, which needs a thermal check;
- the printed retention for the bank must be re-authored.

**Proposal.** Author a "compact" layout in `author_cad.py`. Its validator deliberately rejects layout changes made only through `design.json`. Use the probe's positions, then re-run the fit engine and the study verification on the real CAD.

## 4. HS-3G-B drone: hover sits outside its measured thrust data

**Finding.**

- Mass is 234.9 g against a 250 g limit, leaving 15.1 g of margin. The +5 g scenario is simulated.
- Hover needs 58.7 g per motor. The thrust table for the T-Hobby F1404 KV2900 with GF3028-3 props on 4S starts at 50% throttle and 101.1 g. Hover is therefore at 58% of the lowest measured row.
- Every simulated mission flies on the table's quadratic extrapolation. The study's own scope limits say so, but the result reads stronger than its evidence.
- Full-throttle thrust-to-weight is 5.0. That is racing-class power for a mission airframe, which pushes hover to the bottom of the motor's range.

**Proposal.** Choose one of:

- obtain bench rows below 50% throttle for this motor, prop and voltage. This is the cheapest option and changes no design;
- choose a propulsion set whose measured range covers about 59 g per motor. A lower-KV motor or 3S would put hover inside measured data and probably save mass, but there is no data for those options yet, so the saving is not claimed.

### Update: checking the extrapolation against the propeller's own law

The maker's page ([Ligpower F1404](https://www.ligpower.com/product/f1404-fpv-motor.html)) has no rows below 50% throttle, and no third-party bench test of this combination was found. The retained table matches that page row for row.

The measured rows do follow the propeller law closely: thrust ∝ RPM^2.06, and thrust/RPM² varies by only 3.7% across the table (`hs3g_hover_rpm_law.py`). Extending that law gives:

| | Estimate |
|---|---|
| Hover RPM | about 14,370, which is 77% of the lowest measured RPM (18,626) |
| Hover power per motor | 12.0 W |
| Total hover current | 2.85 A |

The current agrees with the simulation's estimated 3.09 A peak.

Hover therefore needs a modest extrapolation in RPM rather than a guess about the throttle curve. Two things remain unmeasured:

- how the ESC maps throttle to RPM below 50%;
- motor efficiency at low RPM.

A short bench sweep at 25–50% throttle would close both. This is still a calculation, not a measurement.

## 5. What holds up

- **No real-geometry collisions in any of the five models.** The only overlaps involve stand-in shapes.
- **The SPI flash adapter is clean.** Its KiCad DRC and ERC pass, its receipt records 11 checks with none raising issues, and akcli raised 16 warnings, all schematic label placement. Of its 5 notes, 3 are label placement and 2 flag DNP parts (R1, R4) that still carry an order ID. None is an electrical fault.
- **The HS-3G-B measured size matches its study.** 155.5 × 163.6 × 74.0 mm agrees with the study's `model.json` bounds to within 0.5 mm.
