# Ordering HS-BUS-A from JLCPCB (owner's step)

Everything here is prepared; uploading and paying are yours. Quote as of 26 Nov 2026: US$106.44 for 5 assembled boards
(US$97.23 with the three basic-part swaps in `../quote_2026-11-26.json`, which this order does not apply). Re-check at
checkout: prices and stock move.

1. **PCB:** upload `../hs_bus_a_gerbers.zip`. 2 layers, 70 x 56 mm, 1.6 mm FR-4, quantity 5; the other options as offered.
2. **Assembly:** PCB Assembly on, Economic, top side, 5 boards.
3. **Files:** BOM `hs_bus_a_bom_jlc.csv`, placement `hs_bus_a_cpl_jlc.csv` (both made by `../../jlc_order_files.py`).
   Every line carries an LCSC part number; keyword-matched lines were checked against the BOM's value, rating and package.
4. **Check the placement preview before paying.** JLCPCB does not correct rotations. Look at:
   - polarity: D1 (SMBJ15CA), D2-D4 (LEDs), D5 (zener), C7 (electrolytic);
   - pin 1: U1 (FT232RL), U2, U3 (SOT-23-5), U4 (SC-70);
   - the through-hole parts and J1 (C7, J1-J5), placed at the centre of their pads, which KiCad's position file leaves out.
5. **Through-hole parts** (C7, J2-J5, J1's shell) are hand-soldered on the Economic service; the quote includes that.

Nothing in this folder has been built or tested. The board passed KiCad DRC with no errors (two silkscreen warnings) and
its own checks in `../../verification.json`.
