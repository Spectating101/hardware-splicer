# SPI Flash Adapter v1 — Remote Functional Test Plan

**Design under test:** `spi-flash-adapter-v1`, revision `0.2-modeled`  
**Initial state:** `R1` DNP, `R4` DNP, `JP1` open, `J1` disconnected  
**Permitted functional command:** read-only JEDEC ID `0x9F` only

This plan is an engineering-review input. It does not authorize fabrication or power.
The provider must stop and return the failure evidence whenever a prerequisite fails.

## Required capability

- Inspect component top markings and assembly orientation.
- Measure resistance and continuity with all sources removed.
- Apply current-limited 3.3 V and capture both DC values and rail ramps.
- Capture host- and DUT-domain SPI waveforms with an oscilloscope or logic analyzer.
- Execute the supplied read-only host utility at 1 MHz and then 5 MHz.
- Record a 60-second thermal dwell.
- Return original instrument files, not only screenshots or a PASS certificate.

## Ordered execution

1. Photograph both sides of every test article and readable markings for U1, U2 and U3.
   Record board serial, revision and any substitution or rework.
2. With all sources disconnected, check the revision-bound netlist, ground continuity,
   rail-to-ground resistance, domain isolation, R7 OE pull-down and each CS pull-up.
3. Keep `R1`, `R4` and `JP1` open. Connect common ground. Apply 3.3 V through an ammeter
   to R1 pad 2 / TP2 with a 10 mA limit. Accept 3V3=3.20–3.40 V and unloaded
   1V8=1.75–1.85 V only when the current limit does not activate.
4. Remove power and prove discharge. Fit R4 only; leave R1 and JP1 open. Repeat at a
   50 mA limit. Accept 1V8 and DUT_1V8=1.75–1.85 V. Capture startup overshoot and rail
   ramp; a DC reading alone is insufficient.
5. With JP1 open, attach the already-powered 3.3 V host, common ground first. Keep R1
   open. Configure SPI mode 0 with SCLK/MOSI low and CS high. Measure TP9, TP10 and TP16.
6. Start the host utility so it opens and configures the identified transport without issuing
   a transfer. Wait at least 20 us after DUT VCC crosses 1.7 V, then deliberately bridge JP1.
   Confirm OE high and DUT CS high, then type `ENABLED` at the utility prompt.
7. Capture both voltage domains at 1 MHz using only `0x9F`. If rails, edges or current are
   abnormal, stop. Otherwise repeat at 5 MHz for at least ten trials. Every response must
   equal `EF6018`.
8. Record ambient, U1, U2 and U3 temperature for a 60-second powered dwell. Stop on a
   rise above 10 C from ambient, current-limit activation or visible/olfactory anomaly.
9. With CS high, open JP1 before power-down. Capture decay. Before another startup,
   prove DUT VCC below 0.8 V for at least 100 us.
10. Complete the supplied evidence-return manifest with measured values, acceptance
    criteria, operator, instruments, calibration identities and SHA-256 for every raw file.

## Evidence and authority boundary

The host utility does not control power or OE and exposes no write/program/erase command.
Its JSON result is a raw execution record, not self-attested physical evidence. Provider
acceptance, Hardware Splicer evidence import and human authorization remain separate steps.
