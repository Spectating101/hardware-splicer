# Digital assembly, operating model and reversion

These steps define the CAD assembly and local motion study. They have not been performed on hardware. The user owns no donor or components. Do not send the sample to a printer as a substitute for identifying, inspecting and validating an actual future machine.

## Identify the virtual donor

Use only the original manufacturer Ender-3 design at pinned commit `88c7758cea9d0d00a54fdb238bedb3b33425f409`. `sources/Ender-3 BOM.XLS` calls the controller1284P and bed235*235mm. The matching unmodified firmware config selects `BOARD_MELZI_CREALITY`,80/80/400steps per mm for XYZ,235mm XY limits and250mm Z. These are source facts rather than observed settings on a printer.

The manufacturer's E-plate STEP uses u=X, v=vertical and w=front normal. The main plate front is w2.5mm. The two original heating-head bosses end at w7mm. Their M3 axes are `(u,v)=(9.5,7.55)` and `(23.5,7.55)`,14mm apart. The dimensioned PDF independently labels these2*M3. Full-assembly extraction identifies the same plate by shape volume. The original nozzle axis is `(u,w)=(16.5,13.0)` and its tip v=-34.25mm. The new pen axis is `(16.5,32.2)` with selected tip v=-65mm.

## Assemble the digital conversion

1. Retain the frame, complete X/Y/Z motion system, bed, rollers, belts, switches, controller, display, motor harnesses, PSU and its enclosure. Remove the extrusion feeder/Bowden/spool components from the active plotting path and retain them in a virtual reversion kit. Retain the E plate on its original rollers.
2. Remove the original heating-unit mounting screws and fan/shroud attachment screws from the moving plate in the model. Keep the radiator, throat, heater block, nozzle, heater cartridge and hotend thermistor assembled as an intact heating unit. Its heater and thermistor connections remain in the specified original low-voltage harness. The stock bed thermistor also remains connected.
3. Insert two new M3 nuts into the rear pockets of the pen adapter. The two M3*10 mount screws pass through the6mm web into the donor M3 bosses, giving4mm nominal engagement. The web rear lies at w7mm; the main plate has4.5mm clearance except at the intended boss contacts. No donor holes are drilled. The adapter extends to v=-35mm and w32mm.
4. Place the0.5mm EPDM liner around the selected cylindrical pen. Fit the detachable cap with the two M3*40 screws through the captive nuts. The modeled open split is0.4mm. Slide the pen vertically so its tip reaches the chosen paper datum, then specify clamp retention. Tip-to-clamp distance is30mm. Grip friction, tightening torque and compliant pen force are untested; there is no spring force control in this design.
5. Place the parking plate on the front face of the retained top2020 rail. The plate frame holes are50mm apart along the rail, with M4*10 screws and two manufacturer-shape M4 T nuts. Actual CAD fit requires the nut long axis along the rail (90degree rotation from its source STEP); the independently checked placement has zero profile overlap. The parking plate is80*95*4mm, with rear M3 nut pockets.
6. Bolt the intact original heating unit to the parking plate using its existing radiator through holes: two3.2mm bores14mm apart. Use M3*20 screws and two M3 nuts, not printed threads. The parked mount centers are v=-30mm on the plate. At the represented top-rail pose, the parked nozzle tip is273.2mm above paper. Secure the original fans/shroud to the four4*12mm tie slots with four2.5mm-wide ties. The heating unit is supported by screws and the plate, never by wires. Parked fans/shroud are reference envelopes rather than a proven final restraint layout.
7. Specify a slack low-voltage harness route along the existing frame with no load on the heater/thermistor leads, no sharp bends, no contact with belts, no drag on the moving bed and no moving-wire loops in the drawing area. The source heater/thermistor/fan leads are nominally1000mm; the route has not been measured in a physical donor. The study does not validate connectors, cable lengths, temperature readings or a powered wiring configuration.
8. Position180*180mm paper centrally on the235*235mm bed. Specify thin tape outside the drawing, with a maximum1mm raised obstruction. The CAD render shows the pen at the bed center. Z raises the complete clamp and pen for travel. No extra servo, driver board or new power supply is modeled.

## Temperature and firmware scope

Unplugging a thermistor is not a valid conversion. The pinned config enables `TEMP_SENSOR_0=1`, `TEMP_SENSOR_BED=1`, `HEATER_0_MINTEMP=5`, `BED_MINTEMP=5`, `THERMAL_PROTECTION_HOTENDS` and `THERMAL_PROTECTION_BED`. This design retains both sensors and specifies an ambient temperature above5C. It does not defeat temperature protections or supply a new firmware binary. A failed, disconnected or out-of-range sensor can still stop a real controller; no boot or motion test has established otherwise.

All sample heater setpoints are explicitly zero (`M104 S0`, `M140 S0`). There are no heating waits, extrusion commands or positive heater requests. Zero commands are a software state, not physical isolation. The stock heater remains connected as part of the specified intact unit, so a separate future electrical review would be needed before powered use. No mains terminals, PSU enclosure, fuse or mains wiring are altered here.

## Operate the local digital model

Run `scripts/build.py`, then `scripts/simulate.py`, then `scripts/verify.py` using the commands in README. Inspect both PNGs and the STEP/GLB in a CAD viewer. Review the engineering and simulation JSON separately from the integrity result. Change only the four supported requirement values, regenerate all stages and compare the resulting clamp dimensions and drawing trajectory. The scripts do not open a serial connection or any physical machine interface.

The sample adopts a work-coordinate paper surface Z0. Its pen-tip XY offset is `(0,-19.2)`mm from the old nozzle in the chosen conventional bed coordinates; G-code subtracts that offset before commanding XY. The independent decoder adds it back before bed checks and drawing reconstruction. Every stroke lowers to0, draws at600mm/min, and raises to the selected2..5mm before traveling at1200mm/min. Z lift moves at300mm/min and pen lowering at180mm/min. The initial controller XY position117.5/117.5 and initial raised pen are assumptions, not a homed state. Ideal feed time excludes acceleration and settling.

The new tip is30.75mm lower than the original nozzle. Therefore the unchanged stock Z homing datum cannot be assumed usable. The virtual conversion requires a revised paper datum; a future physical design would need measured repositioning of the retained Z-limit bracket or a revised mechanical tip height, followed by independent limit and homing acceptance. This study does not generate that acceptance, bypass endstops or insert a G28 command. It does not present G92 as a substitute for a safe mechanical Z limit.

## Revert the virtual donor

1. Remove the pen, liner, cap and new adapter from the virtual E plate. Restore the original two heating-head mounting screws and fan/shroud attachment hardware from the labeled reversion kit.
2. Release the four fan retention ties, unbolt the intact heating unit from the parking plate, and return heating unit plus original fan/shroud to their manufacturer assembly locations. Do not substitute the new M3*10 or parking screws for the source factory fastener stack.
3. Remove the parking plate, its two added M4 T nuts and new fasteners. Restore the extrusion feeder, original extruder motor, Bowden tube and spool holder from the kit. Restore the original cable routing, Z-limit datum and any removed clips to the manufacturer configuration.
4. Compare the reverted digital assembly against the pinned manufacturer STEP and BOM. Both thermistors, heater cartridge, bed heater, stock fans, motor harnesses, controller and enclosed PSU remain the original specified donor components throughout. No firmware change needs to be undone. A physical reversion, if ever performed, would still require its own inspection and powered acceptance; none occurred here.
