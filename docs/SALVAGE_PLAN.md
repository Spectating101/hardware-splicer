# Take-apart (salvage) plan

The build sequence run the other way over the same retained board: `GET /v1/projects/{id}/revisions/{rev}/salvage-plan`, shown in the
Assemble tab as **Take apart**. It is a rule-of-thumb plan read from the board's file. It measures nothing and approves nothing:
the condition of every part is unknown until it is tested, and a verdict is advice about effort and reuse.

## What it gives

A safety step, then removal in a sensible order (connectors and electrolytic capacitors, then chips from easy packages to hard, then
the rest), then sorting and testing. Each part has a verdict with the rule behind it: worth taking, take it and test first, read the
marking, cheap to buy new, leave it. Parts the design marks do-not-populate have nothing to take.

## Hazards it names

Unplug and disconnect batteries and packs first. Tape exposed battery terminals separately. Do not short, puncture,
disassemble, heat or solder directly onto a cell. A swollen or damaged lithium cell is not for reuse. A holder's chemistry is
not guessed; an AA holder gets a cell warning. An XT30/60/90 plug warns that the pack may still be live.

Preparation has two tiers. On an ordinary board, including mains-side parts without the high-voltage context below,
capacitors can retain charge, including ones with no readable voltage. Discharge through a suitable resistor and use a meter
to prove zero before touching or heating. Leave a resistor across them and re-measure after a wait: voltage can come back.
If you do not know how, leave the board alone and get help.

For the high-voltage tier, preparation gives no discharge procedure. These circuits can hold a lethal charge that a hand
meter and an ordinary resistor are not made for. Leave the part in place and the case closed, and leave it to someone trained.
This tier includes capacitors marked at least 1 kV, microwave/magnetron/MOT/HV diode, CRT/anode cap/flyback transformer/EHT,
photoflash, CCFL and lamp inverter contexts, and every capacitor left in place by the voltage policy below. It replaces the
ordinary resistor and meter instructions; neither the preparation nor the skipped part advises a discharge attempt.
Unmarked film boxes and optocouplers alone do not get a CRT/microwave/lamp disclaimer.

The 100 V marking rule is a decision to leave a capacitor in place, not a claim about its present charge. It also covers kV
(converted to volts), WV, V, VAC, VDC, kVDC, kVAC, WVDC and WVAC, with or without a space, X1/X2/Y1/Y2 and HV/HVC,
high voltage, microwave or flash markings. The no-procedure tier applies to those skipped parts. Film boxes and ceramic discs without readable voltage stay
optional but warn that they might be mains safety capacitors: do not reuse them as generic capacitors or mains protection
parts. No rating is guessed. A polarised can without readable voltage warns that it could be a photoflash capacitor.

Discard bulged or leaking electrolytics; reported bulging or leaking changes the verdict to leave it. Record tantalum
polarity: reverse polarity destroys it. For supercapacitors, remove jewellery and do not short the terminals.

CRT, anode cap, aquadag, EHT, LOPT, flyback transformer, TV flyback, microwave, MOT, magnetron, CCFL, backlight,
fluorescent, mercury, cold cathode, lamp inverter, photoflash and thermal cut-off markings override the chosen kind and leave
the part in place. The spellings magnatron, magentron and magnetrons also get the microwave warning. CRT circuits can regain
charge. Do not power a loose magnetron: it is meant to run fitted to its own waveguide and cavity. No stored microwave
radiation is claimed. A fluorescent or backlight marking may refer to a mercury-containing CCFL: do not break or force it out.
Common anode, flyback diode, LED lamp, white LED lamp and lamp driver labels do not trigger CRT or mercury wording.
Heater/fuser markings apply to typed “other” or “mains or power part” entries, and to file footprint names; a resistor marked
“10k heater sense” does not become a fuser. Let heaters cool; do not power one without its original thermal cut-off.
Do not bypass a thermal fuse; use the appliance's service information for replacement.

Mains parts (transformers, relays including SRD/SONGLE, varistors, fuses and holders, inlets, common-mode chokes and wide
terminal blocks) remain optional and are never "worth taking". Capacitors nearby hold the charge after unplugging; this is not
a claim that transformers retain charge. Do not put a used MOV back on mains or rely on a used relay for mains switching.
Thermistors may be hot: let them cool. Do not rely on a used surge protector for protection.

Offline-switcher families such as LNK, TNY, TOP, VIPer and UC384x, and a MOSFET with a high-voltage marking, keep their usual
verdict with a short note that they may have sat on a mains primary. An optocoupler keeps its usual verdict but warns that
isolation depends on its ratings; a used one is not known to remain an isolation barrier. These notes approve no reuse.

When fitted parts show mains or high-voltage context, the first step names them, including parts left on the board, before any
iron work. It replaces the anti-static strap suggestion with “do not wear a wrist strap near high voltage”. Small unrelated
words such as Electronic, MOVEMENT and OnePiece do not trigger the old keyword rules. This remains a rule list: absence of a
warning proves nothing, and an omitted physical part cannot be seen by the planner. Unmarked film boxes, discs and polarised
cans also remove the strap suggestion because the voltage is unknown.

### Sources used for the hazard wording

These short excerpts are the sources cited by the independent salvage audit. Handling advice without a number is also
ordinary workshop practice; this report supplies no discharge resistor value, wait duration or approval to power anything.

- [Vishay, mains capacitors](https://www.vishay.com/docs/48251/_checklist_safety_caps_vmn_ms7357_1707.pdf): X capacitors “connect line and neutral”; Y failure can cause “an immediate danger of an electric shock”.
- [Technical Safety BC, microwave report](https://files.technicalsafetybc.ca/v3/assets/bltdec2ded849740f4d/blt4ad92d5639485f4d/64e8eef51647f96c739bce17/Appendix_A_-_Engineering_Report_-_Microwave_Safety_-_TSBC_-_Final_-_2022.11.23_Redacted.pdf): “a bleed resistor can cease to function”.
- [Rubycon FKX](https://www.bdtic.com/datasheet/Rubycon/FKX.pdf): the photoflash datasheet uses “330WV”.
- [Illinois Capacitor TTA](https://www1.futureelectronics.com/doc/ILLINOIS%20CAPACITOR/338TTA016M.pdf): “WVDC: MAXIMUM RATED DC WORKING VOLTAGE”. A printed rating reports no present charge.
- [HVC ceramic-disc series](https://www.hv-caps.com/HV-Ceramic-Disc-Capacitor/hv-ceramic-disc-capacitor163.html): source for treating HVC as a high-voltage context token.
- [IEEE IAS, stored capacitor energy](https://hallaweb.jlab.org/tech/Detectors/public_html/hall_a/miscellaneous_info/Working_Safely_With_Hazardous_Capacitors_Establishing_Practical_Thresholds_for_Risks_Associated_With_Stored_Capacitor_Energy.pdf): “voltage rebound after the initial discharge due to dielectric absorption”.
- [Desco, wrist straps around high voltage](https://desco.descoindustries.com/Articles/ESD-Around-High-Voltage.aspx): “We would not recommend grounding personnel” during high-voltage work.
- [CRT service guidance](https://www.crt-mon.com/pdf/_CRT-Data/CRT-Safety.pdf): the anode “can regain some charge even after being discharged”.
- [Panasonic microwave service manual](https://www.partmaster.co.uk/images/mediator/121/nne281bmbpq%20service%20manual.pdf): “Never operate the magnetron unless it is properly installed.” No claim is made about the ceramic material in every magnetron.
- [US EPA, lamps](https://nepis.epa.gov/Exe/ZyPURL.cgi?Dockey=P1005193.TXT): mercury-containing lamps include “fluorescent backlights in flat panel and liquid crystal displays”.
- [Cantherm, thermal cut-offs](https://www.cantherm.com/product_post_type/thermal-cut-off/): “non-resettable” and “the complete thermal fuse must be replaced”.
- [Panasonic, lithium cells](https://energy.panasonic.com/dam/master/pdf/en/psds/lithium-ion/2026/PLI-PSDS-01-EN.pdf): “Do not short-circuit, deform, throw into fire or disassemble.” “Do not solder directly onto batteries.”
- [University of Reading, swollen cells](https://www.reading.ac.uk/health-safety-services/fire-safety/lithium-battery-information/i-have-a-swollen-lithium-ion-battery-what-should-i-do): “Do not ever try to puncture the bulge”.
- [Maxwell, supercapacitors](https://maxwell.com/wp-content/uploads/2021/08/Maxwell_UC_Safety_Data_Sheet_Rev6_.pdf): “when charged and shorted, arcing may occur”; “Remove hand jewelry”.
- [KEMET, tantalum](https://content.kemet.com/datasheets/KEM_T2024_T489.pdf): “damaged or destroyed if connected with the wrong polarity”.
- [Panasonic, leaked electrolyte](https://industrial.panasonic.com/content/data/CP/PDF/news2014/en/VH_E.pdf): “combustible and electrically conductive”.
- [Vishay, optocoupler ratings](https://www.vishay.com/docs/83430/vo617a.pdf): “only within the safety ratings”.
- [Littelfuse, MOV stress](https://www.littelfuse.com/data/en/application_notes/an9311.pdf): stressed MOVs “can fail as a short circuit”.

## Stated limits

- This endpoint needs the board's file. For a physical board without one, use [typed donor capture](DONOR_CAPTURE.md) at `/engineering/donor`.
- A chip is named only as far as the file names it (its part number). Otherwise the verdict is "read the marking", never a guess.
- Whether a part still works is unknown until it is tested. A capacitor is never called good.

## Not yet

Recognising parts from a photo, prices, and the repo's functional-salvage fixtures (donor blocks with evidence gates) shown in 3D.
