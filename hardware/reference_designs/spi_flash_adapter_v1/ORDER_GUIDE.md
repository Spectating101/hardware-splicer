# SPI flash adapter v1: prototype order

Prepared **2026-11-15**, revision **0.2-modeled**, KiCad **9.0.2**.
Order five bare PCBs from JLCPCB and assemble one first, or use the partial SMT
assembly files below. This is a first-article package: no board has been built or
powered. The CAD verifier's existing authority flags remain unchanged; exporting
manufacturing data does not constitute EE sign-off or physical proof.

## Regenerate and identify the order

From this directory, with KiCad 9 and its system Python installed:

```sh
/usr/bin/python3 verify_design.py
/usr/bin/python3 export_fab.py
cd fab && sha256sum -c SHA256SUMS.txt
```

`fab/` is checked in. Regeneration reads the routed, filled PCB; it does not reroute
or modify the CAD. `manifest.json` binds the PCB, schematic, project, procurement
BOM, exporter and procedures by SHA-256. The Gerber/drill header epoch and ZIP
timestamps are fixed for reproducibility; they are not measurement or sourcing dates.
Archive this manifest and the exact uploaded ZIP with the private order record.

## Board options

| Option | Choose |
| --- | --- |
| Material / layers | Rigid FR-4, 2 layers |
| Size / quantity | **90.00 × 50.00 mm**, 5 individual boards, one design |
| Thickness / copper | 1.6 mm, 1 oz outer copper |
| Finish | Lead-free HASL for lowest cost; ENIG optional for easier fine-pitch soldering |
| Mask / legend | Green mask, white silkscreen |
| Vias | Standard through vias, tented where the supplied masks cover them; no filling |
| Special processing | No impedance control, castellations, edge plating, blind/buried vias or V cuts |
| Testing | Flying-probe electrical test enabled |
| Panel / stencil | Single boards; no customer panel. No stencil for hand soldering |

The design uses 0.15 mm minimum track neck-down, 0.20 mm clearance and 0.30 mm
minimum via drill. Four **3.2 mm non-plated** M3 holes are mechanical features.
The drill set has **20 plated 0.30 mm vias, 8 plated 1.00 mm header holes and
4 non-plated 3.20 mm mounting holes**. Ask the fab to preserve that distinction if its import
does not infer it. For PCBA, let the fab propose tooling rails/fiducials; none are
provided as a customer panel, and a provider panel must be reviewed before payment.

## Upload and preview

1. Upload **only** `fab/spi_flash_adapter_v1-jlcpcb-gerbers.zip` to the PCB quote.
   It contains nine Gerbers and two separate Excellon drill files, at the ZIP root.
   The naming follows [JLCPCB's layer table](https://jlcpcb.com/help/article/gerber-files-preparation):

   | Extension | Layer |
   | --- | --- |
   | GTL / GBL | Top / bottom copper |
   | GTS / GBS | Top / bottom solder mask |
   | GTO / GBO | Top / bottom silkscreen (bottom is intentionally empty) |
   | GTP / GBP | Top / bottom paste (bottom is intentionally empty) |
   | GKO | One board outline |
   | -PTH.XLN / -NPTH.XLN | Plated / non-plated metric drills |

2. Check that the preview detects **two copper layers**, a single closed rectangular
   90 × 50 mm outline, four corner mounting holes and no duplicate outline. Copper
   fills must appear on both sides. Check drill holes align with header pads and vias;
   there must be no global shift, mirror or 25.4× unit error. Inspect U1's 0.65 mm
   pitch pads for mask clearance, exposed test pads and readable J1 pin-order text.
   Paste is stencil data, not another copper layer. An empty bottom paste/legend is normal.
3. For bare boards, leave assembly off. Buy all fitted BOM parts and solder one board,
   leaving **R1/R4 absent** and **JP1 without a shunt**. Use the exact U1/U2/U3 packages.
4. For partial assembly, select **top side only**, quantity 2 assembled out of 5 if
   offered (otherwise quote 5). Upload `fab/JLCPCB_BOM.csv` and `fab/JLCPCB_CPL.csv`.
   These follow the documented [BOM](https://jlcpcb.com/help/article/bill-of-materials-for-pcb-assembly)
   and [CPL](https://jlcpcb.com/help/article/pick-place-file-for-pcb-assembly) formats.
   There are **6 BOM lines and 13 placements**. All are on Top. Coordinates are in mm,
   KiCad absolute/Gerber frame (+Y up, so these Y values are negative), with unmodified
   KiCad rotation modulo 360. No supplier-specific rotation correction is assumed.
   Paste Gerbers follow the full PCB pad artwork, including unpopulated pads. Tell
   the assembler to omit paste at R1/R4 and at hand-soldered C2 when preparing its
   assembly stencil; no solder bridge may replace an absent link.
5. Match every assembly MPN and package to `BOM.csv`; do not accept an automatic
   substitute. Inspect the placement preview against KiCad with F.Fab/pad numbers:
   **U1 pin 1 at (142.1375, 86.05), U2 pin 1 at (166.4125, 86.095), U3 pin 1 at
   (123.8625, 67.05) mm in KiCad's +Y-down board frame**. Verify the package's pin-1
   mark follows that pad. The CPL uses the opposite Y sign. U1/U2 body centers are
   (145, 88)/(170, 88); U3 is (125, 68). All three ICs have KiCad rotation 0°;
   the fab library may need a rotation correction. Stop and resolve an incorrect
   pin-1 overlay with the fab before paying. Passive rotations 0°/180° are equivalent.
6. **J1, JP1 and C2 must be hand-soldered** after partial assembly; see
   `fab/HAND_SOLDER.csv`. R1/R4 are loose bring-up parts, never factory fitted.
   TP1–TP18 are bare board pads; H1–H4 are holes, not purchased components.
   Obtain a removable 2.54 mm shunt separately for the later enable step; keep it off
   during initial assembly. Complete C2 before applying power.

The root `BOM.csv` is the procurement authority, with each exact MPN's public
source, check date, stock status or explicit `hand-solder` disposition. Public LCSC
pages were checked on **2026-11-15** for part identity/package. Their current
rendered pages did **not expose stock counts**; stock is recorded as unconfirmed,
not zero or reserved. LCSC retail inventory also does not guarantee JLCPCB PCBA
availability. Recheck all six assembly lines in the order picker, including attrition,
and choose economic/standard service as the picker permits. If one is unavailable,
either wait for that exact MPN or remove it from **both** upload files and arrange
hand soldering; retain a private record of that variant. The default bare-board
route does not depend on assembly inventory. C2 has no established exact LCSC
mapping, and both Samtec through-hole headers are deliberately hand-solder items.

## Budget on 2026-11-15

These are **planning estimates in USD, not live quotes**:

| Route | Expected range |
| --- | --- |
| Five bare boards, before shipping/tax | $2–15 |
| Parts for two hand-built boards, including small-quantity overhead/spares | $15–40 |
| Five boards with two partially assembled, before shipping/tax and hand-solder parts | $35–100 |
| Shipping allowance per order, destination-dependent | $10–35 |
| FT232H USB-SPI board, if needed | About $15–25 plus cable/shipping |

[JLCPCB advertises a $2 starting price for five standard small boards](https://jlcpcb.com/help/article/how-do-i-place-an-order).
[Assembly charges](https://jlcpcb.com/help/article/pcb-assembly-price) add setup,
stencil, component/feeder, placement and possible panel costs. Exact MPNs can be
extended parts; standard assembly or special sourcing can exceed this estimate.
Shipping, duty/tax, coupons and tools are excluded from the PCB/PCBA rows. Review
the itemized quote before paying; no quote or order was submitted for this package.

After delivery, follow [BRING_UP_TEST.md](BRING_UP_TEST.md). Keep shipping labels,
payment details, operator identities and raw bench records outside this public repo.
